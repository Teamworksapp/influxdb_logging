import datetime
import sys
import logging
from logging.handlers import BufferingHandler
import json
import zlib
import traceback
import struct
import random
import socket
import math
import threading
import time
import itertools
from influxdb import InfluxDBClient
from io import StringIO

PY3 = sys.version_info[0] == 3
WAN_CHUNK, LAN_CHUNK = 1420, 8154

if PY3:
    data, text = bytes, str
else:
    data, text = str, unicode
    
SYSLOG_LEVELS = {
    logging.CRITICAL: 2,
    logging.ERROR: 3,
    logging.WARNING: 4,
    logging.INFO: 6,
    logging.DEBUG: 7,
}


# skip_list is used to filter additional fields in a log message.
# It contains all attributes listed in
# http://docs.python.org/library/logging.html#logrecord-attributes
# plus exc_text, which is only found in the logging module source,
# and id, which is prohibited by the GELF format.

SKIP_LIST = {
    'args', 'asctime', 'created', 'exc_info',  'exc_text', 'filename',
    'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
    'msecs', 'message', 'msg', 'name', 'pathname', 'process',
    'processName', 'relativeCreated', 'thread', 'threadName'}


class InfluxHandler(logging.Handler):
    """InfluxDB Log handler
    
    :param database: The database you want log entries to go into.
    :param indexed_keys: The names of keys to be treated as keys (as opposed to fields) in influxdb.
    :param debugging_fields: Send debug fields if true (the default).
    :param extra_fields: Send extra fields on the log record to graylog
        if true (the default).
    :param localname: Use specified hostname as source host.
    :param measurement: Replace measurement with specified value. If not specified,
        record.name will be passed as `logger` parameter.
    :param level_names: Allows the use of string error level names instead
        of numerical values. Defaults to False
    :param client_kwargs: Pass these args to the InfluxDBClient constructor
    """

    def __init__(self, 
        database,
        indexed_keys=None, 
        debugging_fields=True, 
        extra_fields=True, 
        localname=None,
        measurement=None, 
        level_names=False,
        backpop=True,
        **client_kwargs
    ):
        self.debugging_fields = debugging_fields
        self.extra_fields = extra_fields
        self.localname = localname
        self.measurement = measurement
        self.indexed_keys = {'level','short_message'}
        self.client = InfluxDBClient(database=database, **client_kwargs)
        self.backpop = backpop
        
        if database not in {x['name'] for x in self.client.get_list_database()}:
            self.client.create_database(database)
        
        if indexed_keys is not None:
            self.indexed_keys += set(indexed_keys)
        
        logging.Handler.__init__(self)
        
    def set_retention_policy(self, *args, **kwargs):
        return self.client.set_retention_policy(*args, **kwargs)
        
    def emit(self, record):
        """
        Emit a record.

        Send the record to the Web server as line protocol
        """
        self.client.write_points(self.get_point(record))
    
    def get_points(self, record):
        fields = {
            'host': self.localname,
            'short_message': record.getMessage(),
            'full_message': get_full_message(record.exc_info, record.getMessage()),
            'level': SYSLOG_LEVELS.get(record.levelno, record.levelno),
            'level_name': logging.getLevelName(record.levelno)
        }

        if self.debugging_fields:
            fields.update({
                'file': record.pathname,
                'line': record.lineno,
                'function': record.funcName,
                'pid': record.process,
                'thread_name': record.threadName,
            })
            # record.processName was added in Python 2.6.2
            pn = getattr(record, 'processName', None)
            if pn is not None:
                fields['_process_name'] = pn
        if self.extra_fields:
            fields = add_extra_fields(fields, record)

        if self.measurement:
            return [{
                "measurement": self.measurement,
                "tags": {k: fields[k] for k in sorted(fields.keys()) if k in self.indexed_keys},
                "fields": {k: fields[k] for k in sorted(fields.keys())},
                "time": int(record.created * 10**9)  # nanoseconds
            }]
        elif not self.backpop:
            return [{
                "measurement": record.name.replace(".", ":") or 'root',
                "tags": {k: fields[k] for k in sorted(fields.keys()) if k in self.indexed_keys},
                "fields": {k: fields[k] for k in sorted(fields.keys())},
                "time": int(record.created * 10**9)  # nanoseconds
            }] 
        else:
            ret = []
            names = record.name.split('.')
            rname = names[0] or 'root'
            ret.append({
                "measurement": rname,
                "tags": {k: fields[k] for k in sorted(fields.keys()) if k in self.indexed_keys},
                "fields": {k: fields[k] for k in sorted(fields.keys())},
                "time": int(record.created * 10**9)  # nanoseconds
            })
            for sub in names[1:]:
                rname = "{rname}:{sub}".format(rname, sub)
                ret.append({
                    "measurement": rname,
                    "tags": {k: fields[k] for k in sorted(fields.keys()) if k in self.indexed_keys},
                    "fields": {k: fields[k] for k in sorted(fields.keys())},
                    "time": int(record.created * 10**9)  # nanoseconds
                })
            return ret


class BufferingInfluxHandler(InfluxHandler, BufferingHandler):
    """InfluxDB Log handler

    :param indexed_keys: The names of keys to be treated as keys (as opposed to fields) in influxdb.
    :param debugging_fields: Send debug fields if true (the default).
    :param extra_fields: Send extra fields on the log record to graylog
        if true (the default).
    :param localname: Use specified hostname as source host.
    :param measurement: Replace measurement with specified value. If not specified,
        record.name will be passed as `logger` parameter.
    :param level_names: Allows the use of string error level names instead
        of numerical values. Defaults to False
    :param capacity: The number of points to buffer before sending to InfluxDB.
    :param flush_interval: Interval in seconds between flushes, maximum. Defaults to 5 seconds
    :param client_kwargs: Pass these args to the InfluxDBClient constructor
    """

    def __init__(self, 
        indexed_keys=None, 
        debugging_fields=True, 
        extra_fields=True, 
        localname=None,
        measurement=None, 
        level_names=False,
        capacity=64,
        flush_interval=5,  
        backpop=True,
        **client_kwargs
    ):
        self.debugging_fields = debugging_fields
        self.extra_fields = extra_fields
        self.localname = localname
        self.measurement = measurement
        self.level_names = level_names
        self.indexed_keys = {'level','short_message'}
        self.client = InfluxDBClient(**client_kwargs)
        self.flush_interval=flush_interval
        self._thread = None if flush_interval is None else threading.Thread(
            target=self._flush_thread, name="BufferingInfluxHandler", daemon=True)
        
        if indexed_keys is not None:
            self.indexed_keys += set(indexed_keys)
        
        InfluxHandler.__init__(self, 
            indexed_keys=None, 
            debugging_fields=debugging_fields, 
            extra_fields=extra_fields, 
            localname=localname,
            measurement=measurement, 
            level_names=level_names,
            backpop=backpop,
            **client_kwargs
        )
        BufferingHandler.__init__(self, capacity)
        self._thread.start()
        
        
    def emit(self, record):
        BufferingHandler.emit(self, record)
        
    def _flush_thread(self):
        while True:
            time.sleep(self.flush_interval)
            self.flush()
        
    def flush(self):
        self.acquire()
        try:
            if len(self.buffer):
                self.client.write_points(itertools.chain(self.get_point(record) for record in self.buffer))
                self.buffer = []
        finally:
            self.release()
        

def get_full_message(exc_info, message):
    return json.dumps(traceback.format_exception(*exc_info)) if exc_info else json.dumps([message])


def add_extra_fields(message_dict, record):
    for key, value in record.__dict__.items():
        if key not in SKIP_LIST and not key.startswith('_'):
            message_dict[key] = value
    return message_dict

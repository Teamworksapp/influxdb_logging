import logging
import sys
import threading
import time
from logging.handlers import BufferingHandler

from influxdb import InfluxDBClient

PY3 = sys.version_info[0] == 3
WAN_CHUNK, LAN_CHUNK = 1420, 8154

if PY3:
    data, text = bytes, str
else:
    data, text = str, unicode

# skip_list is used to filter additional fields in a log message.
# It contains all attributes listed in
# http://docs.python.org/library/logging.html#logrecord-attributes
# plus exc_text, which is only found in the logging module source,
# and id, which is prohibited by the GELF format.

SKIP_ATTRIBUTES = [
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
    'msecs', 'message', 'msg', 'name', 'pathname', 'process',
    'processName', 'stack_info', 'relativeCreated', 'thread', 'threadName'
]

DEFAULT_TAGS = {
    'filename': 'source.fileName',
    'funcName': 'source.methodName',
    'levelname': 'level',
    'lineno': 'source.lineNumber',
    'thread': 'threadId',
    'threadName': 'threadName'
}

DEFAULT_FIELDS = {
    'message': 'message',
    'thrown.stackTrace': 'exc_text'
}


class InfluxHandler(logging.Handler):
    """InfluxDB Log handler

    :param database: The database you want log entries to go into.
    :param extra_fields: Send extra fields on the log record to graylog
        if true (the default).
    :param measurement: Replace measurement with specified value. If not specified,
        record.name will be passed as `logger` parameter.
    :param lazy_init: Enable lazy initialization. Defaults to False.
    :param include_fields: Include additional fields. Defaults to {}.
    :param include_tags: Include additional tags. Defaults to {}.
    :param extra_fields: Add extra fields if found. Defaults to True.
    :param extra_tags: Add extra tags if found. Defaults to True.
    :param client_kwargs: Pass these args to the InfluxDBClient constructor
    """

    def __init__(self,
                 database: str,
                 measurement: str = None,
                 retention_policy: str = None,
                 backpop: bool = True,
                 lazy_init: bool = False,
                 include_tags: dict = {},
                 include_fields: dict = {},
                 extra_tags: bool = True,
                 extra_fields: bool = True,
                 **client_kwargs
                 ):
        self.measurement = measurement
        self.client = InfluxDBClient(database=database, **client_kwargs)
        self.backpop = backpop
        self.retention_policy = retention_policy

        # extend tags to include
        self.include_tags = DEFAULT_TAGS
        self.include_tags.update(include_tags)

        # extend fields to include
        self.include_fields = DEFAULT_FIELDS
        self.include_fields.update(include_fields)

        self.extra_tags = extra_tags
        self.extra_fields = extra_fields

        if lazy_init is False:
            if database not in {x['name'] for x in self.client.get_list_database()}:
                self.client.create_database(database)

        logging.Handler.__init__(self)

    def emit(self, record):
        """
        Emit a record.

        Send the record to the Web server as line protocol
        """
        self.client.write_points(self.get_point(record), retention_policy=self.retention_policy)

    def convert_to_point(self, key, value, fields={}, tags={}):
        if value is None:
            return
        elif isinstance(value, dict):
            for k in value.items():
                if key:
                    self.convert_to_point(key + '.' + k, value[k], fields, tags)
                else:
                    self.convert_to_point(k, value[k], fields, tags)
        elif isinstance(value, list):
            self.convert_to_point(key, ' '.join(value), fields, tags)
        else:
            if key in self.include_tags:
                tags[self.include_tags.get(key)] = value
            elif key in self.include_fields:
                fields[self.include_fields.get(key)] = value
            elif key in SKIP_ATTRIBUTES:
                return
            else:
                if isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
                    if self.extra_fields:
                        fields[key] = value
                else:
                    if self.extra_tags:
                        tags[key] = value

    def get_point(self, record):
        fields = {}
        tags = {}

        for record_name in record.__dict__.items():
            # ignore methods
            if record_name.startswith('_'):
                continue

            self.convert_to_point(record_name, getattr(record, record_name), fields, tags)

        if self.measurement:
            return [{
                "measurement": self.measurement,
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            }]
        elif not self.backpop:
            return [{
                "measurement": record.name.replace(".", ":") or 'root',
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            }]
        else:
            ret = []
            names = record.name.split('.')
            rname = names[0] or 'root'
            ret.append({
                "measurement": rname,
                "tags": tags,
                "fields": fields,
                "time": int(record.created * 10 ** 9)  # nanoseconds
            })
            for sub in names[1:]:
                rname = f"{rname}:{sub}"
                ret.append({
                    "measurement": rname,
                    "tags": tags,
                    "fields": fields,
                    "time": int(record.created * 10 ** 9)  # nanoseconds
                })
            return ret


class BufferingInfluxHandler(InfluxHandler, BufferingHandler):
    """InfluxDB Log handler

    :param measurement: Replace measurement with specified value. If not specified,
        record.name will be passed as `logger` parameter.
    :param capacity: The number of points to buffer before sending to InfluxDB.
    :param flush_interval: Interval in seconds between flushes, maximum. Defaults to 5 seconds
    :param lazy_init: Enable lazy initialization. Defaults to False.
    :param include_tags: Include additional tags
    :param client_kwargs: Pass these args to the InfluxDBClient constructor
    """

    def __init__(self,
                 database: str,
                 measurement: str = None,
                 retention_policy: str = None,
                 capacity: int = 64,
                 flush_interval: int = 5,
                 backpop: bool = True,
                 lazy_init: bool = False,
                 include_tags: dict = {},
                 include_fields: dict = {},
                 extra_tags: bool = True,
                 extra_fields: bool = True,
                 **client_kwargs
                 ):
        self.flush_interval = flush_interval

        InfluxHandler.__init__(self,
                               database=database,
                               measurement=measurement,
                               retention_policy=retention_policy,
                               backpop=backpop,
                               lazy_init=lazy_init,
                               include_tags=include_tags,
                               include_fields=include_fields,
                               extra_tags=extra_tags,
                               extra_fields=extra_fields,
                               **client_kwargs
                               )

        BufferingHandler.__init__(self, capacity)

        self._thread = None if flush_interval is None else threading.Thread(
            target=self._flush_thread, name="BufferingInfluxHandler", daemon=True)
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
                # process all the buffered records
                points = []
                for record in self.buffer:
                    points.extend(self.get_point(record))

                self.client.write_points(points, retention_policy=self.retention_policy)

                # clear the buffer
                self.buffer.clear()
        finally:
            self.release()

# InfluxDB logging

[InfluxDB](https://www.influxdata.com/) is a timeseries database that is optimized for realtime 
insert and time-aggregated selections. It advertises itself as a logging and devops solution, but
to date there was no integration with the Python logging framework. `influxdb_logging` rectifies 
that. There are two classes: `InfluxHandler` and `BufferingInfluxHandler`. They support all the 
options to `InfluxDBClient` as keyword arguments.

One significant change is that because dots are separators for databases in InfluxQL, to ensure 
maximum compatibility with other products that integrate InfluxDB such as InfluxDB's own clients and
Grafana, we change logger separators from dots to colons on insert.

In general, the logger name is the "measurement" in InfluxDB terms, and the basic "tags" are `level` 
(syslog number) and `short_message`. You can add more by passing an `indexed_keys=` parameter to 
the class. Everything else that is part of the logging record will be added as fields. 

These handler classes were inspired by [graypy](https://github.com/severb/graypy) for Graylog,
although by the time I was done they bear little resemblance to them.  

## Example Usage

```python
from influx_logging import InfluxHandler, BufferingInfluxHandler

influx_handler = InfluxHandler(database='test_influx_handler')    
logging.getLogger().setLevel(logging.DEBUG)

influx_logger = logging.getLogger('influx_logging.tests.simple_message')
influx_logger.addHandler(influx_handler)

influx_logger.debug('Debug message')
influx_logger.info('Info message')
influx_logger.warning('Warning message')
influx_logger.error('Error message')

try:
    raise Exception("This is an exception")
except:
    influx_logger.exception('Exception message')
    
res = influx_handler.client.query(
    'SELECT * FROM "influx_logging:tests:simple_message"'
)
```

## class `InfluxHandler`

##### Parameters

* **database**: The database you want log entries to go into.
* **indexed_keys**: The names of keys to be treated as keys (as opposed to fields) in influxdb.
* **debugging_fields**: Send debug fields if true (the default).
* **extra_fields**: Send extra fields on the log record to graylog
    if true (the default).
* **localname**: Use specified hostname as source host.
* **measurement**: Replace measurement with specified value. If not specified,
    record.name will be passed as `logger` parameter.
* **level_names**: Allows the use of string error level names instead
    of numerical values. Defaults to `False`
* **backpop**: Default `True`. Add a record for each item in the hierarchy of loggers. 
* **lazy_init**: Default `False`. Lazy initialization. Defaults to `False`.
* **\*\*client_kwargs**: Pass these args to the `InfluxDBClient` constructor
  
## class `BufferingInfluxHandler`

##### Parameters

* **indexed_keys**: The names of keys to be treated as keys (as opposed to fields) in influxdb.
* **debugging_fields**: Send debug fields if true (the default).
* **extra_fields**: Send extra fields on the log record to graylog
    if true (the default).
* **localname**: Use specified hostname as source host.
* **measurement**: Replace measurement with specified value. If not specified,
    `record.name` will be passed as `logger` parameter.
* **level_names**: Allows the use of string error level names instead
    of numerical values. Defaults to `False`
* **capacity**: The number of points to buffer before sending to InfluxDB.
* **flush_interval**: Interval in seconds between flushes, maximum. Defaults to 5 seconds
* **backpop**: Default `True`. Add a record for each item in the hierarchy of loggers. 
* **\*\*client_kwargs**: Pass these args to the `InfluxDBClient` constructor

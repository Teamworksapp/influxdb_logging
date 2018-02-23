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

|Name | Description |
|-----|-------------|
| database | The database you want log entries to go into. |
| measurement | Replace measurement with specified value. If not specified, record.name will be passed as `logger` parameter. |
| lazy_init | Enable lazy initialization. Defaults to False. |
| include_fields | Include additional fields ({'record_name': 'field_name'}). Defaults to {}. |
| exclude_fields | Exclude list of field names. Defaults to []. |
| include_tags | Include additional tags ({'record_name': 'tag_name'}). Defaults to {}. |
| exclude_tags | Exclude list of tag names. Defaults to []. |
| extra_fields | Add extra fields if found. Defaults to True. |
| extra_tags | Add extra tags if found. Defaults to True. |
| include_stacktrace | Add stacktraces. Defaults to True. |
| backpop | Default `True`. Add a record for each item in the hierarchy of loggers. |
| **influxdb_opts | InfluxDB client options |
  
## class `BufferingInfluxHandler`

##### Parameters

|Name | Description |
|-----|-------------|
| capacity | The number of points to buffer before sending to InfluxDB. |
| flush_interval | Interval in seconds between flushes, maximum. Defaults to 5 seconds |
| database | The database you want log entries to go into. |
| measurement | Replace measurement with specified value. If not specified, record.name will be passed as `logger` parameter. |
| lazy_init | Enable lazy initialization. Defaults to False. |
| include_fields | Include additional fields ({'record_name': 'field_name'}). Defaults to {}. |
| exclude_fields | Exclude list of field names. Defaults to []. |
| include_tags | Include additional tags ({'record_name': 'tag_name'}). Defaults to {}. |
| exclude_tags | Exclude list of tag names. Defaults to []. |
| extra_fields | Add extra fields if found. Defaults to True. |
| extra_tags | Add extra tags if found. Defaults to True. |
| include_stacktrace | Add stacktraces. Defaults to True. |
| backpop | Default `True`. Add a record for each item in the hierarchy of loggers. |
| **influxdb_opts | InfluxDB client options |

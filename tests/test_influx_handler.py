import pytest
import logging
from influx_logging import InfluxHandler, BufferingInfluxHandler
from influxdb import InfluxDBClient


def test_simple_message():
    InfluxDBClient().drop_database('test_influx_handler')

    influx_handler = InfluxHandler(database='test_influx_handler')    
    logging.getLogger().setLevel(logging.DEBUG)

    influx_logger = logging.getLogger('influx_logging.tests.simple_message')
    for handler in influx_logger.handlers:
        influx_logger.removeHandler(handler)
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
    pts = list(res.get_points())
    assert len(pts[-1]['full_message']) > len(pts[-1]['short_message'])
        

def test_buffered_handler():
    InfluxDBClient().drop_database('test_influx_handler')

    influx_handler = BufferingInfluxHandler(database='test_influx_handler', flush_interval=2)    
    logging.getLogger().setLevel(logging.DEBUG)

    influx_logger = logging.getLogger('influx_logging.tests.buffered_handler')
    for handler in influx_logger.handlers:
        influx_logger.removeHandler(handler)
    influx_logger.addHandler(influx_handler)

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')
        
    res = influx_handler.client.query(
        'SELECT * FROM "influx_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 0
    
    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')

    res = influx_handler.client.query(
        'SELECT * FROM "influx_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 64

    for x in range(8):
        influx_logger.debug('Debug message')
        influx_logger.info('Info message')
        influx_logger.warning('Warning message')
        influx_logger.error('Error message')
    import time
    time.sleep(2.5)
    res = influx_handler.client.query(
        'SELECT * FROM "influx_logging:tests:buffered_handler"'
    )
    assert len(list(res.get_points())) == 64 + 32


        

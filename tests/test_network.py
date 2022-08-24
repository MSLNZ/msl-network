import logging

from msl.network.network import Network
from msl.network.utils import logger

original = logger.level


def teardown():
    assert Network.set_logging_level(original)


def test_set_logging_level(caplog):
    assert Network.set_logging_level(logging.WARNING)
    assert logger.level == logging.WARNING
    assert Network.set_logging_level(40)
    assert logger.level == logging.ERROR
    assert not Network.set_logging_level('debg')
    assert logger.level == logging.ERROR
    assert Network.set_logging_level('20')
    assert logger.level == logging.INFO

    for record in caplog.records:
        assert record.name == 'msl.network'
        assert record.levelname == 'ERROR'
        assert record.message == "invalid logging level 'DEBG'"

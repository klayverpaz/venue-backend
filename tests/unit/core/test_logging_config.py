import logging
from app.core.context import correlation_id
from app.core.logging_config import CorrelationIdFilter, setup_logging


def test_filter_injeta_correlation_id_do_contextvar():
    f = CorrelationIdFilter()
    record = logging.LogRecord("x", logging.INFO, "", 0, "msg", None, None)
    token = correlation_id.set("abc123")
    try:
        f.filter(record)
    finally:
        correlation_id.reset(token)
    assert record.correlation_id == "abc123"


def test_filter_usa_default_quando_nao_setado():
    f = CorrelationIdFilter()
    record = logging.LogRecord("x", logging.INFO, "", 0, "msg", None, None)
    f.filter(record)
    assert record.correlation_id == "-"


def test_setup_logging_configura_handler(caplog):
    setup_logging()
    root = logging.getLogger()
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)

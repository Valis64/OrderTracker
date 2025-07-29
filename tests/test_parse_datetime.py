import logging
from datetime import datetime

import pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from OrderTracker import YBSScraperApp


def _get_app():
    # create an instance without calling __init__ to avoid GUI setup
    app = YBSScraperApp.__new__(YBSScraperApp)
    return app


@pytest.mark.parametrize(
    "text,expected",
    [
        ("09/05/23 14:30", datetime(2023, 9, 5, 14, 30)),
        ("09/05/23 14:30:15", datetime(2023, 9, 5, 14, 30, 15)),
        ("09/05/23 2:30 PM", datetime(2023, 9, 5, 14, 30)),
        ("09/05/23 2:30:15 PM", datetime(2023, 9, 5, 14, 30, 15)),
    ],
)
def test_supported_formats(text, expected):
    app = _get_app()
    assert app.parse_datetime(text) == expected


def test_unrecognized_format_logs_warning(caplog):
    app = _get_app()
    with caplog.at_level(logging.WARNING):
        assert app.parse_datetime("invalid") is None
        assert any("Unrecognized" in record.getMessage() for record in caplog.records)

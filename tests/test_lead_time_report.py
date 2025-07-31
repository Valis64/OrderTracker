import sqlite3
import csv
from datetime import datetime
import pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from OrderTracker import YBSScraperApp, WORKSTATIONS


def _get_app():
    app = YBSScraperApp.__new__(YBSScraperApp)
    app.conn = sqlite3.connect(":memory:")
    cur = app.conn.cursor()
    cur.execute(
        """
        CREATE TABLE events (
            order_num TEXT,
            workstation TEXT,
            timestamp TEXT,
            UNIQUE(order_num, workstation, timestamp)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE current_orders (
            order_num TEXT PRIMARY KEY,
            indigo TEXT,
            laminate TEXT,
            die_cutting_abg TEXT,
            machine_glue TEXT,
            shipping TEXT,
            last_seen TEXT,
            active INTEGER DEFAULT 1
        )
        """
    )
    app.conn.commit()
    return app


def insert_event(app, order_num, ws, ts):
    app.conn.execute(
        "INSERT INTO events(order_num, workstation, timestamp) VALUES(?,?,?)",
        (order_num, ws, ts),
    )
    app.conn.commit()


def test_calculate_lead_times():
    app = _get_app()
    insert_event(app, "1001", "Indigo", "2023-09-05 08:00")
    insert_event(app, "1001", "Laminate", "2023-09-05 10:00")
    insert_event(app, "1001", "Shipping", "2023-09-05 13:00")

    start = datetime(2023, 9, 5)
    end = datetime(2023, 9, 6)
    data = app.calculate_lead_times(start, end)
    assert len(data) == 1
    row = data[0]
    assert row["order_num"] == "1001"
    assert row["durations"]["Indigo"] == pytest.approx(2.0)
    assert row["durations"]["Laminate"] == pytest.approx(3.0)
    assert row["durations"]["Die Cutting ABG"] is None
    assert row["total"] == pytest.approx(5.0)


def test_write_lead_time_csv(tmp_path):
    app = _get_app()
    sample = {
        "order_num": "1001",
        "durations": {ws: None for ws in WORKSTATIONS},
        "total": 5.0,
    }
    sample["durations"]["Indigo"] = 2.0
    sample["durations"]["Laminate"] = 3.0

    csv_path = tmp_path / "out.csv"
    app.write_lead_time_csv([sample], csv_path)

    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["Job"] + WORKSTATIONS + ["Total Hours"]
    assert rows[1][0] == "1001"
    assert rows[1][1] == "2.00"
    assert rows[1][2] == "3.00"
    assert rows[1][-1] == "5.00"

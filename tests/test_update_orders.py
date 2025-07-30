import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from OrderTracker import YBSScraperApp, WORKSTATIONS


def _get_app():
    app = YBSScraperApp.__new__(YBSScraperApp)
    app.settings = {"base_url": "http://example.com"}
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


class DummyResponse:
    def __init__(self, text):
        self.text = text


class DummySession:
    def __init__(self, text):
        self.text = text

    def get(self, url):
        return DummyResponse(self.text)


def test_update_and_deactivate():
    html1 = """
    <table>
        <tr><td>YBS 1001</td><td>09/05/23 14:30</td><td></td><td></td><td></td><td></td></tr>
        <tr><td>YBS 1002</td><td></td><td></td><td></td><td></td><td></td></tr>
    </table>
    """
    app = _get_app()
    session = DummySession(html1)
    count = app.update_orders(session)
    assert count == 1

    cur = app.conn.cursor()
    rows = list(cur.execute("SELECT order_num, active FROM current_orders ORDER BY order_num"))
    assert rows == [("1001", 1), ("1002", 1)]

    html2 = """
    <table>
        <tr><td>YBS 1001</td><td>09/05/23 14:35</td><td></td><td></td><td></td><td></td></tr>
    </table>
    """
    session2 = DummySession(html2)
    count2 = app.update_orders(session2)
    assert count2 == 1

    row1 = cur.execute(
        "SELECT indigo, active FROM current_orders WHERE order_num='1001'"
    ).fetchone()
    assert row1[1] == 1
    assert "14:35" in row1[0]

    row2 = cur.execute(
        "SELECT active FROM current_orders WHERE order_num='1002'"
    ).fetchone()
    assert row2[0] == 0


import json
import sqlite3

_db = sqlite3.connect("db.sqlite3", check_same_thread=False)
_db.execute('PRAGMA foreign_keys=ON;')

# Create DB and schema if it doesn't exist already
_db.execute("""
CREATE TABLE IF NOT EXISTS Events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type VARCHAR(255) NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT current_timestamp,
    target VARCHAR(255) NOT NULL DEFAULT '*',
    data text NOT NULL
);
""")


def purge_events():
    # Delete all data
    _db.execute('DELETE FROM Events;')
    _db.execute("DELETE FROM sqlite_sequence WHERE name='Events';")
    _db.commit()


def add_event(event_type: str, target: str = '*', event_data=None):
    if event_data is None:
        event_data = {}

    cursor = _db.cursor()

    try:
        cursor.execute(
            'INSERT INTO Events (type, target, data) VALUES (?, ?, ?);',
        (event_type, target, json.dumps(event_data))
        )

        _db.commit()
    except sqlite3.Error as e:
        raise AttributeError(e)


def get_event(event_type: str, target: str = '*', first_acceptable_id: int = 1) -> tuple[int, dict[str, str]] | None:
    cursor = _db.cursor()

    try:
        # Get first un-executed event by event_type and target
        raw_data = cursor.execute(
            'SELECT id, data FROM Events WHERE type=? and target=? and id>=? ORDER BY id LIMIT 1;',
            (event_type, target, first_acceptable_id)
        ).fetchone()

        # If no event are available return None
        if raw_data is None:
            return None

        # Parse json and return it
        return int(raw_data[0]), json.loads(raw_data[1])

    except sqlite3.Error as e:
        raise AttributeError(e)

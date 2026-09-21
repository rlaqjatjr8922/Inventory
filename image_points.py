"""Persistent image annotations; original image bytes are never modified."""
from contextlib import contextmanager
import sqlite3


@contextmanager
def connection(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS image_points (
            image_id INTEGER NOT NULL,
            point_id INTEGER NOT NULL,
            x REAL NOT NULL CHECK(x >= 0 AND x <= 1),
            y REAL NOT NULL CHECK(y >= 0 AND y <= 1),
            annotation TEXT NOT NULL,
            PRIMARY KEY (image_id, point_id)
        )""")
        with db:
            yield db
    finally:
        db.close()


def list_points(path, image_id):
    with connection(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM image_points WHERE image_id=? ORDER BY point_id", (image_id,))]


def add_point(path, image_id, changes):
    with connection(path) as db:
        # Serialize allocation across threads and server processes.
        db.execute("BEGIN IMMEDIATE")
        point_id = db.execute(
            "SELECT COALESCE(MAX(point_id), 0) + 1 FROM image_points WHERE image_id=?",
            (image_id,)).fetchone()[0]
        point = dict(image_id=image_id, point_id=point_id, **changes)
        db.execute("INSERT INTO image_points VALUES (:image_id,:point_id,:x,:y,:annotation)", point)
        return point


def update_point(path, image_id, point_id, changes):
    with connection(path) as db:
        keys = [key for key in ("x", "y", "annotation") if key in changes]
        db.execute("UPDATE image_points SET " + ", ".join(key + "=?" for key in keys)
                   + " WHERE image_id=? AND point_id=?",
                   [changes[key] for key in keys] + [image_id, point_id])
        row = db.execute("SELECT * FROM image_points WHERE image_id=? AND point_id=?",
                         (image_id, point_id)).fetchone()
        return dict(row) if row else None


def latest_tool_image(path, image_id=None):
    """One persisted pointer shared by MCP/HTTP server processes."""
    with connection(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS image_tool_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            image_id INTEGER NOT NULL,
            revision INTEGER NOT NULL
        )""")
        if image_id is not None:
            db.execute("""INSERT INTO image_tool_state VALUES (1, ?, 1)
                ON CONFLICT(singleton) DO UPDATE SET
                image_id=excluded.image_id, revision=image_tool_state.revision+1""", (image_id,))
        row = db.execute("SELECT image_id, revision FROM image_tool_state WHERE singleton=1").fetchone()
        return dict(row) if row else {"image_id": None, "revision": 0}

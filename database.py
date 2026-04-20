import sqlite3

DB_PATH = "nas.db"

def init_db():
    """Crée la table si elle n'existe pas"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,
            qc_id        TEXT NOT NULL UNIQUE,
            dsm_user     TEXT NOT NULL,
            dsm_password TEXT NOT NULL,
            location     TEXT DEFAULT '',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_all_nas() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM nas ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_nas(name, qc_id, user, password, location) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO nas (name, qc_id, dsm_user, dsm_password, location)
            VALUES (?, ?, ?, ?, ?)
        """, (name, qc_id, user, password, location))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_nas(nas_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM nas WHERE id = ?", (nas_id,))
    conn.commit()
    conn.close()

def update_nas(nas_id, name, qc_id, user, password, location):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE nas SET
            name=?, qc_id=?, dsm_user=?, dsm_password=?, location=?
        WHERE id=?
    """, (name, qc_id, user, password, location, nas_id))
    conn.commit()
    conn.close()

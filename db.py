import sqlite3
from typing import Optional, Tuple
import bcrypt

DB_PATH = 'attendance.db'

SCHEMA_SQL = '''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER UNIQUE,
    name TEXT,
    email TEXT UNIQUE,
    password_hash BLOB,
    temp_password TEXT,
    role TEXT CHECK (role IN ('Admin','Manager','Employee')),
    employee_type TEXT,
    designation TEXT,
    job_type TEXT,
    employment_type TEXT,
    timing TEXT,
    company TEXT,
    department TEXT,
    status TEXT,
    photo_path TEXT,
    joining_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    category TEXT,
    value TEXT,
    UNIQUE(category, value)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    start_time DATETIME,
    start_lat REAL,
    start_lng REAL,
    start_photo_path TEXT,
    start_location TEXT,
    whats_doing TEXT,
    end_time DATETIME,
    end_lat REAL,
    end_lng REAL,
    end_photo_path TEXT,
    end_location TEXT,
    why_stop TEXT,
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_images (
    id INTEGER PRIMARY KEY,
    attendance_id INTEGER,
    photo_path TEXT,
    tag TEXT CHECK (tag IN ('start','stop','mid')),
    captured_at DATETIME,
    lat REAL,
    lng REAL,
    FOREIGN KEY(attendance_id) REFERENCES attendance(id) ON DELETE CASCADE
);
'''

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)

    # Migrations: ensure new columns exist (start_location, end_location, whats_doing, why_stop, users.temp_password)
    cur.execute("PRAGMA table_info(attendance)")
    cols = [r[1] for r in cur.fetchall()]
    if 'start_location' not in cols:
        cur.execute("ALTER TABLE attendance ADD COLUMN start_location TEXT")
    if 'end_location' not in cols:
        cur.execute("ALTER TABLE attendance ADD COLUMN end_location TEXT")
    if 'whats_doing' not in cols:
        cur.execute("ALTER TABLE attendance ADD COLUMN whats_doing TEXT")
    if 'why_stop' not in cols:
        cur.execute("ALTER TABLE attendance ADD COLUMN why_stop TEXT")

    # Users table migrations
    cur.execute("PRAGMA table_info(users)")
    ucols = [r[1] for r in cur.fetchall()]
    if 'temp_password' not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN temp_password TEXT")

    # Ensure admin seeded only when no users exist
    cur.execute('SELECT COUNT(1) FROM users')
    row = cur.fetchone()
    count = row[0] if row else 0
    if not count:
        # Generate next employee_id starting at 25001
        cur.execute('SELECT MAX(employee_id) FROM users')
        max_emp = cur.fetchone()[0]
        next_emp_id = (max_emp + 1) if max_emp and max_emp >= 25001 else 25001
        password_hash = bcrypt.hashpw('Admin@2025'.encode('utf-8'), bcrypt.gensalt())
        cur.execute(
            '''INSERT INTO users (employee_id, name, email, password_hash, role, status)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (next_emp_id, 'Administrator', 'admin@surefy.ai', password_hash, 'Admin', 'Active')
        )
    conn.commit()
    conn.close()


def get_next_employee_id(conn: Optional[sqlite3.Connection] = None) -> int:
    owns_conn = False
    if conn is None:
        conn = get_conn()
        owns_conn = True
    cur = conn.cursor()
    cur.execute('SELECT MAX(employee_id) FROM users')
    max_emp = cur.fetchone()[0]
    next_emp_id = (max_emp + 1) if max_emp and max_emp >= 25001 else 25001
    if owns_conn:
        conn.close()
    return next_emp_id


# RESET UTILITIES ---------------------------------------------------------

def reset_database_and_photos(admin_email: str = 'admin@surefy.ai', admin_password: str = 'Admin@2025') -> None:
    """Dangerous: wipes the SQLite DB file and photos directory, then
    recreates schema and seeds a single admin user.

    Use this once on a fresh deployment to remove test data.
    """
    import os
    import shutil

    # Remove DB file
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
    except Exception:
        pass

    # Remove photos directory
    photos_dir = 'photos'
    try:
        if os.path.isdir(photos_dir):
            shutil.rmtree(photos_dir)
    except Exception:
        pass

    # Recreate schema
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)

    # Seed admin
    # Start employee IDs from 25001
    next_emp_id = 25001
    password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
    cur.execute(
        '''INSERT INTO users (employee_id, name, email, password_hash, role, status)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (next_emp_id, 'Administrator', admin_email.lower(), password_hash, 'Admin', 'Active')
    )
    conn.commit()
    conn.close()

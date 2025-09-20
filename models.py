from typing import List, Optional, Dict, Any, Tuple
import sqlite3
from db import get_conn, get_next_employee_id

# USERS -----------------------------------------------------------------

def create_user(data: Dict[str, Any]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    employee_id = data.get('employee_id') or get_next_employee_id(conn)
    cur.execute('''
        INSERT INTO users (
            employee_id, name, email, password_hash, temp_password, role,
            employee_type, designation, job_type, employment_type, timing,
            company, department, status, photo_path, joining_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        employee_id,
        data.get('name'),
        data.get('email').lower() if data.get('email') else None,
        data.get('password_hash'),
        data.get('temp_password'),
        data.get('role', 'Employee'),
        data.get('employee_type'),
        data.get('designation'),
        data.get('job_type'),
        data.get('employment_type'),
        data.get('timing'),
        data.get('company'),
        data.get('department'),
        data.get('status', 'Active'),
        data.get('photo_path'),
        data.get('joining_date'),
    ))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def list_users() -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users ORDER BY created_at DESC')
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email = ?', (email.lower(),))
    row = cur.fetchone()
    conn.close()
    return row


def update_user(user_id: int, data: Dict[str, Any]) -> None:
    fields = []
    values = []
    for key in ['name','email','role','employee_type','designation','job_type','employment_type','timing','company','department','status','photo_path','joining_date','password_hash','temp_password']:
        if key in data and data[key] is not None:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return
    values.append(user_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", tuple(values))
    conn.commit()
    conn.close()

def delete_user(user_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

# SETTINGS ---------------------------------------------------------------

def list_settings(category: Optional[str] = None) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    if category:
        cur.execute('SELECT * FROM settings WHERE category = ? ORDER BY value', (category,))
    else:
        cur.execute('SELECT * FROM settings ORDER BY category, value')
    rows = cur.fetchall()
    conn.close()
    return rows


def add_setting(category: str, value: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO settings (category, value) VALUES (?, ?)', (category, value))
    conn.commit()
    conn.close()


def delete_setting(setting_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM settings WHERE id = ?', (setting_id,))
    conn.commit()
    conn.close()

def update_setting_value(setting_id: int, new_value: str) -> bool:
    """Update a settings row's value. Returns True on success, False on uniqueness conflict."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE settings SET value = ? WHERE id = ?', (new_value, setting_id))
        conn.commit()
        ok = cur.rowcount > 0
    except sqlite3.IntegrityError:
        ok = False
    finally:
        conn.close()
    return ok

# ATTENDANCE -------------------------------------------------------------

def get_active_attendance(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM attendance
        WHERE user_id = ? AND end_time IS NULL
        ORDER BY start_time DESC
        LIMIT 1
    ''', (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def start_attendance(user_id: int, start_time: str, lat: Optional[float], lng: Optional[float], photo_path: Optional[str], location: Optional[str], whats_doing: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO attendance (user_id, start_time, start_lat, start_lng, start_photo_path, start_location, whats_doing)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, start_time, lat, lng, photo_path, location, whats_doing))
    attendance_id = cur.lastrowid
    # image record
    cur.execute('''
        INSERT INTO attendance_images (attendance_id, photo_path, tag, captured_at, lat, lng)
        VALUES (?, ?, 'start', ?, ?, ?)
    ''', (attendance_id, photo_path, start_time, lat, lng))
    conn.commit()
    conn.close()
    return attendance_id


def stop_attendance(attendance_id: int, end_time: str, lat: Optional[float], lng: Optional[float], photo_path: Optional[str], location: Optional[str] = None, why_stop: Optional[str] = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    # compute duration in seconds via SQL
    cur.execute('SELECT start_time FROM attendance WHERE id = ?', (attendance_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    start_time = row['start_time']
    # Let SQLite compute difference in seconds; stored as text, use julianday
    cur.execute("""
        UPDATE attendance
        SET end_time = ?, end_lat = ?, end_lng = ?, end_photo_path = ?, end_location = ?, why_stop = ?,
            duration_seconds = CAST((julianday(?) - julianday(start_time)) * 24 * 3600 AS INTEGER)
        WHERE id = ?
    """, (end_time, lat, lng, photo_path, location, why_stop, end_time, attendance_id))
    # image record
    cur.execute('''
        INSERT INTO attendance_images (attendance_id, photo_path, tag, captured_at, lat, lng)
        VALUES (?, ?, 'stop', ?, ?, ?)
    ''', (attendance_id, photo_path, end_time, lat, lng))
    conn.commit()
    conn.close()


def add_mid_image(attendance_id: int, photo_path: str, captured_at: str, lat: Optional[float], lng: Optional[float]) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO attendance_images (attendance_id, photo_path, tag, captured_at, lat, lng)
        VALUES (?, ?, 'mid', ?, ?, ?)
    ''', (attendance_id, photo_path, captured_at, lat, lng))
    conn.commit()
    conn.close()


def list_attendance_for_user(user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    if start_date and end_date:
        cur.execute('''
            SELECT * FROM attendance
            WHERE user_id = ? AND date(start_time) BETWEEN ? AND ?
            ORDER BY start_time DESC
        ''', (user_id, start_date, end_date))
    else:
        cur.execute('''
            SELECT * FROM attendance WHERE user_id = ? ORDER BY start_time DESC
        ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_attendance_images(attendance_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM attendance_images WHERE attendance_id = ? ORDER BY captured_at', (attendance_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def aggregate_user_daily(user_id: int, start_date: Optional[str], end_date: Optional[str]) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    if start_date and end_date:
        cur.execute('''
            SELECT date(start_time) as day, SUM(COALESCE(duration_seconds, 0)) as total_seconds
            FROM attendance
            WHERE user_id = ? AND date(start_time) BETWEEN ? AND ?
            GROUP BY date(start_time)
            ORDER BY day DESC
        ''', (user_id, start_date, end_date))
    else:
        cur.execute('''
            SELECT date(start_time) as day, SUM(COALESCE(duration_seconds, 0)) as total_seconds
            FROM attendance
            WHERE user_id = ?
            GROUP BY date(start_time)
            ORDER BY day DESC
        ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_attendance_all(start_date: Optional[str], end_date: Optional[str], employee_id: Optional[int] = None) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    base = '''
        SELECT a.*, u.name, u.employee_id
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE 1=1
    '''
    params: Tuple[Any, ...] = ()
    if start_date and end_date:
        base += ' AND date(a.start_time) BETWEEN ? AND ?'
        params += (start_date, end_date)
    if employee_id:
        base += ' AND u.employee_id = ?'
        params += (employee_id,)
    base += ' ORDER BY a.start_time DESC'
    cur.execute(base, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def list_active_sessions() -> List[sqlite3.Row]:
    """Return active (not stopped) attendance sessions with user info."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT a.*, u.name, u.employee_id
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.end_time IS NULL
        ORDER BY a.start_time DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return rows


def summarize_total_seconds(start_date: str, end_date: str) -> int:
    """Total worked seconds for all users in date range (by date(start_time))."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT COALESCE(SUM(duration_seconds), 0)
        FROM attendance
        WHERE end_time IS NOT NULL AND date(start_time) BETWEEN ? AND ?
    ''', (start_date, end_date))
    total = cur.fetchone()[0] or 0
    conn.close()
    return int(total)

def get_attendance_by_id(att_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single attendance row with user info by attendance ID."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT a.*, u.name, u.employee_id
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.id = ?
    ''', (att_id,))
    row = cur.fetchone()
    conn.close()
    return row

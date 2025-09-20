from typing import Optional, Dict, Any
import sqlite3
import bcrypt
import streamlit as st
from db import get_conn


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def verify_password(password: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except Exception:
        return False


def login(email: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email = ?', (email.lower(),))
    row = cur.fetchone()
    conn.close()
    if row and verify_password(password, row['password_hash']):
        user = dict(row)
        # minimal session payload
        return {
            'id': user['id'],
            'employee_id': user['employee_id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'photo_path': user['photo_path']
        }
    return None


def require_auth() -> Optional[Dict[str, Any]]:
    return st.session_state.get('user')


def logout() -> None:
    for key in ['user', 'active_attendance_id', 'geo']:
        if key in st.session_state:
            del st.session_state[key]

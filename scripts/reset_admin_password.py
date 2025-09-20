import argparse
import sqlite3
import bcrypt


def reset_password(db_path: str, email: str, new_password: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    pw_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    cur.execute(
        "UPDATE users SET password_hash = ?, temp_password = ? WHERE lower(email) = lower(?)",
        (pw_hash, new_password, email),
    )
    conn.commit()
    rows = cur.rowcount
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='attendance.db')
    parser.add_argument('--email', required=True)
    parser.add_argument('--new', dest='new_password', required=True)
    args = parser.parse_args()
    updated = reset_password(args.db, args.email, args.new_password)
    print(f"Rows updated: {updated}")


if __name__ == '__main__':
    main()

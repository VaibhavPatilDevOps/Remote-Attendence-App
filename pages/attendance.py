import streamlit as st
from datetime import date, timedelta
from auth import require_auth
from models import list_attendance_all, list_attendance_for_user, aggregate_user_daily
from utils import now_ist
from datetime import timedelta as _timedelta


def render(user: dict):
    st.title('Attendance')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_attendance'):
            st.rerun()

    # All roles: Employee, Manager, Admin -> Self attendance with presets
    preset = st.radio('Quick Range', ['Today','This Week','This Month','Custom'], horizontal=True)
    today = now_ist().date()
    if preset == 'Today':
        start = end = today
    elif preset == 'This Week':
        start = today - timedelta(days=today.weekday())
        end = today
    elif preset == 'This Month':
        start = today.replace(day=1)
        end = today
    else:
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input('Start Date', value=today - timedelta(days=7), key='emp_start')
        with col2:
            end = st.date_input('End Date', value=today, key='emp_end')

    rows = list_attendance_for_user(user['id'], start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
    st.subheader('Your Sessions')
    total_sec_emp = 0
    data_emp = []
    for r in rows:
        secs = int(r['duration_seconds'] or 0)
        total_sec_emp += secs
        data_emp.append({
            'Start Time (IST)': r['start_time'],
            'End Time (IST)': r['end_time'],
            'Start Location': (r['start_location'] if 'start_location' in r.keys() else None),
            'End Location': (r['end_location'] if 'end_location' in r.keys() else None),
            'Duration (HH:MM:SS)': str(_timedelta(seconds=secs))
        })
    st.dataframe(data_emp, use_container_width=True)
    st.info(f"Total Duration (All Sessions): {str(_timedelta(seconds=int(total_sec_emp)))}")

    # Daily aggregation
    st.subheader('Daily Totals')
    daily = aggregate_user_daily(user['id'], start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
    st.dataframe([
        {
            'Date': d['day'],
            'Total (HH:MM:SS)': str(_timedelta(seconds=int(d['total_seconds'] or 0)))
        } for d in daily
    ], use_container_width=True)

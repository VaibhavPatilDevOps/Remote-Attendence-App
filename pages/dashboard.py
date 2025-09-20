import streamlit as st
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta, date
from auth import require_auth
from models import (
    get_active_attendance,
    start_attendance,
    stop_attendance,
    add_mid_image,
    list_attendance_for_user,
    list_attendance_images,
    list_active_sessions,
    summarize_total_seconds,
)
from utils import now_ist, fmt_ts, save_image_for_employee, IST, reverse_geocode


def _get_geo():
    try:
        loc = get_geolocation()
        if loc and 'coords' in loc:
            return loc['coords']['latitude'], loc['coords']['longitude']
    except Exception:
        pass
    return None, None


def render(user: dict):
    # Set current page for session state management
    st.session_state['current_page'] = 'dashboard'
    
    st.title('Dashboard')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_dashboard'):
            st.rerun()


    # Prefetch geolocation once per render to capture latest browser state
    try:
        loc = get_geolocation()
        if loc and 'coords' in loc:
            st.session_state['geo_lat'] = loc['coords'].get('latitude')
            st.session_state['geo_lng'] = loc['coords'].get('longitude')
            st.session_state['geo_ok'] = True
            # Resolve a place name for status display
            st.session_state['geo_place'] = reverse_geocode(st.session_state['geo_lat'], st.session_state['geo_lng'])
        else:
            st.session_state['geo_ok'] = False
            st.session_state['geo_place'] = None
    except Exception:
        st.session_state['geo_ok'] = False
        st.session_state['geo_place'] = None

    active = get_active_attendance(user['id'])

    col1, col2, col3 = st.columns(3)
    with col1:
        if not active:
            st.subheader('Start Session')
            with st.form('start_form'):
                cam = st.camera_input('Capture to Start (take photo, then click Start Working)', key='start_cam')
                whats_doing = st.text_area('What are you doing?', placeholder='Describe your work activity...', key='start_whats_doing')
                # Location status only
                if st.session_state.get('geo_ok') and st.session_state.get('geo_lat') is not None:
                    place = st.session_state.get('geo_place') or 'enabled'
                    st.success(f"Location - enabled ({place})")
                else:
                    st.info('Location - not enabled')
                submitted = st.form_submit_button('Start Working')
                if submitted:
                    if cam is None:
                        st.warning('Camera photo is required to start.')
                    else:
                        lat = st.session_state.get('geo_lat')
                        lng = st.session_state.get('geo_lng')
                        if lat is None or lng is None:
                            st.warning('Location not available. Please allow location in your browser and click Start again.')
                        else:
                            loc_name = reverse_geocode(lat, lng)
                            full_path, thumb = save_image_for_employee(user['employee_id'], cam.getvalue(), now_ist())
                            start_attendance(user['id'], fmt_ts(now_ist()), lat, lng, full_path, loc_name, whats_doing)
                            st.success('Session started')
                            st.rerun()
        else:
            st.info('Session is active.')
    with col2:
        if active:
            st.subheader('Stop Session')
            with st.form('stop_form'):
                cam2 = st.camera_input('Capture to Stop', key='stop_cam')
                why_stop = st.text_area('Why are you stopping?', placeholder='Reason for stopping work...', key='stop_why_stop')
                # Location status only
                if st.session_state.get('geo_ok') and st.session_state.get('geo_lat') is not None:
                    place = st.session_state.get('geo_place') or 'enabled'
                    st.success(f"Location - enabled ({place})")
                else:
                    st.info('Location - not enabled')
                submitted2 = st.form_submit_button('Stop Working')
                if submitted2:
                    if cam2 is None:
                        st.warning('Camera photo is required to stop.')
                    else:
                        lat = st.session_state.get('geo_lat')
                        lng = st.session_state.get('geo_lng')
                        if lat is None or lng is None:
                            st.warning('Location not available. Please allow location and click Stop again.')
                        else:
                            loc_name = reverse_geocode(lat, lng)
                            full_path, thumb = save_image_for_employee(user['employee_id'], cam2.getvalue(), now_ist())
                            stop_attendance(active['id'], fmt_ts(now_ist()), lat, lng, full_path, loc_name, why_stop)
                            st.success('Session stopped')
                            st.rerun()
    with col3:
        if active:
            start_dt_naive = datetime.strptime(active['start_time'], '%Y-%m-%d %H:%M:%S')
            start_dt = IST.localize(start_dt_naive)
            st.metric('Started at', active['start_time'])
            st.metric('Duration (so far)', str(now_ist() - start_dt).split('.')[0])
            st.caption('This value refreshes on each page interaction.')

    # Mid-session photo capture for employees when a session is active
    if active and user['role'] == 'Employee':
        st.subheader('Add Mid-Session Photo (optional)')
        with st.form('mid_form'):
            mid_cam = st.camera_input('Capture Mid-Session Photo', key='mid_cam')
            # Location status only
            if st.session_state.get('geo_ok') and st.session_state.get('geo_lat') is not None:
                place = st.session_state.get('geo_place') or 'enabled'
                st.success(f"Location - enabled ({place})")
            else:
                st.info('Location - not enabled')
            mid_submit = st.form_submit_button('Add Photo')
            if mid_submit:
                if mid_cam is None:
                    st.warning('Camera photo is required.')
                else:
                    lat, lng = _get_geo()
                    full_path, thumb = save_image_for_employee(user['employee_id'], mid_cam.getvalue(), now_ist())
                    add_mid_image(active['id'], full_path, fmt_ts(now_ist()), lat, lng)
                    st.success('Mid-session photo added')
                    st.rerun()

    st.subheader("Today's Sessions")
    today = now_ist().strftime('%Y-%m-%d')
    sessions = [r for r in list_attendance_for_user(user['id']) if r['start_time'][:10] == today]
    total_seconds = sum([r['duration_seconds'] or 0 for r in sessions])
    st.write(f"Total Worked Today: {timedelta(seconds=total_seconds)}")

    for s in sessions:
        with st.expander(f"Session {s['start_time']} -> {s['end_time'] or 'Running'} | Duration: {timedelta(seconds=s['duration_seconds'] or 0)}"):
            imgs = list_attendance_images(s['id'])
            cols = st.columns(4)
            i = 0
            for img in imgs:
                with cols[i % 4]:
                    st.image(img['photo_path'], caption=f"{img['tag']} @ {img['captured_at']} ({img['lat']}, {img['lng']})")
                i += 1

    # Admin/Manager dashboard widgets
    if user['role'] in ('Admin','Manager'):
        st.markdown('---')
        st.header('Team Overview')
        active_sessions = list_active_sessions()
        colA, colB, colC, colD = st.columns(4)
        with colA:
            st.metric('Active Sessions', len(active_sessions))
        # Aggregates: today, week, month
        today_dt = now_ist().date()
        start_today = today_dt.strftime('%Y-%m-%d')
        end_today = start_today
        week_start = (today_dt - timedelta(days=today_dt.weekday())).strftime('%Y-%m-%d')
        week_end = today_dt.strftime('%Y-%m-%d')
        month_start = today_dt.replace(day=1).strftime('%Y-%m-%d')
        month_end = week_end
        with colB:
            secs_today = summarize_total_seconds(start_today, end_today)
            st.metric('Today (HH:MM:SS)', str(timedelta(seconds=secs_today)))
        with colC:
            secs_week = summarize_total_seconds(week_start, week_end)
            st.metric('This Week', str(timedelta(seconds=secs_week)))
        with colD:
            secs_month = summarize_total_seconds(month_start, month_end)
            st.metric('This Month', str(timedelta(seconds=secs_month)))

        st.subheader('Active Sessions List')
        if active_sessions:
            st.dataframe([
                {
                    'Employee ID': r['employee_id'],
                    'Name': r['name'],
                    'Start Time (IST)': r['start_time'],
                    'Started Lat': r['start_lat'],
                    'Started Lng': r['start_lng']
                } for r in active_sessions
            ], use_container_width=True)
        else:
            st.info('No active sessions right now.')

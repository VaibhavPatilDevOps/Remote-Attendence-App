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
from streamlit.components.v1 import html
import pandas as pd
import altair as alt


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

    # If a session is active, auto-refresh every second to update timer (when supported)
    if get_active_attendance(user['id']):
        auto = getattr(st, 'autorefresh', None)
        if callable(auto):
            auto(interval=1000, key=f"timer_auto_{user['id']}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if not active:
            st.subheader('Start Session')
            with st.form('start_form'):
                enable_cam = getattr(st, 'toggle', None)
                cam_enabled = False
                if callable(enable_cam):
                    cam_enabled = st.toggle('Enable camera', value=False, key='start_cam_toggle')
                else:
                    cam_enabled = st.checkbox('Enable camera', value=False, key='start_cam_toggle')
                cam = None
                if cam_enabled:
                    cam = st.camera_input('Capture to Start (take photo, then click Start Working)', key='start_cam')
                whats_doing = st.text_input("What's Doing? (max 500 chars)", max_chars=500)
                # Location status only
                if st.session_state.get('geo_ok') and st.session_state.get('geo_lat') is not None:
                    place = st.session_state.get('geo_place') or 'enabled'
                    st.success(f"Location - enabled ({place})")
                else:
                    st.info('Location - not enabled')
                submitted = st.form_submit_button('Start Working')
                if submitted:
                    if not whats_doing or not whats_doing.strip():
                        st.warning("Please describe what you're working on.")
                    elif cam is None:
                        st.warning('Camera photo is required to start.')
                    else:
                        lat = st.session_state.get('geo_lat')
                        lng = st.session_state.get('geo_lng')
                        if lat is None or lng is None:
                            st.warning('Location not available. Please allow location in your browser and click Start again.')
                        else:
                            loc_name = reverse_geocode(lat, lng)
                            full_path, thumb = save_image_for_employee(user['employee_id'], cam.getvalue(), now_ist())
                            start_attendance(user['id'], fmt_ts(now_ist()), lat, lng, full_path, loc_name, whats_doing.strip())
                            st.success('Session started')
                            st.rerun()
        else:
            st.info('Session is active.')
    with col2:
        if active:
            st.subheader('Stop Session')
            with st.form('stop_form'):
                cam2 = st.camera_input('Capture to Stop', key='stop_cam')
                why_stop_txt = st.text_input('Why Stop? (max 500 chars)', max_chars=500)
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
                    elif not why_stop_txt or not why_stop_txt.strip():
                        st.warning('Please provide a reason in "Why Stop?"')
                    else:
                        lat = st.session_state.get('geo_lat')
                        lng = st.session_state.get('geo_lng')
                        if lat is None or lng is None:
                            st.warning('Location not available. Please allow location and click Stop again.')
                        else:
                            loc_name = reverse_geocode(lat, lng)
                            full_path, thumb = save_image_for_employee(user['employee_id'], cam2.getvalue(), now_ist())
                            stop_attendance(active['id'], fmt_ts(now_ist()), lat, lng, full_path, loc_name, why_stop_txt.strip())
                            st.success('Session stopped')
                            st.rerun()
    with col3:
        if active:
            start_dt_naive = datetime.strptime(active['start_time'], '%Y-%m-%d %H:%M:%S')
            start_dt = IST.localize(start_dt_naive)
            # Epoch milliseconds for precise client-side ticking
            start_ms = int(start_dt.timestamp() * 1000)
            st.metric('Started at', active['start_time'])
            timer_div_id = f"timer_{active['id']}"
            html(f'''
                <div style="margin-top:8px">
                  <div style="font-weight:600;color:#6c757d;margin-bottom:4px;">Duration (so far)</div>
                  <div id="{timer_div_id}" style="font-size:32px;font-weight:700;line-height:1.2;">00:00:00</div>
                </div>
                <script>
                  (function(){{
                    const startMs = {start_ms};
                    const pad = n => n.toString().padStart(2,'0');
                    function tick(){{
                      const now = Date.now();
                      let sec = Math.max(0, Math.floor((now - startMs)/1000));
                      const h = Math.floor(sec/3600); sec -= h*3600;
                      const m = Math.floor(sec/60); sec -= m*60;
                      const s = sec;
                      const el = document.getElementById('{timer_div_id}');
                      if (el) el.textContent = pad(h)+':' + pad(m)+':' + pad(s);
                    }}
                    tick();
                    if (!window._attTimers) window._attTimers = {{}};
                    if (window._attTimers['{timer_div_id}']) clearInterval(window._attTimers['{timer_div_id}']);
                    window._attTimers['{timer_div_id}'] = setInterval(tick, 1000);
                  }})();
                </script>
            ''', height=90)

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
            ], width='stretch')
        else:
            st.info('No active sessions right now.')

        # Top performers bar chart (by total worked time) for a period
        st.subheader('Top Performers')
        period = st.radio('Period', ['Today','This Week','This Month'], horizontal=True, key='top_perf_period')
        base_date = now_ist().date()
        if period == 'Today':
            p_start = p_end = base_date
        elif period == 'This Week':
            p_start = base_date - timedelta(days=base_date.weekday())
            p_end = base_date
        else:
            p_start = base_date.replace(day=1)
            p_end = base_date

        # Aggregate by user using attendance_all
        from models import list_attendance_all
        rows = list_attendance_all(p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d'))
        agg = {}
        for r in rows:
            nm = r['name'] if 'name' in r.keys() else str(r['user_id'])
            secs = int(r['duration_seconds'] or 0)
            agg[nm] = agg.get(nm, 0) + secs
        df_top = pd.DataFrame([
            {'Name': name, 'DurationSeconds': secs} for name, secs in agg.items()
        ])
        if not df_top.empty:
            df_top['DurationHHMMSS'] = df_top['DurationSeconds'].apply(lambda s: str(now_ist() - now_ist()).split('.')[0])
            # Proper HH:MM:SS from seconds
            from datetime import timedelta as _td
            df_top['DurationHHMMSS'] = df_top['DurationSeconds'].apply(lambda s: str(_td(seconds=int(s))))
            df_top = df_top.sort_values('DurationSeconds', ascending=False).head(10)
            chart = alt.Chart(df_top).mark_bar().encode(
                x=alt.X('DurationSeconds:Q', title='Total Seconds'),
                y=alt.Y('Name:N', sort='-x', title='Employee'),
                tooltip=[alt.Tooltip('Name:N'), alt.Tooltip('DurationHHMMSS:N', title='Total (HH:MM:SS)')]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info('No data for the selected period.')

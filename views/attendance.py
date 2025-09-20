import streamlit as st
import pandas as pd
from datetime import date, timedelta
from auth import require_auth
from models import list_attendance_all, list_attendance_for_user, aggregate_user_daily, list_attendance_images
from utils import now_ist
from datetime import timedelta as _timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def render(user: dict):
    # Set current page for session state management
    st.session_state['current_page'] = 'attendance'
    
    st.title('Attendance')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_attendance'):
            st.rerun()

    tab_session, tab_sheet = st.tabs(['Session', 'Attendance Sheet'])

    # SESSION TAB ---------------------------------------------------------
    with tab_session:
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
        
        # Daily aggregation - moved above Your Sessions
        st.subheader('Daily Totals')
        daily = aggregate_user_daily(user['id'], start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
        st.dataframe([
            {
                'Date': d['day'],
                'Total (HH:MM:SS)': str(_timedelta(seconds=int(d['total_seconds'] or 0)))
            } for d in daily
        ], use_container_width=True)
        
        # Enhanced view details dialog for attendance
        if ('show_attendance_details' in st.session_state and st.session_state['show_attendance_details'] and 
            st.session_state.get('attendance_dialog_triggered', False)):
            @st.dialog('View Details')
            def _view_attendance_details():
                att_id = st.session_state['show_attendance_details']
                # Find the record from the already loaded rows
                attendance_record = None
                for r in rows:
                    if r['id'] == att_id:
                        attendance_record = r
                        break
                
                if attendance_record:
                    # Get values safely from sqlite3.Row object
                    try:
                        start_time = attendance_record['start_time']
                        end_time = attendance_record['end_time']
                        duration_sec = attendance_record['duration_seconds'] or 0
                        start_location = attendance_record['start_location'] if attendance_record['start_location'] else 'Not available'
                        end_location = attendance_record['end_location'] if attendance_record['end_location'] else 'Not available'
                    except Exception as e:
                        st.error(f"Error accessing record data: {e}")
                        return
                    
                    st.subheader(f"Your Attendance - {start_time[:10]}")
                    
                    # Get photos
                    imgs = list_attendance_images(att_id)
                    start_photos = [img for img in imgs if img['tag'] == 'start']
                    stop_photos = [img for img in imgs if img['tag'] == 'stop']
                    
                    # Also get photo paths directly from attendance record as backup
                    start_photo_path = attendance_record['start_photo_path']
                    end_photo_path = attendance_record['end_photo_path']
                    
                    # Create Start and Stop sections
                    col_start, col_stop = st.columns(2)
                    
                    with col_start:
                        st.markdown("### 🟢 START")
                        st.write(f"**Date:** {start_time[:10]}")
                        st.write(f"**Time:** {start_time[11:19]}")
                        st.write(f"**Location:** {start_location}")
                        
                        # Photo
                        if start_photos:
                            for img in start_photos:
                                st.image(img['photo_path'], width=200)
                        elif start_photo_path:
                            st.image(start_photo_path, width=200)
                        else:
                            st.info("No photo")
                    
                    with col_stop:
                        st.markdown("### 🔴 STOP")
                        st.write(f"**Date:** {end_time[:10] if end_time else 'Still Active'}")
                        st.write(f"**Time:** {end_time[11:19] if end_time else 'Still Active'}")
                        st.write(f"**Location:** {end_location}")
                        
                        # Photo
                        if stop_photos:
                            for img in stop_photos:
                                st.image(img['photo_path'], width=200)
                        elif end_photo_path:
                            st.image(end_photo_path, width=200)
                        else:
                            st.info("No photo" if end_time else "Session active")
                    
                    # Total Duration section
                    st.markdown("---")
                    st.markdown(f"### ⏱️ **Total Duration: {str(_timedelta(seconds=int(duration_sec)))}**")
                else:
                    st.error('Attendance record not found.')
                
                if st.button('Close'):
                    st.session_state['show_attendance_details'] = None
                    st.session_state['attendance_dialog_triggered'] = False
                    st.session_state['last_selected_attendance_id'] = None
                    st.rerun()
            
            _view_attendance_details()

        st.subheader('Your Sessions')
        
        # Build simplified dataframe with only required columns
        data_rows = []
        total_sec_emp = 0
        for r in rows:
            secs = int(r['duration_seconds'] or 0)
            total_sec_emp += secs
            data_rows.append({
                'ID': r['id'],
                'Date': (r['start_time'] or '')[:10],
                'Start Time': r['start_time'][11:19] if r['start_time'] else '',
                'End Time': r['end_time'][11:19] if r['end_time'] else '',
                'Duration': str(_timedelta(seconds=secs)),
                'View Details': 'View'
            })

        df = pd.DataFrame(data_rows)
        
        # Total banner
        if not df.empty:
            st.info(f"Total Duration (All Sessions): {str(_timedelta(seconds=int(total_sec_emp)))}")

        # Render simplified table
        if not df.empty:
            builder = GridOptionsBuilder.from_dataframe(df)
            builder.configure_selection(selection_mode='single', use_checkbox=False)
            builder.configure_column('View Details', header_name='View Details', pinned=False)
            builder.configure_grid_options(domLayout='normal')
            grid_options = builder.build()
            
            grid_response = AgGrid(
                df,
                gridOptions=grid_options,
                height=400,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                allow_unsafe_jscode=True,
            )
            
            # Handle row selection for view details
            sel = grid_response.get('selected_rows', [])
            sel_att_id = None
            
            if isinstance(sel, list) and len(sel) > 0:
                sel_att_id = sel[0].get('ID')
            elif isinstance(sel, pd.DataFrame) and not sel.empty:
                try:
                    sel_att_id = sel.iloc[0].get('ID')
                except Exception:
                    sel_att_id = None
            
            if sel_att_id and st.session_state.get('last_selected_attendance_id') != sel_att_id:
                st.session_state['last_selected_attendance_id'] = sel_att_id
                st.session_state['show_attendance_details'] = sel_att_id
                st.session_state['attendance_dialog_triggered'] = True
                st.rerun()
        else:
            st.dataframe(df, use_container_width=True)

    # ATTENDANCE SHEET TAB -----------------------------------------------
    with tab_sheet:
        st.subheader('Attendance Sheet')
        today = now_ist().date()
        col_y, col_m = st.columns(2)
        with col_y:
            year = st.number_input('Year', min_value=2000, max_value=2100, value=today.year, step=1)
        with col_m:
            months = ['January','February','March','April','May','June','July','August','September','October','November','December']
            month_index = st.selectbox('Month', options=list(range(1,13)), format_func=lambda i: months[i-1], index=today.month-1)

        import calendar
        cal = calendar.Calendar(firstweekday=0)  # Monday=0
        month_days = cal.monthdatescalendar(int(year), int(month_index))

        # Load attendance for selected month
        from datetime import date as _date
        start_month = _date(int(year), int(month_index), 1)
        # last day of month
        _, last_day = calendar.monthrange(int(year), int(month_index))
        end_month = _date(int(year), int(month_index), last_day)
        rows = list_attendance_for_user(user['id'], start_month.strftime('%Y-%m-%d'), end_month.strftime('%Y-%m-%d'))
        present_days = set()
        for r in rows:
            try:
                present_days.add(r['start_time'][:10])
            except Exception:
                pass

        # Render grid
        st.caption('Green = Present, Red = Absent (no session), Light Orange = Not Applicable (future dates). Grey = outside selected month.')
        for week in month_days:
            cols = st.columns([1,1,1,1,1,1,1], gap='small')
            for idx, day in enumerate(week):
                # Determine status
                in_month = (day.month == int(month_index))
                key = day.strftime('%Y-%m-%d')
                is_present = key in present_days
                is_future = day > today
                day_name = day.strftime('%A')
                is_weekend = day.weekday() >= 5  # 5=Saturday, 6=Sunday
                weekend_emoji = '😴' if is_weekend else ''
                # Style
                if not in_month:
                    bg = '#e9ecef'
                    fg = '#6c757d'
                else:
                    if is_present:
                        bg, fg = '#d4edda', '#155724'
                    elif is_future:
                        bg, fg = '#ffe5b4', '#8a6d3b'  # light orange, brown text
                    else:
                        bg, fg = '#f8d7da', '#721c24'  # absent
                # Status label text computed in Python to avoid literal braces showing
                if not in_month:
                    status_label = ''
                else:
                    if is_present:
                        status_label = 'Present'
                    elif is_future:
                        status_label = 'Not Applicable'
                    else:
                        status_label = 'Absent'
                with cols[idx]:
                    st.markdown(
                        f"""
                        <div style='height:80px;border-radius:8px;background:{bg};color:{fg};display:flex;align-items:center;justify-content:center;border:1px solid #dee2e6; margin:6px;'>
                          <div>
                            <div style='font-weight:700;font-size:18px;text-align:center'>{day.day} {weekend_emoji}</div>
                            <div style='font-size:11px;text-align:center;opacity:0.85'>{day_name}</div>
                            <div style='font-size:12px;text-align:center'>{status_label}</div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

        # Build simple month-wise report (table) and download CSV
        import pandas as _pd
        # Prepare per-day summary for selected month
        day_list = []
        for d in range(1, last_day + 1):
            day_obj = _date(int(year), int(month_index), d)
            key = day_obj.strftime('%Y-%m-%d')
            in_future = day_obj > today
            present = key in present_days
            if in_future:
                status = 'Not Applicable'
            else:
                status = 'Present' if present else 'Absent'
            # Sum duration for that day from rows
            total_secs = 0
            for r in rows:
                if r['start_time'][:10] == key:
                    total_secs += int(r['duration_seconds'] or 0)
            day_list.append({
                'Date': key,
                'Day': day_obj.strftime('%A'),
                'Status': status,
                'Total Duration (HH:MM:SS)': str(_timedelta(seconds=int(total_secs)))
            })

        df_report = _pd.DataFrame(day_list)
        st.markdown('---')
        st.subheader('Month Report (Preview)')
        st.dataframe(df_report, width='stretch')
        csv_bytes = df_report.to_csv(index=False).encode('utf-8')
        st.download_button(
            'Download Month Report (CSV)',
            data=csv_bytes,
            file_name=f"attendance_{year}_{int(month_index):02d}.csv",
            mime='text/csv'
        )

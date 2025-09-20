import streamlit as st
import pandas as pd
from datetime import timedelta
from models import list_attendance_all, list_attendance_for_user, list_attendance_images, list_users, get_attendance_by_id
from utils import export_csv, export_pdf_attendance, now_ist
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def render(user: dict):
    st.title('Reports')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_reports'):
            st.rerun()

    tab_sessions, tab_att_sheet = st.tabs(['Session Report', 'Attendance Report'])

    # ---------------------- Session Report (improved) ----------------------
    with tab_sessions:
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input('Start Date', value=now_ist().date(), key='rep_start')
        with col2:
            end = st.date_input('End Date', value=now_ist().date(), key='rep_end')

        # Filters for Admin/Manager
        if user['role'] in ('Admin','Manager'):
            employee_id = st.text_input('Filter by Employee ID (optional)')
            name_filter = st.text_input('Filter by Name (optional)')
            emp_id_val = int(employee_id) if employee_id.strip().isdigit() else None
            rows = list_attendance_all(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), emp_id_val)
        else:
            rows = list_attendance_for_user(user['id'], start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

        # Clear popup state when page loads (unless it was just triggered)
        if 'current_page' not in st.session_state or st.session_state['current_page'] != 'reports':
            st.session_state['current_page'] = 'reports'
            st.session_state['show_details_for'] = None
            st.session_state['last_selected_att_id'] = None

        # Enhanced view details dialog - only show if triggered by a click
        if ('show_details_for' in st.session_state and st.session_state['show_details_for'] and 
            st.session_state.get('dialog_triggered_by_click', False)):
            @st.dialog('View Details')
            def _view_details_dialog():
                att_id = st.session_state['show_details_for']
                # Find the record from the already loaded rows
                attendance_record = None
                for r in rows:
                    if r['id'] == att_id:
                        attendance_record = r
                        break
                
                if attendance_record:
                    # Get values safely from sqlite3.Row object
                    try:
                        name = attendance_record['name'] if 'name' in attendance_record.keys() else user['name']
                        emp_id = attendance_record['employee_id'] if 'employee_id' in attendance_record.keys() else user['employee_id']
                        start_time = attendance_record['start_time']
                        end_time = attendance_record['end_time']
                        duration_sec = attendance_record['duration_seconds'] or 0
                        start_location = attendance_record['start_location'] if attendance_record['start_location'] else 'Not available'
                        end_location = attendance_record['end_location'] if attendance_record['end_location'] else 'Not available'
                        start_lat = attendance_record['start_lat']
                        start_lng = attendance_record['start_lng']
                        end_lat = attendance_record['end_lat']
                        end_lng = attendance_record['end_lng']
                        whats_doing = attendance_record['whats_doing'] if attendance_record['whats_doing'] else 'Not specified'
                        why_stop = attendance_record['why_stop'] if attendance_record['why_stop'] else 'Not specified'
                    except Exception as e:
                        st.error(f"Error accessing record data: {e}")
                        return
                    
                    st.subheader(f"{name} - {start_time[:10]}")
                    
                    # Get photos from both sources
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
                        st.write(f"**Time:** {start_time[11:19]}")  # Show only time part
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
                        st.write(f"**Time:** {end_time[11:19] if end_time else 'Still Active'}")  # Show only time part
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
                    st.markdown(f"### ⏱️ **Total Duration: {str(timedelta(seconds=int(duration_sec)))}**")
                else:
                    st.error('Attendance record not found.')
                
                if st.button('Close'):
                    st.session_state['show_details_for'] = None
                    st.session_state['dialog_triggered_by_click'] = False
                    st.session_state['last_selected_att_id'] = None
                    st.rerun()
            
            _view_details_dialog()

        # Build simplified dataframe with only required columns
        data_rows = []
        for r in rows:
            emp_id = r['employee_id'] if 'employee_id' in r.keys() else user['employee_id']
            name = r['name'] if 'name' in r.keys() else user['name']
            dur_sec = int(r['duration_seconds'] or 0)
            
            data_rows.append({
                'ID': r['id'],
                'Name': name,
                'Date': (r['start_time'] or '')[:10],
                'Start Time': r['start_time'][11:19] if r['start_time'] else '',  # Extract time part
                'End Time': r['end_time'][11:19] if r['end_time'] else '',  # Extract time part
                'Duration': str(timedelta(seconds=dur_sec)),
                'View Details': 'View'
            })

        df = pd.DataFrame(data_rows)
        
        # Apply name filter for Admin/Manager if provided
        if user['role'] in ('Admin','Manager') and not df.empty:
            if 'name_filter' in locals() and name_filter and name_filter.strip():
                mask = df['Name'].str.contains(name_filter.strip(), case=False, na=False)
                df = df[mask]

        # Total banner (after filters)
        if not df.empty:
            total_sec = sum([int(r['duration_seconds'] or 0) for r in rows])
            st.info(f"Total Duration (All Rows): {str(timedelta(seconds=total_sec))}")

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
            
            if sel_att_id and st.session_state.get('last_selected_att_id') != sel_att_id:
                st.session_state['last_selected_att_id'] = sel_att_id
                st.session_state['show_details_for'] = sel_att_id
                st.session_state['dialog_triggered_by_click'] = True
                st.rerun()
        else:
            st.dataframe(df, use_container_width=True)

        # Export functionality
        if not df.empty:
            colx, coly = st.columns(2)
            with colx:
                if st.button('Export CSV'):
                    path = os.path.join('reports_export.csv')
                    export_csv(df, path)
                    st.success(f'CSV exported: {path}')
                    with open(path, 'rb') as f:
                        st.download_button('Download CSV', f, file_name='attendance.csv')
            with coly:
                if st.button('Export PDF'):
                    table_data = [['ID','Name','Date','Start Time','End Time','Duration']]
                    for _, row in df.iterrows():
                        table_data.append([
                            str(row['ID']),
                            row.get('Name',''),
                            row.get('Date',''),
                            row.get('Start Time',''),
                            row.get('End Time','') or '',
                            row.get('Duration','')
                        ])
                    pdf_path = 'attendance_report.pdf'
                    export_pdf_attendance(pdf_path, 'Attendance Report', table_data)
                    st.success(f'PDF exported: {pdf_path}')
                    with open(pdf_path, 'rb') as f:
                        st.download_button('Download PDF', f, file_name='attendance.pdf')

    # ---------------------- Attendance Report (calendar) ----------------------
    with tab_att_sheet:
        st.subheader('Attendance Report')
        # Employee selector (Admins/Managers see all; Employees only self)
        users = list_users()
        options = []
        for u in users:
            options.append((u['id'], f"{u['employee_id']} - {u['name']}"))
        # Default selection is current user
        default_index = 0
        for i, (uid, _) in enumerate(options):
            if uid == user['id']:
                default_index = i
                break
        sel_user_id = st.selectbox('Select Employee (ID - Name)', options=[o[0] for o in options], format_func=lambda uid: dict(options)[uid], index=default_index)

        today = now_ist().date()
        col_y, col_m = st.columns(2)
        with col_y:
            year = st.number_input('Year', min_value=2000, max_value=2100, value=today.year, step=1, key='ar_year')
        with col_m:
            months = ['January','February','March','April','May','June','July','August','September','October','November','December']
            month_index = st.selectbox('Month', options=list(range(1,13)), format_func=lambda i: months[i-1], index=today.month-1, key='ar_month')

        import calendar
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(int(year), int(month_index))
        from datetime import date as _date
        start_month = _date(int(year), int(month_index), 1)
        _, last_day = calendar.monthrange(int(year), int(month_index))
        end_month = _date(int(year), int(month_index), last_day)
        rows = list_attendance_for_user(int(sel_user_id), start_month.strftime('%Y-%m-%d'), end_month.strftime('%Y-%m-%d'))
        present_days = set()
        for r in rows:
            try:
                present_days.add(r['start_time'][:10])
            except Exception:
                pass
        # Legend and grid
        st.caption('Green = Present, Red = Absent (no session), Light Orange = Not Applicable (future dates). Grey = outside selected month.')
        for week in month_days:
            cols = st.columns([1,1,1,1,1,1,1], gap='small')
            for idx, day in enumerate(week):
                in_month = (day.month == int(month_index))
                key = day.strftime('%Y-%m-%d')
                is_present = key in present_days
                is_future = day > today
                day_name = day.strftime('%A')
                is_weekend = day.weekday() >= 5
                weekend_emoji = '😴' if is_weekend else ''
                if not in_month:
                    bg, fg, status_label = '#e9ecef', '#6c757d', ''
                else:
                    if is_present:
                        bg, fg, status_label = '#d4edda', '#155724', 'Present'
                    elif is_future:
                        bg, fg, status_label = '#ffe5b4', '#8a6d3b', 'Not Applicable'
                    else:
                        bg, fg, status_label = '#f8d7da', '#721c24', 'Absent'
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

        # Month report table and CSV download
        import pandas as _pd
        day_list = []
        for d in range(1, last_day + 1):
            day_obj = _date(int(year), int(month_index), d)
            key = day_obj.strftime('%Y-%m-%d')
            in_future = day_obj > today
            present = key in present_days
            status = 'Not Applicable' if in_future else ('Present' if present else 'Absent')
            total_secs = 0
            for r in rows:
                if r['start_time'][:10] == key:
                    total_secs += int(r['duration_seconds'] or 0)
            day_list.append({
                'Date': key,
                'Day': day_obj.strftime('%A'),
                'Status': status,
                'Total Duration (HH:MM:SS)': str(timedelta(seconds=int(total_secs)))
            })
        df_emp_month = _pd.DataFrame(day_list)
        st.markdown('---')
        st.subheader('Month Report (Preview)')
        st.dataframe(df_emp_month, width='stretch')
        csv_bytes = df_emp_month.to_csv(index=False).encode('utf-8')
        st.download_button(
            'Download Month Report (CSV)',
            data=csv_bytes,
            file_name=f"attendance_{sel_user_id}_{year}_{int(month_index):02d}.csv",
            mime='text/csv'
        )

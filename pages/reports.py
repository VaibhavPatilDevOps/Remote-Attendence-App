import streamlit as st
import pandas as pd
from datetime import timedelta
from models import list_attendance_all, list_attendance_for_user, list_attendance_images
from utils import export_csv, export_pdf_attendance, now_ist
import os
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


def render(user: dict):
    st.title('Reports')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_reports'):
            st.rerun()

    # If a photo dialog is requested via query param, render it first
    att_q = st.query_params.get('att_id') if hasattr(st, 'query_params') else None
    if att_q:
        try:
            att_id = int(att_q)
        except Exception:
            att_id = None
        if att_id:
            @st.dialog('Session Photos')
            def _photos_dialog():
                imgs = list_attendance_images(att_id)
                if imgs:
                    cols = st.columns(4)
                    i = 0
                    for img in imgs:
                        with cols[i % 4]:
                            st.image(img['photo_path'], caption=f"{img['tag']} @ {img['captured_at']} ({img['lat']}, {img['lng']})")
                        i += 1
                else:
                    st.info('No photos found for this session.')
                if st.button('Close'):
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.rerun()
            _photos_dialog()

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input('Start Date', value=now_ist().date())
    with col2:
        end = st.date_input('End Date', value=now_ist().date())

    data_rows = []
    if user['role'] in ('Admin','Manager'):
        employee_id = st.text_input('Filter by Employee ID (optional)')
        name_filter = st.text_input('Filter by Name (optional)')
        emp_id_val = int(employee_id) if employee_id.strip().isdigit() else None
        rows = list_attendance_all(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), emp_id_val)
    else:
        rows = list_attendance_for_user(user['id'], start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

    # Build base dataframe
    for r in rows:
        emp_id = r['employee_id'] if 'employee_id' in r.keys() else user['employee_id']
        name = r['name'] if 'name' in r.keys() else user['name']
        dur_sec = int(r['duration_seconds'] or 0)
        data_rows.append({
            'Attendance ID': r['id'],
            'Employee ID': emp_id,
            'Name': name,
            'Start Time': r['start_time'],
            'End Time': r['end_time'],
            'Start Location': (r['start_location'] if 'start_location' in r.keys() else None),
            'End Location': (r['end_location'] if 'end_location' in r.keys() else None),
            'Duration (sec)': dur_sec,
            'Date': (r['start_time'] or '')[:10]
        })

    df = pd.DataFrame(data_rows)
    # Apply name filter for Admin/Manager if provided
    if user['role'] in ('Admin','Manager') and not df.empty:
        if name_filter and name_filter.strip():
            mask = df['Name'].str.contains(name_filter.strip(), case=False, na=False)
            df = df[mask]
    if not df.empty:
        # Duration formatted HH:MM:SS
        df['Duration (HH:MM:SS)'] = df['Duration (sec)'].apply(lambda s: str(timedelta(seconds=int(s))))
        # Aggregate total seconds per employee and date
        agg = df.groupby(['Employee ID','Name','Date'], as_index=False)['Duration (sec)'].sum()
        agg['Daily Total (HH:MM:SS)'] = agg['Duration (sec)'].apply(lambda s: str(timedelta(seconds=int(s))))
        # Map aggregated total back to each row for display
        df = df.merge(agg[['Employee ID','Date','Daily Total (HH:MM:SS)']], on=['Employee ID','Date'], how='left')
        # Order columns
        display_cols = ['Employee ID','Name','Date','Start Time','End Time','Start Location','End Location',"What's Doing",'Duration (HH:MM:SS)','Daily Total (HH:MM:SS)']
        df_display = df[['Attendance ID'] + display_cols].copy()
        df_display['Photos'] = 'View photo'
    else:
        df_display = df

    # Total banner (after filters)
    if not df.empty:
        total_sec = int(df['Duration (sec)'].sum())
        st.info(f"Total Duration (All Rows): {str(timedelta(seconds=total_sec))}")
    # Render AgGrid with a Photos column
    if not df_display.empty:
        builder = GridOptionsBuilder.from_dataframe(df_display)
        builder.configure_selection(selection_mode='single', use_checkbox=False)
        builder.configure_column('Attendance ID', hide=True)
        builder.configure_column('Photos', header_name='Photos', pinned=False)
        builder.configure_grid_options(domLayout='normal')
        grid_options = builder.build()
        grid_response = AgGrid(
            df_display,
            gridOptions=grid_options,
            height=380,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
        )
        # Auto-open dialog when a row is selected (e.g., clicking Photos cell selects row)
        sel = grid_response.get('selected_rows', [])
        sel_att_id = None
        # Handle both list-of-dicts and DataFrame cases to avoid ambiguous truth value
        if isinstance(sel, list) and len(sel) > 0:
            sel_att_id = sel[0].get('Attendance ID')
        elif isinstance(sel, pd.DataFrame) and not sel.empty:
            # st-aggrid older/newer versions may return a DataFrame
            try:
                sel_att_id = sel.iloc[0].get('Attendance ID')
            except Exception:
                sel_att_id = None
        if sel_att_id and st.session_state.get('last_open_att_id') != sel_att_id:
            st.session_state['last_open_att_id'] = sel_att_id
            @st.dialog('Session Photos')
            def _photos_dialog_auto():
                imgs = list_attendance_images(int(sel_att_id))
                if imgs:
                    cols = st.columns(4)
                    i = 0
                    for img in imgs:
                        with cols[i % 4]:
                            st.image(img['photo_path'], caption=f"{img['tag']} @ {img['captured_at']} ({img['lat']}, {img['lng']})")
                        i += 1
                else:
                    st.info('No photos found for this session.')
                if st.button('Close'):
                    st.rerun()
            _photos_dialog_auto()
    else:
        st.dataframe(df_display, use_container_width=True)

    colx, coly = st.columns(2)
    with colx:
        if st.button('Export CSV'):
            path = os.path.join('reports_export.csv')
            export_csv(df_display, path)
            st.success(f'CSV exported: {path}')
            with open(path, 'rb') as f:
                st.download_button('Download CSV', f, file_name='attendance.csv')
    with coly:
        if st.button('Export PDF'):
            table_data = [['Employee ID','Name','Date','Start Time','End Time','Start Location','End Location','Duration (HH:MM:SS)','Daily Total (HH:MM:SS)']]
            for _, row in df_display.iterrows():
                table_data.append([
                    str(row['Employee ID']),
                    row.get('Name',''),
                    row.get('Date',''),
                    row.get('Start Time',''),
                    row.get('End Time','') or '',
                    row.get('Start Location','') or '',
                    row.get('End Location','') or '',
                    row.get('Duration (HH:MM:SS)',''),
                    row.get('Daily Total (HH:MM:SS)','')
                ])
            pdf_path = 'attendance_report.pdf'
            export_pdf_attendance(pdf_path, 'Attendance Report', table_data)
            st.success(f'PDF exported: {pdf_path}')
            with open(pdf_path, 'rb') as f:
                st.download_button('Download PDF', f, file_name='attendance.pdf')

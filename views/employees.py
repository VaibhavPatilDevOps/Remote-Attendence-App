import streamlit as st
from datetime import datetime as _dt, date as _date
from auth import require_auth
from models import list_users, create_user, update_user, get_user_by_email, get_user_by_id, list_settings, delete_user
from utils import save_image_for_employee
from auth import hash_password
from db import get_next_employee_id


def render(user: dict):
    # Set current page for session state management
    st.session_state['current_page'] = 'employees'
    
    if user['role'] not in ('Admin','Manager'):
        st.error('Unauthorized')
        return
    st.title('Employees')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_employees'):
            st.rerun()

    tab1, tab2 = st.tabs(['Employee List', 'Add Employee'])

    with tab1:
        rows = list_users()
        st.subheader('All Employees')
        is_admin = (user['role'] == 'Admin')
        widths_admin = [1.2, 2.0, 2.8, 1.2, 1.2, 2.0, 2.2]
        widths_view = [1.2, 2.0, 2.8, 1.2, 1.2, 1.4]  # managers now see Action (View only)
        header_cols = st.columns(widths_admin if is_admin else widths_view)
        header_cols[0].markdown('**Emp ID**')
        header_cols[1].markdown('**Name**')
        header_cols[2].markdown('**Email**')
        header_cols[3].markdown('**Role**')
        header_cols[4].markdown('**Status**')
        if is_admin:
            header_cols[5].markdown('**Temp Password**')
            header_cols[6].markdown('**Action**')
        else:
            header_cols[5].markdown('**Action**')

        # Helper to load options from settings with blank default
        def _opts(cat):
            vals = list_settings(cat)
            return [''] + [v['value'] for v in vals]

        for r in rows:
            cols = st.columns(widths_admin if is_admin else widths_view)
            cols[0].write(r['employee_id'])
            cols[1].write(r['name'])
            cols[2].write(r['email'])
            cols[3].write(r['role'])
            cols[4].write(r['status'])
            if is_admin:
                cols[5].write(r['temp_password'] if 'temp_password' in r.keys() else '')
                with cols[6]:
                    col_v, col_e, col_d = st.columns(3)
                    with col_v:
                        if st.button('View', key=f"view_{r['id']}"):
                            target_id = int(r['id'])
                            @st.dialog('Employee Details')
                            def _view_dialog(u_id: int = target_id):
                                row = get_user_by_id(u_id)
                                st.subheader(f"{row['name']} ({row['employee_id']})")
                                # Basic info
                                st.markdown(f"**Email:** {row['email']}")
                                st.markdown(f"**Role:** {row['role']}")
                                st.markdown(f"**Status:** {row['status']}")
                                # Extended
                                def _val(k):
                                    return row[k] if k in row.keys() and row[k] is not None else ''
                                colA, colB, colC = st.columns(3)
                                with colA:
                                    st.write('Employee Type:', _val('employee_type'))
                                    st.write('Job Type:', _val('job_type'))
                                with colB:
                                    st.write('Designation:', _val('designation'))
                                    st.write('Employment Type:', _val('employment_type'))
                                with colC:
                                    st.write('Timing:', _val('timing'))
                                    st.write('Company:', _val('company'))
                                st.write('Department:', _val('department'))
                                st.write('Joining Date:', _val('joining_date'))
                                if 'photo_path' in row.keys() and row['photo_path']:
                                    st.image(row['photo_path'], caption='Profile Photo', width=200)
                                st.button('Close', key=f"view_close_{u_id}")
                            _view_dialog()
                    with col_e:
                        if st.button('Edit', key=f"edit_{r['id']}"):
                            target_id = int(r['id'])
                            @st.dialog('Edit Employee')
                            def _edit_dialog(u_id: int = target_id):
                                # Reload latest row to avoid stale/closure issues
                                row = get_user_by_id(u_id)
                                # Prefill fields
                                name = st.text_input('Name', value=row['name'], key=f"ed_name_{u_id}")
                                email = st.text_input('Email', value=row['email'], key=f"ed_email_{u_id}")
                                
                                # Role options based on current user's role
                                if user['role'] == 'Admin':
                                    role_options = ['Employee','Manager','Admin']
                                else:  # Manager
                                    role_options = ['Employee','Manager']
                                
                                # Find current role index, but only if it's in allowed options
                                current_role = row['role']
                                if current_role in role_options:
                                    role_index = role_options.index(current_role)
                                else:
                                    role_index = 0  # Default to first option if current role not allowed
                                
                                role = st.selectbox('Role', options=role_options, index=role_index, key=f"ed_role_{u_id}")
                                status = st.selectbox('Status', options=['Active','Inactive'], index=0 if row['status'] == 'Active' else 1, key=f"ed_status_{u_id}")

                                # Additional fields
                                emp_type_opts = _opts('employee_type')
                                desg_opts = _opts('designation')
                                job_type_opts = _opts('job_type')
                                emp_mode_opts = _opts('employment_type')
                                timing_opts = _opts('timing')
                                company_opts = _opts('company')
                                dept_opts = _opts('department')

                                def _idx(options, val):
                                    v = val or ''
                                    return options.index(v) if v in options else 0

                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    employee_type = st.selectbox('Employee Type', options=emp_type_opts, index=_idx(emp_type_opts, row['employee_type'] if 'employee_type' in row.keys() else None), key=f"ed_emp_type_{u_id}")
                                    job_type = st.selectbox('Job Type', options=job_type_opts, index=_idx(job_type_opts, row['job_type'] if 'job_type' in row.keys() else None), key=f"ed_job_type_{u_id}")
                                with col2:
                                    designation = st.selectbox('Designation', options=desg_opts, index=_idx(desg_opts, row['designation'] if 'designation' in row.keys() else None), key=f"ed_desg_{u_id}")
                                    employment_type = st.selectbox('Employment Type', options=emp_mode_opts, index=_idx(emp_mode_opts, row['employment_type'] if 'employment_type' in row.keys() else None), key=f"ed_emp_mode_{u_id}")
                                with col3:
                                    timing = st.selectbox('Timing', options=timing_opts, index=_idx(timing_opts, row['timing'] if 'timing' in row.keys() else None), key=f"ed_timing_{u_id}")
                                    company = st.selectbox('Company', options=company_opts, index=_idx(company_opts, row['company'] if 'company' in row.keys() else None), key=f"ed_company_{u_id}")
                                department = st.selectbox('Department', options=dept_opts, index=_idx(dept_opts, row['department'] if 'department' in row.keys() else None), key=f"ed_dept_{u_id}")

                                # Joining date
                                jd_val = None
                                try:
                                    if ('joining_date' in row.keys()) and row['joining_date']:
                                        jd_val = _dt.strptime(str(row['joining_date']), '%Y-%m-%d').date()
                                except Exception:
                                    jd_val = None
                                joining_date = st.date_input('Joining Date', value=jd_val or _date.today(), key=f"ed_join_{u_id}")

                                # Optional new password
                                new_pwd = st.text_input('New Password (leave blank to keep current)', type='password', key=f"ed_pwd_{u_id}")
                                if st.button('Save Changes', type='primary', key=f"ed_save_{u_id}"):
                                    update_data = {
                                        'name': name.strip(),
                                        'email': email.strip().lower(),
                                        'role': role,
                                        'status': status,
                                        'employee_type': employee_type or None,
                                        'designation': designation or None,
                                        'job_type': job_type or None,
                                        'employment_type': employment_type or None,
                                        'timing': timing or None,
                                        'company': company or None,
                                        'department': department or None,
                                        'joining_date': joining_date.strftime('%Y-%m-%d') if joining_date else None,
                                    }
                                    if new_pwd and new_pwd.strip():
                                        pwd_hash = hash_password(new_pwd.strip())
                                        update_data['password_hash'] = pwd_hash
                                        update_data['temp_password'] = new_pwd.strip()
                                    update_user(u_id, update_data)
                                    st.success('Employee updated successfully')
                                    st.rerun()
                                st.button('Cancel', key=f"ed_cancel_{u_id}")
                            _edit_dialog()
                    with col_d:
                        if st.button('Delete', key=f"del_{r['id']}"):
                            target_id = int(r['id'])
                            @st.dialog('Confirm Deletion')
                            def _confirm_delete(u_id: int = target_id):
                                st.warning('This will permanently delete the employee and all related data. This action cannot be undone.')
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    if st.button('Confirm Delete', type='primary', key=f"del_conf_{u_id}"):
                                        delete_user(int(u_id))
                                        st.success('Employee deleted')
                                        st.rerun()
                                with col_b:
                                    st.button('Cancel', key=f"del_cancel_{u_id}")
                            _confirm_delete()
            else:
                # Manager view: add Action column with View button
                with cols[5]:
                    if st.button('View Details', key=f"view_mgr_{r['id']}"):
                        target_id = int(r['id'])
                        @st.dialog('Employee Details')
                        def _view_dialog_mgr(u_id: int = target_id):
                            row = get_user_by_id(u_id)
                            st.subheader(f"{row['name']} ({row['employee_id']})")
                            st.markdown(f"**Email:** {row['email']}")
                            st.markdown(f"**Role:** {row['role']}")
                            st.markdown(f"**Status:** {row['status']}")
                            def _val(k):
                                return row[k] if k in row.keys() and row[k] is not None else ''
                            colA, colB, colC = st.columns(3)
                            with colA:
                                st.write('Employee Type:', _val('employee_type'))
                                st.write('Job Type:', _val('job_type'))
                            with colB:
                                st.write('Designation:', _val('designation'))
                                st.write('Employment Type:', _val('employment_type'))
                            with colC:
                                st.write('Timing:', _val('timing'))
                                st.write('Company:', _val('company'))
                            st.write('Department:', _val('department'))
                            st.write('Joining Date:', _val('joining_date'))
                            if 'photo_path' in row.keys() and row['photo_path']:
                                st.image(row['photo_path'], caption='Profile Photo', width=200)
                            st.button('Close', key=f"view_mgr_close_{u_id}")
                        _view_dialog_mgr()

    with tab2:
        # Load dropdown values from settings
        def opts(cat):
            vals = list_settings(cat)
            return [v['value'] for v in vals]

        with st.form('add_emp'):
            col_a, col_b = st.columns(2)
            with col_a:
                suggested_emp = get_next_employee_id()
                employee_id = st.number_input('Employee ID', min_value=25001, value=int(suggested_emp), step=1, help='Defaults to next available ID; you can override if needed.')
            with col_b:
                joining_date = st.date_input('Joining Date')

            name = st.text_input('Name')
            email = st.text_input('Email')

            col1, col2, col3 = st.columns(3)
            with col1:
                # Role options based on current user's role
                if user['role'] == 'Admin':
                    role_options = ['Employee','Manager','Admin']
                else:  # Manager
                    role_options = ['Employee','Manager']
                role = st.selectbox('Role', role_options)
                employee_type = st.selectbox('Employee Type', options=[''] + opts('employee_type'))
                job_type = st.selectbox('Job Type', options=[''] + opts('job_type'))
            with col2:
                designation = st.selectbox('Designation', options=[''] + opts('designation'))
                employment_type = st.selectbox('Employment Type', options=[''] + opts('employment_type'))
                timing = st.selectbox('Timing', options=[''] + opts('timing'))
            with col3:
                company = st.selectbox('Company', options=[''] + opts('company'))
                department = st.selectbox('Department', options=[''] + opts('department'))
                status = st.selectbox('Status', options=['Active','Inactive'])

            password = st.text_input('Temp Password', type='password')
            photo = st.file_uploader('Profile Photo', type=['jpg','jpeg','png'])
            submitted = st.form_submit_button('Create')
            if submitted:
                if not (name and email and password):
                    st.warning('Name, Email, and Password are required')
                elif get_user_by_email(email):
                    st.error('Email already exists')
                else:
                    pwd_hash = hash_password(password)
                    user_id = create_user({
                        'employee_id': int(employee_id) if employee_id else None,
                        'name': name,
                        'email': email,
                        'password_hash': pwd_hash,
                        'temp_password': password,
                        'role': role,
                        'employee_type': employee_type or None,
                        'designation': designation or None,
                        'job_type': job_type or None,
                        'employment_type': employment_type or None,
                        'timing': timing or None,
                        'company': company or None,
                        'department': department or None,
                        'status': status,
                        'joining_date': joining_date.strftime('%Y-%m-%d') if joining_date else None,
                    })
                    # If photo uploaded, save now using generated employee_id and update record
                    if photo is not None:
                        created = get_user_by_id(user_id)
                        if created and created['employee_id']:
                            full_path, thumb = save_image_for_employee(created['employee_id'], photo.read())
                            update_user(user_id, {'photo_path': full_path})
                    st.success('Employee created')
                    st.rerun()

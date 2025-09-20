import streamlit as st
from auth import require_auth
from models import list_users, create_user, update_user, get_user_by_email, get_user_by_id, list_settings
from utils import save_image_for_employee
from auth import hash_password
from db import get_next_employee_id


def render(user: dict):
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
        st.dataframe([{ 'Employee ID': r['employee_id'], 'Name': r['name'], 'Email': r['email'], 'Role': r['role'], 'Status': r['status'] } for r in rows], use_container_width=True)

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
                role = st.selectbox('Role', ['Employee','Manager','Admin'])
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

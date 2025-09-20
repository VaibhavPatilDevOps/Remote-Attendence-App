import streamlit as st
from models import list_settings, add_setting, delete_setting, update_setting_value

CATEGORIES = ['employee_type','designation','job_type','employment_type','timing','status','company','department']


def _settings_tab(category: str):
    st.subheader(category.replace('_',' ').title())
    vals = list_settings(category)

    # Table header
    hdr = st.columns([4,1,1])
    hdr[0].markdown('**Name**')
    hdr[1].markdown('**Edit**')
    hdr[2].markdown('**Delete**')

    # Rows
    for v in vals:
        row = st.columns([4,1,1])
        # Editable name field
        name_key = f"set_name_{category}_{v['id']}"
        new_name = row[0].text_input(' ', value=v['value'], key=name_key, label_visibility='collapsed')
        # Save button
        with row[1]:
            if st.button('Save', key=f"save_{category}_{v['id']}"):
                if new_name and new_name.strip():
                    ok = update_setting_value(int(v['id']), new_name.strip())
                    if ok:
                        st.success('Updated')
                        st.rerun()
                    else:
                        st.error('Value already exists or could not update')
                else:
                    st.warning('Name cannot be empty')
        # Delete button
        with row[2]:
            if st.button('Delete', key=f"del_{category}_{v['id']}"):
                delete_setting(int(v['id']))
                st.success('Deleted')
                st.rerun()

    st.markdown('---')
    # Add new value
    with st.form(f'add_form_{category}'):
        col1, col2 = st.columns([4,1])
        with col1:
            new_val = st.text_input(f'Add {category}', key=f'in_{category}')
        with col2:
            submitted = st.form_submit_button('Add')
        if submitted and new_val and new_val.strip():
            add_setting(category, new_val.strip())
            st.success('Added')
            st.rerun()


def render(user: dict):
    # Set current page for session state management
    st.session_state['current_page'] = 'settings'
    
    if user['role'] not in ('Admin','Manager'):
        st.error('Unauthorized')
        return
    st.title('Employee Settings')
    cols_hdr = st.columns([8,2])
    with cols_hdr[1]:
        if st.button('Reload', type='primary', key='reload_settings'):
            st.rerun()
    tabs = st.tabs([c.replace('_',' ').title() for c in CATEGORIES])
    for i, c in enumerate(CATEGORIES):
        with tabs[i]:
            _settings_tab(c)

import streamlit as st
from models import list_settings, add_setting, delete_setting

CATEGORIES = ['employee_type','designation','job_type','employment_type','timing','status','company','department']


def _settings_tab(category: str):
    st.subheader(category.replace('_',' ').title())
    vals = list_settings(category)
    st.write([v['value'] for v in vals])
    col1, col2 = st.columns([3,1])
    with col1:
        new_val = st.text_input(f'Add {category}', key=f'in_{category}')
    with col2:
        if st.button('Add', key=f'add_{category}'):
            if new_val.strip():
                add_setting(category, new_val.strip())
                st.rerun()
    for v in vals:
        if st.button(f"Delete '{v['value']}'", key=f"del_{category}_{v['id']}"):
            delete_setting(v['id'])
            st.rerun()


def render(user: dict):
    if user['role'] not in ('Admin','Manager'):
        st.error('Unauthorized')
        return
    st.title('Employee Settings')
    tabs = st.tabs([c.replace('_',' ').title() for c in CATEGORIES])
    for i, c in enumerate(CATEGORIES):
        with tabs[i]:
            _settings_tab(c)

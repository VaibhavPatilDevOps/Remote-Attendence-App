import streamlit as st
from db import init_db
from auth import login, require_auth, logout
from models import get_active_attendance
from utils import now_ist

st.set_page_config(page_title='Attendance System', page_icon='⏱️', layout='wide')

# Initialize DB once
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state['db_initialized'] = True


def render_login():
    # Hide sidebar and extra multipage sections while on login
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        /* Expand main area when sidebar is hidden */
        div[data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title('Remote Attendance System')
    st.subheader('Login')
    with st.form('login_form'):
        email = st.text_input('Email')
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('Login')
        if submitted:
            user = login(email, password)
            if user:
                st.session_state['user'] = user
                st.success(f"Welcome, {user['name']}")
                st.rerun()
            else:
                st.error('Invalid credentials')


def sidebar(user):
    # Hide default Streamlit multipage menu if any pages/ folder exists
    st.markdown(
        """
        <style>
        div[data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.title('Navigation')
    st.sidebar.write(f"Logged in as: {user['name']} ({user['role']})")
    if st.sidebar.button('Logout'):
        logout()
        st.rerun()
    menu = []
    if user['role'] in ('Admin','Manager','Employee'):
        menu.append('Dashboard')
        menu.append('Attendance')
    if user['role'] in ('Admin','Manager'):
        menu.append('Employees')
        menu.append('Reports')
        menu.append('Settings')
    choice = st.sidebar.radio('Go to', menu, index=0)
    return choice


# Router that imports page modules lazily

def route(choice: str, user: dict):
    if choice == 'Dashboard':
        from views import dashboard as page
        page.render(user)
    elif choice == 'Employees':
        from views import employees as page
        page.render(user)
    elif choice == 'Attendance':
        from views import attendance as page
        page.render(user)
    elif choice == 'Reports':
        from views import reports as page
        page.render(user)
    elif choice == 'Settings':
        from views import settings as page
        page.render(user)
    else:
        st.info('Select a page from the sidebar.')


def main():
    user = require_auth()
    if not user:
        render_login()
        return
    choice = sidebar(user)
    route(choice, user)


if __name__ == '__main__':
    main()

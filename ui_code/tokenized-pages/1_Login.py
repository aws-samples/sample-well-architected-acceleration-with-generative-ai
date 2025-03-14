import streamlit as st
import boto3
import botocore
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(page_title="Login", layout="wide")


# Cognito configuration
COGNITO_USER_POOL_ID = '{{PARAMETER_COGNITO_USER_POOL_ID}}'
COGNITO_APP_CLIENT_ID = '{{PARAMETER_COGNITO_USER_POOL_CLIENT_ID}}'
COGNITO_REGION = '{{REGION}}'

if not COGNITO_USER_POOL_ID or not COGNITO_APP_CLIENT_ID:
    st.error("Cognito configuration is missing. Please check your SSM parameters or environment variables.")
    st.stop()

logger.info(f"Cognito User Pool ID: {COGNITO_USER_POOL_ID}")
logger.info(f"Cognito App Client ID: {COGNITO_APP_CLIENT_ID}")
logger.info(f"Cognito Region: {COGNITO_REGION}")

def authenticate(username, password):
    client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
    try:
        resp = client.initiate_auth(
            ClientId=COGNITO_APP_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            }
        )
        logger.info(f"Successfully authenticated user: {username}")
        return True, username
    except client.exceptions.NotAuthorizedException:
        logger.warning(f"Authentication failed for user: {username}")
        return False, None
    except client.exceptions.UserNotFoundException:
        logger.warning(f"User not found: {username}")
        return False, None
    except Exception as e:
        logger.error(f"An error occurred during authentication: {str(e)}")
        st.error(f"An error occurred: {str(e)}")
        return False, None

# Main UI
st.title('Login')

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if st.session_state['authenticated']:
    st.write(f"Welcome back, {st.session_state['username']}!")
    if st.button('Logout'):
        st.session_state['authenticated'] = False
        st.session_state.pop('username', None)
        st.rerun()
else:
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        login_button = st.button("Login")

        if login_button:
            if username and password:
                authentication_status, cognito_username = authenticate(username, password)
                if authentication_status:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = cognito_username
                    st.rerun()
            else:
                st.warning("Please enter both username and password")

    with tab2:
        st.info("Please contact your Admin to get registered.")
        
# Navigation options
if st.session_state['authenticated']:
    st.write("Please select where you'd like to go:")
    
    col1, col2, col3, = st.columns(3)
    
    with col1:
        if st.button('  New WAFR Review    '):
            st.switch_page("pages/1_New_WAFR_Review.py")
    with col2:
        if st.button('  Existing WAFR Reviews    '):
            st.switch_page("pages/2_Existing_WAFR_Reviews.py")
    with col3:
        if st.button('  System Architecture    '):
            st.switch_page("pages/3_System_Architecture.py")

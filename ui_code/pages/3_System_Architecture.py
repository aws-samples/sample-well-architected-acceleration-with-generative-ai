import streamlit as st
if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
    st.warning('You are not logged in. Please log in to access this page.')
    st.switch_page("pages/1_Login.py")

# Check authentication


def architecture():
    st.title("Architecture")

    st.header("AWS Well-Architected Acceleration with Generative AI Architecture")
    st.image("sys-arch.png", use_container_width=True)

    st.header("Components")
    st.write("""
    - **Frontend:** The user interface is built using Streamlit, providing an interactive and user-friendly environment for users to conduct reviews.
    - **Backend:** The backend services are developed using Python and integrate with various AWS services to manage data and computations.
    - **Database:** Data is stored securely in DynamoDB. Amazon OpenSearch serverless is used as the knowledge base for Amazon Bedrock.
    - **Integration Services:** The system integrates with Amazon DynamoDB, Amazon Bedrock and AWS Well-Architected Tool APIs to fetch necessary data and provide additional functionality.
    - **Security:** Amazon Cognito is used for user management.
    """)

if __name__ == "__main__":
    architecture()

# Logout function
def logout():
    st.session_state['authenticated'] = False
    st.session_state.pop('username', None)
    st.rerun()

# Add logout button in sidebar
if st.sidebar.button('Logout'):
    logout()

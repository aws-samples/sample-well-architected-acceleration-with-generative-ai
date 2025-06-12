import logging
import streamlit as st

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("You are not logged in. Please log in to access this page.")
    st.switch_page("pages/1_Login.py")


# Logout function
def logout():
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()


# Add logout button in sidebar
if st.sidebar.button("Logout"):
    logout()


def main():
    """
    Streamlit APP
    """
    # Main content for the home page
    st.write(
        """
    ### What is AWS Well-Architected Acceleration with Generative AI sample?

    **WAFR Accelerator** is a comprehensive sample designed to facilitate and expedite the AWS Well-Architected Framework Review process. The AWS Well-Architected Framework helps cloud architects build secure, high-performing, resilient, and efficient infrastructure for their applications. 

    **WAFR Accelerator** offers an intuitive interface and a set of robust features aimed at enhancing the review experience.

    ### Getting Started

    To get started, simply navigate through the features available in the navigation bar. 
    """
    )


if __name__ == "__main__":
    main()

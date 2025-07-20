import streamlit as st
import boto3
import uuid
import json
import datetime
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

# Check authentication
if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
    st.warning('You are not logged in. Please log in to access this page.')
    st.switch_page("pages/1_Login.py")

st.set_page_config(page_title="Create WAFR Analysis", layout="wide")

# Initialize AWS clients
s3_client = boto3.client('s3')
well_architected_client = boto3.client('wellarchitected', region_name="{{REGION}}")

def list_static_lenses():

    lenses = {}
    lenses["AWS Well-Architected Framework"] = "wellarchitected"
    lenses["Data Analytics Lens"] = "arn:aws:wellarchitected::aws:lens/dataanalytics"
    lenses["Financial Services Industry Lens"] = "arn:aws:wellarchitected::aws:lens/financialservices"
    lenses["Generative AI Lens"] = "arn:aws:wellarchitected::aws:lens/genai"

    return lenses

# Not used as only 4 lenses are supported
def list_lenses(wa_client):

    next_token = None
    lenses = {}
    
    try:
        while True:
            # Prepare the parameters for the API call
            params = {}
            if next_token:
                params['NextToken'] = next_token

            # Make the API call
            response = wa_client.list_lenses(**params)
            
            for lens in response.get('LensSummaries', []):
                lens_name = lens.get('LensName', 'Unknown')
                lens_alias = lens.get('LensAlias', lens.get('LensArn', 'Unknown'))
                lenses[lens_name] = lens_alias
                print (f"{lens_name} : {lens_alias}")
                
            # Check if there are more results
            next_token = response.get('NextToken')
            if not next_token:
                break

        return lenses

    except ClientError as e:
        print(f"An error occurred: {e}")
        return None
        
lenses = list_static_lenses()
lens_list = list(lenses.keys())

def get_current_user():
    return st.session_state.get('username', 'Unknown User')

# Initialize session state
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False

if 'form_data' not in st.session_state:
    st.session_state.form_data = {
        'wafr_lens': lens_list[0],
        'environment': 'PREPRODUCTION',
        'analysis_name': '',
        'created_by': get_current_user(),
        'selected_pillars': [],
        'workload_desc': '',
        'review_owner': '',
        'industry_type': 'Agriculture',
        'analysis_review_type': 'Quick'
    }
else:
    st.session_state.form_data['created_by'] = get_current_user()

if 'success_message' not in st.session_state:
    st.session_state.success_message = None

def upload_to_s3(file, bucket, key):
    try:
        s3_client.upload_fileobj(file, bucket, key)
        return True
    except Exception as e:
        st.error(f"Error uploading to S3: {str(e)}")
        return False

def trigger_wafr_review(input_data):
    try:
        sqs = boto3.client('sqs', region_name="{{REGION}}")
        queue_url = '{{SQS_QUEUE_NAME}}'
        message_body = json.dumps(input_data)
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        return response['MessageId']
    except Exception as e:
        st.error(f"Error sending message to SQS: {str(e)}")
        return None

def create_wafr_analysis(analysis_data, uploaded_file):
    analysis_id = str(uuid.uuid4())

    if uploaded_file:
        s3_key = f"{analysis_data['created_by']}/analyses/{analysis_id}/{uploaded_file.name}"
        if not upload_to_s3(uploaded_file, "{{WAFR_UPLOAD_BUCKET_NAME}}", s3_key):
            return False, "Failed to upload document to S3."
    else:
        return False, "No document uploaded. Please upload a document before creating the analysis."

    wafr_review_input = {
        'analysis_id': analysis_id,
        'analysis_name': analysis_data['analysis_name'],
        'wafr_lens': analysis_data['wafr_lens'],
        'analysis_submitter': analysis_data['created_by'],
        'selected_pillars': analysis_data['selected_pillars'],
        'document_s3_key': s3_key,
        'review_owner': analysis_data['review_owner'],
        'analysis_owner': analysis_data['created_by'],
        'lenses': lenses[analysis_data['wafr_lens']],
        'environment': analysis_data['environment'],
        'workload_desc': analysis_data['workload_desc'],
        'industry_type': analysis_data['industry_type'],
        'analysis_review_type': analysis_data['analysis_review_type']
    }

    message_id = trigger_wafr_review(wafr_review_input)
    if message_id:
        dynamodb = boto3.resource('dynamodb', region_name="{{REGION}}")
        wafr_accelerator_runs_table = dynamodb.Table('{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}')
        
        creation_date = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        
        wafr_accelerator_run_item = {
            'analysis_id': analysis_id,
            'analysis_submitter': analysis_data['created_by'],
            'analysis_title': analysis_data['analysis_name'],
            'selected_lens': analysis_data['wafr_lens'],
            'creation_date': creation_date,
            'review_status': "Submitted",
            'selected_wafr_pillars': analysis_data['selected_pillars'],
            'document_s3_key': s3_key,
            'analysis_owner': analysis_data['created_by'],
            'lenses': lenses[analysis_data['wafr_lens']],
            'environment': analysis_data['environment'],
            'workload_desc': analysis_data['workload_desc'],
            'review_owner': analysis_data['review_owner'],
            'industry_type': analysis_data['industry_type'],
            'analysis_review_type': analysis_data['analysis_review_type']
        }
        
        wafr_accelerator_runs_table.put_item(Item=wafr_accelerator_run_item)
    else:
        return False, "Failed to start the analysis process."

    return True, f"WAFR Analysis created successfully! Message ID: {message_id}"

# Main application layout
st.title("Create New WAFR Analysis")

# User info and logout in sidebar
with st.sidebar:
    if st.button('Logout'):
        st.session_state['authenticated'] = False
        st.session_state.pop('username', None)
        st.rerun()

# Success message
if st.session_state.success_message:
    st.success(st.session_state.success_message)
    if st.button("Clear Message"):
        st.session_state.success_message = None
        st.rerun()

# First row: Analysis Name and Workload Description
with st.expander("Workload Analysis", expanded=True):
    st.subheader("Workload Analysis")
    analysis_review_type = st.selectbox("Analysis Type", ["Quick", "Deep with Well-Architected Tool"], index=["Quick",  "Deep with Well-Architected Tool"].index(st.session_state.form_data['analysis_review_type']))
    analysis_name = st.text_input("Workload Name", value=st.session_state.form_data['analysis_name'], max_chars=100)
    workload_desc = st.text_area("Workload Description", value=st.session_state.form_data['workload_desc'], height=100, max_chars=250)
    if workload_desc:
        char_count = len(workload_desc)
        if char_count < 3:
            st.error("Workload Description must be at least 3 characters long")


# Second row: Environment, Review Owner, Created By, Industry Type, Lens
with st.expander("Additional Details", expanded=True):
    st.subheader("Industry & Lens Details")
    col1, col2 = st.columns(2)
    with col1:
        wafr_environment = st.selectbox("WAFR Environment", options=['PRODUCTION', 'PREPRODUCTION'], index=['PRODUCTION', 'PREPRODUCTION'].index(st.session_state.form_data['environment']))
        review_owner = st.text_input("Review Owner", value=st.session_state.form_data['review_owner'])
        st.text_input("Created By", value=st.session_state.form_data['created_by'], disabled=True)
    with col2:
        industry_type = st.selectbox("Industry Type", options=["Agriculture", "Automotive", "Defense", "Design_And_Engineering", "Digital_Advertising", "Education", "Environmental_Protection", "Financial_Services", "Gaming", "General_Public_Services", "Healthcare", "Hospitality", "InfoTech", "Justice_And_Public_Safety", "Life_Sciences", "Manufacturing", "Media_Entertainment", "Mining_Resources", "Oil_Gas", "Power_Utilities", "Professional_Services", "Real_Estate_Construction", "Retail_Wholesale", "Social_Protection", "Telecommunications", "Travel_Transportation_Logistics", "Other"])
        wafr_lens = st.selectbox("WAFR Lens", options=lens_list, index=lens_list.index(st.session_state.form_data['wafr_lens']))

# Third row: Select WAFR Pillars
with st.expander("Select Pillars", expanded=True):
    st.subheader("Well Architected Framework Pillars")
    pillars = ["Operational Excellence", "Security", "Reliability", "Performance Efficiency", "Cost Optimization", "Sustainability"]
    selected_pillars = st.multiselect("Select WAFR Pillars", options=pillars, default=st.session_state.form_data['selected_pillars'], key="pillar_select")

# Document Upload
with st.expander("Document Upload", expanded=True):
    st.subheader("Design Artifacts Upload")
    uploaded_file = st.file_uploader("Upload Document", type=["pdf"])

def duplicate_wa_tool_workload(workload_name):
    try:
        next_token = None
        
        search_name = workload_name.lower()
        
        while True:
            if next_token:
                response = well_architected_client.list_workloads(NextToken=next_token)
            else:
                response = well_architected_client.list_workloads()

            for workload in response['WorkloadSummaries']:
                if workload['WorkloadName'].lower() == search_name:
                    return True

            next_token = response.get('NextToken')
            if not next_token:
                break

        return False

    except ClientError as e:
        print(f"Error checking workload: {e}")
        return False
        
def duplicate_wafr_accelerator_workload(workload_name):
    try:
        dynamodb = boto3.resource('dynamodb', region_name="{{REGION}}")
        wafr_accelerator_runs_table = dynamodb.Table('{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}')
        
        filter_expression = Attr("analysis_title").eq(workload_name)
        
        response = wafr_accelerator_runs_table.scan(
            FilterExpression=filter_expression,
            ProjectionExpression="analysis_title, analysis_id, analysis_submitter"
        )
        return len(response.get('Items', [])) > 0
        
    except ClientError as e:
        print(f"ClientError when checking workload: {e}")
        return False  
    except Exception as e:
        print(f"Error checking workload: {e}")
        return False  
        
# Full-width button
if st.button("Create WAFR Analysis", type="primary", use_container_width=True):
    if not analysis_name:
        st.error("Please enter an Analysis Name.")
    elif ((not workload_desc) or (len (workload_desc)<3)):
        st.error("Workload Description needs to be at least 3 characters long.")
    elif ((not review_owner) or (len (review_owner)<3)):
        st.error("Review owner needs to be at least 3 characters long.")
    elif not selected_pillars:
        st.error("Please select at least one WAFR Pillar.")
    elif not uploaded_file:
        st.error("Please upload a document.")
    else:
        if (duplicate_wafr_accelerator_workload(analysis_name) ):
            st.error("Workload with the same name already exists!")
        elif ((analysis_review_type == 'Deep with Well-Architected Tool') and (duplicate_wa_tool_workload(analysis_name)) ):
            st.error("Workload with the same name already exists in AWS Well Architected Tool!")
        else:
            st.session_state.form_data.update({
                'wafr_lens': wafr_lens,
                'environment': wafr_environment,
                'analysis_name': analysis_name,
                'selected_pillars': selected_pillars,
                'workload_desc': workload_desc,
                'review_owner': review_owner,
                'industry_type': industry_type,
                'analysis_review_type': analysis_review_type
            })
            with st.spinner("Creating WAFR Analysis..."):
                success, message = create_wafr_analysis(st.session_state.form_data, uploaded_file)
            if success:
                st.session_state.success_message = message
                st.session_state.form_submitted = True
                st.rerun()
            else:
                st.error(message)

if st.session_state.form_submitted:
    st.session_state.form_data = {
        'wafr_lens': lens_list[0],
        'environment': 'PREPRODUCTION',
        'analysis_name': '',
        'created_by': get_current_user(),
        'selected_pillars': [],
        'workload_desc': '',
        'review_owner': '',
        'industry_type': 'Agriculture',
        'analysis_review_type': 'Quick'
    }
    st.session_state.form_submitted = False
    st.rerun()

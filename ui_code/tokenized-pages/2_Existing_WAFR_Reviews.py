import streamlit as st
import pandas as pd
import datetime
import boto3
import json
from boto3.dynamodb.types import TypeDeserializer
import pytz
import dotenv

# Check authentication
if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
    st.warning('You are not logged in. Please log in to access this page.')
    st.switch_page("pages/1_Login.py")
st.set_page_config(page_title="WAFR Analysis Grid", layout="wide")


# Logout function
def logout():
    st.session_state['authenticated'] = False
    st.session_state.pop('username', None)
    st.rerun()

# Add logout button in sidebar
if st.sidebar.button('Logout'):
    logout()    

dotenv.load_dotenv()

client = boto3.client("bedrock-runtime", region_name = "{{REGION}}")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0" 


def load_data():
    # Initialize DynamoDB client
    dynamodb = boto3.client('dynamodb', region_name='{{REGION}}') 
    
    try:
        # Scan the table
        response = dynamodb.scan(TableName='{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}')
        
        items = response['Items']
        
        # Continue scanning if we haven't scanned all items
        while 'LastEvaluatedKey' in response:
            response = dynamodb.scan(
                TableName='{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])
        
        # Check if items is empty
        if not items:
            st.warning("There are no existing WAFR review records")
            return pd.DataFrame(columns=['Analysis Id', 'Workload Name', 'Workload Description', 'Analysis Type', 'WAFR Lens', 'Creation Date', 'Status', 'Created By', 'Review Owner', 'Solution Summary', 'pillars', 'selected_wafr_pillars'])
        
        # Unmarshal the items
        deserializer = TypeDeserializer()
        unmarshalled_items = [{k: deserializer.deserialize(v) for k, v in item.items()} for item in items]
        
        # Convert to DataFrame
        df = pd.DataFrame(unmarshalled_items)
        
        # Define the mapping of expected column names
        column_mapping = {
            'analysis_id': 'Analysis Id',
            'analysis_title': 'Workload Name',
            'workload_desc': 'Workload Description',
            'analysis_review_type': 'Analysis Type',
            'selected_lens': 'WAFR Lens',
            'creation_date': 'Creation Date',
            'review_status': 'Status',
            'analysis_submitter': 'Created By',
            'review_owner' : 'Review Owner', 
            'extracted_document' : 'Document',
            'architecture_summary' : 'Solution Summary'
        }
        
        # Rename columns that exist in the DataFrame
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Add missing columns with empty values
        for col in column_mapping.values():
            if col not in df.columns:
                df[col] = ''
        
        # Parse Pillars
        def parse_pillars(pillars):
            if isinstance(pillars, list):
                return [
                    {
                        'pillar_id': item.get('pillar_id', ''),
                        'pillar_name': item.get('pillar_name', ''),
                        'llm_response': item.get('llm_response', '')
                        if isinstance(item.get('llm_response'), str)
                        else item.get('llm_response', {})
                    }
                    for item in pillars
                ]
            return []

        # Apply parse_pillars only if 'pillars' column exists
        if 'pillars' in df.columns:
            df['pillars'] = df['pillars'].apply(parse_pillars)
        else:
            df['pillars'] = [[] for _ in range(len(df))]
        
        # Ensure all required columns exist, add empty ones if missing
        required_columns = ['Analysis Id', 'Workload Name', 'Workload Description', 'Analysis Type', 'WAFR Lens', 'Creation Date', 'Status', 'Created By', 'Review Owner', 'Solution Summary', 'pillars', 'selected_wafr_pillars', 'Document']
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Select and return required columns
        return df[required_columns]
    
    except Exception as e:
        st.error(f"An error occurred while loading data: {str(e)}")
        return pd.DataFrame(columns=['Analysis Id', 'Workload Name', 'Workload Description', 'Analysis Type', 'WAFR Lens', 'Creation Date', 'Status', 'Created By', 'Review Owner', 'Solution Summary', 'pillars', 'selected_wafr_pillars', 'Document'])

# Function to display summary of a selected analysis
def display_summary(analysis):
    st.subheader("Summary")
    
    # Ensure selected_wafr_pillars is a string representation of the array
    if isinstance(analysis['selected_wafr_pillars'], list):
        selected_wafr_pillars = ', '.join(analysis['selected_wafr_pillars'])
    else:
        selected_wafr_pillars = str(analysis['selected_wafr_pillars'])
    
    summary_data = {
        "Field": ["Analysis Id", "Workload Name",  "Workload Description" ,"Analysis Type", "Status", "WAFR Lens", "Creation Date", "Created By", "Review Owner", "Selected WAFR Pillars"],
        "Value": [
            analysis['Analysis Id'],
            analysis['Workload Name'],
            analysis['Workload Description'],
            analysis['Analysis Type'],
            analysis['Status'],            
            analysis['WAFR Lens'],
            analysis['Creation Date'],
            analysis['Created By'],
            analysis['Review Owner'],            
            selected_wafr_pillars
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, hide_index=True, use_container_width=True)
    
# Function to display design review data
def display_design_review(analysis):
    st.subheader("Solution Summary")
    architecture_review = analysis['Solution Summary']
    if isinstance(architecture_review, str):
        st.write(architecture_review)
    else:
        st.write("No architecture review data available.")

# Function to display pillar data
def display_pillar(pillar):
    st.subheader(f"Review findings & recommendations for pillar: {pillar['pillar_name']}")
    llm_response = pillar.get('llm_response')
    if llm_response:
        st.write(llm_response)
    else:
        st.write("No LLM response data available.")

def parse_stream(stream):
    for event in stream:
        chunk = event.get('chunk')
        if chunk:
            message = json.loads(chunk.get("bytes").decode())
            if message['type'] == "content_block_delta":
                yield message['delta']['text'] or ""
            elif message['type'] == "message_stop":
                return "\n"
            
            
# Main Streamlit app
def main():
    st.title("WAFR Analysis")
    
    st.subheader("WAFR Analysis Runs", divider="rainbow")
    
    # Generate sample data
    data = load_data()

    # Display the data grid with selected columns
    selected_columns = ['Analysis Id', 'Workload Name', 'Analysis Type', 'WAFR Lens', 'Creation Date', 'Status', 'Created By']
    st.dataframe(data[selected_columns], use_container_width=True)
    
    st.subheader("Analysis Details", divider="rainbow")
    
    # Create a selectbox for choosing an analysis
    analysis_names = data['Workload Name'].tolist()
    selected_analysis = st.selectbox("Select an analysis to view details:", analysis_names)

    # Display details of the selected analysis
    if selected_analysis:
        selected_data = data[data['Workload Name'] == selected_analysis].iloc[0]
        
        wafr_container = st.container()
        
        with wafr_container:
            # Create tabs dynamically
            tab_names = ["Summary", "Solution Summary"] + [f"{pillar['pillar_name']}" for pillar in selected_data['pillars']]
            tabs = st.tabs(tab_names)
            
            # Populate tabs
            with tabs[0]:
                display_summary(selected_data)
                
            with tabs[1]:
                display_design_review(selected_data)
            
            # Display pillar tabs
            for i, pillar in enumerate(selected_data['pillars'], start=2):
                with tabs[i]:
                    display_pillar(pillar)
        
        st.subheader("", divider="rainbow")
        
        # Create chat container here
        chat_container = st.container()
        
        with chat_container:
            st.subheader("WAFR Chat")

            # Create a list of options including Summary, Solution Summary, and individual pillars
            chat_options = ["Summary", "Solution Summary", "Document"] + [pillar['pillar_name'] for pillar in selected_data['pillars']]
            
            # Let the user select an area to discuss
            selected_area = st.selectbox("Select an area to discuss:", chat_options)

            prompt = st.text_input("Ask a question about the selected area:")
            
        if prompt:
            # Prepare the context based on the selected area
            if selected_area == "Summary":
                area_context = "WAFR Analysis Summary:\n"
                area_context += f"Workload Name: {selected_data['Workload Name']}\n"
                area_context += f"Workload Description: {selected_data['Workload Description']}\n"
                area_context += f"WAFR Lens: {selected_data['WAFR Lens']}\n"
                area_context += f"Status: {selected_data['Status']}\n"
                area_context += f"Created By: {selected_data['Created By']}\n"
                area_context += f"Creation Date: {selected_data['Creation Date']}\n"
                area_context += f"Selected WAFR Pillars: {', '.join(selected_data['selected_wafr_pillars'])}\n"
                area_context += f"Architecture Review: {selected_data['Solution Summary']}\n"
                area_context += f"Review Owner: {selected_data['Review Owner']}\n"
            elif selected_area == "Solution Summary":
                area_context = "WAFR Solution Summary:\n"
                area_context += f"Architecture Review: {selected_data['Solution Summary']}\n"
            elif selected_area == "Document":
                area_context = "Document:\n"
                area_context += f"{selected_data['Document']}\n"
            else:
                pillar_data = next((pillar for pillar in selected_data['pillars'] if pillar['pillar_name'] == selected_area), None)
                if pillar_data:
                    area_context = f"WAFR Analysis Context for {selected_area}:\n"
                    area_context += pillar_data['llm_response']
                else:
                    area_context = "Error: Selected area not found in the analysis data."

            # Combine the user's prompt with the context
            full_prompt = f"{area_context}\n\nUser Question: {prompt}\n\nPlease answer the question based on the WAFR analysis context provided above for the {selected_area}."

            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": full_prompt}],
                    }
                ],
            })

            if("{{GUARDRAIL_ID}}" == "Not Selected"):
                streaming_response = client.invoke_model_with_response_stream(
                    modelId=model_id,
                    body=body
                )
            else: # Use guardrails
                streaming_response = client.invoke_model_with_response_stream(
                    modelId=model_id,
                    body=body,
                    guardrailIdentifier="{{GUARDRAIL_ID}}",
                    guardrailVersion="DRAFT",
                )
                
            st.subheader("Response")
            stream = streaming_response.get("body")
            st.write_stream(parse_stream(stream))
        
if __name__ == "__main__":
    main()

import os
import boto3
import json
import datetime
import time
import logging  

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

from botocore.client import Config
from botocore.exceptions import ClientError

s3 = boto3.resource('s3')

WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME = os.environ['WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME']
UPLOAD_BUCKET_NAME = os.environ['UPLOAD_BUCKET_NAME']
REGION = os.environ['REGION']
WAFR_PROMPT_DD_TABLE_NAME = os.environ['WAFR_PROMPT_DD_TABLE_NAME']
KNOWLEDGE_BASE_ID=os.environ['KNOWLEDGE_BASE_ID']
LLM_MODEL_ID=os.environ['LLM_MODEL_ID'] 
START_WAFR_REVIEW_STATEMACHINE_ARN = os.environ['START_WAFR_REVIEW_STATEMACHINE_ARN']
BEDROCK_SLEEP_DURATION = int(os.environ['BEDROCK_SLEEP_DURATION'])
BEDROCK_MAX_TRIES = int(os.environ['BEDROCK_MAX_TRIES'])
WAFR_REFERENCE_DOCS_BUCKET = os.environ['WAFR_REFERENCE_DOCS_BUCKET']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID']

dynamodb = boto3.resource('dynamodb')
bedrock_config = Config(connect_timeout=120, region_name=REGION, read_timeout=120, retries={'max_attempts': 0})
bedrock_client = boto3.client('bedrock-runtime',region_name=REGION)
bedrock_agent_client = boto3.client("bedrock-agent-runtime", config=bedrock_config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info (f"start_wafr_review invoked at  {entry_timestamp}" )
    logger.info(json.dumps(event))
    
    logger.info(f"REGION: {REGION}")
    logger.debug(f"START_WAFR_REVIEW_STATEMACHINE_ARN: {START_WAFR_REVIEW_STATEMACHINE_ARN}")
    logger.debug(f"WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME: {WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}" )
    
    data = json.loads(event['Records'][0]['body'])
    
    return_status = ""
    analysis_review_type = data['analysis_review_type']
    
    try:
        if (analysis_review_type != 'Quick' ): #"Deep with Well-Architected Tool"
            logger.info("Initiating \'Deep with Well-Architected Tool\' analysis")
            sf = boto3.client('stepfunctions', region_name = REGION)
            response = sf.start_execution(stateMachineArn = START_WAFR_REVIEW_STATEMACHINE_ARN, input = json.dumps(event['Records']))
            logger.info (f"Step function response: {response}")
            return_status = 'Deep analysis commenced successfully!'
        else: #Quick
            logger.info("Executing \'Quick\' analysis")
            do_quick_analysis (data, context)
            return_status = 'Quick analysis completed successfully!'
    except Exception as error:
        handle_error (data, error)
        raise Exception (f'Exception caught in start_wafr_review: {error}')
                
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info(f"Exiting start_wafr_review at {exit_timeestamp}" )
    
    return {
        'statusCode': 200,
        'body': json.dumps(return_status)
    }        

def handle_error (data, error):
    
    dynamodb = boto3.resource('dynamodb')
    wafr_accelerator_runs_table = dynamodb.Table(WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME)
    
    # Define the key for the item you want to update
    wafr_accelerator_run_key = {
        'analysis_id':  data['analysis_id'],  # Replace with your partition key name and value
        'analysis_submitter':  data['analysis_submitter']  # If you have a sort key, replace with its name and value
    }
    
    # Handle errors and update DynamoDB status
    wafr_accelerator_runs_table.update_item(
        Key=wafr_accelerator_run_key,
        UpdateExpression="SET review_status = :val",
        ExpressionAttributeValues={':val': "Errored"},
        ReturnValues='UPDATED_NEW'
    )
    logger.error(f"Exception caught in start_wafr_review: {error}")
    
def get_pillar_string (pillars):
    pillar_string =""

    for item in pillars:
        logger.info (f"selected_pillars: {item}")
        pillar_string = pillar_string + item + ","
        logger.info ("pillar_string: " + pillar_string)
        
    pillar_string = pillar_string.rstrip(',')    
    
    return pillar_string

def do_quick_analysis (data, context):

    logger.info(f"WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME: {WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}")
    logger.info(f"UPLOAD_BUCKET_NAME: {UPLOAD_BUCKET_NAME}")
    logger.info(f"WAFR_PROMPT_DD_TABLE_NAME: {WAFR_PROMPT_DD_TABLE_NAME}")
    logger.info(f"KNOWLEDGE_BASE_ID: {KNOWLEDGE_BASE_ID}")
    logger.info(f"LLM_MODEL_ID: {LLM_MODEL_ID}")
    logger.info(f"BEDROCK_SLEEP_DURATION: {BEDROCK_SLEEP_DURATION}")
    logger.info(f"BEDROCK_MAX_TRIES: {BEDROCK_MAX_TRIES}")
    if(GUARDRAIL_ID):
        logger.info(f"GUARDRAIL_ID: {GUARDRAIL_ID}" )
    else:
        logger.info(f"GUARDRAIL_ID nNot specified" )
    
    wafr_accelerator_runs_table = dynamodb.Table(WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME)
    wafr_prompts_table = dynamodb.Table(WAFR_PROMPT_DD_TABLE_NAME)

    logger.info(json.dumps(data))

    analysis_id = data['analysis_id'] 
    name = data['analysis_name']
    wafr_lens = data['wafr_lens']
    
    analysis_submitter = data['analysis_submitter']
    document_s3_key = data['document_s3_key']

    pillars = data['selected_pillars']    
    pillar_string = get_pillar_string (pillars)
    logger.info ("Final pillar_string: " + pillar_string)

    logger.debug ("do_quick_analysis checkpoint 1")
    
    wafr_accelerator_run_key = {
        'analysis_id':  analysis_id,  
        'analysis_submitter': analysis_submitter  
    }
        
    response = wafr_accelerator_runs_table.update_item(
        Key=wafr_accelerator_run_key,
        UpdateExpression="SET review_status = :val",
        ExpressionAttributeValues={':val': "In Progress"},
        ReturnValues='UPDATED_NEW'  
    )
    
    logger.info (f"wafr-accelerator-runs dynamodb table summary update response: {response}" )
    logger.debug ("do_quick_analysis checkpoint 2")
    
    try:
        
        # Get the bucket object
        output_bucket = s3.Bucket(UPLOAD_BUCKET_NAME)
        
        # Extract document text and write to s3 
        extracted_document_text = extract_document_text(UPLOAD_BUCKET_NAME, document_s3_key, output_bucket, wafr_accelerator_runs_table, wafr_accelerator_run_key, REGION)
        
        logger.debug ("do_quick_analysis checkpoint 3")

        # Generate solution summary
        summary = generate_solution_summary (extracted_document_text, wafr_accelerator_runs_table, wafr_accelerator_run_key)

        logger.info ("Generated architecture summary:" + summary)
        
        logger.debug ("do_quick_analysis checkpoint 4")
        
        partition_key_value = wafr_lens
    
        sort_key_values = pillars
    
        logger.info ("wafr_lens: " + wafr_lens)
        
        pillar_responses = []
        pillar_counter = 0
        
        #Get All the pillar prompts in a loop
        for item in pillars:
            logger.info (f"selected_pillars: {item}") 
            response = wafr_prompts_table.query(
                ProjectionExpression ='wafr_pillar_id, wafr_pillar_prompt',
                KeyConditionExpression=Key('wafr_lens').eq(wafr_lens) & Key('wafr_pillar').eq(item),
                ScanIndexForward=True  
            )
           
            logger.info (f"response wafr_pillar_id: "  + str(response['Items'][0]['wafr_pillar_id']))
            logger.info (f"response wafr_pillar_prompt: " + response['Items'][0]['wafr_pillar_prompt'])
            
            logger.debug ("document_s3_key.rstrip('.'): " + document_s3_key.rstrip('.'))
            logger.debug ("document_s3_key[:document_s3_key.rfind('.')]: " + document_s3_key[:document_s3_key.rfind('.')] )
            pillar_review_prompt_filename = document_s3_key[:document_s3_key.rfind('.')]+ "-" + wafr_lens + "-" + item + "-prompt.txt"
            pillar_review_output_filename = document_s3_key[:document_s3_key.rfind('.')]+ "-" + wafr_lens + "-" + item + "-output.txt"
            
            logger.info (f"pillar_review_prompt_filename: {pillar_review_prompt_filename}")
            logger.info (f"pillar_review_output_filename: {pillar_review_output_filename}")
            
            pillar_specific_prompt_question = response['Items'][0]['wafr_pillar_prompt']
            
            claude_prompt_body = bedrock_prompt(wafr_lens, item, pillar_specific_prompt_question, KNOWLEDGE_BASE_ID, extracted_document_text, WAFR_REFERENCE_DOCS_BUCKET)
            output_bucket.put_object(Key=pillar_review_prompt_filename, Body=claude_prompt_body)
            
            logger.debug (f"do_quick_analysis checkpoint 5.{pillar_counter}")
            
            streaming = True
            
            pillar_review_output = invoke_bedrock(streaming, claude_prompt_body, pillar_review_output_filename, output_bucket)

            # Comment the next line if you would like to retain the prompts files
            output_bucket.Object(pillar_review_prompt_filename).delete()

            logger.debug (f"do_quick_analysis checkpoint 6.{pillar_counter}")
            
            logger.info ("pillar_id: " + str(response['Items'][0]['wafr_pillar_id']))#
            
            pillarResponse = {
                'pillar_name': item,
                'pillar_id': str(response['Items'][0]['wafr_pillar_id']),
                'llm_response': pillar_review_output
            }
        
            pillar_responses.append(pillarResponse)
            
            pillar_counter += 1
        
        logger.debug (f"do_quick_analysis checkpoint 7")
        
        attribute_updates = {
            'pillars': {
                'Action': 'ADD'  
            }
        }
        
        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET pillars = :val",
            ExpressionAttributeValues={':val': pillar_responses},
            ReturnValues='UPDATED_NEW'  
        )
        
        logger.info (f"dynamodb status update response: {response}" )
        logger.debug (f"do_quick_analysis checkpoint 8")

        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET review_status = :val",
            ExpressionAttributeValues={':val': "Completed"},
            ReturnValues='UPDATED_NEW'  
        )
        
        logger.info (f"dynamodb status update response: {response}" )
    except Exception as error:
        handle_error (data, error)
        raise Exception (f'Exception caught in do_quick_analysis: {error}')
        
    logger.debug (f"do_quick_analysis checkpoint 9")
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info("Exiting do_quick_analysis at " + exit_timeestamp)
    
def extract_document_text(upload_bucket_name, document_s3_key, output_bucket, wafr_accelerator_runs_table, wafr_accelerator_run_key, region):

    textract_config = Config(retries = dict(max_attempts = 5))
    textract_client = boto3.client('textract', region_name=region, config=textract_config)

    logger.debug ("extract_document_text checkpoint 1")

    response = textract_client.start_document_text_detection(
        DocumentLocation={
            'S3Object': {
                'Bucket': upload_bucket_name,
                'Name': document_s3_key
            }
        }
    )
    
    job_id = response["JobId"]

    logger.debug ("extract_document_text checkpoint 2")
    
    # Wait for the job to complete
    while True:
        response = textract_client.get_document_text_detection(JobId=job_id)
        status = response["JobStatus"]
        if status == "SUCCEEDED":
            break
    
    logger.debug ("extract_document_text checkpoint 3")
    
    pages = []
    next_token = None
    while True:
        if next_token:
            response = textract_client.get_document_text_detection(JobId=job_id, NextToken=next_token)
        else:
            response = textract_client.get_document_text_detection(JobId=job_id)
        pages.append(response)
        if 'NextToken' in response:
            next_token = response['NextToken']
        else:
            break
    
    logger.debug ("extract_document_text checkpoint 4")
    
    # Extract the text from all pages
    extracted_text = ""
    for page in pages:
        for item in page["Blocks"]:
            if item["BlockType"] == "LINE":
                extracted_text += item["Text"] + "\n"
    
    attribute_updates = {
        'extracted_document': {
            'Action': 'ADD'  
        }
    }
    
    # Update the item
    response = wafr_accelerator_runs_table.update_item(
        Key=wafr_accelerator_run_key,
        UpdateExpression="SET extracted_document = :val",
        ExpressionAttributeValues={':val': extracted_text}, 
        ReturnValues='UPDATED_NEW' 
    )
    
    logger.debug ("document_s3_key.rstrip('.'): " + document_s3_key.rstrip('.'))
    logger.debug ("document_s3_key[:document_s3_key.rfind('.')]: " + document_s3_key[:document_s3_key.rfind('.')] )
    output_filename = document_s3_key[:document_s3_key.rfind('.')]+ "-extracted-text.txt"
    
    logger.info (f"Extracted document text ouput filename: {output_filename}")
    output_bucket.put_object(Key=output_filename, Body=bytes(extracted_text, encoding='utf-8'))
        
    return extracted_text
    
def generate_solution_summary (extracted_document_text, wafr_accelerator_runs_table, wafr_accelerator_run_key):

    prompt = f"The following document is a solution architecture document that you are reviewing as an AWS Cloud Solutions Architect. Please summarise the following solution in 250 words. Begin directly with the architecture summary, don't provide any other opening or closing statements.\n<Architecture>\n{extracted_document_text}\n</Architecture>\n" #\nSummary:"
    
    response = bedrock_client.invoke_model(
        modelId= LLM_MODEL_ID, 
        contentType="application/json",
        accept="application/json",
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200000,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
            }   
        )
    )
    
    logger.info(f"generate_solution_summary: response: {response}")
    
    # Extract the summary
    response_body = json.loads(response['body'].read())
    summary = response_body['content'][0]['text']
    
    logger.debug (f"start_wafr_review checkpoint 9")
    
    attribute_updates = {
        'architecture_summary': {
            'Action': 'ADD'  
        }
    }

    logger.debug (f"start_wafr_review checkpoint 10")
    
    response = wafr_accelerator_runs_table.update_item(
        Key=wafr_accelerator_run_key,
        UpdateExpression="SET architecture_summary = :val",
        ExpressionAttributeValues={':val': summary}, 
        ReturnValues='UPDATED_NEW'  
    )
    
    return summary
        
def invoke_bedrock(streaming, claude_prompt_body, pillar_review_output_filename, output_bucket):
    
    pillar_review_output = ""
    retries = 1
    max_retries = BEDROCK_MAX_TRIES
    
    while retries <= max_retries:
        try:
            if(streaming):
                if(GUARDRAIL_ID == "Not Selected"):
                    streaming_response = bedrock_client.invoke_model_with_response_stream(
                        modelId=LLM_MODEL_ID,
                        body=claude_prompt_body
                    )
                else: # Use guardrails
                    streaming_response = bedrock_client.invoke_model_with_response_stream(
                        modelId=LLM_MODEL_ID,
                        body=claude_prompt_body,
                        guardrailIdentifier= GUARDRAIL_ID,
                        guardrailVersion="DRAFT"
                    )
                
                logger.debug (f"invoke_bedrock checkpoint 1.{retries}")
                stream = streaming_response.get("body")
                
                logger.debug (f"invoke_bedrock checkpoint 2.{retries}")
        
                for chunk in parse_stream(stream):
                    pillar_review_output += chunk
                    
                # Uncomment next line if you would like to see response files for each question too. 
                # output_bucket.put_object(Key=pillar_review_output_filename, Body=bytes(pillar_review_output, encoding='utf-8'))
                
                return pillar_review_output
                
            else:
                non_streaming_response = bedrock_client.invoke_model(
                    modelId=LLM_MODEL_ID,
                    body=claude_prompt_body
                )
                if(GUARDRAIL_ID == "Not Selected"):
                    non_streaming_response = bedrock_client.invoke_model(
                        modelId=LLM_MODEL_ID,
                        body=claude_prompt_body
                    )
                else: # Use guardrails
                    non_streaming_response = bedrock_client.invoke_model(
                        modelId=LLM_MODEL_ID,
                        body=claude_prompt_body,
                        guardrailIdentifier=GUARDRAIL_ID,
                        guardrailVersion="DRAFT"
                    )

                response_json = json.loads(non_streaming_response["body"].read().decode("utf-8"))
        
                logger.info (response_json)
                
                logger.debug (f"invoke_bedrock checkpoint 1.{retries}")
        
                # Extract the response text.
                pillar_review_output = response_json["content"][0]["text"]
        
                logger.debug (pillar_review_output)
                logger.debug (f"invoke_bedrock checkpoint 2.{retries}")
                
                # Uncomment next line if you would like to see response files for each question too. 
                # output_bucket.put_object(Key=pillar_review_output_filename, Body=pillar_review_output)
                
                return pillar_review_output
                
        except Exception as e:
            retries += 1
            logger.info(f"Sleeping as attempt {retries} failed with exception: {e}")
            time.sleep(BEDROCK_SLEEP_DURATION)  # Add a delay before the next retry

    logger.info(f"Maximum retries ({max_retries}) exceeded. Unable to invoke the model.")
    raise Exception (f"Maximum retries ({max_retries}) exceeded. Unable to invoke the model.")

def get_lens_filter(kb_bucket, wafr_lens):

    # Map lens prefixes to their corresponding lens names - allows for additional of lenses
    lens_mapping = {
        "Financial Services Industry Lens": "financialservices",
        "Data Analytics Lens": "dataanalytics",
        "Generative AI Lens": "genai"
    }
    
    # Get lens name or default to "wellarchitected"
    lens = next(
        (value for prefix, value in lens_mapping.items() 
         if wafr_lens.startswith(prefix)), 
        "wellarchitected"
    )
    
    # If wellarchitected lens then also use the overview documentation
    if lens == "wellarchitected":
        lens_filter = {
            "orAll": [
                {
                    "startsWith": {
                        "key": "x-amz-bedrock-kb-source-uri",
                        "value": f"s3://{kb_bucket}/{lens}"
                    }
                },
                {
                    "startsWith": {
                        "key": "x-amz-bedrock-kb-source-uri",
                        "value": f"s3://{kb_bucket}/overview"
                    }
                }
            ]
        }
    else: # Just use the lens documentation 
        lens_filter = {
            "startsWith": {
                "key": "x-amz-bedrock-kb-source-uri",
                "value": f"s3://{kb_bucket}/{lens}/"
            }
        }    
        
    logger.info(f"get_lens_filter: {json.dumps(lens_filter)}")
    return lens_filter
    
def bedrock_prompt(wafr_lens, pillar, questions, kb_id, document_content=None, wafr_reference_bucket = None):    
    
    lens_filter = get_lens_filter(wafr_reference_bucket, wafr_lens)
    response = retrieve(questions, kb_id, lens_filter)
    
    retrievalResults = response['retrievalResults']
    contexts = get_contexts(retrievalResults)
   
    system_prompt = f"""<description>You are an AWS Cloud Solutions Architect who specializes in reviewing solution architecture documents against the AWS Well-Architected Framework, using a process called the Well-Architected Framework Review (WAFR).
    The WAFR process consists of evaluating the provided solution architecture document against the 6 pillars of the specified AWS Well-Architected Framework lens, namely:
        Operational Excellence Pillar
        Security Pillar
        Reliability Pillar
        Performance Efficiency Pillar
        Cost Optimization Pillar
        Sustainability Pillar
    
    A solution architecture document is provided below in the "uploaded_document" section that you will evaluate by answering the questions provided in the "pillar_questions" section in accordance with the WAFR pillar indicated by the "<current_pillar>" section and the specified WAFR lens indicated by the "<current_lens>" section. Answer each and every question without skipping any question, as it would make the entire response invalid. Follow the instructions listed under the "instructions" section below. 
    <description>
    <instructions>
    1) For each question, be concise and limit responses to 350 words maximum. Responses should be specific to the specified lens (listed in the "<current_lens>" section) and pillar only (listed in the "<current_pillar>" section). Your response to each question should have five parts: 'Assessment', 'Best practices followed', 'Recommendations/Examples', 'Risks' and 'Citations'.
    2) You are also provided with a Knowledge Base which has more information about the specific lens and pillar from the Well-Architected Framework. The relevant parts from the Knowledge Base will be provided under the "kb" section. 
    3) For each question, start your response with the 'Assessment' section, in which you will give a short summary (three to four lines) of your answer.
    4) For each question, 
        a) Provide which Best practices from the specified pillar have been followed, including the best practice titles and IDs from the respective pillar guidance for the question. List them under the 'Best practices followed' section. 
            Example: REL01-BP03: Accommodate fixed service quotas and constraints through architecture 
            Example: BP 15.5: Optimize your data modeling and data storage for efficient data retrieval
        b) provide your recommendations on how the solution architecture should be updated to address the question's ask. If you have a relevant example, mention it clearly like so: "Example: ". List all of this under the 'Recommendations/Examples' section.
        c) Highlight the risks identified based on not following the best practises relevant to the specific WAFR question. Categorize the overall Risk for this question by selecting one of the three: High, Medium, or Low. List them under the 'Risks' section and mention your categorization.
        d) Add Citations section listing best practice ID and heading for best practices, recommendations, and risks from the specified lens ("<current_lens>") and specified pillar ("<current_pillar>") under the <kb> section. If there are no citations then return 'N/A' for Citations. 
            Example: REL01-BP03: Accommodate fixed service quotas and constraints through architecture 
            Example: BP 15.5: Optimize your data modeling and data storage for efficient data retrieval
    5) For each question, if the required information is missing or is inadequate to answer the question, then first state that the document doesn't provide any or enough information. Then, list the recommendations relevant to the question to address the gap in the solution architecture document under the 'Recommendations' section. In this case, the 'Best practices followed' section will simply state "not enough information". 
    6) Use Markdown formatting for your response. First list, the question in bold. Then the response, and section headings for each of the four sections in your response should also be in bold. Add a Markdown new line at the end of the response.
    7) Do not make any assumptions or make up information including best practice titles and ID. Your responses should only be based on the actual solution document provided in the "uploaded_document" section below.
    8> Each line represents a question, for example 'Question 1 -' followed by the actual question text. Do recheck that all the questions have been answered before sending back the response. 
    </instructions>
    """

    #Add Soln Arch Doc to the system_prompt
    if document_content:
        system_prompt += f"""
        <uploaded_document>
        {document_content}
        </uploaded_document>
    """
    
    prompt = f"""
    <current_lens>
    {wafr_lens}
    </current_lens>

    <current_pillar>
    {pillar}
    </current_pillar>
    
    <kb>
    {contexts}
    </kb>
    
    <pillar_questions>
    {questions}
    </pillar_questions>
    """

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200000,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
    })
    return body
    
def retrieve(questions, kbId, lens_filter):
    kb_prompt = f"""For each question provide:
    - Recommendations
    - Best practices
    - Examples
    - Risks
    {questions}"""
    
    return bedrock_agent_client.retrieve(
        retrievalQuery= {
            'text': kb_prompt
        },
        knowledgeBaseId=kbId,
        retrievalConfiguration={
            'vectorSearchConfiguration':{
                'numberOfResults': 20,
                "filter": lens_filter
            }
        }
    )

def get_contexts(retrievalResults):
    contexts = []
    for retrievedResult in retrievalResults: 
        contexts.append(retrievedResult['content']['text'])
    return contexts

def parse_stream(stream):
    for event in stream:
        chunk = event.get('chunk')
        if chunk:
            message = json.loads(chunk.get("bytes").decode())
            if message['type'] == "content_block_delta":
                yield message['delta']['text'] or ""
            elif message['type'] == "message_stop":
                return "\n"

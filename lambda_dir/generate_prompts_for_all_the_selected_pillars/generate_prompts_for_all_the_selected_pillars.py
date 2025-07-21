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
s3client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

WAFR_REFERENCE_DOCS_BUCKET = os.environ['WAFR_REFERENCE_DOCS_BUCKET']

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info(f"generate_prompts_for_all_the_selected_pillars invoked at {entry_timestamp}")
    
    logger.info(json.dumps(event))

    data = event
    wafr_accelerator_runs_table = dynamodb.Table(data['wafr_accelerator_runs_table'])
    wafr_prompts_table = dynamodb.Table(data['wafr_prompts_table'])
    wafr_accelerator_run_key = data['wafr_accelerator_run_key']
    
    try:
    
        document_s3_key = data['wafr_accelerator_run_items']['document_s3_key']
        extract_output_bucket = data['extract_output_bucket']
        region = data['region']
        wafr_lens = data['wafr_accelerator_run_items']['selected_lens']
        knowledge_base_id = data ['knowledge_base_id'] 
        pillars = data['wafr_accelerator_run_items'] ['selected_wafr_pillars']
        wafr_workload_id = data['wafr_accelerator_run_items'] ['wafr_workload_id']
        lens_alias = data['wafr_accelerator_run_items'] ['lens_alias']
        
        waclient = boto3.client('wellarchitected', region_name=region)
        
        bedrock_config = Config(connect_timeout=120, region_name=region, read_timeout=120, retries={'max_attempts': 0})
        bedrock_client = boto3.client('bedrock-runtime',region_name=region)
        bedrock_agent_client = boto3.client("bedrock-agent-runtime", config=bedrock_config)
    
        return_response = {}

        prompt_file_locations = []
        all_pillar_prompts = [] 
    
        pillar_name_alias_mappings = get_pillar_name_alias_mappings ()
        logger.info(pillar_name_alias_mappings)
    
        pillars_dictionary = get_pillars_dictionary (waclient, wafr_workload_id, lens_alias)

        extracted_document_text = read_s3_file (data['extract_output_bucket'], data['extract_text_file_name'])
    
        pillar_counter = 0 

        #Get all the pillar prompts in a loop
        for item in pillars:
            
            prompt_file_locations = []
            logger.info (f"selected_pillar: {item}") 
            response = ""
            logger.debug ("document_s3_key.rstrip('.'): " + document_s3_key.rstrip('.'))
            logger.debug ("document_s3_key[:document_s3_key.rfind('.')]: " + document_s3_key[:document_s3_key.rfind('.')] )

            questions = {}
            
            logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 1")
            
            # Loop through key-value pairs
            question_array_counter = 0 
            current_wafr_pillar = item

            logger.info (f"generate_prompts_for_all_the_selected_pillars checkpoint 1.{pillar_counter}")
            
            questions = pillars_dictionary[current_wafr_pillar]["wafr_q"]
            
            logger.debug (json.dumps(questions))
            
            logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 2.{pillar_counter}")
            
            for question in questions: 
                
                logger.info (json.dumps(question))
                
                logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 3.{pillar_counter}.{question_array_counter}")
                
                pillar_specfic_question_id = question["id"]
                pillar_specfic_prompt_question = question["text"]
                pillar_specfic_wafr_answer_choices = question["wafr_answer_choices"]
                
                logger.info (f"pillar_specfic_question_id: {pillar_specfic_question_id}")
                logger.info (f"pillar_specfic_prompt_question: {pillar_specfic_prompt_question}")
                logger.info (f"pillar_specfic_wafr_answer_choices: {json.dumps(pillar_specfic_wafr_answer_choices)}")

                logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 4.{pillar_counter}.{question_array_counter}")
                claude_prompt_body = bedrock_prompt(wafr_lens, current_wafr_pillar, pillar_specfic_question_id, pillar_specfic_wafr_answer_choices, pillar_specfic_prompt_question, knowledge_base_id, bedrock_agent_client, extracted_document_text, WAFR_REFERENCE_DOCS_BUCKET)
                
                logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 5.{pillar_counter}.{question_array_counter}")

                # Write the textract output to a txt file 
                output_bucket = s3.Bucket(extract_output_bucket)
                logger.debug ("document_s3_key.rstrip('.'): " + document_s3_key.rstrip('.'))
                logger.debug ("document_s3_key[:document_s3_key.rfind('.')]: " + document_s3_key[:document_s3_key.rfind('.')] )
                pillar_review_prompt_filename = document_s3_key[:document_s3_key.rfind('.')]+ "-" + pillar_name_alias_mappings[item] + "-" + pillar_specfic_question_id + "-prompt.txt"
                logger.info (f"Output prompt file name: {pillar_review_prompt_filename}")
                
                # Upload the file to S3
                output_bucket.put_object(Key=pillar_review_prompt_filename, Body=claude_prompt_body)
                
                logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 6.{pillar_counter}.{question_array_counter}")
                question_metadata = {}
                
                question_metadata["pillar_review_prompt_filename"] = pillar_review_prompt_filename  ##########
                question_metadata["pillar_specfic_question_id"] = pillar_specfic_question_id
                question_metadata["pillar_specfic_prompt_question"] = pillar_specfic_prompt_question
                question_metadata["pillar_specfic_wafr_answer_choices"] = pillar_specfic_wafr_answer_choices
                
                logger.info (f"generate_prompts_for_all_the_selected_pillars checkpoint 7.{pillar_counter}.{question_array_counter}")
                prompt_file_locations.append(question_metadata)
                
                question_array_counter = question_array_counter + 1

            pillar_prompts = {}
            
            pillar_prompts['wafr_accelerator_run_items'] = data ['wafr_accelerator_run_items']
            pillar_prompts['wafr_accelerator_run_key'] = data['wafr_accelerator_run_key']
            pillar_prompts['extract_output_bucket'] = data['extract_output_bucket'] 
            pillar_prompts['wafr_accelerator_runs_table'] = data ['wafr_accelerator_runs_table'] 
            pillar_prompts['wafr_prompts_table'] = data ['wafr_prompts_table'] 
            pillar_prompts['llm_model_id'] =  data ['llm_model_id']                
            pillar_prompts['region'] = data['region']
            pillar_prompts['input_pillar'] = item
            pillar_prompts['guardrail_id'] =  data ['guardrail_id']                

            return_response['wafr_accelerator_run_items'] = data ['wafr_accelerator_run_items']
    
            pillar_prompts[item] = prompt_file_locations

            logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 9.{pillar_counter}")
            
            all_pillar_prompts.append(pillar_prompts)
            
            pillar_counter =  pillar_counter + 1
            
        logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 10")

    except Exception as error:
        all_pillar_prompts = []
        wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET review_status = :val",
            ExpressionAttributeValues={':val': "Errored"},
            ReturnValues='UPDATED_NEW'
        )
        logger.error(f"Exception caught in generate_solution_summary: {error}")
        raise Exception (f'Exception caught in generate_prompts_for_all_the_selected_pillars: {error}')
        
    logger.debug (f"generate_prompts_for_all_the_selected_pillars checkpoint 11")
    
    return_response = {}

    return_response = data
    return_response['all_pillar_prompts'] =  all_pillar_prompts

    logger.info(f"return_response: {return_response}")
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info(f"Exiting generate_prompts_for_all_the_selected_pillars at {exit_timeestamp}")
        
    # Return a success response
    return {
        'statusCode': 200,
        'body': return_response
    }

def get_pillar_name_alias_mappings():

    mappings = {}
    
    mappings["Cost Optimization"] = "costOptimization"
    mappings["Operational Excellence"] = "operationalExcellence"
    mappings["Performance Efficiency"] = "performance"
    mappings["Reliability"] = "reliability"
    mappings["Security"] = "security"
    mappings["Sustainability"] = "sustainability"
    
    return mappings

def get_pillars_dictionary(waclient, wafr_workload_id, lens_alias):

    pillars_dictionary = {}
    
    lens_review = get_lens_review (waclient, wafr_workload_id, lens_alias)

    for item in lens_review['data']:
        pillars_dictionary[item["wafr_pillar"]] = item 
    
    return pillars_dictionary
    
def get_lens_review(client, workload_id, lens_alias):
    try:
        response = client.get_lens_review(
            WorkloadId=workload_id,
            LensAlias=lens_alias
        )
      
        lens_review = response['LensReview']
        formatted_data = {
            "workload_id": workload_id,
            "data": []
        }
      
        for pillar in lens_review['PillarReviewSummaries']:
            pillar_data = {
                "wafr_lens": lens_alias,
                "wafr_pillar": pillar['PillarName'],
                "wafr_pillar_id": pillar['PillarId'],
                "wafr_q": []
            }
      
            # Manual pagination for list_answers
            next_token = None
       
            while True:
                if next_token:
                    answers_response = client.list_answers(
                        WorkloadId=workload_id,
                        LensAlias=lens_alias,
                        PillarId=pillar['PillarId'],
                        MaxResults=50,
                        NextToken=next_token
                    )
                else:
                    answers_response = client.list_answers(
                        WorkloadId=workload_id,
                        LensAlias=lens_alias,
                        PillarId=pillar['PillarId'],
                        MaxResults=50
                    )
          
                for question in answers_response.get('AnswerSummaries', []):
                    question_details = client.get_answer(
                        WorkloadId=workload_id,
                        LensAlias=lens_alias,
                        QuestionId=question['QuestionId']
                    )
                    formatted_question = {
                        "id": question['QuestionId'],
                        "text": question['QuestionTitle'],
                        "wafr_answer_choices": []
                    }
                    for choice in question_details['Answer'].get('Choices', []):
                        formatted_question['wafr_answer_choices'].append({
                            "id": choice['ChoiceId'],
                            "text": choice['Title']
                        })
             
                    pillar_data['wafr_q'].append(formatted_question)
             
                next_token = answers_response.get('NextToken')
            
                if not next_token:
                    break
           
            formatted_data['data'].append(pillar_data)
       
        # Add additional workload information
        formatted_data['workload_name'] = lens_review.get('WorkloadName')
        formatted_data['workload_id'] = workload_id
        formatted_data['lens_alias'] = lens_alias
        formatted_data['lens_name'] = lens_review.get('LensName')
        formatted_data['updated_at'] = str(lens_review.get('UpdatedAt'))  
        return formatted_data
    
    except ClientError as e:
        logger.info(f"Error getting lens review: {e}")
        return None

def get_lens_filter(kb_bucket, wafr_lens):

    # Map lens prefixes to their corresponding lens names - will make it easier to add additional lenses
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

def bedrock_prompt(wafr_lens, pillar, pillar_specfic_question_id, pillar_specfic_wafr_answer_choices, pillar_specfic_prompt_question, kb_id, bedrock_agent_client, document_content=None, wafr_reference_bucket = None):    
    
    lens_filter = get_lens_filter(wafr_reference_bucket, wafr_lens)
    
    response = retrieve(pillar_specfic_prompt_question, kb_id, bedrock_agent_client, lens_filter, pillar, wafr_lens)
    
    retrievalResults = response['retrievalResults']
    contexts = get_contexts(retrievalResults)
    
    system_prompt = f"""<description>You are an AWS Cloud Solutions Architect who specializes in reviewing solution architecture documents against the AWS Well-Architected Framework, using a process called the Well-Architected Framework Review (WAFR).
    The WAFR process consists of evaluating the provided solution architecture document against the 6 pillars of the specified AWS Well-Architected Framework lens, namely:
        - Operational Excellence Pillar
        - Security Pillar
        - Reliability Pillar
        - Performance Efficiency Pillar
        - Cost Optimization Pillar
        - Sustainability Pillar

        A solution architecture document is provided below in the "uploaded_document" section that you will evaluate by answering the questions provided in the "pillar_questions" section in accordance with the WAFR pillar indicated by the "current_pillar" section and the specified WAFR lens indicated by the "<current_lens>" section. Follow the instructions listed under the "instructions" section below. 
    </description>
    <instructions>
    1) For each question, be concise and limit responses to 350 words maximum. Responses should be specific to the specified lens (listed in the "<current_lens>" section) and pillar only (listed in the "<current_pillar>" section). Your response should have three parts: 'Assessment', 'Best Practices Followed', and 'Recommendations/Examples'. Begin with the question asked.
    2) You are also provided with a Knowledge Base which has more information about the specific pillar from the Well-Architected Framework. The relevant parts from the Knowledge Base will be provided under the "kb" section. 
    3) For each question, start your response with the 'Assessment' section, in which you will give a short summary (three to four lines) of your answer.
    4) For each question:
        a) Provide which Best Practices from the specified pillar have been followed, including the best practice IDs and titles from the respective pillar guidance. List them under the 'Best Practices Followed' section. 
            Example: REL01-BP03: Accommodate fixed service quotas and constraints through architecture 
            Example: BP 15.5: Optimize your data modeling and data storage for efficient data retrieval
        b) Provide your recommendations on how the solution architecture should be updated to address the question's ask. If you have a relevant example, mention it clearly like so: "Example: ". List all of this under the 'Recommendations/Examples' section.
    5) For each question, if the required information is missing or is inadequate to answer the question, then first state that the document doesn't provide any or enough information. Then, list the recommendations relevant to the question to address the gap in the solution architecture document under the 'Recommendations' section. In this case, the 'Best practices followed' section will simply state "Not enough information".
    6) First list the question within <question> and </question> tags in the respons. 
    7) Add citations for the best practices and recommendations by including the best practice ID and heading from the specified lens ("<current_lens>") and specified pillar ("<current_pillar>") under the <kb> section, strictly within <citations> and </citations> tags. And every citation within it should be separated by ',' and start on a new line. If there are no citations then return 'N/A' within <citations> and </citations>. 
        Example: REL01-BP03: Accommodate fixed service quotas and constraints through architecture 
        Example: BP 15.5: Optimize your data modeling and data storage for efficient data retrieval
    8) Do not make any assumptions or make up information. Your responses should only be based on the actual solution document provided in the "uploaded_document" section.
    9) Based on the assessment, select the most appropriate choices applicable from the choices provided within the <pillar_choices> section. Do not make up ids and use only the ids specified in the provided choices.
    10) Return the entire response strictly in well-formed XML format. There should not be any text outside the XML response. Use the following XML structure, and ensure that the XML tags are in the same order:
        <response>
            <question>This is the input question</question>
            <assessment>This is assessment</assessment>
            <best_practices_followed>Best practices followed with citaiton fom Well Architected best practices for the pillar</best_practices_followed>
            <recommendations_and_examples>Recommendations with examples</recommendations_and_examples>
            <citations>citations<citations>
            <wafr_answer_choices>
                <choice>
                    <id>sec_securely_operate_multi_accounts</id>
                </choice>
                <choice>
                    <id>sec_securely_operate_aws_account</id>
                </choice>
                <choice>
                    <id>sec_securely_operate_control_objectives</id>
                </choice>
                <choice>
                    <id>sec_securely_operate_updated_threats</id>
                </choice>
            </wafr_answer_choices>
        </response>
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
    Please answer the following questions for the {pillar} pillar of the Well-Architected Framework Review (WAFR).
    Questions:
    {pillar_specfic_prompt_question}
    </pillar_questions>
    <pillar_choices>
    Choices:
    {pillar_specfic_wafr_answer_choices}
    </pillar_choices>
    """
    # ask about anthropic version
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
    
def retrieve(question, kbId, bedrock_agent_client, lens_filter, pillar, wafr_lens):
    
    kb_prompt = f"""For the given question from the {pillar} pillar of {wafr_lens}, provide:
    - Recommendations
    - Best practices
    - Examples
    - Risks
    Question: {question}"""
    
    logger.debug (f"question: {question}")
    logger.debug (f"kb_prompt: {kb_prompt}")
    
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

def read_s3_file (bucket, filename):

    document_text_object = s3client.get_object(
        Bucket=bucket,
        Key=filename,
    )
    
    logger.info (f"read_s3_file: {document_text_object}")
    
    document_text = document_text_object['Body'].read()
    
    return document_text

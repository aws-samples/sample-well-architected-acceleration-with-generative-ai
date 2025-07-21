import os
import boto3
import json
import datetime
import time
import logging
import re

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

from botocore.client import Config
from botocore.exceptions import ClientError

s3 = boto3.resource('s3')
s3client = boto3.client('s3')

dynamodb = boto3.resource('dynamodb')
wa_client = boto3.client('wellarchitected')

BEDROCK_SLEEP_DURATION = int(os.environ['BEDROCK_SLEEP_DURATION'])
BEDROCK_MAX_TRIES = int(os.environ['BEDROCK_MAX_TRIES'])

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info(f"generate_pillar_question_response invoked at {entry_timestamp}")
    
    logger.info(json.dumps(event))

    logger.debug(f"BEDROCK_SLEEP_DURATION: {BEDROCK_SLEEP_DURATION}")
    logger.debug(f"BEDROCK_MAX_TRIES: {BEDROCK_MAX_TRIES}")
    
    data = event

    region = data['region']
    bedrock_config = Config(connect_timeout=120, region_name=region, read_timeout=120, retries={'max_attempts': 0})
    bedrock_client = boto3.client('bedrock-runtime',region_name=region)
    bedrock_agent_client = boto3.client("bedrock-agent-runtime", config=bedrock_config)

    wafr_accelerator_runs_table = dynamodb.Table(data['wafr_accelerator_runs_table'])
    wafr_prompts_table = dynamodb.Table(data['wafr_prompts_table'])

    document_s3_key = data['wafr_accelerator_run_items']['document_s3_key']
    extract_output_bucket_name = data['extract_output_bucket']
    
    wafr_lens = data['wafr_accelerator_run_items']['selected_lens']
    
    pillars = data['wafr_accelerator_run_items'] ['selected_wafr_pillars']
    input_pillar = data['input_pillar']
    llm_model_id = data['llm_model_id']
    wafr_workload_id = data['wafr_accelerator_run_items'] ['wafr_workload_id']
    lens_alias = data['wafr_accelerator_run_items'] ['lens_alias']
    guardrail_id = data['guardrail_id']

    return_response = {}
    
    logger.debug (f"generate_pillar_question_response checkpoint 0")
    logger.info (f"input_pillar: {input_pillar}")
    logger.info (f"wafr_lens: {wafr_lens}")
    
    try:
        extract_output_bucket = s3.Bucket(extract_output_bucket_name)

        streaming = False
        
        logger.debug (f"generate_pillar_question_response checkpoint 1")
        
        input_pillar_id = get_pillar_name_to_id_mappings()[input_pillar]
        
        wafr_accelerator_run_key = {
            'analysis_id':  data['wafr_accelerator_run_items']['analysis_id'],  
            'analysis_submitter': data['wafr_accelerator_run_items']['analysis_submitter']  
        }

        logger.debug (f"generate_pillar_question_response checkpoint 2")
        
        pillar_responses = get_existing_pillar_responses(wafr_accelerator_runs_table, data['wafr_accelerator_run_items']['analysis_id'], data['wafr_accelerator_run_items']['analysis_submitter'])
        
        logger.debug (f"generate_pillar_question_response checkpoint 3")

        pillar_review_output = ""
        
        logger.debug (f"generate_pillar_question_response checkpoint 4")
        
        logger.info (input_pillar)
        
        file_counter = 0 

        # read file content
        # invoke bedrock
        # append response
        # update pillar

        pillar_name_alias_mappings = get_pillar_name_alias_mappings ()
        
        question_mappings = get_question_id_mappings (data['wafr_prompts_table'], wafr_lens, input_pillar)
        
        for pillar_question_object in data[input_pillar]:
            
            filename = pillar_question_object["pillar_review_prompt_filename"]
            logger.info (f"generate_pillar_question_response checkpoint 5.{file_counter}")
            logger.info (f"Input Prompt filename: " + filename)
            
            current_prompt_object = s3client.get_object(
                Bucket=extract_output_bucket_name,
                Key=filename,
            )
                    
            current_prompt = current_prompt_object['Body'].read()
            
            logger.info (f"current_prompt: {current_prompt}")
            
            logger.debug ("filename.rstrip('.'): " + filename.rstrip('.'))
            logger.debug ("filename[:document_s3_key.rfind('.')]: " + filename[:filename.rfind('.')] )
            pillar_review_prompt_ouput_filename = filename[:filename.rfind('.')]+ "-output.txt"
            logger.info (f"Ouput Prompt ouput filename: " + pillar_review_prompt_ouput_filename)            
            
            logger.info (f"generate_pillar_question_response checkpoint 6.{file_counter}")
            
            pillar_specfic_question_id = pillar_question_object["pillar_specfic_question_id"]
            pillar_specfic_prompt_question = pillar_question_object["pillar_specfic_prompt_question"]
            
            pillar_question_review_output = invoke_bedrock(streaming, current_prompt, pillar_review_prompt_ouput_filename, extract_output_bucket, bedrock_client, llm_model_id, guardrail_id)
            
            logger.debug (f"pillar_question_review_output: {pillar_question_review_output}")

            # Comment the next line if you would like to retain the prompts files
            s3client.delete_object(Bucket=extract_output_bucket_name, Key=filename)

            pillar_question_review_output = sanitise_string(pillar_question_review_output)
            logger.debug (f"sanitised_string: {pillar_question_review_output}")
            
            full_assessment, extracted_question, extracted_assessment, best_practices_followed, recommendations_and_examples, risk, citations = extract_assessment(pillar_question_review_output, question_mappings, pillar_question_object["pillar_specfic_prompt_question"])
            logger.debug (f"extracted_assessment: {full_assessment}")
            
            extracted_choices = extract_choices(pillar_question_review_output)
            logger.debug (f"extracted_choices: {extracted_choices}")

            update_wafr_question_response(wa_client, wafr_workload_id, lens_alias, pillar_specfic_question_id, extracted_choices, f"{extracted_assessment} {best_practices_followed} {recommendations_and_examples}")
            
            pillar_review_output = pillar_review_output + "  \n" + full_assessment 
            
            logger.debug (f"generate_pillar_question_response checkpoint 7.{file_counter}")
            
            file_counter = file_counter + 1
        
        logger.debug (f"generate_pillar_question_response checkpoint 8")
        
        # Now write the completed pillar response in DynamoDB  
        pillar_response = {
            'pillar_name': input_pillar,
            'pillar_id': input_pillar_id,
            'llm_response': pillar_review_output
        }
    
        # Add the dictionary object to the list
        pillar_responses.append(pillar_response)
            
        # Update the item
        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET pillars = :val",
            ExpressionAttributeValues={':val': pillar_responses},
            ReturnValues='UPDATED_NEW'  
        )
        
        logger.info (f"dynamodb status update response: {response}" )
        logger.info (f"generate_pillar_question_response checkpoint 10")
    
    except Exception as error:
        handle_error(wafr_accelerator_runs_table, wafr_accelerator_run_key, error)
        raise Exception (f'Exception caught in generate_pillar_question_response: {error}')
    finally:    
        logger.info (f"generate_pillar_question_response inside finally")
        
    logger.debug (f"generate_pillar_question_response checkpoint 11")
    
    return_response = data

    logger.info(f"return_response: " + json.dumps(return_response))
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info(f"Exiting generate_pillar_question_response at {exit_timeestamp}")
        
    # Return a success response
    return {
        'statusCode': 200,
        'body': return_response
    }

def get_pillar_name_to_id_mappings():
    mappings = {}
    
    mappings["Operational Excellence"] = "1"
    mappings["Security"] = "2"
    mappings["Reliability"] = "3"
    mappings["Performance Efficiency"] = "4"
    mappings["Cost Optimization"] = "5"
    mappings["Sustainability"] = "6"
    
    return mappings

def get_pillar_name_alias_mappings():

    mappings = {}
    
    mappings["Cost Optimization"] = "costOptimization"
    mappings["Operational Excellence"] = "operationalExcellence"
    mappings["Performance Efficiency"] = "performance"
    mappings["Reliability"] = "reliability"
    mappings["Security"] = "security"
    mappings["Sustainability"] = "sustainability"
    
    return mappings
    
def sanitise_string(content):
    junk_list = ["```", "xml", "**wafr_answer_choices:**", "{", "}", "[", "]", "<b>", "</b>", "<citation>", "</citation>", "Recommendations:", "Assessment:"]
    for junk in junk_list:
        content = content.replace(junk, '')
    return content

def sanitise_string_2(content):
    junk_list = ["<citations>", "</citations>", "**", "```", "<b>", "</b>"]
    for junk in junk_list:
        content = content.replace(junk, '')
    return content

# Function to recursively print XML nodes
def extract_assessment(content, question_mappings, question):
    
    tag_content = ""
    full_assessment = question=  assessment = best_practices_followed = recommendations_and_examples = risk = citations = ""
    try:
        xml_start = content.find('<question>')
        if xml_start != -1:
            xml_content = content[(xml_start+len("<question>")):]
            xml_end = xml_content.find('</question>')
            if xml_end != -1:
                tag_content = xml_content[:xml_end].strip()
                print (f"question: {tag_content}")
                question = f"**Question: {question_mappings[sanitise_string_2(tag_content)]} - {tag_content}**  \n"
            else:
                print (f"End tag for question not found")        
                question = f"**Question: {question_mappings[sanitise_string_2(question)]} - {question}**  \n"
        else:
            question = f"**Question: {question_mappings[sanitise_string_2(question)]} - {question}**  \n"
        
        assessment = f"**Assessment:** {extract_tag_data(content, 'assessment')}  \n  \n"
        best_practices_followed = f"**Best Practices Followed:** {extract_tag_data(content, 'best_practices_followed')}  \n  \n"
        recommendations_and_examples = f"**Recommendations:** {extract_tag_data(content, 'recommendations_and_examples')}  \n  \n"
        citations = f"**Citations:** {extract_tag_data(content, 'citations')}  \n  \n"
        
        full_assessment = question + assessment + best_practices_followed + recommendations_and_examples + risk +citations
        
    except Exception as error:
        errorFlag = True
        logger.info("Exception caught by try loop in extract_assessment!")
        logger.info("Error received is:")
        logger.info(error) 
        
    return full_assessment, question, assessment, best_practices_followed, recommendations_and_examples, risk, citations

def extract_tag_data(content, tag):
    tag_content = ""
    xml_start = content.find(f'<{tag}>')
    if xml_start != -1:
        xml_content = content[(xml_start+len(f'<{tag}>')):]
        xml_end = xml_content.find(f'</{tag}>')
        if xml_end != -1:
            tag_content = sanitise_string_2(xml_content[:xml_end].strip())
            print (f"{tag}: {tag_content}")
        else:
            print (f"End tag for assessment not found")
    return tag_content     

def extract_choices(content):

    selectedChoices = []
    
    xml_end = -1
    
    try:
        xml_start = content.find('<wafr_answer_choices>')
        if xml_start != -1:
            xml_content = content[xml_start:]
            xml_end = xml_content.find('</wafr_answer_choices>')
            wafr_answer_choices = xml_content[:(xml_end + len("</wafr_answer_choices>"))].strip()
            logger.info(f"wafr_answer_choices: {wafr_answer_choices}")
            logger.info(f"response_root is a well-formed XML")
        
        if ((xml_start!=-1) and (xml_end!=-1)):
            # Use regular expression to find all occurrences of <id>...</id>
            id_pattern = re.compile(r'<id>(.*?)</id>', re.DOTALL)       
            # Find all matches
            ids = id_pattern.findall(wafr_answer_choices)
            # Loop through the matches
            for index, id_value in enumerate(ids, 1):
                print(f"ID {index}: {id_value.strip()}")
                selectedChoices += [id_value.strip()]
                            
    except Exception as error:
        errorFlag = True
        logger.info("Exception caught by try loop in extract_choices!")
        logger.info("Error received is:")
        logger.info(error) 
    
    return selectedChoices

def get_question_id_mappings(wafr_prompts_table_name, wafr_lens, input_pillar):
    questions = {}
    
    wafr_prompts_table = dynamodb.Table(wafr_prompts_table_name)
    response = wafr_prompts_table.query(
    		ProjectionExpression ='wafr_pillar_id, wafr_pillar_prompt',
    		KeyConditionExpression=Key('wafr_lens').eq(wafr_lens) & Key('wafr_pillar').eq(input_pillar),
    		ScanIndexForward=True  # Set to False to sort in descending order
    	)
    logger.debug (f"response wafr_pillar_id: "  + str(response['Items'][0]['wafr_pillar_id']))
    logger.debug (f"response wafr_pillar_prompt: " + response['Items'][0]['wafr_pillar_prompt'])
    pillar_specific_prompt_question = response['Items'][0]['wafr_pillar_prompt']

    line_counter = 0
    # Before rubnning this, ensure wafr prompt row has only questions and no text before it. Otherwise, the below fails.
    for line in response['Items'][0]['wafr_pillar_prompt'].splitlines():
    	line_counter = line_counter + 1
    	if(line_counter > 2):
    		question_id, question_text = line.strip().split(': ', 1)
    		questions[question_text] = question_id
    return questions
    
def handle_error(table, key, error):
    # Handle errors and update DynamoDB status
    table.update_item(
        Key=key,
        UpdateExpression="SET review_status = :val",
        ExpressionAttributeValues={':val': "Errored"},
        ReturnValues='UPDATED_NEW'
    )
    logger.error(f"Exception caught in generate_pillar_question_response: {error}")


def update_wafr_question_response(wa_client, wafr_workload_id, lens_alias, pillar_specfic_question_id, choices, assessment):
    
    errorFlag = False
    
    try:
        if(errorFlag == True):
            selectedChoices = []
            logger.info(f"Error Flag is true")
        else:
            selectedChoices = choices
            
        logger.debug(f"update_wafr_question_response: 1")
        logger.info(f"wafr_workload_id: {wafr_workload_id}, lens_alias: {lens_alias}, pillar_specfic_question_id: {pillar_specfic_question_id}")
        
        try:
            response = wa_client.update_answer(
                    WorkloadId=wafr_workload_id,
                    LensAlias=lens_alias,
                    QuestionId=pillar_specfic_question_id,
                    SelectedChoices=selectedChoices,
                    Notes=assessment[:2084],
                    IsApplicable=True 
                )
            logger.info(f"With Choices- response: {response}")
            logger.debug(f"update_wafr_question_response: 2")
        except Exception as error:
            logger.info("Updated answer with choices failed, now attempting update without the choices!")
            logger.info("With Choices- Error received is:")
            logger.info(error)
            selectedChoices = []
            response = wa_client.update_answer(
                    WorkloadId=wafr_workload_id,
                    LensAlias=lens_alias,
                    QuestionId=pillar_specfic_question_id,
                    SelectedChoices=selectedChoices,
                    Notes=assessment[:2084],
                    IsApplicable=True
                )
            logger.info(f"Without Choices- response: {response}")
            logger.debug(f"update_wafr_question_response: 3")
            
        logger.info (json.dumps(response))
        
    except Exception as error:
        logger.info("Exception caught by external try in update_wafr_question_response!")
        logger.info("Error received is:")
        logger.info(error)
    finally:    
        logger.info (f"update_wafr_question_response Inside finally")
        
def invoke_bedrock(streaming, claude_prompt_body, pillar_review_outputFilename, bucket, bedrock_client, llm_model_id, guardrail_id):

    pillar_review_output = ""
    retries = 0
    max_retries = BEDROCK_MAX_TRIES
    pillar_review_output = ""
    while retries < max_retries:
        try:

            if(streaming):
                if(guardrail_id == "Not Selected"):
                    streaming_response = bedrock_client.invoke_model_with_response_stream(
                        modelId=llm_model_id,
                        body=claude_prompt_body                     
                    )
                else: # Use guardrails
                    streaming_response = bedrock_client.invoke_model_with_response_stream(
                        modelId=llm_model_id,
                        body=claude_prompt_body,
                        guardrailIdentifier= guardrail_id,
                        guardrailVersion="DRAFT"
                    )
                    logger.info (f"Used Guardrail Id: {guardrail_id}")

                logger.info (f"invoke_bedrock checkpoint 1.{retries}")
                stream = streaming_response.get("body")
                
                logger.info (f"invoke_bedrock checkpoint 2.{retries}")
        
                for chunk in parse_stream(stream):
                    pillar_review_output += chunk
                    
                # Uncomment next line if you would like to see response files for each question too. 
                # bucket.put_object(Key=pillar_review_output_filename, Body=bytes(pillar_review_output, encoding='utf-8'))
                
                return pillar_review_output
                
            else:
                if(guardrail_id == "Not Selected"):
                    non_streaming_response = bedrock_client.invoke_model(
                        modelId=llm_model_id,
                        body=claude_prompt_body
                    )
                else: # Use guardrails
                    non_streaming_response = bedrock_client.invoke_model(
                        modelId=llm_model_id,
                        body=claude_prompt_body,
                        guardrailIdentifier=guardrail_id,
                        guardrailVersion="DRAFT"
                    )
                    logger.debug (f"Used Guardrail Id: {guardrail_id}")
                response_json = json.loads(non_streaming_response["body"].read().decode("utf-8"))
        
                logger.debug (response_json)
                
                logger.info (f"invoke_bedrock checkpoint 1.{retries}")
        
                # Extract and logger.info the response text.
                pillar_review_output = response_json["content"][0]["text"]
        
                logger.debug (f"invoke_bedrock checkpoint 2.{retries}")
                
                # Uncomment next line if you would like to see response files for each question too. 
                #bucket.put_object(Key=pillar_review_outputFilename, Body=pillar_review_output)
                
                return pillar_review_output
                
        except Exception as e:
            retries += 1
            logger.info(f"Sleeping as attempt {retries} failed with exception: {e}")
            time.sleep(BEDROCK_SLEEP_DURATION)  # Add a delay before the next retry

    logger.info(f"Maximum retries ({max_retries}) exceeded. Unable to invoke the model.")
    raise Exception (f"Maximum retries ({max_retries}) exceeded. Unable to invoke the model.")

def parse_stream(stream):
    for event in stream:
        chunk = event.get('chunk')
        if chunk:
            message = json.loads(chunk.get("bytes").decode())
            if message['type'] == "content_block_delta":
                yield message['delta']['text'] or ""
            elif message['type'] == "message_stop":
                return "\n"


def get_existing_pillar_responses(wafr_accelerator_runs_table, analysis_id, analysis_submitter):
    
    pillar_responses = []    
    logger.info (f"analysis_id : {analysis_id}")
    logger.info (f"analysis_submitter: " + analysis_submitter)
    
    response = wafr_accelerator_runs_table.query(
        ProjectionExpression ='pillars',
        KeyConditionExpression=Key('analysis_id').eq(analysis_id) & Key('analysis_submitter').eq(analysis_submitter),
        ConsistentRead=True, 
        ScanIndexForward=True  
    )

    logger.info (f"Existing pillar responses stored in wafr_prompts_table table : {response}" )

    items = response['Items']
    
    logger.debug (f"items assigned: {items}" )
    
    logger.info (f"Items length: {len(response['Items'])}" )
    
    try:
        if len(response['Items']) > 0: 
            for item in items:
                pillars = item['pillars']
                logger.info (pillars)
                for pillar in pillars:
                    logger.info (pillar)
                    pillar_response = {
                        'pillar_name': pillar['pillar_name'],
                        'pillar_id': str(pillar['pillar_id']),
                        'llm_response': pillar['llm_response']
                    }
                    logger.info (f"pillar_response {pillar_response}")                
                    # Add the dictionary object to the list
                    pillar_responses.append(pillar_response)             
        else:
            logger.info("List is empty")
            
    except Exception as error:
        logger.info("Exception caught by try loop in get_existing_pillar_responses! Looks attribute is empty.")
        logger.info(f"Error received is: {error}")
        
    return pillar_responses
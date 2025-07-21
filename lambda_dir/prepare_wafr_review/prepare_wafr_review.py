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
dynamodb = boto3.resource('dynamodb')
well_architected_client = boto3.client('wellarchitected')

WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME = os.environ['WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME']
UPLOAD_BUCKET_NAME = os.environ['UPLOAD_BUCKET_NAME']
REGION = os.environ['REGION']
WAFR_PROMPT_DD_TABLE_NAME = os.environ['WAFR_PROMPT_DD_TABLE_NAME']
KNOWLEDGE_BASE_ID=os.environ['KNOWLEDGE_BASE_ID']
LLM_MODEL_ID=os.environ['LLM_MODEL_ID']
BEDROCK_SLEEP_DURATION = os.environ['BEDROCK_SLEEP_DURATION']
BEDROCK_MAX_TRIES = os.environ['BEDROCK_MAX_TRIES']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID']

bedrock_config = Config(connect_timeout=120, region_name=REGION, read_timeout=120, retries={'max_attempts': 0})
bedrock_client = boto3.client('bedrock-runtime',region_name=REGION)
bedrock_agent_client = boto3.client("bedrock-agent-runtime", config=bedrock_config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_lens_alias (wafr_lens):
    wafr_prompts_table = dynamodb.Table(WAFR_PROMPT_DD_TABLE_NAME)
    
    response = wafr_prompts_table.query(
        ProjectionExpression ='wafr_pillar_id, wafr_pillar_prompt, wafr_lens_alias',
        KeyConditionExpression=Key('wafr_lens').eq(wafr_lens),
        ScanIndexForward=True  
    )
   
    print (f"response wafr_lens_alias: " + response['Items'][0]['wafr_lens_alias'])
    
    return response['Items'][0]['wafr_lens_alias']
    
def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info('prepare_wafr_review invoked at ' + entry_timestamp)

    logger.info(json.dumps(event))

    data = json.loads(event[0]['body'])
        
    try:
        
        logger.info("WAFR_PROMPT_DD_TABLE_NAME: " + WAFR_PROMPT_DD_TABLE_NAME)
        logger.info("WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME: " + WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME)
        logger.info("REGION: " + REGION)
        logger.info("UPLOAD_BUCKET_NAME: " + UPLOAD_BUCKET_NAME)
        logger.info("LLM_MODEL_ID: " + LLM_MODEL_ID)
        logger.info("KNOWLEDGE_BASE_ID: " + KNOWLEDGE_BASE_ID)
        logger.info("BEDROCK_SLEEP_DURATION: " + BEDROCK_SLEEP_DURATION)
        logger.info("BEDROCK_MAX_TRIES: " + BEDROCK_MAX_TRIES)
    
        wafr_accelerator_runs_table = dynamodb.Table(WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME)
        
        analysis_id = data['analysis_id'] 
        analysis_submitter = data['analysis_submitter']
        analysis_response = wafr_accelerator_runs_table.get_item(
            Key={
                'analysis_id': analysis_id,
                'analysis_submitter': analysis_submitter
            }
        )
        analysis = analysis_response.get("Item", {})
        
        logger.info(f'analysis: {json.dumps(analysis)}')
        
        name = data.get("analysis_name", "")
        wafr_lens = data['wafr_lens']
        
        workload_name = data['analysis_name']
        workload_desc = analysis['workload_desc']
        environment = analysis['environment']
        review_owner = analysis['review_owner']
        industry_type = analysis['industry_type']
        creation_date = analysis['creation_date']
        
        # Get the lens ARN from the friendly name
        lenses =  analysis["lenses"] 

        aws_regions = [REGION]  
            
        logger.info('creation_date: ' + creation_date)
        
        wafr_workload_id = create_workload(well_architected_client, workload_name, 
            workload_desc, environment, lenses, review_owner, industry_type, aws_regions)
    
        review_status = "In Progress"
        document_s3_key = data['document_s3_key']

        wafr_accelerator_run_key = {
            'analysis_id': analysis_id,
            'analysis_submitter': analysis_submitter
        }
            
        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET review_status = :val1, wafr_workload_id = :val2",
            ExpressionAttributeValues={
                ':val1': review_status,
                ':val2': wafr_workload_id
            },
            ReturnValues='UPDATED_NEW'
        )
        logger.info(f'wafr-accelerator-runs dynamodb table summary update response: {response}')
        
        pillars = data['selected_pillars']        
        pillar_string = ",".join(pillars)
        logger.info("Final pillar_string: " + pillar_string)
    
        logger.debug("prepare_wafr_review checkpoint 1")
        
        # Prepare the item to be returned
        wafr_accelerator_run_items = {
            'analysis_id': analysis_id,
            'analysis_submitter': analysis_submitter,
            'analysis_title': name,
            'selected_lens': wafr_lens,
            'creation_date': creation_date,
            'review_status': review_status,
            'selected_wafr_pillars': pillars,
            'document_s3_key': document_s3_key,
            'analysis_owner': name,
            'wafr_workload_id': wafr_workload_id,
            'workload_name': workload_name,
            'workload_desc': workload_desc,
            'environment': environment,
            'review_owner': review_owner,
            'industry_type': industry_type,
            'lens_alias': lenses
        }
        
        logger.debug('prepare_wafr_review checkpoint 2')
        
        return_response = {}

        return_response['wafr_accelerator_run_items'] = wafr_accelerator_run_items
        return_response['wafr_accelerator_run_key'] = wafr_accelerator_run_key
        return_response['extract_output_bucket'] = UPLOAD_BUCKET_NAME
        return_response['pillars_string'] = pillar_string
        return_response['wafr_accelerator_runs_table'] = WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME
        return_response['wafr_prompts_table'] = WAFR_PROMPT_DD_TABLE_NAME
        return_response['region'] = REGION
        return_response['knowledge_base_id'] = KNOWLEDGE_BASE_ID
        return_response['llm_model_id'] = LLM_MODEL_ID
        return_response['wafr_workload_id'] = wafr_workload_id
        return_response['lens_alias'] = lenses
        return_response['guardrail_id'] = GUARDRAIL_ID
    
    except Exception as error:
        update_analysis_status (data, error)
        raise Exception (f'Exception caught in prepare_wafr_review: {error}')
        
    logger.info(f'return_response: {return_response}')
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info(f'Exiting prepare_wafr_review at {exit_timeestamp}')
    
    return {
        'statusCode': 200,
        'body': json.dumps(return_response)
    }
    
def create_workload(client, workload_name, description, environment, lenses, review_owner, industry_type, aws_regions, architectural_design=None):
    workload_params = {
        'WorkloadName': workload_name,
        'Description': description,
        'Environment': environment,
        'ReviewOwner': review_owner,
        'IndustryType': industry_type,
        'Lenses': [lenses] if isinstance(lenses, str) else lenses,
        'AwsRegions': aws_regions
    }
    if architectural_design:
        workload_params['ArchitecturalDesign'] = architectural_design
    response = client.create_workload(**workload_params)
    return response['WorkloadId']
        
def update_analysis_status (data, error):
    
    dynamodb = boto3.resource('dynamodb')
    wafr_accelerator_runs_table = dynamodb.Table(WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME)
    
    wafr_accelerator_run_key = {
        'analysis_id':  data['analysis_id'],  
        'analysis_submitter':  data['analysis_submitter']  
    }
    
    wafr_accelerator_runs_table.update_item(
        Key=wafr_accelerator_run_key,
        UpdateExpression="SET review_status = :val",
        ExpressionAttributeValues={':val': "Errored"},
        ReturnValues='UPDATED_NEW'
    )
    logger.error(f"Exception caught in prepare_wafr_review: {error}")
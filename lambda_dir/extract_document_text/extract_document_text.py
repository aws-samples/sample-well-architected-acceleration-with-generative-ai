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

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info("extract_document_text invoked at " + entry_timeestamp)

    output_filename = extract_document_text = ""
    logger.info(json.dumps(event))
    
    return_response = data = event
    upload_bucket_name = data['extract_output_bucket']
    region = data['region']

    wafr_accelerator_runs_table = dynamodb.Table(data['wafr_accelerator_runs_table'])
    wafr_accelerator_run_key = data['wafr_accelerator_run_key']
    
    document_s3_key = data['wafr_accelerator_run_items']['document_s3_key']
    
    try:

        # Extract text from the document
        extracted_document_text = extract_text(upload_bucket_name, document_s3_key , region)
        
        attribute_updates = {
            'extracted_document': {
                'Action': 'ADD'  # PUT to update or ADD to add a new attribute
            }
        }
        
        # Update the item
        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET extracted_document = :val",
            ExpressionAttributeValues={':val': extracted_document_text}, 
            ReturnValues='UPDATED_NEW' 
        )
        
        # Write the textract output to a txt file 
        output_bucket = s3.Bucket(upload_bucket_name)
        logger.info ("document_s3_key.rstrip('.'): " + document_s3_key.rstrip('.'))
        logger.info ("document_s3_key[:documentS3Key.rfind('.')]: " + document_s3_key[:document_s3_key.rfind('.')] )
        output_filename = document_s3_key[:document_s3_key.rfind('.')]+ "-extracted-text.txt"
        return_response['extract_text_file_name'] = output_filename
        
        # Upload the file to S3
        output_bucket.put_object(Key=output_filename, Body=bytes(extracted_document_text, encoding='utf-8'))
        
    except Exception as error:
        # Handle errors and update DynamoDB status
        handle_error(wafr_accelerator_runs_table, wafr_accelerator_run_key, error)
        raise Exception (f'Exception caught in extract_document_text: {error}')
    
    logger.info('return_response: ' + json.dumps(return_response))
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    logger.info("Exiting extract_document_text at " + exit_timeestamp)
    
    # Return a success response
    return {
        'statusCode': 200,
        'body': json.dumps(return_response)
    }

def handle_error(table, key, error):
    # Handle errors and update DynamoDB status
    table.update_item(
        Key=key,
        UpdateExpression="SET review_status = :val",
        ExpressionAttributeValues={':val': "Errored"},
        ReturnValues='UPDATED_NEW'
    )
    logger.error(f"Exception caught in extract_document_text: {error}")
    
def extract_text(upload_bucket_name, document_s3_key, region):

    logger.info ("solution_design_text is null and hence using Textract")
    # # Initialize Textract and Bedrock clients
    textract_config = Config(retries = dict(max_attempts = 5))
    textract_client = boto3.client('textract', region_name=region, config=textract_config)

    logger.debug ("extract_text checkpoint 1")
    # Start the text detection job
    response = textract_client.start_document_text_detection(
        DocumentLocation={
            'S3Object': {
                'Bucket': upload_bucket_name,
                'Name': document_s3_key
            }
        }
    )
    
    job_id = response["JobId"]
    
    logger.info (f"textract response: {job_id}")
    
    logger.debug ("extract_text checkpoint 2")
    
    # Wait for the job to complete
    while True:
        response = textract_client.get_document_text_detection(JobId=job_id)
        status = response["JobStatus"]
        if status == "SUCCEEDED":
            break
    
    logger.debug ("extract_text checkpoint 3")
    # Get the job results
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
    
    logger.debug ("extract_text checkpoint 4")
    # Extract the text from all pages
    extracted_text = ""
    for page in pages:
        for item in page["Blocks"]:
            if item["BlockType"] == "LINE":
                extracted_text += item["Text"] + "\n"

    
    return extracted_text
import boto3
import json
import datetime
import logging

from botocore.client import Config
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
s3 = boto3.resource('s3')
s3client = boto3.client('s3')
wa_client = boto3.client('wellarchitected')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    
    logger.info(f"generate_solution_summary invoked at {entry_timestamp}")
    
    logger.info(json.dumps(event))

    # Extract data from the input event
    return_response = data = event
    wafr_accelerator_runs_table = dynamodb.Table(data['wafr_accelerator_runs_table'])
    wafr_accelerator_run_key = data['wafr_accelerator_run_key']
    
    # Set up Bedrock client
    REGION = data['region']
    LLM_MODEL_ID = data['llm_model_id']
    bedrock_config = Config(connect_timeout=120, region_name=REGION, read_timeout=120, retries={'max_attempts': 0})
    bedrock_client = boto3.client('bedrock-runtime', config=bedrock_config)

    try:
        extracted_document_text = read_s3_file (data['extract_output_bucket'], data['extract_text_file_name'])

        # Prepare prompts for solution summary and workload description
        prompt = f"The following document is a solution architecture document that you are reviewing as an AWS Cloud Solutions Architect. Please summarise the following solution in 250 words. Begin directly with the architecture summary, don't provide any other opening or closing statements.\n\n<Architecture>\n{extracted_document_text}\n</Architecture>\n"

        # Generate summaries using Bedrock model
        summary = invoke_bedrock_model(bedrock_client, LLM_MODEL_ID, prompt)

        logger.info(f"Solution Summary: {summary}")

        # Update DynamoDB item with the generated summary
        update_dynamodb_item(wafr_accelerator_runs_table, wafr_accelerator_run_key, summary)

        # Write summary to S3
        write_summary_to_s3(s3, data['extract_output_bucket'], data['wafr_accelerator_run_items']['document_s3_key'], summary)

    except Exception as error:
        wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET review_status = :val",
            ExpressionAttributeValues={':val': "Errored"},
            ReturnValues='UPDATED_NEW'
        )
        logger.error(f"Exception caught in generate_solution_summary: {error}")
        raise Exception (f'Exception caught in generate_solution_summary: {error}')

    # Prepare and return the response
    logger.info(f"return_response: {json.dumps(return_response)}")
    logger.info(f"Exiting generate_solution_summary at {datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S-%f')}")

    return {'statusCode': 200, 'body': return_response}

def read_s3_file (bucket, filename):

    document_text_object = s3client.get_object(
        Bucket=bucket,
        Key=filename,
    )
    
    logger.info (document_text_object)
    
    document_text = document_text_object['Body'].read()
    
    return document_text
    
def invoke_bedrock_model(bedrock_client, model_id, prompt):
    # Invoke Bedrock model and return the generated text
    response = bedrock_client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200000,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
        })
    )
    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']

def update_dynamodb_item(table, key, summary):
    # Update DynamoDB item with the generated summary
    table.update_item(
        Key=key,
        UpdateExpression="SET architecture_summary = :val",
        ExpressionAttributeValues={':val': summary},
        ReturnValues='UPDATED_NEW'
    )

def write_summary_to_s3(s3, bucket_name, document_key, summary):
    output_bucket = s3.Bucket(bucket_name)
    output_filename = f"{document_key[:document_key.rfind('.')]}-solution-summary.txt"
    logger.info(f"write_summary_to_s3: {output_filename}")
    output_bucket.put_object(Key=output_filename, Body=summary)

import os
import boto3
import json
import datetime
import urllib.parse
import logging
from botocore.exceptions import ClientError

s3Client = boto3.client('s3')
s3Resource = boto3.resource('s3')

TABLE_NAME = os.environ['DD_TABLE_NAME']
REGION_NAME = os.environ['REGION_NAME']
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(TABLE_NAME)


logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    
    status = 'Prompts inserted successfully!'
    
    logger.info(f"insert_wafr_prompts invoked at {entry_timestamp}")
    
    logger.info(json.dumps(event))

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    message = "WAFR prompts json is stored here - " + bucket + "/" + key 
    logger.info (message)
    logger.info (f"insert_wafr_prompts checkpoint 1")
    
    purge_existing_data(table)
    
    try:
        s3_input_string = "s3://" + bucket + "/" + key
        logger.info("s3_input_string is : " + s3_input_string)
        
        response = s3Client.get_object(Bucket=bucket, Key=key)
        
        # Read the content of the file
        content = response['Body'].read().decode('utf-8')

        prompts_json = json.loads(content)

        logger.info (f"insert_wafr_prompts checkpoint 2")
        
        logger.info(json.dumps(prompts_json))
        
        # Iterate over the array of items
        for item_data in prompts_json['data']:
            # Prepare the item to be inserted
            item = {
                'wafr_lens': item_data['wafr_lens'],
                'wafr_lens_alias': item_data['wafr_lens_alias'],                
                'wafr_pillar': item_data['wafr_pillar'],
                'wafr_pillar_id': item_data['wafr_pillar_id'],
                'wafr_pillar_prompt': item_data['wafr_pillar_prompt']
                #'wafr_q': item_data['wafr_q']
            }
        
            # Insert the item into the DynamoDB table
            table.put_item(Item=item)

        logger.info (f"insert_wafr_prompts checkpoint 4")
        
    except Exception as error:
        logger.error(error)
        logger.error("S3 Object could not be opened. Check environment variable. ")
        status = 'Failed to insert Prompts!'
    
    exit_timeestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info("Exiting insert_wafr_prompts at " + exit_timeestamp)
    
    # Return a success response
    return {
        'statusCode': 200,
        'body': json.dumps(status)
    }
            
def purge_existing_data(table):
    existing_items = table.scan()
    with table.batch_writer() as batch:
        for item in existing_items['Items']:
            batch.delete_item(
                Key={
                    'wafr_lens': item['wafr_lens'],
                    'wafr_pillar': item['wafr_pillar']
                }
            )
    
import os
import boto3
import json
import datetime
import time
import logging
import uuid

from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr
from botocore.client import Config
from botocore.exceptions import ClientError

s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb')
well_architected_client = boto3.client('wellarchitected')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info(f"update_review_status invoked at {entry_timestamp}" )
    logger.info(json.dumps(event))
        
    return_response = 'Success'
    
    # Parse the input data
    data = event

    wafr_accelerator_runs_table = dynamodb.Table(data[0]['wafr_accelerator_runs_table'])
    wafr_accelerator_run_key = data[0]['wafr_accelerator_run_key']
    wafr_workload_id = data[0]['wafr_accelerator_run_items']['wafr_workload_id']
    
    try:
        logger.debug(f"update_review_status checkpoint 1")

        # Create a milestone
        wafr_milestone = well_architected_client.create_milestone(
            WorkloadId=wafr_workload_id,
            MilestoneName="WAFR Accelerator Baseline",
            ClientRequestToken=str(uuid.uuid4())
        )

        logger.debug(f"Milestone created - {json.dumps(wafr_milestone)}")

        # Update the item
        response = wafr_accelerator_runs_table.update_item(
            Key=wafr_accelerator_run_key,
            UpdateExpression="SET review_status = :val",
            ExpressionAttributeValues={':val': "Completed"},
            ReturnValues='UPDATED_NEW'  
        )
        logger.debug(f"update_review_status checkpoint 2")
    except Exception as error:
        return_response = 'Failed'
        logger.error(f"Exception caught in update_review_status: {error}")
    
    exit_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
    
    logger.info(f"Exiting update_review_status at {exit_timestamp}" )
    
    return {
        'statusCode': 200,
        'body' : return_response
    }

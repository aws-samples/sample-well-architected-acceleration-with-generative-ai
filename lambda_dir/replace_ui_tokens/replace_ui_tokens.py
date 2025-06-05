import os
import boto3
import json
import datetime
import urllib.parse
import re
import logging

WAFR_ACCELERATOR_QUEUE_URL = os.environ['WAFR_ACCELERATOR_QUEUE_URL']
WAFR_UI_BUCKET_NAME = os.environ['WAFR_UI_BUCKET_NAME']
WAFR_UI_BUCKET_ARN = os.environ['WAFR_UI_BUCKET_ARN']
REGION_NAME = os.environ['REGION_NAME']
WAFR_RUNS_TABLE=os.environ['WAFR_RUNS_TABLE']
EC2_INSTANCE_ID=os.environ['EC2_INSTANCE_ID']
UPLOAD_BUCKET_NAME=os.environ['UPLOAD_BUCKET_NAME'] 
PARAMETER_1_NEW_WAFR_REVIEW=os.environ['PARAMETER_1_NEW_WAFR_REVIEW'] 
PARAMETER_2_EXISTING_WAFR_REVIEWS=os.environ['PARAMETER_2_EXISTING_WAFR_REVIEWS'] 
PARAMETER_UI_SYNC_INITAITED_FLAG=os.environ['PARAMETER_UI_SYNC_INITAITED_FLAG'] 
PARAMETER_3_LOGIN_PAGE=os.environ['PARAMETER_3_LOGIN_PAGE'] 
PARAMETER_COGNITO_USER_POOL_ID = os.environ['PARAMETER_COGNITO_USER_POOL_ID'] 
PARAMETER_COGNITO_USER_POOL_CLIENT_ID = os.environ['PARAMETER_COGNITO_USER_POOL_CLIENT_ID']
GUARDRAIL_ID = os.environ['GUARDRAIL_ID'] 

ssm_client = boto3.client('ssm')
s3Client = boto3.client('s3')
s3Resource = boto3.resource('s3')
ssm_parameter_store = boto3.client('ssm', region_name=REGION_NAME) 

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    entry_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    
    logger.info("replace_ui_tokens invoked at " + entry_timestamp)
    
    s3_script = """
import boto3
import os

s3 = boto3.client('s3')

try:
    bucket_name = '{{UI_CODE_BUCKET_NAME}}'
    
    objects = s3.list_objects_v2(Bucket=bucket_name)['Contents']
    
    for obj in objects:
        print(obj['Key'])
        current_directory = os.path.dirname(os.path.realpath(__file__))
        key = obj['Key']
        # Skip if the object is a directory
        if key.endswith('/'):
            continue
        # Create the local directory structure if it doesn't exist
        local_path = os.path.join(current_directory, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        # Download the object
        s3.download_file(bucket_name, key, local_path)
        print(f'Downloaded: {key}')
except Exception as e:
    print(f'Error: {e}')
    """
    
    logger.info("WAFR_ACCELERATOR_QUEUE_URL: " + WAFR_ACCELERATOR_QUEUE_URL)
    logger.info("WAFR_UI_BUCKET_NAME: " + WAFR_UI_BUCKET_NAME)
    logger.info("WAFR_UI_BUCKET_ARN: " + WAFR_UI_BUCKET_ARN)
    logger.info("REGION_NAME: " + REGION_NAME)
    logger.info("WAFR_RUNS_TABLE: " + WAFR_RUNS_TABLE)
    logger.info("EC2_INSTANCE_ID: " + EC2_INSTANCE_ID)
    logger.info("UPLOAD_BUCKET_NAME: " + UPLOAD_BUCKET_NAME)
    logger.info("PARAMETER_1_NEW_WAFR_REVIEW: " + PARAMETER_1_NEW_WAFR_REVIEW)
    logger.info("PARAMETER_2_EXISTING_WAFR_REVIEWS: " + PARAMETER_2_EXISTING_WAFR_REVIEWS)
    logger.info("PARAMETER_UI_SYNC_INITAITED_FLAG: " + PARAMETER_UI_SYNC_INITAITED_FLAG)
    logger.info("PARAMETER_3_LOGIN_PAGE: " + PARAMETER_3_LOGIN_PAGE)
    logger.info("PARAMETER_COGNITO_USER_POOL_ID: " + PARAMETER_COGNITO_USER_POOL_ID)
    logger.info("PARAMETER_COGNITO_USER_POOL_CLIENT_ID: " + PARAMETER_COGNITO_USER_POOL_CLIENT_ID)
    logger.info("GUARDRAIL_ID: " + GUARDRAIL_ID)

    logger.info(json.dumps(event))

    status = 'Everything done successfully - token update, s3 script creation and execution!'
    
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
     
    logger.info(f"replace_ui_tokens invoked for  {bucket} / {key}")
    
    logger.info (f"replace_ui_tokens checkpoint 1")
        
    try:
        # Check if the input key has the "tokenized-pages/" prefix
        if (key.startswith('tokenized-pages')):
            
            logger.info (f"replace_ui_tokens checkpoint 2")
            
            # Replace the prefix with "pages/"
            output_key = 'pages/' + key.split('tokenized-pages/')[1]
    
            if(key.startswith('tokenized-pages/1_New_WAFR_Review.py')):
                # Read the file from the input key
                response = s3Client.get_object(Bucket=bucket, Key=key)
                file_content = response['Body'].read().decode('utf-8')
            
                #1_New_WAFR_Run.py'                
                updated_content = re.sub(r'{{REGION}}', REGION_NAME, file_content)
                updated_content = re.sub(r'{{SQS_QUEUE_NAME}}', WAFR_ACCELERATOR_QUEUE_URL, updated_content)
                updated_content = re.sub(r'{{WAFR_UPLOAD_BUCKET_NAME}}', UPLOAD_BUCKET_NAME, updated_content)
                updated_content = re.sub(r'{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}', WAFR_RUNS_TABLE, updated_content)
                
                # Write the updated content to the output key
                s3Client.put_object(Bucket=bucket, Key=output_key, Body=updated_content.encode('utf-8'))

                ssm_parameter_store.put_parameter(
                    Name=PARAMETER_1_NEW_WAFR_REVIEW,
                    Value=f'True',
                    Type='String',
                    Overwrite=True
                )
                
                logger.info (f"replace_ui_tokens checkpoint 3a")
                
            elif(key.startswith('tokenized-pages/2_Existing_WAFR_Reviews.py')):
                response = s3Client.get_object(Bucket=bucket, Key=key)
                file_content = response['Body'].read().decode('utf-8')
                
                updated_content = re.sub(r'{{REGION}}', REGION_NAME, file_content)
                updated_content = re.sub(r'{{WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME}}', WAFR_RUNS_TABLE, updated_content)
                updated_content = re.sub(r'{{GUARDRAIL_ID}}', GUARDRAIL_ID, updated_content)
                
                # Write the updated content to the output key
                s3Client.put_object(Bucket=bucket, Key=output_key, Body=updated_content.encode('utf-8'))
                
                ssm_parameter_store.put_parameter(
                    Name=PARAMETER_2_EXISTING_WAFR_REVIEWS,
                    Value=f'True',
                    Type='String',
                    Overwrite=True
                )
                logger.info (f"replace_ui_tokens checkpoint 3b")
                
            elif(key.startswith('tokenized-pages/1_Login.py')):
                response = s3Client.get_object(Bucket=bucket, Key=key)
                file_content = response['Body'].read().decode('utf-8')
                
                updated_content = re.sub(r'{{REGION}}', REGION_NAME, file_content)
                updated_content = re.sub(r'{{PARAMETER_COGNITO_USER_POOL_ID}}', PARAMETER_COGNITO_USER_POOL_ID, updated_content)
                updated_content = re.sub(r'{{PARAMETER_COGNITO_USER_POOL_CLIENT_ID}}', PARAMETER_COGNITO_USER_POOL_CLIENT_ID, updated_content)

                # Write the updated content to the output key
                s3Client.put_object(Bucket=bucket, Key=output_key, Body=updated_content.encode('utf-8'))
                
                ssm_parameter_store.put_parameter(
                    Name=PARAMETER_3_LOGIN_PAGE,
                    Value=f'True',
                    Type='String',
                    Overwrite=True
                )
                
                logger.info (f"replace_ui_tokens checkpoint 3c")
            else: # all other files in the folder
                response = s3Client.copy_object(Bucket=bucket, CopySource=key, Key=output_key)
                logger.info (f"replace_ui_tokens checkpoint 3d")
    
            logger.info(f'File processed: {key} -> {output_key}')

            logger.info (f"replace_ui_tokens checkpoint 3d")
            
        else:
            logger.info(f'Skipping file: {key} (does not have the "tokenized-pages/" prefix)')
            
        
    except Exception as error:
        logger.info(error)
        logger.info("replace_ui_tokens: S3 Object could not be opened. Check environment variable.")
        status = 'File updates failed!'
    
    update1 = update2 = ui_sync_flag = update3 = "False"
    
    try:
        update1 = ssm_parameter_store.get_parameter(Name=PARAMETER_1_NEW_WAFR_REVIEW, WithDecryption=True)['Parameter']['Value']
        logger.info (f"replace_ui_tokens checkpoint 4a: update1 (PARAMETER_1_NEW_WAFR_REVIEW) = " + update1)
        update2 = ssm_parameter_store.get_parameter(Name=PARAMETER_2_EXISTING_WAFR_REVIEWS, WithDecryption=True)['Parameter']['Value']
        logger.info (f"replace_ui_tokens checkpoint 4b: update2 (PARAMETER_2_EXISTING_WAFR_REVIEWS) = " + update2)
        update3 = ssm_parameter_store.get_parameter(Name=PARAMETER_3_LOGIN_PAGE, WithDecryption=True)['Parameter']['Value']
        logger.info (f"update_login_page checkpoint 4c: update3 (PARAMETER_3_LOGIN_PAGE) = " + update3)
        ui_sync_flag = ssm_parameter_store.get_parameter(Name=PARAMETER_UI_SYNC_INITAITED_FLAG, WithDecryption=True)['Parameter']['Value']
        logger.info (f"ui_sync_flag checkpoint 4d: ui_synC_flag (PARAMETER_UI_SYNC_INITAITED_FLAG) = " + ui_sync_flag)        
    except Exception as error:
        logger.info(error)
        logger.info("One of the parameters is missing, wait for the next event")
    
    if( ui_sync_flag == "False"):
        if(((update1 =="True") and (update2 =="True")) and (update3 =="True")):
            logger.info (f"replace_ui_tokens checkpoint 4d : All the parameters are true, sending SSM command!")
            send_ssm_command (EC2_INSTANCE_ID, s3_script, WAFR_UI_BUCKET_NAME)
            ssm_parameter_store.put_parameter(
                    Name=PARAMETER_UI_SYNC_INITAITED_FLAG,
                    Value=f'True',
                    Type='String',
                    Overwrite=True
            )
            logger.info (f"ui_synC_flag set to True checkpoint 4e")
    else:
        logger.info(f'ui_synC_flag is already set, files are not synced again! Reset the {PARAMETER_UI_SYNC_INITAITED_FLAG} to False for file sync to happen again')
            
    logger.info (f"replace_ui_tokens checkpoint 5")
    
    return {
        'statusCode': 200,
        'body': json.dumps(status)
    }    

def send_ssm_command(ec2InstanceId, s3_script, wafrUIBucketName):
    
    s3_script = re.sub(r'{{UI_CODE_BUCKET_NAME}}', wafrUIBucketName, s3_script)
    
        # Send the SSM Run Command to process the file
    command_id = ssm_client.send_command(
        InstanceIds=[ec2InstanceId],  # Replace with your instance ID
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                'sudo mkdir -p /wafr-accelerator && cd /wafr-accelerator',
                f'sudo echo "{s3_script}" > /wafr-accelerator/syncUIFolder.py',
                'sleep 30 && sudo chown -R ec2-user:ec2-user /wafr-accelerator',
                'python3 syncUIFolder.py',
                'sleep 30 && sudo chown -R ec2-user:ec2-user /wafr-accelerator'
            ]
        }
    )['Command']['CommandId']
    
        
    logger.info (f"replace_ui_tokens checkpoint 4f: command_id " + command_id)
    
    # Wait for the command execution to complete
    waiter = ssm_client.get_waiter('command_executed')
    waiter.wait(
        CommandId=command_id,
        InstanceId=ec2InstanceId,  # Replace with your instance ID
        WaiterConfig={
            'Delay': 30,
            'MaxAttempts': 30
        }
    )
    
    logger.info (f"replace_ui_tokens checkpoint 4g: Wait over")


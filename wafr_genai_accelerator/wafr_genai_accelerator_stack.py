import os
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    Tags,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_ec2 as ec2,
    custom_resources as cr,
    aws_s3_deployment as s3deploy,
    aws_dynamodb as dynamodb,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_sqs as sqs,
    aws_lambda_event_sources as lambda_event_source,
    aws_elasticloadbalancingv2 as elbv2,
    aws_wafv2 as wafv2,
    aws_cognito as cognito,
    aws_ssm as ssm,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda_event_sources as lambda_events,
    aws_logs
)
import aws_cdk.aws_elasticloadbalancingv2_targets as elasticloadbalancingv2_targets

from aws_cdk.aws_ssm import StringParameter
import aws_cdk as cdk
from constructs import Construct
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from aws_cdk import Duration
import re

from cdklabs.generative_ai_cdk_constructs import (
    bedrock 
)
import json
import datetime

class WafrGenaiAcceleratorStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, description="AWS Well-Architected Framework Review (WAFR) Acceleration with Generative AI (GenAI) sample. (uksb-ig1li00ta6)", **kwargs)
        
        entryTimestampRaw = datetime.datetime.now()
        entryTimestamp = entryTimestampRaw.strftime("%Y%m%d%H%M")
        entryTimestampLabel = entryTimestampRaw.strftime("%Y-%m-%d-%H-%M")
        
        #Creates Bedrock KB using the generative_ai_cdk_constructs. More info: https://github.com/awslabs/generative-ai-cdk-constructs
        kb = bedrock.KnowledgeBase(self, 'WAFR-KnowledgeBase', 
                    embeddings_model= bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V1,
                    instruction=  'Use this knowledge base to answer questions about AWS Well Architected Framework Review (WAFR).',
                    description= 'This knowledge base contains AWS Well Architected Framework Review (WAFR) reference documents'
                )
        
        KB_ID = kb.knowledge_base_id

        # Create a bucket for server access logs
        accessLogsBucket = s3.Bucket(self, 'wafr-accelerator-access-logs',
            bucket_name=f"wafr-accelerator-s3-access-logs-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            access_control=s3.BucketAccessControl.LOG_DELIVERY_WRITE)

        #Create S3 bucket where well architected reference docs are stored 
        #S3 bucket for the knowledge base - name of stack followed by well-architected-knowledge-base-analytics
        wafrReferenceDocsBucket = s3.Bucket(self, 
            'wafr-accelerator-kb', 
            bucket_name=f"wafr-accelerator-kb-{entryTimestamp}",
            enforce_ssl=True,
            server_access_logs_bucket=accessLogsBucket,
            server_access_logs_prefix="wafr-reference-docs-logs/",
            removal_policy=RemovalPolicy.DESTROY, 
            auto_delete_objects=True)

        WAFR_REFERENCE_DOCS_BUCKET = wafrReferenceDocsBucket.bucket_name

        #Uploading WAFR docs to the corresponding S3 bucket [wafrReferenceDocsBucket]
        wafrReferenceDeploy = s3deploy.BucketDeployment(self, "uploadwellarchitecteddocs",
            sources=[s3deploy.Source.asset('well_architected_docs')],
            destination_bucket=wafrReferenceDocsBucket
        )
        
        #S3 Bucket where customer design is stored
        userUploadBucket = s3.Bucket(self, 
            'wafr-accelerator-upload',
            bucket_name=f"wafr-accelerator-upload-{entryTimestamp}",
            enforce_ssl=True,
            server_access_logs_bucket=accessLogsBucket,
            server_access_logs_prefix="wafr-upload-docs-logs/",
            removal_policy=RemovalPolicy.DESTROY, 
            auto_delete_objects=True)
        
        UPLOAD_BUCKET_NAME = userUploadBucket.bucket_name
              
        DEAD_LETTER_QUEUE_UNIQUE_NAME = "wafrAcceleratorDeadLetterQueue-" + entryTimestamp
        WAFR_ACCELERATOR_QUEUE_UNIQUE_NAME = "wafrAcceleratorQueue-" + entryTimestamp
        
        # Create a dead-letter queue
        wafrAcceleratorDeadLetterQueue = sqs.Queue(
            self,
            "WAFRAcceleratorDeadLetterQueue",
            queue_name=DEAD_LETTER_QUEUE_UNIQUE_NAME,
            encryption=sqs.QueueEncryption.KMS_MANAGED,  # Use the AWS-managed KMS key for SQS
            enforce_ssl=True
        )
        
        # Create the main queue with a dead-letter queue
        wafrAcceleratorQueue = sqs.Queue(
            self,
            "WAFRAcceleratorQueue",
            queue_name=WAFR_ACCELERATOR_QUEUE_UNIQUE_NAME,
            visibility_timeout=Duration.minutes(20),
            retention_period=Duration.days(4),
            delivery_delay=Duration.seconds(5),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=wafrAcceleratorDeadLetterQueue,
            ),
            encryption=sqs.QueueEncryption.KMS_MANAGED,  # Use the AWS-managed KMS key for SQS
            enforce_ssl=True
        )
        
        #Create DynamoDB table for tracking WAFR accelerator runs
        wafrRunsTable = dynamodb.TableV2(self, "review-runs",
            table_name=f"wafr-reviewruns-{entryTimestamp}",
            partition_key=dynamodb.Attribute(
                name="analysis_id", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(
                    name="analysis_submitter", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY
        )
        
                                
        WAFR_RUNS_TABLE = wafrRunsTable.table_name

        #Adds the created S3 bucket [docBucket] as a Data Source for Bedrock KB
        kbDataSource = bedrock.S3DataSource(self, 'DataSource',
            bucket= wafrReferenceDocsBucket,
            knowledge_base=kb,
            data_source_name='wafr-reference-docs',
            chunking_strategy = bedrock.ChunkingStrategy.FIXED_SIZE,
            max_tokens=500,
            overlap_percentage=20
        )
        
        # Data Ingestion Params
        dataSourceIngestionParams = {
            "dataSourceId": kbDataSource.data_source_id,
            "knowledgeBaseId": KB_ID,
        }
        
         # Define a custom resource to make an AwsSdk startIngestionJob call. This will do an initial sync of the S3 bucket [docBucket].    
        ingestion_job_cr = cr.AwsCustomResource(self, "IngestionCustomResource",
            on_create=cr.AwsSdkCall(
                service="bedrock-agent",
                action="startIngestionJob",
                parameters=dataSourceIngestionParams,
                physical_resource_id=cr.PhysicalResourceId.of("Parameter.ARN")
                ),
                policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                    resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
        )
        
        #Create DynamoDB table for tracking WAFR accelerator runs 
        wafrPillarQuestionPromptsTable = dynamodb.TableV2(self, "wafr-pillar-question-prompts",
            table_name=f"wafr-pillar-question-prompts-{entryTimestamp}",
            partition_key=dynamodb.Attribute(
                name="wafr_lens", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name="wafr_pillar", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=RemovalPolicy.DESTROY
            )
        
        WAFR_PILLAR_QUESTIONS_PROMPT_TABLE = wafrPillarQuestionPromptsTable.table_name
        
        # Create an IAM role for the insertWafrPromptsFunctionRole Lambda function
        insertWafrPromptsFunctionRole = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        insertWafrPromptsFunction = _lambda.Function(self, "insertWAFRPrompts",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code = _lambda.Code.from_asset("lambda_dir/insert_wafr_prompts"), 
            handler="insert_wafr_prompts.lambda_handler",
            timeout=cdk.Duration.seconds(30),
            memory_size=128,
            environment={
                "DD_TABLE_NAME": WAFR_PILLAR_QUESTIONS_PROMPT_TABLE,
                "REGION_NAME": Stack.of(self).region
            },
            role = insertWafrPromptsFunctionRole
        )
        
        wafrPillarQuestionPromptsTable.grant_write_data(insertWafrPromptsFunction)
        wafrPillarQuestionPromptsTable.grant_read_data(insertWafrPromptsFunction)
        
        promptsBucket = s3.Bucket(self, 'wafr-prompts',
            bucket_name=f"wafr-prompts-{entryTimestamp}", 
            removal_policy=RemovalPolicy.DESTROY, 
            enforce_ssl=True,
            server_access_logs_bucket=accessLogsBucket,
            server_access_logs_prefix="wafr-prompts-logs/",
            auto_delete_objects=True)
            
        promptsBucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(insertWafrPromptsFunction)
        )
        promptsBucket.grant_put(insertWafrPromptsFunction)
        promptsBucket.grant_read(insertWafrPromptsFunction)

        #Upload bucket for Uploading WAFR docs to the corresponding S3 bucket [docBucket]
        promptsBucketDeploy = s3deploy.BucketDeployment(self, "promptsBucketDeploy",
            sources=[s3deploy.Source.asset('wafr-prompts')],
            destination_bucket=promptsBucket
        )
        
        # Create VPC
        vpc = ec2.Vpc(self, "StreamlitAppVPC-" + entryTimestamp,
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="Private",
                    cidr_mask=24
                )
            ]
        )
        
        # Create Security Group
        ec2_security_group = ec2.SecurityGroup(self, "StreamlitAppSG" +entryTimestamp,
            vpc=vpc,
            description="Security group for Streamlit app",
            allow_all_outbound=True
        )
                     
    
        # Create IAM role for EC2 instance
        ec2Role = iam.Role(self, "StreamlitAppRole-" + entryTimestamp,
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ],
            inline_policies={
                "ec2RolePolicies": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:Query"],
                            resources=[
                                wafrPillarQuestionPromptsTable.table_arn,
                                wafrRunsTable.table_arn
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": self.account
                                }
                            },
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                f"arn:aws:s3:::wafr-prompts-{entryTimestamp}/*",
                                f"arn:aws:s3:::wafr-accelerator-ui-{entryTimestamp}",
                                f"arn:aws:s3:::wafr-accelerator-ui-{entryTimestamp}/*",
                                f"arn:aws:s3:::wafr-accelerator-upload-{entryTimestamp}/*"
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": self.account
                                }
                            },
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
                            ],
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:Retrieve"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{KB_ID}",
                                f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{KB_ID}/*"
                            ],
                            effect=iam.Effect.ALLOW
                        ),
                        
                        iam.PolicyStatement(
                            actions=[
                                "sqs:SendMessage",
                                "sqs:ReceiveMessage",
                                "sqs:DeleteMessage",
                                "sqs:GetQueueAttributes",
                                "sqs:GetQueueUrl"
                            ],
                            resources=[
                                f"arn:aws:sqs:{self.region}:{self.account}:{DEAD_LETTER_QUEUE_UNIQUE_NAME}",
                                f"arn:aws:sqs:{self.region}:{self.account}:{WAFR_ACCELERATOR_QUEUE_UNIQUE_NAME}"
                            ],
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ssm:GetParameter",
                                "ssm:GetParameters",
                                "ssm:GetParametersByPath",
                                "ssm:PutParameter",
                                "ssm:DeleteParameter",
                                "ssm:DeleteParameters",
                                "ssm:DescribeParameters",
                                "ssm:LabelParameterVersion"
                            ],
                            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/wafr-accelerator/*"]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "textract:StartDocumentAnalysis",
                                "textract:StartDocumentTextDetection",
                                "textract:GetDocumentAnalysis",
                                "textract:GetDocumentTextDetection"
                            ],
                            resources=["*"]  
                        ),
                        iam.PolicyStatement(
                        actions=[
                            "wellarchitected:CreateWorkload",
                            "wellarchitected:UpdateWorkload",
                            "wellarchitected:UpdateAnswer",
                            "wellarchitected:GetAnswer",
                            "wellarchitected:ListAnswers",
                            "wellarchitected:ListLensReviewImprovements",
                            "wellarchitected:ListWorkloads"
                        ],
                        resources=["*"]  
                        )
                    ]
                )
            }
        )
        
        #Reading user_data_script.sh file which contains the linux commands that must be run when the EC2 boots up.
        with open("user_data_script.sh", "r", encoding='UTF-8') as f:
            user_data_script = f.read()
        
        user_data_script = re.sub(r'{{REGION}}', Stack.of(self).region, user_data_script)
  
        ec2_create = ec2.Instance(self, "StreamlitAppInstance-" + entryTimestamp,
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=ec2_security_group,
            role=ec2Role,
            associate_public_ip_address=False,  # This disables public IPv4
            #detailed_monitoring=True,
            user_data=ec2.UserData.custom(user_data_script),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=8,  # Size in GB
                        encrypted=True,
                        delete_on_termination=True  # Optional: delete the volume when the instance is terminated
                    )
                )
            ]
        )

        EC2_INSTANCE_ID = ec2_create.instance_id
        
        alb_security_group = ec2.SecurityGroup(self, "ALBSecurityGroup-" + entryTimestamp,
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for ALB"
        )
        
        # us-east-1: PrefixList: pl-3b927c52
        # us-east-2: PrefixList: pl-b6a144df
        # us-west-1: PrefixList: pl-4ea04527
        # us-west-2: PrefixList: pl-82a045eb
        alb_security_group.add_ingress_rule(
            ec2.Peer.prefix_list("pl-82a045eb"),
            ec2.Port.HTTP,
            "Allow inbound connections only from Cloudfront to Streamlit port"
        )
        
        # Create ALB
        alb = elbv2.ApplicationLoadBalancer(
            self, 'StreamlitAppALB-' + entryTimestamp,
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group
        )
        
        # Enable access logging after ALB creation
        alb.log_access_logs(
            bucket=accessLogsBucket,
            prefix='ec2-alb-logs'  # Optional: Specify a prefix for your log files,
        )
            
        instance_target = elasticloadbalancingv2_targets.InstanceTarget(ec2_create, 8501)
        
        # Create target group
        target_group = elbv2.ApplicationTargetGroup(
            self, "StreamlitAppTargetGroup-" + entryTimestamp,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[instance_target], 
            health_check=elbv2.HealthCheck(
                path="/",
                port="8501"
            ),
            vpc=vpc
        )
        # Add listener to ALB
        alb.add_listener(
            "Listener",
            port=80,
            default_target_groups=[target_group],
            open=False
        )
        
        # add access from ALB 
        ec2_security_group.add_ingress_rule(
            peer=alb_security_group,
            connection=ec2.Port.tcp(8501),
            description="Allow HTTP traffic from ALB"
        )
            
        #Print the Cloudfront Public Domain Name after CDK Deployment for easier access
        CfnOutput(
            self, "FrontEnd-EC2-Instance-Id",
            value=EC2_INSTANCE_ID,
            description="Front end UI EC2 instance id created at : " + entryTimestampLabel
        )
        
        # Create WAF WebACL
        waf_web_acl = wafv2.CfnWebACL(
            self, "WAFWebACL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="REGIONAL",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="WAFWebACL",
                sampled_requests_enabled=True
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="LimitRequests100",
                    priority=1,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=100,
                            aggregate_key_type="IP"
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="LimitRequests100",
                        sampled_requests_enabled=True
                    )
                )
            ]
        )
        wafv2.CfnWebACLAssociation(self, "WAFWebACLAssociation",
            resource_arn=alb.load_balancer_arn,
            web_acl_arn=waf_web_acl.attr_arn
        )
        
        # Uses ALB - Creating CloudFront CDN Distribution
        cdn = cloudfront.Distribution(self, 'CDN', 
            comment='CDK created distribution for AWS Well Architect Framework Review (WAFR) Accelerator',
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(alb, http_port=80, protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY),
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            ),
            enable_logging=True,
            log_bucket=accessLogsBucket,
            log_file_prefix='cloudfront-logs', 
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021 
        )
        
        cdn.apply_removal_policy(RemovalPolicy.DESTROY)
        
        #Print the Cloudfront Public Domain Name after CDK Deployment for easier access
        CfnOutput(
            self, "CloudFront-Distribution-Domain-Name",
            value="https://" + cdn.distribution_domain_name,
            description="The CloudFront Distribution Domain Name"
        )
        
        PARAMETER_COGNITO_USER_POOL_NAME = "WafrAcceleratorUserPool-" + entryTimestamp
    
        #add cognito user_pool
        user_pool = cognito.UserPool(self, PARAMETER_COGNITO_USER_POOL_NAME,
            user_pool_name="wafr-accelerator-user-pool-" + entryTimestamp,
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED
        )
    
        #Print the Cloudfront Public Domain Name after CDK Deployment for easier access
        CfnOutput(
            self, "Cognito-User-Pool-Name",
            value=PARAMETER_COGNITO_USER_POOL_NAME,
            description="Cognito user pool created at : " + entryTimestampLabel
        )        
        
        PARAMETER_COGNITO_USER_POOL_ID = user_pool.user_pool_id
              
        app_client = user_pool.add_client("WafrAcceleratorAppClient-" + entryTimestamp,
            user_pool_client_name="wafr-accelerator-app-client-" + entryTimestamp,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=[f"https://{cdn.distribution_domain_name}", "http://localhost:8501"]
            ),
            prevent_user_existence_errors=True
        )
        
        PARAMETER_COGNITO_USER_POOL_CLIENT_ID = app_client.user_pool_client_id
        
        uiPage1UpdateParameter = StringParameter(
            self, "uiPage1UpdateParameter-" + entryTimestamp,
            parameter_name="/wafr-accelerator/" + entryTimestamp + "/1_New_WAFR_Review-updated",
            string_value="False",
            description="1_New_WAFR_Review-updated status created at : " + entryTimestampLabel
        )
        
        PARAMETER_1_NEW_WAFR_REVIEW = uiPage1UpdateParameter.parameter_name
        
        uiPage2UpdateParameter = StringParameter(
            self, "uiPage2UpdateParameter-" + entryTimestamp,
            parameter_name="/wafr-accelerator/" + entryTimestamp + "/2_Existing_WAFR_Reviews-updated",
            string_value="False",
            description="2_Existing_WAFR_Reviews-updated status created at : " + entryTimestampLabel
        )
        
        PARAMETER_2_EXISTING_WAFR_REVIEWS = uiPage2UpdateParameter.parameter_name
        
        uiSyncFlagParameter = StringParameter(
            self, "uiSyncFlagParameter-" + entryTimestamp,
            parameter_name="/wafr-accelerator/" + entryTimestamp + "/uiSyncInitiatedFlag",
            string_value="False",
            description="uiSyncInitiatedFlag created at : " + entryTimestampLabel
        )
        
        PARAMETER_UI_SYNC_INITAITED_FLAG = uiSyncFlagParameter.parameter_name
        
        uiLoginPageParameter = StringParameter(
            self, "uiLoginPageParameter-" + entryTimestamp,
            parameter_name="/wafr-accelerator/" + entryTimestamp + "/uiLoginPageParameter",
            string_value="False",
            description="uiLoginPageParameter-updated status created at : " + entryTimestampLabel
        )
        
        PARAMETER_3_LOGIN_PAGE = uiLoginPageParameter.parameter_name
    
        
        # bucket for ui source code
        wafrUIBucket = s3.Bucket(self, 
            'wafr-accelerator-ui', 
            bucket_name=f"wafr-accelerator-ui-{entryTimestamp}", 
            removal_policy=RemovalPolicy.DESTROY, 
            enforce_ssl=True,
            server_access_logs_bucket=accessLogsBucket,
            server_access_logs_prefix="wafr-uibucket-logs/",
            auto_delete_objects=True)
        
        # Create an IAM role for the replaceUITokensFunctionRole Lambda function
        replaceUITokensFunctionRole = iam.Role(
            self, "replaceUITokensFunctionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "replaceUITokensFunctionRolePolicies": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject"
                            ],
                            resources=[
                                f"{wafrUIBucket.bucket_arn}/*"
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": self.account
                                }
                            },
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ssm:GetParameter",
                                "ssm:GetParameters",
                                "ssm:GetParametersByPath",
                                "ssm:PutParameter",
                                "ssm:DeleteParameter",
                                "ssm:DeleteParameters",
                                "ssm:DescribeParameters",
                                "ssm:LabelParameterVersion"
                            ],
                            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/wafr-accelerator/*"]
                        ),
                         iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:SendCommand",
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}::document/AWS-RunShellScript",
                                f"arn:aws:ec2:{self.region}:{self.account}:instance/{EC2_INSTANCE_ID}"
                            ]
                        ),
                         iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ssm:GetCommandInvocation" 
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.region}:{self.account}:*"
                            ]
                        )
                    ]
                )
            }
        )
        
        replaceUITokensFunction = _lambda.Function(self, "replaceUITokensFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code = _lambda.Code.from_asset("lambda_dir/replace_ui_tokens"), # Points to the lambda directory
            handler="replace_ui_tokens.lambda_handler",
            timeout=cdk.Duration.seconds(300),
            memory_size=128,
            environment={
                "WAFR_ACCELERATOR_QUEUE_URL": wafrAcceleratorQueue.queue_url,
                "WAFR_UI_BUCKET_NAME": wafrUIBucket.bucket_name,
                "WAFR_UI_BUCKET_ARN": wafrUIBucket.bucket_arn,
                "REGION_NAME": Stack.of(self).region,
                "WAFR_RUNS_TABLE": wafrRunsTable.table_name,
                "EC2_INSTANCE_ID": EC2_INSTANCE_ID,
                "UPLOAD_BUCKET_NAME" : UPLOAD_BUCKET_NAME,
                "PARAMETER_2_EXISTING_WAFR_REVIEWS" : PARAMETER_2_EXISTING_WAFR_REVIEWS,
                "PARAMETER_1_NEW_WAFR_REVIEW" : PARAMETER_1_NEW_WAFR_REVIEW,
                "PARAMETER_UI_SYNC_INITAITED_FLAG" : PARAMETER_UI_SYNC_INITAITED_FLAG,
                "PARAMETER_3_LOGIN_PAGE" : PARAMETER_3_LOGIN_PAGE, 
                "PARAMETER_COGNITO_USER_POOL_ID" : PARAMETER_COGNITO_USER_POOL_ID ,
                "PARAMETER_COGNITO_USER_POOL_CLIENT_ID" : PARAMETER_COGNITO_USER_POOL_CLIENT_ID,
            },
            role = replaceUITokensFunctionRole,
            events=[lambda_events.S3EventSource(bucket=wafrUIBucket, events=[s3.EventType.OBJECT_CREATED], filters=[s3.NotificationKeyFilter(prefix="tokenized-pages/", suffix=".py")])]
        )
                    
        #Uploading UI code to the corresponding S3 bucket [wafrReferenceDocsBucket]
        wafrUIBucketDeploy = s3deploy.BucketDeployment(self, "uploaduicode",
            sources=[s3deploy.Source.asset('ui_code')],
            destination_bucket=wafrUIBucket
        )
               
        # Create an IAM role for the startWafrReviewFunctionRole Lambda function
        startWafrReviewFunctionRole = iam.Role(
            self, "startWafrReviewFunctionRoleLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "startWafrReviewFunctionRolePolicies": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Scan", "dynamodb:Query"],
                            resources=[
                                wafrPillarQuestionPromptsTable.table_arn,
                                wafrRunsTable.table_arn
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": self.account
                                }
                            },
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject",
                                "s3:DeleteObject"
                            ],
                            resources=[
                                f"arn:aws:s3:::wafr-prompts-{entryTimestamp}/*",
                                f"arn:aws:s3:::wafr-accelerator-upload-{entryTimestamp}/*"
                            ],
                            conditions={
                                "StringEquals": {
                                    "aws:ResourceAccount": self.account
                                }
                            },
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
                            ],
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:Retrieve"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{KB_ID}",
                                f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{KB_ID}/*"
                            ],
                            effect=iam.Effect.ALLOW
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "sqs:SendMessage",
                                "sqs:ReceiveMessage",
                                "sqs:DeleteMessage",
                                "sqs:GetQueueAttributes",
                                "sqs:GetQueueUrl"
                            ],
                            resources=[
                                f"arn:aws:sqs:{self.region}:{self.account}:{DEAD_LETTER_QUEUE_UNIQUE_NAME}",
                                f"arn:aws:sqs:{self.region}:{self.account}:{WAFR_ACCELERATOR_QUEUE_UNIQUE_NAME}"
                            ]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "states:StartExecution",
                                "states:DescribeExecution",
                                "states:GetExecutionHistory"
                            ],
                            resources=[f"arn:aws:states:{self.region}:{self.account}:stateMachine:WAFRReviewStateMachine-{entryTimestamp}"]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "textract:StartDocumentAnalysis",
                                "textract:StartDocumentTextDetection",
                                "textract:GetDocumentAnalysis",
                                "textract:GetDocumentTextDetection"
                            ],
                            resources=["*"]  
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "wellarchitected:CreateWorkload",
                                "wellarchitected:UpdateWorkload",
                                "wellarchitected:UpdateAnswer",
                                "wellarchitected:GetAnswer",
                                "wellarchitected:ListAnswers",
                                "wellarchitected:ListLensReviewImprovements",
                                "wellarchitected:ListWorkloads",
                                "wellarchitected:GetLensReview"
                            ],
                            resources=["*"]  
                        )
                    ]
                )
            }
        )
        
        #Define Lambda functions
        prepare_wafr_review = _lambda.Function(self, "prepare_wafr_review",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="prepare_wafr_review.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/prepare_wafr_review"),
            timeout=cdk.Duration.minutes(5),
            memory_size=512,
            environment={
                "KNOWLEDGE_BASE_ID": KB_ID,
                "LLM_MODEL_ID": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "REGION": Stack.of(self).region, 
                "UPLOAD_BUCKET_NAME": userUploadBucket.bucket_name,
                "WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME": WAFR_RUNS_TABLE,
                "WAFR_PROMPT_DD_TABLE_NAME": WAFR_PILLAR_QUESTIONS_PROMPT_TABLE,
                "BEDROCK_SLEEP_DURATION" : "60",
                "BEDROCK_MAX_TRIES" : "5"
            },
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1
        )
        extract_document_text = _lambda.Function(self, "extract_document_text",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="extract_document_text.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/extract_document_text"),
            timeout=cdk.Duration.minutes(15),
            memory_size=256,
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1
        )
        generate_solution_summary = _lambda.Function(self, "generate_solution_summary",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="generate_solution_summary.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/generate_solution_summary"),
            timeout=cdk.Duration.minutes(15),
            memory_size=256,
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1
        )
        generate_prompts = _lambda.Function(self, "generate_prompts_for_all_the_selected_pillars",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="generate_prompts_for_all_the_selected_pillars.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/generate_prompts_for_all_the_selected_pillars"),
            timeout=cdk.Duration.minutes(15),
            memory_size=256,
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1,
            environment={
                "WAFR_REFERENCE_DOCS_BUCKET" : WAFR_REFERENCE_DOCS_BUCKET
            }
        )
        generate_pillar_question_response = _lambda.Function(self, "generate_pillar_question_response",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="generate_pillar_question_response.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/generate_pillar_question_response"),
            timeout=cdk.Duration.minutes(15),
            memory_size=256,
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1,
            environment={
                "BEDROCK_SLEEP_DURATION" : "60",
                "BEDROCK_MAX_TRIES" : "5"
            }
        )
        update_review_status = _lambda.Function(self, "update_review_status",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="update_review_status.lambda_handler",
            code=_lambda.Code.from_asset("lambda_dir/update_review_status"),
            timeout=cdk.Duration.minutes(15),
            memory_size=256,
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1
        )

        # Create an IAM role for the Step Function
        step_function_role = iam.Role(
            self, "WAFRStepFunctionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            inline_policies={
                "StepFunctionRolePolicies": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/vendedlogs/states/*"],
                            effect=iam.Effect.ALLOW
                        )
                    ]
                )
            }
        )

        # Grant the Step Function role permission to invoke the Lambda functions
        prepare_wafr_review.grant_invoke(step_function_role)
        extract_document_text.grant_invoke(step_function_role)
        generate_solution_summary.grant_invoke(step_function_role)
        generate_prompts.grant_invoke(step_function_role)
        generate_pillar_question_response.grant_invoke(step_function_role)
        update_review_status.grant_invoke(step_function_role)
        
        # Define Step Function tasks
        pass_state = sfn.Pass(
            self, "Pass",
            result=sfn.Result.from_object({"InitializeWAFRReview": True}),
            result_path=sfn.JsonPath.DISCARD
        )

        prepare_wafr_review_task = tasks.LambdaInvoke(
            self, "Prepare WAFR review",
            lambda_function=prepare_wafr_review,
            output_path="$.Payload.body"
        )
        extract_document_text_task = tasks.LambdaInvoke(
            self, "Extract document text",
            lambda_function=extract_document_text,
            output_path="$.Payload.body"
        )
        generate_solution_summary_task = tasks.LambdaInvoke(
            self, "Generate solution summary",
            lambda_function=generate_solution_summary,
            output_path="$.Payload.body"
        )
        generate_prompts_task = tasks.LambdaInvoke(
            self, "Generate prompts for selected pillars",
            lambda_function=generate_prompts,
            output_path="$.Payload.body"
        )
        generate_pillar_question_response_task = tasks.LambdaInvoke(
            self, "Generate pillar question response",
            lambda_function=generate_pillar_question_response,
            output_path="$.Payload.body"
        )
        update_review_status_task = tasks.LambdaInvoke(
            self, "Mark review as complete",
            lambda_function=update_review_status,
            output_path="$.Payload"
        )

        wait_state = sfn.Wait(
            self, "Wait", 
            time=sfn.WaitTime.duration(cdk.Duration.seconds(40))
        )
     
        # Define the Map state
        map_state = sfn.Map(
            self, "Loop through selected pillars",
            max_concurrency=1,
            items_path="$.all_pillar_prompts"
        )
        
        # Define the iterator chain
        iterator_chain = sfn.Chain \
            .start(wait_state) \
            .next(generate_pillar_question_response_task)
        
        # Set the iterator
        map_state.iterator(iterator_chain)

        # Create a log group for the Step Function
        wafr_stepmachine_log_group = aws_logs.LogGroup(
            self, "WAFRReviewStateMachineLogGroup",
            retention=aws_logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY 
        )

        # Define the chain of states
        chain = sfn.Chain \
            .start(pass_state) \
            .next(prepare_wafr_review_task) \
            .next(extract_document_text_task) \
            .next(generate_solution_summary_task) \
            .next(generate_prompts_task) \
            .next(map_state) \
            .next(update_review_status_task)

        # Create the state machine using definitionBody instead of definition
        state_machine = sfn.StateMachine(
            self, "WAFRReviewStateMachine",
            state_machine_name=f"WAFRReviewStateMachine-{entryTimestamp}",
            removal_policy=RemovalPolicy.DESTROY,
            definition_body=sfn.DefinitionBody.from_chainable(chain),
            timeout=cdk.Duration.seconds(6000),
            role=step_function_role,
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=wafr_stepmachine_log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=False
            )
        )        
        
        startWafrReviewFunction = _lambda.Function(self, "startWafrReview",
            runtime=_lambda.Runtime.PYTHON_3_12,
            code = _lambda.Code.from_asset("lambda_dir/start_wafr_review"), # Points to the lambda directory
            handler="start_wafr_review.lambda_handler",
            timeout=cdk.Duration.minutes(15),
            memory_size=512,
            environment={
                "KNOWLEDGE_BASE_ID": KB_ID,
                "LLM_MODEL_ID": "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "REGION": Stack.of(self).region,
                "UPLOAD_BUCKET_NAME": userUploadBucket.bucket_name,
                "WAFR_ACCELERATOR_RUNS_DD_TABLE_NAME": WAFR_RUNS_TABLE,
                "WAFR_PROMPT_DD_TABLE_NAME": WAFR_PILLAR_QUESTIONS_PROMPT_TABLE,
                "START_WAFR_REVIEW_STATEMACHINE_ARN": state_machine.state_machine_arn,
                "BEDROCK_SLEEP_DURATION" : "60",
                "BEDROCK_MAX_TRIES" : "5",
                "WAFR_REFERENCE_DOCS_BUCKET" : WAFR_REFERENCE_DOCS_BUCKET
            },
            role = startWafrReviewFunctionRole,
            reserved_concurrent_executions=1
        )

        wafrPillarQuestionPromptsTable.grant_write_data(startWafrReviewFunction)
        wafrRunsTable.grant_write_data(startWafrReviewFunction)
        
        # Grant the Lambda function permission to access the SQS queue
        wafrAcceleratorQueue.grant_consume_messages(startWafrReviewFunction)
        
        sqs_event_source = lambda_event_source.SqsEventSource(wafrAcceleratorQueue, batch_size=1 )#, maximum_concurrency = 2 )
        
        # Create the SQS event source with maximum concurrency set to 2
        startWafrReviewFunction.add_event_source(sqs_event_source)
        
        # # ------------ Node dependencies ---------------------
        kbDataSource.node.add_dependency(wafrReferenceDocsBucket)
        ingestion_job_cr.node.add_dependency(kb)
        
        ec2_create.node.add_dependency(kb)

        ec2Role.node.add_dependency(vpc)
        ec2_create.node.add_dependency(ec2Role)
        alb.node.add_dependency(ec2_create)
        target_group.node.add_dependency(ec2_create)
        cdn.node.add_dependency(alb)

        wafrUIBucketDeploy.node.add_dependency(replaceUITokensFunction)
        
        wafrUIBucketDeploy.node.add_dependency(ec2_create)
        
        startWafrReviewFunction.node.add_dependency(state_machine)
        startWafrReviewFunction.node.add_dependency(ec2_create)
        
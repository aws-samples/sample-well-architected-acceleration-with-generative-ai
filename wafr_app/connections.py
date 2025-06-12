import os


class Connections:
    SQS_QUEUE_NAME = os.getenv("SQS_QUEUE_NAME", "")
    REGION_NAME = os.getenv("REGION_NAME", "")
    WAFR_RUNS_TABLE = os.getenv("WAFR_RUNS_TABLE", "")
    UPLOAD_BUCKET_NAME = os.getenv("UPLOAD_BUCKET_NAME", "")
    SSM_PARAMETER_COGNITO_APP_CLIENT_ID = os.getenv(
        "SSM_PARAMETER_COGNITO_USER_POOL_CLIENT_ID", ""
    )
    GUARDRAIL_ID = os.getenv(
        "GUARDRAIL_ID", ""
    )

# Security and Compliance Considerations

## TLS 1.2 enforcement
To enforce TLS 1.2 for compliance requirements:
- Create a custom SSL/TLS certificate
- Disable SSL 3.0 and TLS 1.0
- Enable TLS 1.2 or higher
- Implement strong cipher suites

## Multi-Factor Authentication (MFA)
To implement MFA:
- Add MFA to your Cognito user pool
- Follow the [AWS Cognito MFA setup guide](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa.html)

## VPC Flow Logs
To enable VPC flow logs:
- Follow the instructions in the [AWS Knowledge Center guide](https://repost.aws/knowledge-center/saw-activate-vpc-flow-logs)
- Monitor and analyze network traffic
- Ensure proper logging configuration

## IAM permission for Well Architected Tool
Currently the IAM policies for Well Architected tool uses wildcard (*) as the target resource. This is because the sample
requires full access to Well Architected Tool to create new workloads, update workloads as analysis progresses and read existing workload names to avoid duplicate workload creation: [AWS Well-Architected Tool identity-based policy examples](https://docs.aws.amazon.com/wellarchitected/latest/userguide/security_iam_id-based-policy-examples.html )

## Size of the text extracted from the uploaded document
The extracted document content alongside the rest of analysis and associated information is stored in the same DynamoDB item. The maximum Dynamo DB item size is 400KB. Hence uploading an extra long document may exceed this limit.

## Important note
⚠️ When reviewing model-generated analysis:
- Always verify the responses independently
- Remember that LLM outputs are not deterministic
- Cross-reference with official AWS documentation
- Validate against your specific use case requirements
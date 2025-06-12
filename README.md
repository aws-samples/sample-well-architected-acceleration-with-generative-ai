# Sample AWS Well-Architected Review (WAFR) Acceleration with Generative AI (GenAI)


This is a comprehensive sample designed to facilitate and expedite the AWS Well-Architected Framework Review process. 

This sample aims to accelerate AWS Well-Architected Framework Review (WAFR) velocity and adoption by leveraging the power of generative AI to provide organizations with automated comprehensive analysis and recommendations for optimizing their AWS architectures.

## Core Features

* Ability to upload technical content (for example solution design and architecture documents) to be reviewed in PDF format<br/> 
* Creation of architecture assessment including:
	* Solution summary
	* Assessment
	* Well-Architected best practices
	* Recommendations for improvements
	* Risk
	* Ability to chat with the document as well as generated content
* Creation of Well-Architected workload in Well-Architected tool that has:
	* Initial selection of choices for each of the question based on the assessment.
	* Notes populated with the generated assessment.

## Optional / Configurable Features

* [Amazon Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/) - initial set of Amazon Bedrock Guardrail configurations for Responsible AI. 
	* Default - Enabled

_* Note: The above list of features can be individually enabled and disabled by updating the 'optional_features' JSON object in 'app.py' file._

## Technical Architecture

 ![WAFR Accelerator System Architecture Diagram](sys-arch.png)<br/> 

## Folder and Files

* The `lambda_dir` contains the Amazon Lambda Python code files for the multiple Amazon Lambdas that are used in the Amazon Step Function state machine.

* The `wafr_app` folder is the front end application as a container.

* The `wafr_genai_accelerator` folder contains the AWS CDK file `wafr_genai_accelerator_stack.py` used to generate the Amazon resources.

* The `wafr-prompts` folder contains the prompts used by the AI.

* The `well_architected_docs` folder contains the Amazon Well-Architected Framework .pdf files that are uploaded to S3 to be used by the Amazon Bedrock model. To refresh the documents with the latest releases of the Well-Architected Framework run the `download_pdf_files.sh` script and then:<br/> 
	1.	Upload the files to the knowledge base bucket created by the stack, adhering to the folder structure and file names.<br/> 
	2.	On AWS management console go to Amazon Bedrock -> Knowledge bases -> Click on the knowledge base created by the stack-> Data Source -> Sync. This will re-sync the knowledge base from the S3 bucket.


## Set up

### Pre-requisites
* Ensure you have access to the following models in Amazon Bedrock:
	* Titan Text Embeddings V2
	* Claude 3-5 Sonnet (not possible in eu-west-2)
	* Claude 3 Sonnet (for eu-west-2)

* Install the AWS CDK

```
npm install -g aws-cdk
```

* Install Podman or Docker:
	* For Podman have to install the tool, download a VM and start it.

```
brew install podman
```
```
podman machine init
```
```
podman machine start --log-level debug
```

* Update the AWS CDK source files if change the AWS Region or AWS account number. Open the `app.py` file, pick one of the following lines based on your deployment location:

```
#env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
```
Or
```
#env=cdk.Environment(account='*********', region='us-west-2'),
```

### CDK Deployment 

Manually create a virtualenv on MacOS and Linux:

```
python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
pip3 install -r requirements.txt
```    

* Export this command when create a new Terminal screen if using Podman:

```
export CDK_DOCKER=podman
```

* If you are deploying AWS CDK for the first time in the AWS account, run the below command (if not, skip this step):

```
cdk bootstrap
```

* At this point you can now synthesize the CloudFormation template for this code.

```
cdk synth
```

* You can now deploy the CDK stack:

```
cdk deploy
```

**You will need to enter 'y' to confirm the deployment. The deployment can take around 20-25 minutes to complete.**

The first time running Podman and AWS CDK it will take some time to download the necessary images locally.

On the cdk build completion, you would see three outputs:
	a) Amazon Cognito user pool name.
	b) ECS Fargate ALB URL.
	c) Amazon Cloudfront URL for the web application.

### Add a user to Amazon Cognito user pool

[Manually add a new user to the Amazon Cognito pool](https://docs.aws.amazon.com/cognito/latest/developerguide/how-to-create-user-accounts.html#creating-a-new-user-using-the-console) indicated in the output. You would use this user credentials for application login later on. 

### Run the Web Application

The Frontend is hosted via the ECS Fargate. It uses Streamlit. Streamlit converts Python files into a Frontend UI. 

You can now use either the ECS Fargate ALB URL or the Amazon Cloudfront URL from the CDK output to access the sample application in a web browser.

### Testing the demo application

Open a new web browser window and copy the Amazon Cloudfront URL copied earlier into the address bar. On the login page, enter the user credentials for the previously created user.<br/>
<br/> 
![Login page](graphics/loginpage.png)<br/> 
<br/> 
On home page, click on the "New WAFR Review" link.
<br/> <br/>
![Welcome page](graphics/home.png)<br/> 
<br/> 
On "Create New WAFR Analysis" page, select the analysis type ("Quick" or "Deep with Well-Architected Tool") and provide analysis name, description, Well Architectd lens, etc. in the input form. <br/>
<br/> 
**Analysis Types**:<br/>
* **"Quick"** - quick analysis without the creation of workload in the AWS Well-Architected tool. Relatively faster as it groups all questions for an individual pillar into a single prompt; suitable for initial assessment. 
* **"Deep with Well-Architected Tool"** - robust and deep analysis that also creates workload in the AWS Well-Architected tool. Takes longer to complete as it doesn't group questions and responses are generated for every question individually. This takes longer to execute. 

![Create new WAFR analysis page](graphics/createnew.png)

* Note: "Created by" field is automatically populated with the logged user name.
  
You have an option to select one or more Well-Architected pillars. <br/><br/>Finally upload the solution architecture / technical design document that needs to be analysed and press the "Create WAFR Analysis" button.<br/> 
<br/> 
Post successful submission, navigate to the "Existing WAFR Reviews" page. The newly submitted analysis would be listed in the table along with any existing reviews. <br/> <br/> 
![Existing WAFR reviews](graphics/existing.png)<br/> 

Once the analysis is marked "Completed", the WAFR analysis for the selected lens would be shown at the bottom part of the page. If there are multiple reviews, then select the relevant analysis from the combo list. 
<br/>

![Create new WAFR analysis page](graphics/output.png)<br/> 

* Note: Analysis duration varies based on the Analysis Type ("Quick" or "Deep with Well-Architected Tool") and number of WAFR Pillars selected. A 'Quick' analysis type with one WAFR pillar is likely to be much quicker than "Deep with Well-Architected Tool" analysis type with all the six WAFR Pillars selected.<br/> 
* Note: Only the questions for the selected Well-Architected lens and pillars are answered. <br/>

To chat with the uploaded document as well as any of the generated content by using the "WAFR Chat" section at the bottom of the "Existing WAFR Reviews" page.
<br/>

![WAFR chat](graphics/chat.png)<br/> 
<br/> 

## Uninstall the AWS CDK deployment

If you no longer need the application or would like to delete the CDK deployment, run the following command:

```
cdk destroy
```

**Once started there is a manual step to enter 'y' to continue the deployment.**

If one of the S3 Bucket contains any objects the destroy command can fail. Manually remove the objects and re-run the command.

## Additional considerations

Please see [Additional Considerations](Additional%20Considerations.md)


## Disclaimer
This is a sample code, for non-production usage. You should work with your security and legal teams to meet your organizational security, regulatory and compliance requirements before deployment.


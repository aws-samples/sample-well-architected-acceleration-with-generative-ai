## Refreshing Amazon Bedrock Knowledge Base with the latest AWS Well-Architected Reference Documents 

### Purging the old version

* In the AWS Management Console, go to CloudFormation -> Stacks -> Click on the 'WellArchitectedReviewUsingGenAIStack' stack and navigate to the 'Resources' tab.
* Under the Resources tab, identify the knowledge base S3 bucket by searching for 'wafr-accelerator-kb'.
* Delete all files and subfolders within the identified S3 bucket.

### AWS Well-Architected reference documents locations

* **[AWS Well-Architected Framework Overview](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/framework/wellarchitected-framework.pdf):** (create 'overview' subfolder and place the PDF file in it)

* **AWS Well-Architected Framework pillar documents:** (create 'wellarchitected' subfolder and place the PDF file in it)
 
	* [Operational Excellence](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/operational-excellence-pillar/wellarchitected-operational-excellence-pillar.pdf)
	* [Security](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/security-pillar/wellarchitected-security-pillar.pdf)
	* [Reliability](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/reliability-pillar/wellarchitected-reliability-pillar.pdf)
	* [Performance efficiency](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/performance-efficiency-pillar/wellarchitected-performance-efficiency-pillar.pdf)
	* [Cost optimization](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/cost-optimization-pillar/wellarchitected-cost-optimization-pillar.pdf)
	* [Sustainability](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/sustainability-pillar/wellarchitected-sustainability-pillar.pdf)

Repeat the above for:<br/>
 
* **[Financial Services Industry Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/financial-services-industry-lens/wellarchitected-financial-services-industry-lens.pdf)** Create 'financialservices' subfolder and place the PDF file in it. 

* **[Data Analytics Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/analytics-lens/analytics-lens.pdf)**  Create 'dataanalytics' subfolder and place the PDF file in it. 

* **[Generative AI Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/generative-ai-lens/generative-ai-lens.pdf)**  Create 'genai' subfolder and place the PDF file in it.  

*Note: At present, only the above Well-Architected lenses are supported.*
  
### Preparing and populating Amazon Bedrock Knowledge Base with AWS Well-Architected Reference Documents

The Amazon Bedrock knowledge base is driven by AWS Well-Architected documents. Download the documents in PDF format and place them in their respective subfolders in the S3 bucket. You need to create individual subfolders within S3 before uploading the files. 

+---**well_architected_docs**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+---**dataanalytics**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|       analytics-lens.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+---**financialservices**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|       wellarchitected-financial-services-industry-lens.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+---**genai**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|       generative-ai-lens.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+---**overview**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|       wellarchitected-framework.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;+---**wellarchitected**<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-cost-optimization-pillar.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-operational-excellence-pillar.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-performance-efficiency-pillar.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-reliability-pillar.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-security-pillar.pdf<br/> 
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|        wellarchitected-sustainability-pillar.pdf<br/> 
 <br/> 


### Re-sync the knowledge base Preparing and populating Amazon Bedrock Knowledge Base with AWS Well-Architected Reference Documents

* In the AWS Management Console, go to Amazon Bedrock -> Knowledge bases -> Click on the knowledge base created by the stack -> Data Source -> Sync. This will re-sync the knowledge base from the S3 bucket. <br/> 
  
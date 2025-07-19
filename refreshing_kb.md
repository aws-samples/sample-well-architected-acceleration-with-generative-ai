## Refreshing Amazon Bedrock Knowledge Base with the latest AWS Well-Architected Reference Documents 

### Purging the old version

* On AWS management console, go to CloudFormation -> Stacks -> Click on the 'WellArchitectedReviewUsingGenAIStack' stack and navigate to 'Resources' tab.
* Under Resources tab, identify the knowledge base S3 bucket by searching for 'wafr-accelerator-kb'
* Delete all the files and subfolders within the identified S3 bucket.

### AWS Well-Architected reference documents locations

* **[AWS Well-Architected Framework Overview](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/framework/wellarchitected-framework.pdf):** (create 'overview' subfolder and uploaded the PDF file underneath it)

* **AWS Well-Architected Framework pillar documents:** (create 'wellarchitected' subfolder and uploaded the PDF file underneath it)
 
	* [Operational Excellence](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/operational-excellence-pillar/wellarchitected-operational-excellence-pillar.pdf)
	* [Security](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/security-pillar/wellarchitected-security-pillar.pdf)
	* [Reliability](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/reliability-pillar/wellarchitected-reliability-pillar.pdf)
	* [Performance efficiency](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/performance-efficiency-pillar/wellarchitected-performance-efficiency-pillar.pdf)
	* [Cost optimization](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/cost-optimization-pillar/wellarchitected-cost-optimization-pillar.pdf)
	* [Sustainability](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/sustainability-pillar/wellarchitected-sustainability-pillar.pdf)

Repeat the above for:<br/>
 
* **[Financial Services Industry Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/financial-services-industry-lens/wellarchitected-financial-services-industry-lens.pdf)** Create 'financialservices' subfolder and place the PDF file underneath it. 

* **[Data Analytics Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/analytics-lens/analytics-lens.pdf)**  Create 'dataanalytics' subfolder and place the PDF file underneath it. 

* **[Generative AI Lens:](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/generative-ai-lens/generative-ai-lens.pdf)**  Create 'genai' subfolder and place the PDF file underneath it.  

*Note: At present, only the above Well-Architected lenses are supported.*
  
### Preparing and populating Amazon Bedrock Knowledge Base with AWS Well-Architected Reference Documents

Amazon Bedrock knowledge base is driven by the AWS Well-Architected documents. Download the documents in the PDF format and put them under respective subfolders in the S3 bucket. You would need to create the individual subfolders within S3 before uploading the files. 
 <br/>  
 +---dataanalytics<br/> 
|       analytics-lens.pdf<br/> 
|<br/> 
+---financialservices<br/> 
|       wellarchitected-financial-services-industry-lens.pdf<br/> 
|<br/> 
+---genai<br/> 
|       wellarchitected-financial-services-industry-lens.pdf<br/> 
|<br/> 
+---overview<br/> 
|       wellarchitected-framework.pdf<br/> 
|<br/> 
+---wellarchitected<br/> 
|        wellarchitected-cost-optimization-pillar.pdf<br/> 
|        wellarchitected-operational-excellence-pillar.pdf<br/> 
|        wellarchitected-performance-efficiency-pillar.pdf<br/> 
|        wellarchitected-reliability-pillar.pdf<br/> 
|        wellarchitected-security-pillar.pdf<br/> 
|        wellarchitected-sustainability-pillar.pdf<br/> 
 <br/> 


### Re-sync the knowledge base Preparing and populating Amazon Bedrock Knowledge Base with AWS Well-Architected Reference Documents

* On AWS management console, go to Amazon Bedrock -> Knowledge bases -> Click on the knowledge base created by the stack-> Data Source -> Sync. This will re-sync the knowledge base from the S3 bucket. <br/> 

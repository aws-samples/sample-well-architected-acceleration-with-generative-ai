#!/bin/bash
# Check output in /var/log/cloud-init-output.log
export AWS_DEFAULT_REGION={{REGION}}
max_attempts=5
attempt_num=1
success=false
#Adding the while loop since getting "RPM: error: can't create transaction lock on /var/lib/rpm/.rpm.lock (Resource temporarily unavailable)" frequently
while [ $success = false ] && [ $attempt_num -le $max_attempts ]; do
  echo "Trying to install required modules..."
  yum update -y
  yum install -y python3-pip
  yum remove -y python3-requests
  pip3 install boto3 awscli streamlit streamlit-authenticator numpy python-dotenv 
  pip3 install streamlit 
  pip3 install streamlit-authenticator 
  # Check the exit code of the command
  if [ $? -eq 0 ]; then
    echo "Installation succeeded!"
    success=true
  else
    echo "Attempt $attempt_num failed. Sleeping for 10 seconds and trying again..."
    sleep 10
    ((attempt_num++))
  fi
done

sudo mkdir -p /wafr-accelerator && cd /wafr-accelerator
sudo chown -R ec2-user:ec2-user /wafr-accelerator

chown -R ec2-user:ec2-user /wafr-accelerator

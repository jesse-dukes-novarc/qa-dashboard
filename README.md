QA Project Dashboard
Overview
The QA Project Dashboard is a Streamlit-based web application designed to track project readiness, testing estimates, bug resolutions, and welding defect metrics. It acts as a live, read-only visualization layer, securely pulling real-time data directly from a designated Google Sheet using a Google Cloud Service Account.

Key Features
Project Inventory & Status: A high-level tabular view of active and completed projects, highlighting whether welding inspections were required and linking directly to QA Release forms.

Dynamic Performance Radars: Visualizes 10 different QA rating factors (scored out of 10) for individual projects. The radar chart dynamically changes color based on the overall average (Green > 8.8, Yellow 7.2–8.8, Red < 7.2).

Portfolio Benchmarking: Compare selected projects against a rolling portfolio average (30 days, 3 months, 6 months, or 1 year) using dedicated comparison radar charts.

Estimations vs. Actuals: Combo charts tracking original test estimates, actual QA days spent, and variations driven by Release Candidate (rc) iterations.

Bug Tracking: Overlay bar charts highlighting the resolution rate of reported vs. resolved bugs per project.

Welding Metrics: 100% stacked bar charts showing joint pass/fail rates, alongside pie charts detailing the exact distribution of weld defects (e.g., Undercut, Porosity, Lack of Fusion).

Deployment Guide: AWS EC2 (Ubuntu)
This guide explains how to package the dashboard locally and deploy it as a persistent background service on an AWS EC2 instance.

Prerequisites: Ensure you are using a local Ubuntu terminal (or WSL on Windows). You will need the AWS EC2 Public IP address and your .pem SSH key. Ensure .streamlit/secrets.toml contains your Google Sheets credentials before starting.

Step 1: Package the Application Locally
Run the packaging script in your local terminal. This bundles the app, requirements, secrets, and install script into a single compressed file.

Bash
chmod +x package.sh
./package.sh
Output: qa-dashboard.tar.gz

Step 2: Transfer to the AWS Instance
Use Secure Copy (scp) to send the package to your AWS server.

Bash
scp -i /path/to/your-aws-key.pem qa-dashboard.tar.gz ubuntu@<AWS_INSTANCE_IP>:~
Step 3: Connect and Install on AWS
SSH into the EC2 instance, unpack the archive, and run the automated install script.

Bash
# 1. Connect to the server
ssh -i /path/to/your-aws-key.pem ubuntu@<AWS_INSTANCE_IP>

# 2. Extract the package
mkdir -p ~/qa-dashboard
tar -xzvf qa-dashboard.tar.gz -C ~/qa-dashboard
cd ~/qa-dashboard

# 3. Run the installation script
chmod +x install.sh
./install.sh
The install.sh script automatically installs Python dependencies, configures the virtual environment, and sets up Streamlit as a systemd service so it runs continuously in the background.

Step 4: Verify the Application
Check that the background service is running successfully:

Bash
sudo systemctl status qadashboard
Step 5: AWS Network Configuration
For the dashboard to be accessible in a web browser, the AWS architect must configure the EC2 Security Group:

Inbound Rules: Allow Custom TCP on Port 8501 (from your corporate IP or 0.0.0.0/0).

Outbound Rules: Ensure outbound HTTPS (Port 443) is allowed to reach the Google Sheets API.

Once configured, visit the dashboard at:

`

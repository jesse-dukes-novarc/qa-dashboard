#!/bin/bash
# install.sh

echo "1. Updating system and installing Python..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

echo "2. Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "3. Installing application dependencies..."
pip install -r requirements.txt

echo "4. Setting up Streamlit as a background systemd service..."
# Create a systemd service file
sudo bash -c 'cat > /etc/systemd/system/qadashboard.service <<EOF
[Unit]
Description=QA Dashboard Streamlit App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/qa-dashboard
ExecStart=/home/ubuntu/qa-dashboard/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
EOF'

echo "5. Starting the application..."
sudo systemctl daemon-reload
sudo systemctl enable qadashboard
sudo systemctl start qadashboard

echo "Installation complete! Dashboard is running."

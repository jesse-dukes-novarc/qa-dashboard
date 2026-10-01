#!/bin/bash
# package.sh

echo "Packaging QA Dashboard..."
# Zips the python app, requirements, secrets, and install script into one file
tar -czvf qa-dashboard.tar.gz app.py requirements.txt .streamlit/secrets.toml install.sh
echo "Done! qa-dashboard.tar.gz is ready."

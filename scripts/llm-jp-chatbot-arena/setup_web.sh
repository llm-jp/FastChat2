#!/bin/sh
# git clone https://github.com/llm-jp/FastChat2.git

# Setup Apache
sudo apt-get update
sudo apt-get install -y apache2 apache2-dev
sudo systemctl start apache2

## Enable reverse proxy
sudo a2enmod proxy proxy_http
sudo systemctl restart apache2

sudo cp FastChat2/scripts/llm-jp-chatbot-arena/000-default.conf /etc/apache2/sites-available/000-default.conf
sudo systemctl reload apache2

# Install python venv
sudo apt-get update
sudo apt-get install -y python3-venv

# Install Chatbot Arena
cd FastChat2
python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -e ".[model_worker,webui]" plotly scipy openai
pip3 install gradio==4.44.1


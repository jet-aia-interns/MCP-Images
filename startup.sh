#!/bin/bash

# Azure Web App startup script for Python
echo "Starting MCP Image Service..."

# Update package lists first
apt-get update -y

# Install Chrome dependencies for Selenium (if needed)
apt-get install -y wget gnupg unzip software-properties-common

# Add Google Chrome repository properly
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list

# Update again after adding the repository
apt-get update -y

# Install Google Chrome (with error handling)
if apt-get install -y google-chrome-stable; then
    echo "Chrome installed successfully"
else
    echo "Chrome installation failed, continuing without it..."
    export SELENIUM_AVAILABLE=false
fi

# Install ChromeDriver only if Chrome was installed successfully
if command -v google-chrome &> /dev/null; then
    CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE 2>/dev/null || echo "114.0.5735.90")
    wget -O /tmp/chromedriver.zip "http://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip" 2>/dev/null || {
        echo "ChromeDriver download failed, using alternative..."
        wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip"
    }
    unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ 2>/dev/null
    chmod +x /usr/local/bin/chromedriver 2>/dev/null
fi

# Create necessary directories
mkdir -p /tmp/Temp
mkdir -p /tmp/data

# Set environment variables for Chrome (if available)
if command -v google-chrome &> /dev/null; then
    export CHROME_BIN=/usr/bin/google-chrome
    export CHROME_PATH=/usr/bin/google-chrome
fi

# Start the FastAPI application with Uvicorn (not Gunicorn)
exec python -m uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1
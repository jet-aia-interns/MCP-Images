#!/bin/bash

# Simple startup script for Azure Web App
echo "Starting MCP Image Service (Simple Version)..."

# Create necessary directories
mkdir -p /tmp/Temp
mkdir -p /tmp/data

# Get the port from environment variable or default to 8000
PORT=${PORT:-8000}

# Start the FastAPI application with Uvicorn
echo "Starting server on port $PORT..."
exec python -m uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1
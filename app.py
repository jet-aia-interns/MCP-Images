#!/usr/bin/env python3
"""
Flask web server wrapper for the MCP Image Service
This allows the MCP server to be deployed as a web service on Azure Web Apps
"""

import os
import json
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Import the existing MCP server
from mcp_image import mcp

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "MCP Image Service",
        "version": "1.0.0"
    })

@app.route('/tools', methods=['GET'])
def list_tools():
    """List available MCP tools"""
    try:
        # Get tools from the MCP server
        tools = []
        for tool_name, tool in mcp._tool_manager._tools.items():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters if hasattr(tool, 'parameters') else {}
            })
        return jsonify({"tools": tools})
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/call_tool', methods=['POST'])
def call_tool():
    """Execute an MCP tool"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        tool_name = data.get('tool_name')
        arguments = data.get('arguments', {})
        
        if not tool_name:
            return jsonify({"error": "tool_name is required"}), 400
        
        # Check if tool exists
        if tool_name not in mcp._tool_manager._tools:
            return jsonify({"error": f"Tool '{tool_name}' not found"}), 404
        
        # Execute the tool
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Create a mock context for the tool execution
            class MockContext:
                def __init__(self):
                    pass
            
            context = MockContext()
            tool = mcp._tool_manager._tools[tool_name]
            
            # Execute the tool function
            if tool.is_async:
                result = loop.run_until_complete(tool.fn(ctx=context, **arguments))
            else:
                result = tool.fn(ctx=context, **arguments)
            
            return jsonify({"result": result})
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/search_images', methods=['POST'])
def search_images():
    """Search for images endpoint"""
    try:
        data = request.json
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        
        if not query:
            return jsonify({"error": "query parameter is required"}), 400
        
        # Call the search_google_images tool
        return call_tool_internal('search_google_images', {
            'search_query': query,
            'max_results': max_results
        })
    
    except Exception as e:
        logger.error(f"Error in search_images: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/save_image', methods=['POST'])
def save_image():
    """Save image endpoint"""
    try:
        data = request.json
        image_url = data.get('image_url', '')
        filename = data.get('filename', '')
        
        if not image_url:
            return jsonify({"error": "image_url parameter is required"}), 400
        
        # Call the upload_single_image_to_azure tool
        return call_tool_internal('upload_single_image_to_azure', {
            'image_source': image_url,
            'blob_name': filename if filename else None
        })
    
    except Exception as e:
        logger.error(f"Error in save_image: {e}")
        return jsonify({"error": str(e)}), 500

def call_tool_internal(tool_name, arguments):
    """Internal helper to call MCP tools"""
    try:
        if tool_name not in mcp._tool_manager._tools:
            return jsonify({"error": f"Tool '{tool_name}' not found"}), 404
        
        # Execute the tool
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            class MockContext:
                def __init__(self):
                    pass
            
            context = MockContext()
            tool = mcp._tool_manager._tools[tool_name]
            
            if tool.is_async:
                result = loop.run_until_complete(tool.fn(ctx=context, **arguments))
            else:
                result = tool.fn(ctx=context, **arguments)
            
            return jsonify({"result": result})
        
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
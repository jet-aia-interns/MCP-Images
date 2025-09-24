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
from flask_socketio import SocketIO, emit
import logging

# Import the existing MCP server
from mcp_image import mcp

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ...existing code...

@socketio.on('mcp_request')
def handle_mcp_request(data):
    """Handle MCP protocol requests via WebSocket"""
    try:
        method = data.get('method')
        params = data.get('params', {})
        request_id = data.get('id')
        
        if method == 'tools/list':
            # List available tools
            tools = []
            for tool_name, tool in mcp._tool_manager._tools.items():
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.parameters if hasattr(tool, 'parameters') else {}
                })
            
            emit('mcp_response', {
                "id": request_id,
                "result": {"tools": tools}
            })
            
        elif method == 'tools/call':
            # Execute a tool
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            
            if tool_name not in mcp._tool_manager._tools:
                emit('mcp_response', {
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
                })
                return
            
            # Execute tool in new event loop
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
                
                emit('mcp_response', {
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                })
                
            finally:
                loop.close()
        else:
            emit('mcp_response', {
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            })
            
    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        emit('mcp_response', {
            "id": request_id,
            "error": {"code": -32603, "message": str(e)}
        })

# ...existing code...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
#!/usr/bin/env python3
"""
Simple HTTP wrapper for test-mcp-echo-server MCP protocol server.

Exposes MCP tools as a simple HTTP REST API with /tools endpoint.
This is a temporary wrapper until full MCP protocol support is added.
"""

import os
import sys
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MCP HTTP Wrapper")

# Simple mock tools for the echo server
MOCK_TOOLS: Dict[str, List[Dict[str, Any]]] = {
    "echo_server": [
        {
            "name": "echo",
            "description": "Echo back the input message",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to echo"
                    }
                },
                "required": ["message"]
            }
        }
    ]
}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "MCP HTTP Wrapper for echo server"}

@app.get("/tools")
async def get_tools():
    """Get available tools from the MCP echo server"""
    try:
        return {"tools": MOCK_TOOLS.get("echo_server", [])}
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    """Readiness check endpoint"""
    return {"status": "ready"}

@app.post("/tool/invoke")
async def invoke_tool(request: Dict[str, Any]):
    """Invoke a tool (mock implementation for echo tool)"""
    tool_name = request.get("tool")
    arguments = request.get("arguments", {})

    if tool_name == "echo":
        message = arguments.get("message", "")
        return {
            "result": f'Echo: "{message}"',
            "success": True
        }
    else:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    logger.info(f"Starting MCP HTTP Wrapper on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

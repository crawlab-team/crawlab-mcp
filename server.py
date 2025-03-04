#!/usr/bin/env python3
"""
Crawlab MCP Server

This server provides AI applications with access to Crawlab functionality
through the Model Context Protocol (MCP).
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CRAWLAB_API_BASE_URL = os.getenv("CRAWLAB_API_BASE_URL", "http://localhost:8080/api")
CRAWLAB_API_TOKEN = os.getenv("CRAWLAB_API_TOKEN", "")

# Create an MCP server
mcp = FastMCP("Crawlab")

# Helper functions for API requests
def api_request(method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
    """Make a request to the Crawlab API."""
    url = f"{CRAWLAB_API_BASE_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {CRAWLAB_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        params=params
    )
    
    response.raise_for_status()
    return response.json()

# Resources
@mcp.resource()
def spiders() -> List[Dict]:
    """Get a list of all spiders in Crawlab."""
    response = api_request("GET", "spiders")
    return response.get("data", [])

@mcp.resource()
def tasks() -> List[Dict]:
    """Get a list of all tasks in Crawlab."""
    response = api_request("GET", "tasks")
    return response.get("data", [])

# Tools - Spider Management
@mcp.tool()
def get_spider(spider_id: str) -> Dict:
    """Get details of a specific spider by ID."""
    response = api_request("GET", f"spiders/{spider_id}")
    return response.get("data", {})

@mcp.tool()
def create_spider(name: str, description: str = "", cmd: str = "python main.py") -> Dict:
    """Create a new spider in Crawlab."""
    data = {
        "name": name,
        "description": description,
        "cmd": cmd
    }
    response = api_request("POST", "spiders", data=data)
    return response.get("data", {})

@mcp.tool()
def update_spider(spider_id: str, name: str = None, description: str = None, cmd: str = None) -> Dict:
    """Update an existing spider."""
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if cmd is not None:
        data["cmd"] = cmd
    
    response = api_request("PUT", f"spiders/{spider_id}", data=data)
    return response.get("data", {})

@mcp.tool()
def delete_spider(spider_id: str) -> Dict:
    """Delete a spider by ID."""
    response = api_request("DELETE", f"spiders/{spider_id}")
    return response.get("data", {})

# Tools - Task Management
@mcp.tool()
def get_task(task_id: str) -> Dict:
    """Get details of a specific task by ID."""
    response = api_request("GET", f"tasks/{task_id}")
    return response.get("data", {})

@mcp.tool()
def run_spider(spider_id: str, param: str = "") -> Dict:
    """Run a spider by ID."""
    data = {
        "spider_id": spider_id,
        "param": param
    }
    response = api_request("POST", "tasks/run", data=data)
    return response.get("data", {})

@mcp.tool()
def cancel_task(task_id: str) -> Dict:
    """Cancel a running task."""
    response = api_request("POST", f"tasks/{task_id}/cancel")
    return response.get("data", {})

@mcp.tool()
def restart_task(task_id: str) -> Dict:
    """Restart a task."""
    response = api_request("POST", f"tasks/{task_id}/restart")
    return response.get("data", {})

@mcp.tool()
def get_task_logs(task_id: str) -> str:
    """Get logs for a specific task."""
    response = api_request("GET", f"tasks/{task_id}/logs")
    return response.get("data", "")

# Tools - Spider Files
@mcp.tool()
def get_spider_files(spider_id: str, path: str = "") -> List[Dict]:
    """Get files for a specific spider."""
    params = {"path": path} if path else None
    response = api_request("GET", f"spiders/{spider_id}/files", params=params)
    return response.get("data", [])

@mcp.tool()
def get_spider_file(spider_id: str, path: str) -> str:
    """Get the content of a specific spider file."""
    params = {"path": path}
    response = api_request("GET", f"spiders/{spider_id}/file", params=params)
    return response.get("data", "")

@mcp.tool()
def save_spider_file(spider_id: str, path: str, content: str) -> Dict:
    """Save content to a spider file."""
    data = {
        "path": path,
        "content": content
    }
    response = api_request("POST", f"spiders/{spider_id}/file", data=data)
    return response.get("data", {})

# Main entry point
if __name__ == "__main__":
    # Start the MCP server
    mcp.run() 
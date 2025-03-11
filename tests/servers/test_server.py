#!/usr/bin/env python3
"""
Simple MCP Test Server for integration testing

This server implements the basic endpoints needed for testing client connections.
"""

import asyncio
import json
import os
import sys
import signal
from typing import Dict, Any, List

# Import aiohttp for SSE support
try:
    import aiohttp
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    print("Warning: aiohttp not available. Falling back to basic HTTP server.")
    from http.server import HTTPServer, BaseHTTPRequestHandler


# Available test tools
TEST_TOOLS = [
    {
        "name": "getSystemInfo",
        "description": "Get system information",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "getNodeList",
        "description": "Get list of available nodes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter nodes by status"
                }
            },
            "required": []
        }
    },
    {
        "name": "getSpiderList",
        "description": "Get list of spiders",
        "inputSchema": {
            "type": "object", 
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter spiders by status"
                }
            },
            "required": []
        }
    }
]

# Available tags
TEST_TAGS = [
    "system",
    "node",
    "spider"
]


async def handle_tool_call(request_data):
    """Handle a tool call request"""
    tool_name = request_data.get("name", "")
    args = request_data.get("args", {})
    
    # Return mock responses based on the tool name
    if tool_name == "getSystemInfo":
        response = {
            "cpuCount": 4,
            "memoryTotal": 8589934592,  # 8 GB
            "memoryFree": 4294967296,   # 4 GB
            "uptime": 86400,            # 1 day
            "osInfo": "Linux Test Server 5.10.0"
        }
    elif tool_name == "getNodeList":
        nodes = [
            {"id": "node1", "name": "Main Node", "status": "online"},
            {"id": "node2", "name": "Worker 1", "status": "online"},
            {"id": "node3", "name": "Worker 2", "status": "offline"}
        ]
        
        # Apply status filter if provided
        status_filter = args.get("status")
        if status_filter:
            nodes = [node for node in nodes if node["status"] == status_filter]
            
        response = {"nodes": nodes}
    elif tool_name == "getSpiderList":
        spiders = [
            {"id": "spider1", "name": "Web Crawler", "status": "idle"},
            {"id": "spider2", "name": "Data Scraper", "status": "running"},
            {"id": "spider3", "name": "API Monitor", "status": "error"}
        ]
        
        # Apply status filter if provided
        status_filter = args.get("status")
        if status_filter:
            spiders = [spider for spider in spiders if spider["status"] == status_filter]
            
        response = {"spiders": spiders}
    elif tool_name == "list_tags":
        response = {"tags": TEST_TAGS}
    else:
        return None, f"Unknown tool: {tool_name}"
        
    return response, None


# AioHTTP Server Implementation (Preferred)
if HAS_AIOHTTP:
    async def get_tools(request):
        """Handle GET /tools endpoint"""
        return web.json_response({"tools": TEST_TOOLS})
    
    async def get_tags(request):
        """Handle GET /tags endpoint"""
        return web.json_response({"tags": TEST_TAGS})
    
    async def initialize_sse(request):
        """Initialize SSE connection"""
        # Setup SSE response
        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        await response.prepare(request)
        
        # Send initial message
        await response.write(b'event: initialize\ndata: {"status":"initialized"}\n\n')
        
        # Keep the connection alive
        try:
            msg_id = 0
            while True:
                # Check if client is still connected
                if request.transport.is_closing():
                    break
                
                # Keep-alive ping every 30 seconds
                await asyncio.sleep(30)
                await response.write(f'id: {msg_id}\nevent: ping\ndata: {{}}\n\n'.encode('utf-8'))
                msg_id += 1
                
        except ConnectionResetError:
            pass
        except asyncio.CancelledError:
            pass
            
        return response
    
    async def call_tool(request):
        """Handle tool call requests"""
        try:
            request_data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        
        response_data, error = await handle_tool_call(request_data)
        if error:
            return web.json_response({"error": error}, status=400)
        
        return web.json_response({"content": json.dumps(response_data)})
    
    async def start_aiohttp_server(port=7821):
        """Start the aiohttp server"""
        app = web.Application()
        
        # Configure routes
        app.router.add_get('/tools', get_tools)
        app.router.add_get('/tags', get_tags)
        app.router.add_get('/list_tags', get_tags)
        app.router.add_post('/initialize', initialize_sse)
        app.router.add_post('/call_tool', call_tool)
        
        # Start the server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', port)
        await site.start()
        
        print(f"MCP test server started on port {port}")
        
        # Return the runner for cleanup
        return runner

# Fallback HTTP Server Implementation
else:
    class MCPTestHandler(BaseHTTPRequestHandler):
        """HTTP handler for the MCP test server"""
        
        def do_GET(self):
            """Handle GET requests"""
            if self.path == "/tools":
                self._send_json_response(200, {"tools": TEST_TOOLS})
            elif self.path == "/tags" or self.path.startswith("/list_tags"):
                self._send_json_response(200, {"tags": TEST_TAGS})
            else:
                self._send_json_response(404, {"error": "Not found"})
        
        def do_POST(self):
            """Handle POST requests"""
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                request = json.loads(post_data) if post_data else {}
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Invalid JSON"})
                return
            
            # Initialize SSE connection
            if self.path == "/initialize":
                # Set SSE headers
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                
                # Send initial message
                self.wfile.write(b'event: initialize\ndata: {"status":"initialized"}\n\n')
                self.wfile.flush()
                
                # Note: This is a simplified approach and won't properly keep the connection alive
                # as we can't easily do async in the basic HTTP server
                return
            
            # Handle tool calls
            elif self.path.startswith("/call_tool"):
                response_data, error = asyncio.run(handle_tool_call(request))
                if error:
                    self._send_json_response(400, {"error": error})
                    return
                
                self._send_json_response(200, {"content": json.dumps(response_data)})
            else:
                self._send_json_response(404, {"error": "Not found"})
        
        def _send_json_response(self, status_code: int, data: Dict[str, Any]):
            """Send a JSON response with the given status code and data"""
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))


    def run_http_server(port: int = 7821):
        """Run the fallback HTTP server on the specified port"""
        server = HTTPServer(('localhost', port), MCPTestHandler)
        print(f"Starting MCP test server (HTTP fallback) on port {port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            print("Server stopped")


if __name__ == "__main__":
    # Get port from command line argument or environment variable
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("MCP_TEST_SERVER_PORT", 7821))
    
    if HAS_AIOHTTP:
        # Use aiohttp server (preferred)
        loop = asyncio.get_event_loop()
        runner = None
        
        async def shutdown(signal, loop):
            """Cleanup server on shutdown"""
            if runner:
                await runner.cleanup()
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            loop.stop()
        
        try:
            # Setup signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
            
            # Start server
            runner = loop.run_until_complete(start_aiohttp_server(port))
            loop.run_forever()
        finally:
            loop.close()
            print("Server stopped")
    else:
        # Use fallback HTTP server
        run_http_server(port) 
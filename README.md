# Crawlab MCP Server

This is a Model Context Protocol (MCP) server for Crawlab, allowing AI applications to interact with Crawlab's functionality.

## Overview

The MCP server provides a standardized way for AI applications to access Crawlab's features, including:

- Spider management (create, read, update, delete)
- Task management (run, cancel, restart)
- File management (read, write)
- Resource access (spiders, tasks)

## Installation and Usage

### Option 1: Install as a Python package

You can install the MCP server as a Python package, which provides a convenient CLI:

```bash
# Install from source
pip install -e .

# Or install from GitHub (when available)
# pip install git+https://github.com/crawlab-team/crawlab-mcp-server.git
```

After installation, you can use the CLI:

```bash
# Start the MCP server
crawlab-mcp server [--spec PATH_TO_SPEC] [--host HOST] [--port PORT]

# Start the MCP client
crawlab-mcp client SERVER_URL
```

### Option 2: Running Locally

### Prerequisites

- Python 3.8+
- Crawlab instance running and accessible
- API token from Crawlab

### Configuration

1. Copy the `.env.example` file to `.env`:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file with your Crawlab API details:
   ```
   CRAWLAB_API_BASE_URL=http://your-crawlab-instance:8080/api
   CRAWLAB_API_TOKEN=your_api_token_here
   ```

### Running Locally

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the server:
   ```
   python server.py
   ```

### Running with Docker

1. Build the Docker image:
   ```
   docker build -t crawlab-mcp-server .
   ```

2. Run the container:
   ```
   docker run -p 8000:8000 --env-file .env crawlab-mcp-server
   ```

## Integration with Docker Compose

To add the MCP server to your existing Crawlab Docker Compose setup, add the following service to your `docker-compose.yml`:

```yaml
services:
  # ... existing Crawlab services
  
  mcp-server:
    build: ./backend/mcp-server
    ports:
      - "8000:8000"
    environment:
      - CRAWLAB_API_BASE_URL=http://backend:8000/api
      - CRAWLAB_API_TOKEN=your_api_token_here
    depends_on:
      - backend
```

## Using with AI Applications

The MCP server can be used with any AI application that supports the Model Context Protocol, such as:

- Claude Desktop
- Custom applications using the MCP client libraries

### Example: Using with Claude Desktop

1. Open Claude Desktop
2. Go to Settings > MCP Servers
3. Add a new server with the URL of your MCP server (e.g., `http://localhost:8000`)
4. In a conversation with Claude, you can now use Crawlab functionality

## Available Resources and Tools

### Resources

- `spiders`: List all spiders
- `tasks`: List all tasks

### Tools

#### Spider Management
- `get_spider`: Get details of a specific spider
- `create_spider`: Create a new spider
- `update_spider`: Update an existing spider
- `delete_spider`: Delete a spider

#### Task Management
- `get_task`: Get details of a specific task
- `run_spider`: Run a spider
- `cancel_task`: Cancel a running task
- `restart_task`: Restart a task
- `get_task_logs`: Get logs for a task

#### File Management
- `get_spider_files`: List files for a spider
- `get_spider_file`: Get content of a specific file
- `save_spider_file`: Save content to a file
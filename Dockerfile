FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY crawlab_mcp/servers/server.py .
COPY .env .

# Make the server executable
RUN chmod +x server.py

# Expose the MCP server port
EXPOSE 8000

# Run the server
CMD ["python", "server.py"] 
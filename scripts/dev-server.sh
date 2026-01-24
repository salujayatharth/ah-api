#!/bin/bash
# Vibe Kanban Dev Server Script for AH Receipts API
# This script starts the FastAPI development server on any available port

set -e

# Ensure dependencies are installed
uv sync

# Activate virtual environment
source .venv/bin/activate

# Find an available port
find_available_port() {
    python3 -c "
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(('', 0))
    s.listen(1)
    port = s.getsockname()[1]
    print(port)
"
}

PORT=$(find_available_port)

# Start the FastAPI development server
echo "Starting AH Receipts API development server on port $PORT..."
uvicorn app.main:app --reload --port "$PORT"

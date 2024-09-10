#!/bin/bash

# Activate virtual environment if you're using one
# source /path/to/your/venv/bin/activate

# Set environment variables if needed
# export ENVIRONMENT=production

# Run the application using uvicorn
uvicorn asgi:app --host 0.0.0.0 --port 8000 --workers 4 --reload
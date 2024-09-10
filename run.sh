#!/bin/bash

# Check if pyenv is available
if ! command -v pyenv &> /dev/null
then
    echo "pyenv could not be found. Please make sure it's installed and initialized."
    exit 1
fi

# Activate pyenv and the virtual environment
echo "Activating virtual environment: mysql_monitor"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate mysql_monitor

# Check if virtual environment activation was successful
if [[ "$VIRTUAL_ENV" != *"mysql_monitor"* ]]; then
    echo "Failed to activate the virtual environment."
    exit 1
fi

# Set environment variables if needed
# export ENVIRONMENT=production

# Run the application using uvicorn
echo "Starting the application..."
uvicorn asgi:app --host 0.0.0.0 --port 8000 --workers 4 --reload

# Deactivate the virtual environment
echo "Deactivating virtual environment"
pyenv deactivate

echo "Script completed."
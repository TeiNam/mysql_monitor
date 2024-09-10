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

# Run the collectors
echo "Starting the collectors..."

# MySQL Slow Queries Collector
python collectors/mysql_slow_queries.py &
SLOW_QUERIES_PID=$!

# MySQL Command Status Collector
python collectors/mysql_command_status.py &
COMMAND_STATUS_PID=$!

# MySQL Disk Status Collector
python collectors/mysql_disk_status.py &
DISK_STATUS_PID=$!

# RDS Instance Status Collector
python collectors/rds_instance_status.py &
RDS_STATUS_PID=$!

# Wait for all background processes to complete
wait $SLOW_QUERIES_PID $COMMAND_STATUS_PID $DISK_STATUS_PID $RDS_STATUS_PID

echo "All collectors have finished."

# Deactivate the virtual environment
echo "Deactivating virtual environment"
pyenv deactivate

echo "Script completed."
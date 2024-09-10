#!/bin/bash

# 스크립트가 있는 디렉토리로 이동
cd "$(dirname "$0")"

# 가상환경 경로 설정 (프로젝트 루트에 있다고 가정)
VENV_PATH="./venv"

# 가상환경이 존재하는지 확인
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# 가상환경 활성화
source "$VENV_PATH/bin/activate"

# 가상환경이 제대로 활성화되었는지 확인
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "Virtual environment activated successfully"

# Collectors 실행
echo "Starting collectors..."

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

# 모든 백그라운드 프로세스가 완료될 때까지 대기
wait $SLOW_QUERIES_PID $COMMAND_STATUS_PID $DISK_STATUS_PID $RDS_STATUS_PID

echo "All collectors have finished"

# 가상환경 비활성화
deactivate

echo "Virtual environment deactivated"
#!/bin/bash

# Configuration
TARGET_BRANCH="dev"
API_PORT=8002
WS_PORT=8765
FRONTEND_PORT=3001
DB_PATH="$HOME/.cradle_data/new_video_compare.db"
PROJECT_DIR="$PWD"

echo "========================================"
echo "🛠️ Starting Cradle DEV Environment"
echo "========================================"

# 1. Branch Guard
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$TARGET_BRANCH" ]; then
    echo -e "\033[0;31mWARNING: Current branch is '$CURRENT_BRANCH', but this script expects '$TARGET_BRANCH'.\033[0m"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "\033[0;31mAborting.\033[0m"
        exit 1
    fi
else
    echo -e "\033[0;32m✅ Branch check passed ($TARGET_BRANCH)\033[0m"
fi

# 2. Port Guard
for PORT in $API_PORT $WS_PORT $FRONTEND_PORT; do
    PIDS=$(lsof -ti :$PORT | tr '\n' ' ')
    if [ ! -z "$PIDS" ]; then
        echo -e "\033[0;31mERROR: Port $PORT is already in use by PID(s): $PIDS\033[0m"
        echo "Please stop the existing process before running this script (e.g. 'kill -9 $PIDS')."
        exit 1
    fi
done
echo -e "\033[0;32m✅ Port check passed (ports are free)\033[0m"

# 3. Database Info
echo -e "\033[0;34m📂 Database Path: $DB_PATH\033[0m"
echo "----------------------------------------"

# 4. Start Backend (DEV)
echo "Starting Backend DEV on port $API_PORT in a new terminal window..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR/new_video_compare/backend' && source '$HOME/miniforge3/bin/activate' && conda activate cradle-env && uvicorn main:app --host 0.0.0.0 --port $API_PORT --reload\""

# Wait and Healthcheck
echo -n "Waiting for backend healthcheck..."
max_retries=15
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -s http://localhost:$API_PORT/health | grep -q "healthy"; then
        echo -e "\n\033[0;32m✅ Backend is UP and healthy!\033[0m"
        break
    fi
    echo -n "."
    sleep 2
    retry_count=$((retry_count+1))
done

if [ $retry_count -eq $max_retries ]; then
    echo -e "\n\033[0;31mERROR: Backend failed to start or healthcheck timed out.\033[0m"
    exit 1
fi

# 5. Start Desktop App
echo "Starting Desktop App (WebSocket) on port $WS_PORT in a new terminal window..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR/desktop-app' && source '$HOME/miniforge3/bin/activate' && conda activate cradle-env && python src/main.py\""

# 6. Start Frontend (DEV)
echo "Starting Frontend DEV on port $FRONTEND_PORT in a new terminal window..."
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR/new_video_compare/frontend' && PORT=$FRONTEND_PORT REACT_APP_API_URL=http://localhost:$API_PORT REACT_APP_WS_URL=ws://localhost:$API_PORT/ws npm start\""

echo "========================================"
echo -e "\033[0;32m🎉 All DEV services started successfully!\033[0m"
echo "========================================"

#!/bin/bash

echo "🎯 Debate Analysis Web Interface Startup"
echo "========================================"

cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"
WEB_DIR="$PROJECT_ROOT/web"

echo "📁 Project root: $PROJECT_ROOT"
echo "💾 Data directory: $WEB_DIR/data"

# Kill any existing Flask processes
echo "🧹 Cleaning up existing processes..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 2

# Check for available port
check_port() {
    local port=$1
    if ! netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        return 0  # Port is available
    else
        return 1  # Port is in use
    fi
}

PORT=8080
if ! check_port $PORT; then
    PORT=8081
    if ! check_port $PORT; then
        PORT=8082
        if ! check_port $PORT; then
            echo "❌ Ports 8080-8082 are all in use!"
            echo "💡 Please manually kill Flask processes: pkill -f python"
            exit 1
        fi
    fi
fi

echo "🌐 Starting server on port $PORT..."
echo "📝 Open in browser: http://127.0.0.1:$PORT"
echo "⏹️  Press Ctrl+C to stop"
echo

cd "$WEB_DIR"

# Set up Python path and run
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('..').resolve()))
from app import app
app.run(host='127.0.0.1', port=$PORT, debug=True)
"

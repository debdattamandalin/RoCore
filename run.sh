#!/bin/bash
cd "$(dirname "$0")"

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run the FastAPI server via uvicorn
echo "Starting RoCore Server..."
export PORT=8080
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT

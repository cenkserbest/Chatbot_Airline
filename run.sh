#!/bin/bash

# Airline AI Agent - Starter for Mac/Linux (Standalone)
echo "🚀 Starting the AI Agent Stack..."

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "⚠️ .venv not found. Creating it now..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

# 1. Start the Agent Backend API
echo "🌐 Starting Agent API on port 8001..."
source .venv/bin/activate && python3 agent_api.py &
BACKEND_PID=$!

# 2. Start the React Frontend
echo "💻 Starting React Frontend..."
cd frontend && npm install && npm run dev &
FRONTEND_PID=$!

echo "✅ Stack is starting up!"
echo "--------------------------------------------------"
echo "Agent Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "--------------------------------------------------"
echo "Press Ctrl+C to stop."

# Wait for background processes
wait

#!/bin/bash

echo "🚀 Starting the AI Agent Stack..."

# Check if .venv exists
if [ ! -d "ai_agent/.venv" ]; then
    echo "⚠️  .venv not found. Creating it now..."
    cd ai_agent && python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# 1. Start the MCP Server (standalone SSE server on port 8002)
echo "🔧 [1/3] Starting MCP Server on port 8002..."
cd ai_agent && source .venv/bin/activate && python3 mcp_server.py &
MCP_PID=$!
cd ..

echo "⏳ Waiting for MCP Server to boot..."
sleep 4

# 2. Start the Agent Backend API
echo "🌐 [2/3] Starting Agent API on port 8001..."
cd ai_agent && source .venv/bin/activate && python3 agent_api.py &
BACKEND_PID=$!
cd ..

# 3. Start the React Frontend
echo "💻 [3/3] Starting React Frontend..."
cd ai_agent/frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================================"
echo " ✅ Stack is starting up!"
echo "  MCP Server  : http://localhost:8002"
echo "  Agent API   : http://localhost:8001"
echo "  Frontend    : http://localhost:5173"
echo "============================================================"
echo " MCP PID: $MCP_PID | Agent PID: $BACKEND_PID | Frontend PID: $FRONTEND_PID"
echo " Press Ctrl+C to stop all services."
echo "============================================================"

wait

@echo off
echo Starting the AI Agent Stack...

echo [1/3] Starting MCP Server on port 8002...
start "MCP Server (port 8002)" cmd /k "cd ai_agent && .venv\Scripts\activate && python mcp_server.py"

echo Waiting for MCP Server to boot...
timeout /t 4 /nobreak > nul

echo [2/3] Starting Agent Backend API on port 8001...
start "Agent API (port 8001)" cmd /k "cd ai_agent && .venv\Scripts\activate && python agent_api.py"

echo [3/3] Starting React Frontend...
start "React Frontend" cmd /k "cd ai_agent\frontend && npm run dev"

echo.
echo ============================================================
echo  Stack is starting up!
echo  MCP Server  : http://localhost:8002
echo  Agent API   : http://localhost:8001
echo  Frontend    : http://localhost:5173
echo ============================================================

@echo off
echo Starting the AI Agent Stack...

:: Start Agent Backend
start "Agent Backend API" cmd /k ".venv\Scripts\activate && python agent_api.py"

:: Start React Frontend
start "React Frontend" cmd /k "cd frontend && npm run dev"

echo Stack started!
echo The Agent API is running on port 8001
echo The React Frontend is running in another window.

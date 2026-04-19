import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class ChatRequest(BaseModel):
    message: str
    session_id: str

sessions = {}

mcp_client_ctx = None
mcp_session_ctx = None
mcp_session: ClientSession = None

async def init_mcp():
    global mcp_client_ctx, mcp_session_ctx, mcp_session
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )
    mcp_client_ctx = stdio_client(server_params)
    read, write = await mcp_client_ctx.__aenter__()
    
    mcp_session_ctx = ClientSession(read, write)
    mcp_session = await mcp_session_ctx.__aenter__()
    await mcp_session.initialize()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mcp()
    yield
    global mcp_client_ctx, mcp_session_ctx
    if mcp_session_ctx:
        await mcp_session_ctx.__aexit__(None, None, None)
    if mcp_client_ctx:
        await mcp_client_ctx.__aexit__(None, None, None)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@tool
async def get_all_flights(skip: int = 0) -> str:
    """Call this tool IMMEDIATELY when the user asks to list all flights or see all flights."""
    args = {"number_of_people": 1, "is_round_trip": False}
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def search_flights(airport_from: Optional[str] = None, airport_to: Optional[str] = None, date: Optional[str] = None, date_to: Optional[str] = None, number_of_people: int = 1, is_round_trip: bool = False) -> str:
    """Use this tool ONLY if the user specifically provides SOME filtering criteria (like airport locations OR dates) to search."""
    
    # Gemini Safety Guard: Prevent early call without airports
    if not airport_from or not airport_to or not date:
        return "REJECTION: I am missing required search data (airports or date). Please ask the user politely for the departure airport, arrival airport, and date."

    args = {
        "number_of_people": number_of_people,
        "is_round_trip": is_round_trip
    }
    if airport_from:
        args["airport_from"] = airport_from
    if airport_to:
        args["airport_to"] = airport_to
    if date:
        args["date"] = date
    if date_to:
        args["date_to"] = date_to
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def book_flight(flight_number: str, date: str, passenger_names: List[str]) -> str:
    """Book a flight ticket. REQUIRES flight_number, date (YYYY-MM-DD), and passenger_names."""
    
    # Sanitize inputs
    cl_date = date.split(" ")[0].split("T")[0].strip()
    
    args = {
        "flight_number": flight_number.replace(" ", "").upper(),
        "date": cl_date,
        "passenger_names": passenger_names
    }
    result = await mcp_session.call_tool("book_flight", arguments=args)
    return str(result.content)

@tool
async def check_in(ticket_number: str, flight_number: str, date: str, passenger_name: str) -> str:
    """Perform a check-in. REQUIRES ticket_number, flight_number, date (YYYY-MM-DD), and passenger_name."""
    
    # Gemini Safety Guard: Prevent early call with missing data
    missing = []
    if not ticket_number or "unknown" in ticket_number.lower(): missing.append("ticket_number")
    if not flight_number or "unknown" in flight_number.lower(): missing.append("flight_number")
    if not date or "unknown" in date.lower(): missing.append("date")
    if not passenger_name or "unknown" in passenger_name.lower(): missing.append("passenger_name")
    
    if missing:
        return f"REJECTION: I am missing {', '.join(missing)}. Please ask the user for these specific details politely."

    # Sanitize inputs for weak LLM capabilities
    cl_date = date.split(" ")[0].split("T")[0].strip()
    
    args = {
        "ticket_number": ticket_number.replace(" ", "").upper(),
        "flight_number": flight_number.replace(" ", "").upper(),
        "date": cl_date,
        "passenger_name": passenger_name.strip()
    }
    result = await mcp_session.call_tool("check_in", arguments=args)
    return str(result.content)

tools = [get_all_flights, search_flights, book_flight, check_in]

def get_system_message():
    current_date = datetime.now().strftime("%Y-%m-%d")
    return SystemMessage(content=f"""You are a helpful and professional Airline Assistant. Today's date is {current_date}. 

Your goal is to assist customers with flight searches, bookings, and check-ins. Be polite, natural, and efficient. 

INTENT GUIDELINES:
- **Search**: Before searching, naturally find out if they want a **Round-Trip** or **One-Way**. 
  - If One-Way: You need Departure Airport, Destination Airport, and Date.
  - If Round-Trip: You need Departure Airport, Destination Airport, Departure Date, and Return Date.
- **Booking**: You need Flight Number, Passenger Name(s), and Date.
- **Check-in**: You need Ticket Number, Passenger Name, Flight Number, and Date. Do NOT assume a name; always ask/confirm. Do NOT use today's date for a booking unless explicitly asked.

STRICT RULES:
1. NO PREMATURE CALLS: Do not call a tool until you have all the required information for that specific task. If data is missing, ask for it in a polite, conversational way.
2. DATA INTEGRITY: You are a TOOL EXECUTION ENGINE. Do not invent flight data or success messages. Only report what the tools return.
3. CONTEXT: Stay focused on the user's current request. Do not switch from check-in to searching unless asked.

Be concise but friendly.
""")

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = []
        
    history = sessions[session_id]
    history.append(HumanMessage(content=request.message))
    
    # Gemini Optimization: Dynamic System Message + Sliding Window (last 40 messages for stability)
    current_system_message = get_system_message()
    full_history = [current_system_message] + history[-40:]
    
    llm = ChatOllama(model="llama3.1")
    llm_with_tools = llm.bind_tools(tools)
    
    try:
        response = await llm_with_tools.ainvoke(full_history)
        history.append(response)
        
        while response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                if not tool_name:
                    continue
                tool_args = tool_call["args"]
                
                tool_func = next((t for t in tools if t.name == tool_name), None)
                if not tool_func:
                    result_content = f"Error: Tool {tool_name} not found."
                else:
                    try:
                        result_content = await tool_func.ainvoke(tool_args)
                    except Exception as e:
                        result_content = str(e)
                
                history.append(ToolMessage(tool_call_id=tool_call["id"], content=result_content))
                
            # Keep history context stable
            response = await llm_with_tools.ainvoke([current_system_message] + history[-40:])
            history.append(response)

        final_content = response.content
        if isinstance(final_content, list):
            final_content = " ".join([str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in final_content])
        elif not isinstance(final_content, str):
            final_content = str(final_content)
            
        return {"response": final_content.strip()}
    
    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "Failed to connect" in error_msg:
            return {"response": "Could not connect to Ollama. Please make sure the Ollama app is running locally!"}
        return {"response": f"I encountered an AI error: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_api:app", host="0.0.0.0", port=8001, reload=True)

import os
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

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
    args = {"number_of_people": 1, "is_round_trip": False, "skip": skip}
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def search_flights(airport_from: Optional[str] = None, airport_to: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, number_of_people: int = 1, is_round_trip: bool = False, skip: int = 0) -> str:
    """Use this tool ONLY if the user specifically provides SOME filtering criteria (like airport locations OR dates) to search."""
    args = {
        "number_of_people": number_of_people,
        "is_round_trip": is_round_trip,
        "skip": skip
    }
    if airport_from:
        args["airport_from"] = airport_from
    if airport_to:
        args["airport_to"] = airport_to
    if date_from:
        args["date_from"] = date_from
    if date_to:
        args["date_to"] = date_to
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def book_flight(flight_number: str, flight_date: str, passenger_names: List[str]) -> str:
    """Book a flight ticket. REQUIRES flight_number, flight_date (YYYY-MM-DD), and passenger_names."""
    
    # Sanitize inputs
    cl_date = flight_date.split(" ")[0].split("T")[0].strip()
    
    args = {
        "flight_number": flight_number.replace(" ", "").upper(),
        "flight_date": cl_date,
        "passenger_names": passenger_names
    }
    result = await mcp_session.call_tool("book_flight", arguments=args)
    return str(result.content)

@tool
async def check_in(ticket_number: str, flight_number: str, flight_date: str, passenger_name: str) -> str:
    """Perform a check-in. REQUIRES ticket_number, flight_number, flight_date (YYYY-MM-DD), and passenger_name."""
    
    # Sanitize inputs for weak LLM capabilities
    cl_date = flight_date.split(" ")[0].split("T")[0].strip()
    
    args = {
        "ticket_number": ticket_number.replace(" ", "").upper(),
        "flight_number": flight_number.replace(" ", "").upper(),
        "flight_date": cl_date,
        "passenger_name": passenger_name.strip()
    }
    result = await mcp_session.call_tool("check_in", arguments=args)
    return str(result.content)

tools = [get_all_flights, search_flights, book_flight, check_in]

system_message = SystemMessage(content="""You are an Airline Assistant. Speak ONLY in English.
You have 4 tools: get_all_flights, search_flights, book_flight, check_in.

You are a TOOL EXECUTION ENGINE. You are FORBIDDEN from generating your own flight data, ticket numbers, or success messages.

ACTION MAPPINGS:
- USER: "Buy/Book" -> CALL tool: book_flight(flight_number, passenger_name, date)
- USER: "Check in" -> CALL tool: check_in(ticket_number, passenger_name, flight_number, date)
- USER: "Find/Search" -> CALL tool: search_flights(airport_from, airport_to, date_from)

STRICT OPERATIONAL RULES:
1. NO TOOL OUTPUT = NO DATA. 
   - Never say "Booking successful" unless the tool returned a success message.
   - Never generate a ticket number (e.g. AEB99DD6). ONLY report the one from the tool.
2. NO CHAT: If data is missing (e.g. "Who is the passenger?"), ask briefly and STOP.
3. Once data is ready, CALL THE TOOL IMMEDIATELY.
4. Report Tool Results LITERALLY. If check_in returns a Seat Number, you MUST print it.

DO NOT ROLEPLAY. EXECUTE THE TOOL OR ASK FOR MISSING DATA.
""")

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = [system_message]
        
    history = sessions[session_id]
    history.append(HumanMessage(content=request.message))
    
    # Always keep system message at the top
    full_history = [system_message] + history
    
    llm = ChatOllama(model="llama3.2")
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
                
            response = await llm_with_tools.ainvoke([system_message] + history)
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

import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool

from mcp import ClientSession
from mcp.client.sse import sse_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MCP_SERVER_URL = "http://localhost:8002/sse"   # Standalone MCP server address

class ChatRequest(BaseModel):
    message: str
    session_id: str

sessions = {}

mcp_client_ctx = None
mcp_session_ctx = None
mcp_session: ClientSession = None

# ---------------------------------------------------------------------------
# MCP Connection (SSE/HTTP)
# ---------------------------------------------------------------------------
async def init_mcp():
    global mcp_client_ctx, mcp_session_ctx, mcp_session
    mcp_client_ctx = sse_client(MCP_SERVER_URL)
    read, write = await mcp_client_ctx.__aenter__()
    mcp_session_ctx = ClientSession(read, write)
    mcp_session = await mcp_session_ctx.__aenter__()
    await mcp_session.initialize()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mcp()
    yield
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

# ---------------------------------------------------------------------------
# LangChain Tools  (thin wrappers — NO Python-level guards, LLM decides)
# ---------------------------------------------------------------------------

@tool
async def get_all_flights() -> str:
    """List ALL available flights in the system. Call this when the user wants to see all flights without any filters."""
    args = {"number_of_people": 1, "is_round_trip": False}
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def search_flights(
    airport_from: str,
    airport_to: str,
    date: str,
    date_to: Optional[str] = None,
    number_of_people: int = 1,
    is_round_trip: bool = False
) -> str:
    """
    Search for flights between two airports on a given date.
    Required: airport_from (IATA code), airport_to (IATA code), date (YYYY-MM-DD).
    For round-trips also provide date_to (return date) and set is_round_trip=True.
    """
    args = {
        "airport_from": airport_from.upper(),
        "airport_to": airport_to.upper(),
        "date": date,
        "number_of_people": number_of_people,
        "is_round_trip": is_round_trip,
    }
    if date_to:
        args["date_to"] = date_to
    result = await mcp_session.call_tool("search_flights", arguments=args)
    return str(result.content)

@tool
async def book_flight(flight_number: str, date: str, passenger_names: List[str]) -> str:
    """
    Book seats on a flight and receive ticket numbers.
    Required: flight_number, date (YYYY-MM-DD), passenger_names (list of full names).
    """
    cl_date = date.split(" ")[0].split("T")[0].strip()
    args = {
        "flight_number": flight_number.replace(" ", "").upper(),
        "date": cl_date,
        "passenger_names": passenger_names,
    }
    result = await mcp_session.call_tool("book_flight", arguments=args)
    return str(result.content)

@tool
async def check_in(ticket_number: str, flight_number: str, date: str, passenger_name: str) -> str:
    """
    Perform check-in for an existing ticket and receive a seat assignment.
    Required: ticket_number, flight_number, date (YYYY-MM-DD), passenger_name.
    """
    cl_date = date.split(" ")[0].split("T")[0].strip()
    args = {
        "ticket_number": ticket_number.replace(" ", "").upper(),
        "flight_number": flight_number.replace(" ", "").upper(),
        "date": cl_date,
        "passenger_name": passenger_name.strip(),
    }
    result = await mcp_session.call_tool("check_in", arguments=args)
    return str(result.content)

tools = [get_all_flights, search_flights, book_flight, check_in]

# ---------------------------------------------------------------------------
# System Prompt — ReAct pattern, LLM is the orchestrator
# ---------------------------------------------------------------------------
def get_system_message():
    current_date = datetime.now().strftime("%Y-%m-%d")
    return SystemMessage(content=f"""You are an Airline AI Agent. Today's date is {current_date}.

You have access to 4 tools:
- get_all_flights(): List all available flights.
- search_flights(airport_from, airport_to, date, [date_to], [is_round_trip]): Search for flights.
- book_flight(flight_number, date, passenger_names): Book a flight ticket.
- check_in(ticket_number, flight_number, date, passenger_name): Check in with an existing ticket.

YOUR DECISION PROCESS — follow this for every user message:

1. THINK: Identify the user's intent (search / book / check-in / list).
   Then check: do I have ALL required parameters for the correct tool?
   - search_flights needs: airport_from, airport_to, date
   - book_flight needs: flight_number, date, passenger_names
   - check_in needs: ticket_number, flight_number, date, passenger_name

2. ACT:
   - If ALL required parameters are present → call the tool immediately.
   - If ANY parameter is missing → ask the user ONLY for the missing ones, politely.
   - For search: first ask if it's One-Way or Round-Trip, then collect airports and date(s).
   - NEVER switch intent (e.g. do not search for flights during a check-in flow).

3. OBSERVE: Read the tool's response carefully.

4. RESPOND: Report the result to the user clearly and concisely.
   Never invent ticket numbers, seat numbers, or flight data.
   Only report what the tools return.
""")

# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------
@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = []

    history = sessions[session_id]
    history.append(HumanMessage(content=request.message))

    current_system_message = get_system_message()
    full_history = [current_system_message] + history[-40:]

    llm = ChatOllama(model="llama3.1", temperature=0.0)  # Deterministic for reliable tool orchestration
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
                    result_content = f"Error: Tool '{tool_name}' not found."
                else:
                    try:
                        result_content = await tool_func.ainvoke(tool_args)
                    except Exception as e:
                        result_content = str(e)

                history.append(ToolMessage(tool_call_id=tool_call["id"], content=result_content))

            response = await llm_with_tools.ainvoke([current_system_message] + history[-40:])
            history.append(response)

        final_content = response.content
        if isinstance(final_content, list):
            final_content = " ".join(
                [str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in final_content]
            )
        elif not isinstance(final_content, str):
            final_content = str(final_content)

        return {"response": final_content.strip()}

    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "Failed to connect" in error_msg:
            return {"response": "Could not connect to Ollama. Please make sure the Ollama app is running locally!"}
        return {"response": f"An AI error occurred: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_api:app", host="0.0.0.0", port=8001, reload=True)

# ✈️ Airline AI Assistant Chatbot

> [!IMPORTANT]
> **📽️ Presentation Video**: [Click here to Access Google Drive](https://drive.google.com/drive/folders/1ecz4At40q8SAYgaV_3IipXfqtwon07me?usp=sharing)

This repository contains the **Airline AI Agent**, a professional-grade implementation of a Service-Oriented Architecture (SOA). It features an agentic AI built with **Llama 3.1 (8B)** and **LangChain**, interacting with a production-ready cloud backend hosted on **Azure**, powered by a **Neon (PostgreSQL)** database.

---

## 🏛️ System Design & Architecture (SOA)

This project is built using a modern **Service-Oriented Architecture (SOA)**, cleanly separating the intelligence layer from the data layer:

1.  **Intelligence Layer (Local — port 8001)**: Powered by **Llama 3.1 (8B)** via Ollama. A **FastAPI** agent receives chat messages and uses LangChain to bind the LLM to MCP tools. The LLM acts as the true **orchestrator** — it decides which tool to call and when, following a ReAct (Reason + Act) pattern.
2.  **Tooling Layer (Local — port 8002)**: A **standalone MCP (Model Context Protocol) Server** (`mcp_server.py`) runs as an independent HTTP/SSE service. The agent connects to it over the network, and the LLM calls its tools to perform real actions.
3.  **Service Layer (Cloud)**: The MCP server connects to a production-ready **Azure-hosted Airline API Gateway**, which is backed by a **Neon (PostgreSQL)** cloud database.
4.  **UI Layer**: A modern, responsive chat interface built with **React** (port 5173).

```
[User (React :5173)]
       ↓
[FastAPI Agent :8001]  ←→  [Llama 3.1 via Ollama]
       ↓  (HTTP/SSE)
[MCP Server :8002]
       ↓  (HTTPS REST)
[Azure API Gateway]
       ↓
[Neon PostgreSQL DB]
```

---

## 🛡️ Technical Stability & Security

To ensure production-grade reliability and avoid common LLM pitfalls, several guardrails were implemented:

-   **Unified Parameter Schema**: All tools (`search_flights`, `book_flight`, `check_in`) share a single, consistent `date` parameter (YYYY-MM-DD). This eliminates parameter-name routing errors that cause small models to lose context.
-   **Python-Level Safety Guards**: To prevent AI "hallucinations," transactional tools include Python-level pre-call validation. If the LLM attempts to call a tool with missing or placeholder data, execution is blocked and the agent is instructed to ask the user for the specific missing field.
-   **VRAM & Context Management**:
    - **40-Message Sliding Window**: The agent maintains the last 40 messages in history, preventing GPU memory (VRAM) overflow while preserving long-term conversational context.
    - **Pagination Safety**: Flight searches are capped at 5 pages (50 results max) to prevent context-window bloating and out-of-memory (OOM) crashes.
-   **Input Sanitization**: All user-provided dates are stripped of time-zone suffixes (`T`, spaces) and flight/ticket codes are uppercased before being sent to the API.

---

## 🧠 Logical Assumptions & Guardrails

### ✅ Design Decisions

- **Directional Search**: Round-trip requests perform two sequential, atomic searches (Outbound leg & Return leg) with airports automatically swapped for the return. This prevents the model from hallucinating return flight data.
- **Data-Driven Transparency**: The AI is a "Tool Execution Engine." It is explicitly forbidden from inventing ticket numbers, seat numbers, or success messages. It reports **ONLY** what the backend API returns.
- **Explicit Intent Mapping**: The agent follows a strict intent-locking system. A check-in flow will never accidentally trigger a flight search, and vice versa.
- **Typo Tolerance (MCP Layer)**: The backend API uses a misspelled field `passeger_names`. This is silently corrected at the MCP layer, shielding the AI and the user from this backend inconsistency.
- **Auto-Auth**: The MCP server automatically handles OAuth2 authentication (fetching a Bearer token before booking) and can self-register if the user doesn't exist yet.

### ⚠️ Known Constraints & Limitations

These are known limitations arising from the use of a **local, open-source 8B parameter model** (Llama 3.1):

| Constraint | Description |
|---|---|
| **English Only** | The agent is designed to operate in **English only**. Llama 3.1's tool-calling capability is fine-tuned primarily on English data. Sending queries in other languages (e.g., Turkish) will likely cause the model to lose intent, skip tool calls, or respond conversationally instead of executing the correct action. |
| **Avoid Long Dialogues** | Llama 3.1 (8B) has a limited effective reasoning window. After **5–6 back-and-forth turns** within a single task flow, the model can lose track of the original intent and begin hallucinating or asking for information it already has. It is strongly recommended to provide all required data in as few messages as possible. |
| **Concise Input Preferred** | The model performs best when inputs are short and structured. Long, conversational sentences (e.g., *"Well, I was thinking maybe I could possibly fly from Istanbul..."*) degrade tool-call accuracy compared to direct inputs (e.g., *"IST to JFK on 2026-05-15"*). |
| **Ambiguity Sensitivity** | Relative time expressions such as *"tomorrow"*, *"next week"*, or *"this Friday"* are not reliably interpreted. Always use the explicit **YYYY-MM-DD** date format for consistent results. |
| **Context Window (128K tokens)** | While Llama 3.1 supports a 128K token context window, practical performance degrades significantly with large flight result sets. The 40-message sliding window and 50-result pagination cap are in place specifically to prevent this. |
| **Sequential Tool Calls** | The agent processes one tool at a time per reasoning cycle. It cannot search multiple routes in parallel or perform simultaneous booking and check-in. |
| **Hardware Dependency** | Running Llama 3.1 (8B) locally requires a GPU with at least **8GB VRAM** (e.g., NVIDIA RTX 4060). CPU-only execution is significantly slower (~10x) and not recommended for live demos. |
| **Single Session in Demo** | The agent's memory is session-based and stored in-memory. Restarting the server clears all conversation history. |

---

## 🚀 Installation & Setup

### 🛠️ Prerequisites
1. **Ollama**: [Download Ollama](https://ollama.com/) and pull the model:
   ```bash
   ollama pull llama3.1:8b
   ```
2. **Python 3.10+**
3. **Node.js & npm** (for the React frontend)

### ⚙️ Quick Start
1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd ai_agent
   ```
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application**:
   - **Windows**: Double-click or run `run.bat`
   - **Mac/Linux**: Run `bash run.sh`

The script will start Ollama (if not running), the FastAPI backend on port `8001`, and the React frontend.

---

## 🧪 Some Test Cases

1.  **List All Flights**: *"Show me all available flights."* → Calls `get_all_flights` and lists results.
2.  **One-Way Search**: *"Find flights from IST to JFK on 2026-05-15."* → Returns labeled `[OUTBOUND]` results.
3.  **Round-Trip Search**: *"Find flights IST to JFK on 2026-05-15, return on 2026-05-20."* → Returns both `[OUTBOUND]` and `[RETURN]` labeled results.
4.  **Booking**: *"I want to buy a ticket."* → Agent asks for Flight Number, Passenger Name, and Date, then books via the API.
5.  **Check-in**: *"I want to check in."* → Agent asks for Ticket Number, Name, Flight Number, and Date, then returns the assigned seat.

---

## 🔗 Resources
- **Model**: Llama 3.1 (8B) via [Ollama](https://ollama.com/)
- **Agent Framework**: [LangChain](https://python.langchain.com/)
- **Backend API**: [FastAPI](https://fastapi.tiangolo.com/) + [FastMCP](https://github.com/jlowin/fastmcp)
- **UI**: [React](https://react.dev/)
- **Cloud Backend**: [Azure App Service](https://azure.microsoft.com/en-us/products/app-service)
- **Database**: [Neon (PostgreSQL)](https://neon.tech/)
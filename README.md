# ✈️ Airline AI Assistant Chatbot

> [!IMPORTANT]
> **📽️ Presentation Video**: [Click here to Access Google Drive](https://drive.google.com/drive/folders/1ecz4At40q8SAYgaV_3IipXfqtwon07me?usp=sharing)

This repository contains the **Airline AI Agent**, a professional-grade implementation of a Service-Oriented Architecture (SOA). It features an agentic AI interacting with a production-ready cloud backend.

---

## 🏛️ System Design & Architecture (SOA)

This project is built using a modern **Service-Oriented Architecture (SOA)**, separating the intelligence layer from the data layer:

1.  **Intelligence Layer (Local)**: Powered by **Llama 3.1 (8B)** via Ollama. It orchestrates user requests through a custom **FastAPI Agent**.
2.  **Tooling Layer (Local)**: A custom **MCP (Model Context Protocol)** server (`mcp_server.py`) acts as a secure adapter, translating AI intents into API calls.
3.  **Service Layer (Cloud)**: The agent connects to a production-ready **Azure-hosted Airline API Gateway**. This backend is connected to a scalable **Neon (PostgreSQL)** database.
4.  **UI Layer**: A modern Chat interface built with **React**.

---

## 🛡️ Technical Stability & Security

To ensure production-grade reliability and avoid common LLM pitfalls, several guardrails were implemented:

-   **Unified Parameter Schema**: All tools share a consistent `date` parameter, eliminating routing errors and ensuring the AI remains locked to the correct transaction.
-   **Python-Level Safety Guards**: To prevent AI "hallucinations," transactional tools (Booking/Check-in) include Python-level validation. The agent is blocked from execution until the user explicitly confirms all required data points.
-   **VRAM & Context Management**: 
    - **40-Message Sliding Window**: Maintains long-term context while preventing GPU memory overflow.
    - **Pagination Safety**: Flight searches are limited to a maximum of 5 pages (50 results) to maintain a stable context window.

---

## 🧠 Logical Assumptions & Guardrails

- **Directional Search**: Round-trip requests perform automated sequential searches (Outbound/Return) to ensure data accuracy.
- **Data-Driven Transparency**: The AI is forbidden from inventing ticket numbers or flight schedules. It reports ONLY what the backend returns.
- **Explicit Intent Mapping**: The agent follows a strict intent logic, preventing accidental "switching" between check-in and booking flows.

---

## 🚀 Installation & Setup

### 🛠️ Prerequisites
1. **Ollama**: [Download Ollama](https://ollama.com/). Pull the model: `ollama run llama3.1:8b`
2. **Python 3.10+**
3. **Node.js & npm**

### ⚙️ Quick Start
1. **Clone this repository**.
2. **Install Dependencies**:
   - Backend: `pip install -r requirements.txt`
3. **Run the Application**:
   - **Windows**: Run `run.bat`
   - **Mac/Linux**: Run `bash run.sh`

---

## 🧪 Presentation Test Cases

1.  **Round-Trip**: *"Find flights IST to JFK on 2026-05-15, return on 2026-05-20."* (Shows directional labeling).
2.  **Booking**: *"I am Ali, buy a ticket for TK2026 on 2026-05-15."* (Shows explicit name mapping and transaction).
3.  **Check-in**: *"Check in for ticket [NUM], name Ali, flight TK2026."* (Shows live data validation and seat assignment).

---

## 🔗 Resources
- **Model**: Llama 3.1 (8B) Optimized
- **Stack**: LangChain, FastAPI, FastMCP, React
- **Cloud Backend**: Azure App Service
- **Database**: Neon (PostgreSQL)
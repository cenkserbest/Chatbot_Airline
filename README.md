# ✈️ Airline AI Assistant Chatbot

> [!IMPORTANT]
> **📽️ Presentation Video**: [Click here to Access Google Drive](https://drive.google.com/drive/folders/1ecz4At40q8SAYgaV_3IipXfqtwon07me?usp=sharing)

This repository contains the **Airline AI Agent**, a professional-grade implementation of a Service-Oriented Architecture (SOA). It features an agentic AI built with **Llama 3.2** and **LangChain**, interacting with a production-ready cloud backend.

---

## 🏛️ System Design & Architecture (SOA)

This project is built using a modern **Service-Oriented Architecture (SOA)**, separating the intelligence layer from the data layer:

1.  **Intelligence Layer (Local)**: Powered by **Llama 3.2 (3B)** via Ollama. It orchestrates user requests through a custom **FastAPI Agent**.
2.  **Tooling Layer (Local)**: A custom **MCP (Model Context Protocol)** server (`mcp_server.py`) acts as a secure adapter, translating AI intents into API calls.
3.  **Service Layer (Cloud)**: The agent connects to a production-ready **Azure-hosted Airline API Gateway**. This backend has been specifically optimized for the final submission to resolve historical SQL performance issues and data integrity bugs.
4.  **UI Layer**: A modern Chat interface built with **React** for seamless user interaction.

---

## 🧠 Logical Assumptions & Guardrails

To ensure a robust user experience and 100% data integrity, we implemented the following:
- **Directional Search**: Round-trip requests perform two atomic searches (Outbound/Return) to prevent AI hallucination over flight legs.
- **Zero-Tolerance Hallucination**: The system prompt enforces a "Data-Only" policy. If the API doesn't provide it, the AI is forbidden from making it up.
- **Explicit Approval Flow**: All transactional actions (Booking/Check-in) require a final user "YES" confirmation to ensure accuracy.
- **Cloud Synchronization**: Every search is performed in real-time against the live Azure database.

---

## 🚀 Installation & Setup

### 🛠️ Prerequisites
1. **Ollama**: [Download Ollama](https://ollama.com/). Pull the model: `ollama run llama3.2`
2. **Python 3.10+**
3. **Node.js & npm**

### ⚙️ Quick Start
1. **Clone this repository**.
2. **Install Dependencies**:
   - Backend: `pip install -r requirements.txt`
   - Frontend: `cd frontend && npm install`
3. **Run the Application**:
   - **Windows**: Run `run.bat`
   - **Mac/Linux**: Run `bash run.sh`

*The system will automatically connect to the Azure Gateway URL.*

---

## 🧪 Presentation Test Cases

1.  **Round-Trip**: *"Find flights IST to JFK on 2026-05-15, return on 2026-05-20."* (Shows directional labeling).
2.  **Booking**: *"I am Ali, buy a ticket TK2026 for 2026-05-15."* (Shows explicit approval and memory).
3.  **Check-in**: *"Check in for ticket [NUM], name Ali, flight TK2026."* (Shows data validation and seat assignment).

---

## 🔗 Resources
- **Model**: Llama3.2 (3B)
- **Stack**: LangChain, FastAPI, FastMCP, React
- **Cloud Backend**: Azure App Service (Azure SQL Database)
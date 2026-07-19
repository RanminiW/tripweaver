# TripWeaver — MCP-Based Multi-Agent Travel Planner

TripWeaver is a multi-agent travel planning assistant built with **LangGraph**, **FastAPI**, and **Gradio**. A traveller chats naturally about flights, hotels, or general travel questions, and the system routes the request to a specialised agent (General QA, Hotel, or Flight), which calls out to live services through the **Model Context Protocol (MCP)** to search, list, and book real travel options.

**Live demo:** `https://tripweaver-production-be26.up.railway.app`
**Backend API:** `https://tripweaver-production-4416.up.railway.app`
**Repository:** `https://github.com/RanminiW/tripweaver`

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Local Setup](#local-setup)
4. [MCP Server Setup Guide](#mcp-server-setup-guide)
5. [Running Locally](#running-locally)
6. [Deployment (Railway)](#deployment-railway)
7. [User Guide](#user-guide)
8. [Known Limitations](#known-limitations)
9. [Tech Stack](#tech-stack)

---

## Features

- **Intent-routed multi-agent workflow** — a router agent classifies each message and hands off to the General QA, Hotel, or Flight agent.
- **Live MCP integration** — flight and hotel search/booking are served by standalone MCP servers, not hardcoded in-process logic. Swapping either service does not require touching agent code.
- **Streaming responses with activity cues** — the UI shows what the system is doing ("Searching hotel suggestions…", "Booking your flight…") while agents work, instead of a single blocking wait.
- **Graceful failure handling** — if a flight or hotel service goes down, the affected agent returns a clear, friendly message. The rest of the app (other agents, other services) keeps working. Nothing crashes.
- **Conversational memory** — the last few exchanges are included in each request so the assistant keeps context across a session.

---

## Architecture

```
┌──────────────┐      HTTP       ┌──────────────┐
│   Gradio     │ ───────────────▶│   FastAPI    │
│  Frontend    │◀─── streaming ──│   (main.py)  │
└──────────────┘   (SSE events)  └──────┬───────┘
                                         │
                                  LangGraph workflow
                                         │
                     ┌───────────────────┼───────────────────┐
                     ▼                   ▼                   ▼
              ┌────────────┐      ┌────────────┐      ┌────────────┐
              │  Router     │      │ Hotel Node │      │ Flight Node│
              │ (intent +   │      │            │      │            │
              │ extraction) │      └─────┬──────┘      └─────┬──────┘
              └────────────┘             │                   │
                                   MCP (streamable-http) MCP (streamable-http)
                                          │                   │
                                          ▼                   ▼
                                  ┌──────────────┐    ┌──────────────┐
                                  │ hotel-service│    │flight-service│
                                  │  (MCP server)│    │  (MCP server)│
                                  └──────┬───────┘    └──────┬───────┘
                                         │                   │
                                         ▼                   ▼
                                   External Hotel API   External Flight API
```

**Why separate MCP servers?** Each external capability (hotels, flights) is exposed by its own standalone MCP server rather than being called in-process. This means:

- The `main` backend never talks to the hotel/flight APIs directly — it discovers and calls tools (`get_hotels`, `search_hotel`, `book_hotel`, `get_flights`, `search_flights`, `book_flight`) over the MCP protocol.
- If one MCP server goes down, the FastAPI app and the other agents are unaffected, because each server runs as an isolated process/container.
- Swapping an underlying travel API only requires changing the relevant MCP server file — the agent and graph code are untouched.

### Project structure

```
tripweaver/
├── agents/
│   ├── entity.py        # GraphState definition
│   ├── graph.py          # LangGraph workflow assembly
│   ├── llm.py             # LLM client setup
│   ├── mcp_tools.py       # MCP client bridge — the only file that knows server URLs
│   ├── nodes.py           # Router, Hotel, Flight, QA node logic
│   ├── prompts.py         # System prompts
│   └── tools.py           # (legacy — logic migrated to mcp_servers/)
├── mcp_servers/
│   ├── flight_service.py  # Standalone MCP server exposing flight tools
│   └── hotel_service.py   # Standalone MCP server exposing hotel tools
├── entity.py               # ChatRequest / ChatResponse models
├── main.py                 # FastAPI app, /chat and /chat/stream endpoints
├── frontend.py              # Gradio chat UI
├── requirements.txt
└── .env                     # Local secrets (not committed)
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/RanminiW/tripweaver.git
cd tripweaver
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file at the project root:

```
OPENAI_API_KEY=your-openai-api-key
BACKEND_URL=http://127.0.0.1:8080/chat
```

`.env` is listed in `.gitignore` and must never be committed.

---

## MCP Server Setup Guide

TripWeaver runs **two independent MCP servers**, each exposing a set of tools over `streamable-http` transport. They are ordinary Python processes and must be running *before* the FastAPI backend starts, since the backend connects to them at startup.

### flight_service.py (port 8000 by default)

Exposes:
- `get_flights` — list all flights
- `search_flights(origin, destination, date?)` — search by route
- `book_flight(flight_id, passenger_name, passenger_email)` — book a flight

### hotel_service.py (port 8001 by default)

Exposes:
- `get_hotels` — list all hotels
- `search_hotel(city, checkIn?, checkOut?)` — search by city
- `book_hotel(hotel_id, guest_name, guest_email, check_in_date, check_out_date, room_type)` — book a room

Both servers read their listening port from the `PORT` environment variable (defaulting to 8000/8001 locally), and bind to `0.0.0.0` so they are reachable both locally and from other containers in a deployed environment.

### How the backend finds them

`agents/mcp_tools.py` is the single bridge between the agents and the MCP layer:

```python
MCP_SERVERS = {
    "hotel":  {"url": os.environ.get("HOTEL_SERVICE_URL",  "http://localhost:8001/mcp"), "transport": "streamable_http"},
    "flight": {"url": os.environ.get("FLIGHT_SERVICE_URL", "http://localhost:8000/mcp"), "transport": "streamable_http"},
}
```

At startup, `init_mcp_tools()` connects to both servers via `MultiServerMCPClient` and caches the discovered tools. Agent nodes retrieve tools by name via `get_tool("search_flights")` etc. — they never import server logic directly. Because MCP responses are wrapped in content blocks (`[{"type": "text", "text": "<json>"}]`), every tool result is passed through `parse_mcp_result()` to unwrap it into plain Python dicts before use.

### Testing an MCP server in isolation

Each server can be started and queried independently, useful for verifying it works before wiring it into the agents:

```bash
python mcp_servers/flight_service.py
```

Then, in a separate script or the MCP Inspector, connect a `MultiServerMCPClient` to `http://localhost:8000/mcp` and call `get_tools()` / `ainvoke()` to confirm real data comes back.

---

## Running Locally

Four processes run simultaneously, each in its own terminal, **in this order**:

```bash
# Terminal 1 — flight MCP server
python mcp_servers/flight_service.py

# Terminal 2 — hotel MCP server
python mcp_servers/hotel_service.py

# Terminal 3 — FastAPI backend (must start after both MCP servers)
python main.py

# Terminal 4 — Gradio frontend
python frontend.py
```

Once all four are running, open the Gradio URL printed in Terminal 4 (typically `http://127.0.0.1:7860`) and start chatting.

### Quick manual test

- `http://127.0.0.1:8080/` → welcome message
- `http://127.0.0.1:8080/hotels` → live hotel data
- `http://127.0.0.1:8080/flights` → live flight data

### Resilience test

Stop `flight_service.py` while the app is running, then ask a flight question in the chat. You should see a friendly "temporarily unavailable" message — not a crash — and a hotel question sent immediately after should still work normally.

---

## Deployment (Railway)

The app is deployed as **four independent services within one Railway project**, connected over Railway's private network so the MCP servers are never exposed publicly.

| Service | Start command | Public domain |
|---|---|---|
| `flight-service` | `python mcp_servers/flight_service.py` | No (internal only) |
| `hotel-service` | `python mcp_servers/hotel_service.py` | No (internal only) |
| `main` | `python main.py` | Yes |
| `frontend` | `python frontend.py` | Yes |

### Steps

1. Push the repository to GitHub.
2. In Railway, create a new project from the GitHub repo, then add three more services from the same repo (four services total in one project).
3. For each service, set its **Custom Start Command** (Settings → Deploy) as per the table above.
4. Give `flight-service` and `hotel-service` a fixed `PORT` value (`8000` and `8001` respectively) via their Variables tab, so the backend can rely on a known port.
5. Generate a public domain (Settings → Networking) for `main` and `frontend` only.
6. Set environment variables:

   **On `main`:**
   ```
   OPENAI_API_KEY=<your key>
   FLIGHT_SERVICE_URL=http://${{flight-service.RAILWAY_PRIVATE_DOMAIN}}:8000/mcp
   HOTEL_SERVICE_URL=http://${{hotel-service.RAILWAY_PRIVATE_DOMAIN}}:8001/mcp
   ```
   Using Railway's `${{service.RAILWAY_PRIVATE_DOMAIN}}` reference syntax (rather than hand-typing `service-name.railway.internal`) is what reliably resolves the internal DNS.

   **On `frontend`:**
   ```
   BACKEND_URL=https://<main's-public-domain>/chat
   ```
7. Ensure `main.py`, `frontend.py`, and both MCP server files all read the `PORT` environment variable rather than a hardcoded port, since Railway assigns ports dynamically for public-facing services:
   ```python
   port = int(os.environ.get("PORT", 8080))
   ```

Railway auto-redeploys each service whenever its part of the repo changes and is pushed to the connected branch.

### Common pitfalls (encountered during this deployment)

- **`pywin32` in `requirements.txt`** — if `requirements.txt` was generated via `pip freeze` on Windows, it may include Windows-only packages that fail to install on Railway's Linux build image. Remove any `pywin32==...` line before pushing.
- **MCP server binding to `127.0.0.1`** — FastMCP must be told to bind to `host="0.0.0.0"`, or it will be unreachable from other containers even though it reports as healthy.
- **DNS resolution for private networking** — manually typing `<service>.railway.internal` can be fragile; using Railway's `${{service.RAILWAY_PRIVATE_DOMAIN}}` reference variable is the reliable approach.
- **Service naming** — Railway service names must be lowercase with simple characters; a service name auto-generated from a mixed-case, hyphen-heavy repo name can be rejected outright.

---

## User Guide

1. Open the frontend URL.
2. Type a natural-language request, e.g.:
   - *"Show me hotels in Bangkok"*
   - *"Flights from CMB to BKK on 2025-11-15"*
   - *"Book hotel `<hotel_id>` for Jane Smith, jane@email.com, check in 2026-08-10, check out 2026-08-15, room type double"*
   - *"What's the best time of year to visit Japan?"*
3. Watch the status line update ("Understanding your request…", "Searching hotel suggestions…") while the relevant agent works.
4. The final response streams in with formatted results.
5. If a service is temporarily unavailable, the assistant explains this clearly instead of failing silently — try another request type (e.g. hotels) in the meantime.

*(Insert screenshots here: a hotel search result, a flight booking confirmation, and the resilience message shown when a service is down.)*

---

## Known Limitations

- **Referential booking is not yet resolved.** Asking to "book the second hotel" from a prior search result is not currently linked back to that result — the assistant will ask for an explicit `hotel_id` / `flight_id` instead. A future improvement would resolve ordinal references against `hotel_results` / `flight_results` already held in graph state.
- **No travel-themed visual design.** The interface uses Gradio's default styling rather than a custom travel-themed layout, by scope decision for this iteration.
- **Token-by-token LLM streaming** applies to the General QA agent's responses; hotel/flight results are revealed as a complete formatted block once the MCP call resolves, rather than being typed out character by character, since they are structured data rather than free-form LLM text.

---

## Tech Stack

- **Orchestration:** LangGraph
- **LLM:** OpenAI (via `langchain-openai`)
- **Backend:** FastAPI, Uvicorn
- **Frontend:** Gradio
- **Tool protocol:** Model Context Protocol (`mcp`, `langchain-mcp-adapters`), `streamable-http` transport
- **Deployment:** Railway (multi-service project with private networking)
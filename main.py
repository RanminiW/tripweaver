from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents.mcp_tools import init_mcp_tools, get_tool, parse_mcp_result

from entity import ChatRequest, ChatResponse
from agents.graph import graph
import os
import json
from fastapi.responses import StreamingResponse

NODE_CUES = {
    "hotel_node": {
        "search": "Searching hotel suggestions...",
        "list_all": "Fetching all hotels...",
        "book": "Booking your hotel...",
    },
    "flight_node": {
        "search": "Searching flight options...",
        "list_all": "Fetching all flights...",
        "book": "Booking your flight...",
    },
    "unknown_node": "Thinking...",
    "router": "Understanding your request...",
}


def get_cue(node_name: str, state: dict) -> str | None:
    cue = NODE_CUES.get(node_name)
    if cue is None:
        return None
    if isinstance(cue, dict):
        return cue.get(state.get("sub_action", "search"), "Working on it...")
    return cue

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mcp_tools()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(   #we need to integrate fronend using a middleware
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")  #simple API endpoint using fastAPI
async def greeting():
    return {
        "message" : "Welcome to multi agent travel planner"
    }


@app.get("/hotels")
async def hotels():
    result = await get_tool("get_hotels").ainvoke({})
    return parse_mcp_result(result)


@app.get("/flights")
async def flights():
    result = await get_tool("get_flights").ainvoke({})
    return parse_mcp_result(result)


conversation_history_messages = [] #to save our old conversation history

#post request to return output, we need to pass data to the server
@app.post("/chat")
async def chat(request:ChatRequest) -> ChatResponse:
    

    recent_pairs = conversation_history_messages[-3:] # working with last 3 messages(can change the amount if needed)
    flattened_messages = []
    for user_msg, assistant_msg in recent_pairs:
        flattened_messages.append(user_msg)
        flattened_messages.append(assistant_msg)
    flattened_messages.append(request.message)
    
    initial_state = {
        "messages": flattened_messages, #previsly i used only last message, but here we need to provide our list of messages
        "intent": "",
        "sub_action": "",
        "city": None,
        "check_in": None,
        "check_out": None,
        "origin": None,
        "destination": None,
        "flight_date": None,
        "hotel_id": None,
        "guest_name": None,
        "guest_email": None,
        "room_type": None,
        "flight_id": None,
        "passenger_name": None,
        "passenger_email": None,
        "hotel_results": [],
        "flight_results": [],
        "response_text": "",
    }

    result = await graph.ainvoke(initial_state) # result also needed to be appended to my conversation history message

    response_text = result.get("response_text", "Something went wrong. Please try again.")

    conversation_history_messages.append((request.message, response_text))

    return ChatResponse(
        response=result.get("response_text", "Something went wrong. Please try again"),
        hotels=result.get("hotel_results", []) or None,
        flights=result.get("flight_results", []) or None,
    )


#ENDPOINT

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    recent_pairs = conversation_history_messages[-3:]
    flattened_messages = []
    for user_msg, assistant_msg in recent_pairs:
        flattened_messages.append(user_msg)
        flattened_messages.append(assistant_msg)
    flattened_messages.append(request.message)

    initial_state = {
        "messages": flattened_messages,
        "intent": "", "sub_action": "",
        "city": None, "check_in": None, "check_out": None,
        "origin": None, "destination": None, "flight_date": None,
        "hotel_id": None, "guest_name": None, "guest_email": None, "room_type": None,
        "flight_id": None, "passenger_name": None, "passenger_email": None,
        "hotel_results": [], "flight_results": [], "response_text": "",
    }

    async def event_generator():
        accumulated = dict(initial_state)
        sent_cues = set()

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event.get("event")
                name = event.get("name")

                if kind == "on_chain_start" and name in NODE_CUES:
                    node_input = event.get("data", {}).get("input", {}) or {}
                    cue = get_cue(name, node_input)
                    if cue and cue not in sent_cues:
                        sent_cues.add(cue)
                        yield f"data: {json.dumps({'type': 'status', 'text': cue})}\n\n"

                if kind == "on_chain_end" and name in {
                    "router", "hotel_node", "flight_node", "unknown_node", "generate_response"
                }:
                    output = event.get("data", {}).get("output", {}) or {}
                    if isinstance(output, dict):
                        accumulated.update(output)

        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'text': 'Sorry, something went wrong. Please try again.'})}\n\n"
            return

        response_text = accumulated.get("response_text", "Something went wrong. Please try again.")
        conversation_history_messages.append((request.message, response_text))

        yield f"data: {json.dumps({'type': 'final', 'text': response_text, 'hotels': accumulated.get('hotel_results') or None, 'flights': accumulated.get('flight_results') or None})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":  #to run the application we are using uvicorn server
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port) #mention app to acces the fast API aplication we created at the top
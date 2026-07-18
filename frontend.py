import json
import os
from urllib.request import Request, urlopen
import gradio as gr
from dotenv import load_dotenv
import requests

load_dotenv()


def format_flights(flights):
    lines = ["Flights:"]
    for flight in flights:
        id = flight.get("_id") or "Unknown ID"
        airline = flight.get("airline", "Unknown Airline")
        flight_number = flight.get("flightNumber", "Unknown Flight Number")
        origin = flight.get("origin", {}).get("airport", "Unknown Origin")
        destination = flight.get("destination", {}).get("airport", "Unknown Destination")
        flight_date = flight.get("flightDate", "Unknown Date")
        departure_time = flight.get("departureTime", "Unknown Departure Time")
        arrival_time = flight.get("arrivalTime", "Unknown Arrival Time")
    
        available_seats = flight.get("availableSeats", "Unknown Available Seats")
        lines.append(
            f"{id}: {airline} {flight_number} from {origin} to {destination} "
            f"on {flight_date} {departure_time} - {arrival_time} "
            f"- {available_seats} seats"
        )
    return "\n".join(lines)


def format_hotels(hotels):
    lines = ["Hotels:"]
    for hotel in hotels:
        id = hotel.get("_id",) or "Unknown ID"
        name = hotel.get("name") or "Unknown Hotel"
        city = hotel.get("city") or hotel.get("location", {}).get("city", "")
        price_per_night = hotel.get("pricePerNight") or "Unknown ID"
        lines.append(f"{id}: {name} in {city} - {price_per_night} price/night")
    return "\n".join(lines)


#chat api stream

def call_chat_api_stream(message):
    stream_url = os.getenv("BACKEND_URL").replace("/chat", "/chat/stream")
    payload = {"message": message}

    try:
        with requests.post(stream_url, json=payload, stream=True, timeout=60) as response:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                event = json.loads(line[len("data: "):])

                if event["type"] == "status":
                    yield event["text"], False
                elif event["type"] == "final":
                    parts = [event["text"]]
                    if event.get("flights"):
                        parts.append(format_flights(event["flights"]))
                    if event.get("hotels"):
                        parts.append(format_hotels(event["hotels"]))
                    yield "\n\n".join(parts), True
                elif event["type"] == "error":
                    yield event["text"], True
    except Exception:
        yield (
            "Sorry, I'm having trouble reaching the travel planning service right now. "
            "Please check your connection and try again in a moment."
        ), True


def respond(message, history):
    if history is None:
        history = []

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "..."},
    ]
    yield history, history

    for text, is_final in call_chat_api_stream(message):
        history[-1]["content"] = text
        yield history, history
        if is_final:
            break



# def call_chat_api(message):
#     payload = json.dumps({"message": message}).encode("utf-8")
#     request = Request(os.getenv("BACKEND_URL"), data=payload, headers={"Content-Type": "application/json"})

#     try:
#         response = urlopen(request, timeout=30)
#         data = json.loads(response.read().decode("utf-8"))
#     except Exception:
#         return (
#             "Sorry, I'm having trouble reaching the travel planning service right now. "
#             "Please check your connection and try again in a moment."
#         )

#     chat_text = data.get("response", "No response returned.")
#     parts = [chat_text]

#     if data.get("flights"):
#         parts.append(format_flights(data["flights"]))
#     if data.get("hotels"):
#         parts.append(format_hotels(data["hotels"]))

#     return "\n\n".join(parts)


# def respond(message, history):
#     if history is None:
#         history = []

#     answer = call_chat_api(message)
#     history = history + [
#         {"role": "user", "content": message},
#         {"role": "assistant", "content": answer},
#     ]
#     return history, history



def main():
    with gr.Blocks() as demo:
        gr.Markdown(
            "# TripWeaver - MCP-Based Multi-Agent Travel Planner\nAsk the backend for flights, hotels, or travel plans. ``TRAVEL_PLANNER_API_URL`` can be set to point to your FastAPI server."
        )
        chatbot = gr.Chatbot()
        message = gr.Textbox(label="Your message", placeholder="Find me flights from CAN to HAN on 2025-11-15")
        submit = gr.Button("Send")

        submit.click(respond, inputs=[message, chatbot], outputs=[chatbot, chatbot])
        message.submit(respond, inputs=[message, chatbot], outputs=[chatbot, chatbot])

    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))


if __name__ == "__main__":
    main()
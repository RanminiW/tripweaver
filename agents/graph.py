from .nodes import router, unknown_node, hotel_node, flight_node, generate_response, route_after_extraction
from .entity import GraphState
from langgraph.graph import StateGraph, START, END



def build_graph() -> StateGraph: #we initiate a build_graph function which embed our workflow
    builder = StateGraph(GraphState)
    #initialise nodes -----------------

    builder.add_node("router", router)
    builder.add_node("hotel_node", hotel_node)
    builder.add_node("flight_node", flight_node)
    builder.add_node("unknown_node", unknown_node)
    builder.add_node("generate_response", generate_response)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_after_extraction,
        {
            "hotel": "hotel_node",
            "flight": "flight_node",
            "unknown": "unknown_node",
        },
    )

    builder.add_edge("hotel_node", "generate_response")
    builder.add_edge("flight_node", "generate_response")
    builder.add_edge("unknown_node", "generate_response")
    builder.add_edge("generate_response", END)

    return builder


graph = build_graph().compile()
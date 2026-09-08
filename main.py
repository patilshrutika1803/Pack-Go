"""
FastAPI backend entry point with SSE streaming support.
"""
import os
import uuid
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agentic_workflow import GraphBuilder, build_final_plan, validate_final_state
from utils.streaming import format_sse_event
from memory.long_term import LongTermMemory
from logger.logging import get_logger

logger = get_logger(__name__)

GENERIC_ERROR_MESSAGE = "Unable to generate the travel plan at this time. Please try again."
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("PACK_GO_ALLOWED_ORIGINS", "")
    if configured_origins:
        origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
        return origins
    return DEFAULT_ALLOWED_ORIGINS


app = FastAPI(title="PACK & GO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.exception("Unhandled server error during %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": GENERIC_ERROR_MESSAGE},
    )

class PlanRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None
    remember_me: bool = True

@app.post("/plan")
async def plan_trip_sync(request: PlanRequest):
    """Backward compatible synchronous endpoint."""
    try:
        thread_id = request.thread_id or str(uuid.uuid4())
        
        graph_builder = GraphBuilder()
        graph = graph_builder.build_graph()
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # We invoke the graph
        output = graph.invoke({"messages": [request.question]}, config=config)

        if output.get("intent") == "general_chat":
            return {
                "thread_id": thread_id,
                "state": "complete",
                "intent": "general_chat",
                "response": output.get("chat_response", ""),
                "chat_response": output.get("chat_response", ""),
            }

        validation_errors = validate_final_state(output)
        if validation_errors:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Workflow failed validation.",
                    "details": validation_errors,
                    "failed_agents": output.get("failed_agents", []),
                    "failure_reasons": output.get("failure_reasons", {}),
                },
            )
        
        # Save to long term memory if requested
        if request.remember_me and "preferences" in output and output["preferences"]:
            pref = output["preferences"]
            memory = LongTermMemory()
            memory.save_preferences(
                thread_id=thread_id,
                destination=pref.destination,
                travel_style=pref.travel_style,
                interests=pref.interests,
                things_to_avoid=pref.things_to_avoid,
                budget=pref.total_budget,
                duration=pref.duration
            )
            
        return {"thread_id": thread_id, "state": "complete", "plan": build_final_plan(output)}
    except Exception as exc:
        logger.exception("Unexpected error in /plan request")
        return JSONResponse(status_code=500, content={"error": GENERIC_ERROR_MESSAGE})

@app.get("/graph")
async def get_graph_png():
    """Returns the LangGraph architecture as a PNG image."""
    try:
        graph_builder = GraphBuilder()
        graph = graph_builder.build_graph()
        png_data = graph.get_graph().draw_mermaid_png()
        return Response(content=png_data, media_type="image/png")
    except Exception as exc:
        logger.exception("Unexpected error generating graph PNG")
        return JSONResponse(status_code=500, content={"error": GENERIC_ERROR_MESSAGE})

@app.post("/plan/stream")
async def plan_trip_stream(request: PlanRequest):
    """SSE Streaming endpoint for live updates."""
    thread_id = request.thread_id or str(uuid.uuid4())
    
    async def event_generator():
        try:
            graph_builder = GraphBuilder()
            graph = graph_builder.build_graph()
            config = {"configurable": {"thread_id": thread_id}}
            
            yield format_sse_event("running", "System", "Starting PACK & GO workflow...", data={"thread_id": thread_id})
            
            # Stream events as nodes complete
            for event in graph.stream({"messages": [request.question]}, config=config):
                for node_name, node_state in event.items():
                    yield format_sse_event("running", node_name, f"{node_name} completed processing.", data=None)
            
            # Get the FULL merged state after all nodes have run
            final_state = graph.get_state(config).values
            
            # After complete, save to long term memory
            if final_state and request.remember_me and "preferences" in final_state and final_state["preferences"]:
                pref = final_state["preferences"]
                memory = LongTermMemory()
                memory.save_preferences(
                    thread_id=thread_id,
                    destination=pref.destination,
                    travel_style=pref.travel_style,
                    interests=pref.interests,
                    things_to_avoid=pref.things_to_avoid,
                    budget=pref.total_budget,
                    duration=pref.duration
                )
            
            if final_state:
                if final_state.get("intent") == "general_chat":
                    chat_errors = validate_final_state(final_state)
                    if chat_errors:
                        yield format_sse_event(
                            "error",
                            "System",
                            "Workflow failed validation.",
                            data={"details": chat_errors},
                        )
                        return
                    yield format_sse_event(
                        "done",
                        "System",
                        "Chat response complete.",
                        data={
                            "intent": "general_chat",
                            "response": final_state.get("chat_response", ""),
                            "chat_response": final_state.get("chat_response", ""),
                        },
                    )
                    return

                validation_errors = validate_final_state(final_state)
                if validation_errors:
                    yield format_sse_event(
                        "error",
                        "System",
                        "Workflow failed validation.",
                        data={
                            "details": validation_errors,
                            "failed_agents": final_state.get("failed_agents", []),
                            "failure_reasons": final_state.get("failure_reasons", {}),
                        },
                    )
                else:
                    yield format_sse_event(
                        "done", "System", "Workflow complete.", data=build_final_plan(final_state)
                    )
            else:
                yield format_sse_event("error", "System", "Failed to generate plan.")
                
        except Exception as exc:
            logger.exception("Unexpected error in /plan/stream request for thread_id=%s", thread_id)
            yield format_sse_event("error", "System", GENERIC_ERROR_MESSAGE)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
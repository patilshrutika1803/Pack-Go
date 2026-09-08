"""
FastAPI backend entry point with SSE streaming support.
"""
import uuid
import json
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.agentic_workflow import GraphBuilder, build_final_plan, validate_final_state
from utils.streaming import format_sse_event
from memory.long_term import LongTermMemory
from models.schemas import TravelPlan

app = FastAPI(title="PACK & GO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/graph")
async def get_graph_png():
    """Returns the LangGraph architecture as a PNG image."""
    try:
        graph_builder = GraphBuilder()
        graph = graph_builder.build_graph()
        png_data = graph.get_graph().draw_mermaid_png()
        return Response(content=png_data, media_type="image/png")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to generate graph: {e}"})

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
                
        except Exception as e:
            yield format_sse_event("error", "System", str(e))
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
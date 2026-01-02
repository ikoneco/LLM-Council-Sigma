"""FastAPI backend for LLM Council with sequential expert collaboration."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple
import uuid
import json
import asyncio

from . import storage
from .council import (
    generate_conversation_title,
    stage0_analyze_intent,
    stage_brainstorm_experts,
    get_expert_contribution,
    stage_verification,
    stage_synthesis_planning,
    stage_editorial_guidelines,
    stage3_synthesize_final,
)
from .config import AVAILABLE_MODELS, COUNCIL_MODELS, CHAIRMAN_MODEL, MIN_EXPERT_MODELS

app = FastAPI(title="LLM Council API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    pass


class ModelSelection(BaseModel):
    chairman_model: str
    expert_models: List[str]


class SendMessageRequest(BaseModel):
    content: str
    model_selection: Optional[ModelSelection] = None


class ConversationMetadata(BaseModel):
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


def normalize_model_selection(selection: Optional[ModelSelection]) -> Tuple[str, List[str]]:
    if selection is None:
        return CHAIRMAN_MODEL, COUNCIL_MODELS

    available = set(AVAILABLE_MODELS)

    if selection.chairman_model not in available:
        raise HTTPException(status_code=400, detail="Invalid chairman model selection")

    seen = set()
    expert_models = []
    invalid_models = []
    for model in selection.expert_models:
        if model not in available:
            invalid_models.append(model)
            continue
        if model in seen:
            continue
        seen.add(model)
        expert_models.append(model)

    if invalid_models:
        raise HTTPException(status_code=400, detail="Invalid expert model selection")

    if len(expert_models) < MIN_EXPERT_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Select at least {MIN_EXPERT_MODELS} expert models",
        )

    return selection.chairman_model, expert_models


@app.get("/")
async def root():
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/models")
async def list_models():
    return {
        "available_models": AVAILABLE_MODELS,
        "default_expert_models": COUNCIL_MODELS,
        "default_chairman_model": CHAIRMAN_MODEL,
        "min_expert_models": MIN_EXPERT_MODELS,
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    try:
        storage.delete_conversation(conversation_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """Send a message and stream the sequential expert collaboration process."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    chairman_model, expert_models = normalize_model_selection(request.model_selection)
    num_experts = len(expert_models)
    model_selection = {
        "chairman_model": chairman_model,
        "expert_models": expert_models,
    }

    async def event_generator():
        try:
            storage.add_user_message(conversation_id, request.content)

            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Define history for context-aware functions (excludes current message which is added in storage but not in 'conversation' variable yet)
            history = conversation.get("messages", [])

            # Stage 0: Analyze intent
            yield f"data: {json.dumps({'type': 'stage0_start'})}\n\n"
            intent_analysis = await stage0_analyze_intent(request.content, history)
            yield f"data: {json.dumps({'type': 'stage0_complete', 'data': {'analysis': intent_analysis}})}\n\n"

            # Stage 0.5: Brainstorm experts
            yield f"data: {json.dumps({'type': 'brainstorm_start'})}\n\n"
            brainstorm_content, experts = await stage_brainstorm_experts(
                request.content,
                intent_analysis,
                history,
                expert_models=expert_models,
                chairman_model=chairman_model,
                num_experts=num_experts,
            )
            yield f"data: {json.dumps({'type': 'brainstorm_complete', 'data': {'brainstorm_content': brainstorm_content, 'experts': experts}})}\n\n"

            # Stage 1: Sequential Expert Contributions
            yield f"data: {json.dumps({'type': 'contributions_start'})}\n\n"
            
            contributions = []
            for i, expert in enumerate(experts):
                order = expert.get('order', i + 1)
                
                yield f"data: {json.dumps({'type': 'expert_start', 'data': {'order': order, 'expert': expert}})}\n\n"
                
                contribution = await get_expert_contribution(
                    request.content, 
                    expert, 
                    contributions, 
                    order,
                    intent_analysis,
                    history,
                    expert_models=expert_models,
                    num_experts=num_experts,
                )
                
                entry = {
                    "order": order,
                    "expert": expert,
                    "contribution": contribution,
                    "model": expert_models[(order - 1) % len(expert_models)]
                }
                contributions.append(entry)
                
                yield f"data: {json.dumps({'type': 'expert_complete', 'data': entry})}\n\n"

            yield f"data: {json.dumps({'type': 'contributions_complete', 'data': {'num_experts': len(contributions)}})}\n\n"

            # Stage 2.5: Verification
            yield f"data: {json.dumps({'type': 'verification_start'})}\n\n"
            verification_data = await stage_verification(request.content, contributions, history)
            yield f"data: {json.dumps({'type': 'verification_complete', 'data': verification_data})}\n\n"

            # Stage 2.75: Synthesis Planning
            yield f"data: {json.dumps({'type': 'planning_start'})}\n\n"
            synthesis_plan = await stage_synthesis_planning(
                request.content,
                contributions,
                intent_analysis,
                verification_data,
                history
            )
            yield f"data: {json.dumps({'type': 'planning_complete', 'data': synthesis_plan})}\n\n"

            # Stage 2.9: Editorial Guidelines
            yield f"data: {json.dumps({'type': 'editorial_start'})}\n\n"
            editorial_guidelines = await stage_editorial_guidelines(
                request.content,
                intent_analysis,
                contributions,
                synthesis_plan,
                history
            )
            yield f"data: {json.dumps({'type': 'editorial_complete', 'data': editorial_guidelines})}\n\n"

            # Stage 3: Final Synthesis
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content,
                contributions,
                intent_analysis=intent_analysis,
                verification_data=verification_data,
                synthesis_plan=synthesis_plan,
                editorial_guidelines=editorial_guidelines,
                history=history,
                chairman_model=chairman_model,
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            metadata = {
                "intent_analysis": intent_analysis,
                "verification_data": verification_data,
                "synthesis_plan": synthesis_plan,
                "editorial_guidelines": editorial_guidelines,
                "num_experts": len(contributions),
                "model_selection": model_selection,
            }
            storage.add_assistant_message_debate(
                conversation_id,
                experts,
                contributions,
                stage3_result,
                metadata
            )

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)

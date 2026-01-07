"""FastAPI backend for LLM Council with sequential expert collaboration."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from typing import List, Dict, Any, Optional, Tuple
import uuid
import json
import asyncio

from . import storage
from .council import (
    generate_conversation_title,
    stage0_generate_intent_draft,
    stage0_finalize_intent,
    stage_brainstorm_experts,
    get_expert_contribution,
    stage_verification,
    stage_synthesis_planning,
    stage_editorial_guidelines,
    stage3_synthesize_final,
)
from .config import (
    AVAILABLE_MODELS,
    COUNCIL_MODELS,
    CHAIRMAN_MODEL,
    MIN_EXPERT_MODELS,
    DEFAULT_NUM_EXPERTS,
    THINKING_SUPPORTED_MODELS,
    THINKING_EFFORT,
    THINKING_MAX_TOKENS,
    REASONING_EFFORT_MODELS,
    REASONING_MAX_TOKENS_MODELS,
    REASONING_EFFORT_LEVELS,
    REASONING_MAX_TOKENS_MIN,
    REASONING_MAX_TOKENS_MAX,
)

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
    thinking_enabled: Optional[bool] = False
    thinking_by_model: Optional[Dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    content: str
    model_selection: Optional[ModelSelection] = None


class ClarificationAnswer(BaseModel):
    question_id: str
    selected_option: Optional[str] = None
    selected_options: Optional[List[str]] = None
    other_text: Optional[str] = None

    def normalized_options(self) -> List[str]:
        if self.selected_options:
            return self.selected_options
        if self.selected_option:
            return [self.selected_option]
        return []


class ContinueMessageRequest(BaseModel):
    answers: List[ClarificationAnswer] = []
    free_text: Optional[str] = None
    skip: bool = False


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


def _normalize_thinking_config(raw_value: Any) -> Optional[Any]:
    if isinstance(raw_value, bool):
        return True if raw_value else None
    if isinstance(raw_value, dict):
        enabled = raw_value.get("enabled", True)
        if enabled is False:
            return None
        config: Dict[str, Any] = {}
        effort = raw_value.get("effort")
        if isinstance(effort, str) and effort in REASONING_EFFORT_LEVELS:
            config["effort"] = effort
        max_tokens = raw_value.get("max_tokens")
        if isinstance(max_tokens, int):
            max_tokens = max(REASONING_MAX_TOKENS_MIN, min(max_tokens, REASONING_MAX_TOKENS_MAX))
            config["max_tokens"] = max_tokens
        exclude = raw_value.get("exclude")
        if isinstance(exclude, bool):
            config["exclude"] = exclude
        return config or True
    return None


def normalize_model_selection(selection: Optional[Any]) -> Tuple[str, List[str], Dict[str, Any]]:
    if selection is None:
        return CHAIRMAN_MODEL, COUNCIL_MODELS, {}

    if isinstance(selection, dict):
        try:
            selection = ModelSelection(**selection)
        except ValidationError:
            raise HTTPException(status_code=400, detail="Invalid model selection payload")

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

    thinking_by_model: Dict[str, Any] = {}
    raw_map = getattr(selection, "thinking_by_model", None)
    if isinstance(raw_map, dict):
        for model, raw_value in raw_map.items():
            if model not in THINKING_SUPPORTED_MODELS:
                continue
            normalized = _normalize_thinking_config(raw_value)
            if normalized is not None:
                thinking_by_model[model] = normalized
    elif bool(getattr(selection, "thinking_enabled", False)):
        for model in {selection.chairman_model, *expert_models}:
            if model in THINKING_SUPPORTED_MODELS:
                thinking_by_model[model] = True

    return selection.chairman_model, expert_models, thinking_by_model


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
        "thinking_supported_models": sorted(THINKING_SUPPORTED_MODELS),
        "reasoning_effort_models": sorted(REASONING_EFFORT_MODELS),
        "reasoning_max_tokens_models": sorted(REASONING_MAX_TOKENS_MODELS),
        "reasoning_effort_levels": REASONING_EFFORT_LEVELS,
        "reasoning_max_tokens_min": REASONING_MAX_TOKENS_MIN,
        "reasoning_max_tokens_max": REASONING_MAX_TOKENS_MAX,
        "default_reasoning_effort": THINKING_EFFORT,
        "default_reasoning_max_tokens": THINKING_MAX_TOKENS,
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
    """Send a message and stream the intent draft + clarification questions."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    chairman_model, expert_models, thinking_by_model = normalize_model_selection(request.model_selection)
    model_selection = {
        "chairman_model": chairman_model,
        "expert_models": expert_models,
        "thinking_by_model": thinking_by_model,
    }

    async def event_generator():
        try:
            storage.add_user_message(conversation_id, request.content)

            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Define history for context-aware functions (excludes current message which is added in storage but not in 'conversation' variable yet)
            history = conversation.get("messages", [])

            # Phase 1: Draft intent + clarification questions
            yield f"data: {json.dumps({'type': 'intent_draft_start'})}\n\n"
            intent_draft = await asyncio.wait_for(
                stage0_generate_intent_draft(
                    request.content,
                    history,
                    analysis_model=chairman_model,
                    thinking_by_model=thinking_by_model,
                ),
                timeout=90.0,
            )
            storage.add_assistant_message_intent_draft(
                conversation_id,
                intent_draft,
                intent_draft.get("display", {}),
                intent_draft.get("questions", []),
                {"model_selection": model_selection},
            )
            yield f"data: {json.dumps({'type': 'intent_draft_complete', 'data': intent_draft})}\n\n"
            yield f"data: {json.dumps({'type': 'clarification_required'})}\n\n"

            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.post("/api/conversations/{conversation_id}/message/continue")
async def continue_message_stream(conversation_id: str, request: ContinueMessageRequest):
    """Continue a message after intent clarifications (or skip)."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    pending = storage.find_pending_intent_message(conversation_id)
    if pending is None:
        raise HTTPException(status_code=400, detail="No pending intent clarification found")

    pending_index, pending_message = pending
    if pending_index == 0:
        raise HTTPException(status_code=400, detail="Pending intent has no user context")

    user_message = conversation["messages"][pending_index - 1]
    user_query = user_message.get("content", "")
    history = conversation["messages"][:pending_index - 1]

    model_selection_payload = (pending_message.get("metadata") or {}).get("model_selection")
    chairman_model, expert_models, thinking_by_model = normalize_model_selection(model_selection_payload)
    num_experts = DEFAULT_NUM_EXPERTS

    clarification_payload = {
        "answers": [
            {
                "question_id": answer.question_id,
                "selected_options": answer.normalized_options(),
                "other_text": answer.other_text or "",
            }
            for answer in request.answers
        ],
        "free_text": request.free_text or "",
        "skip": request.skip,
    }
    question_lookup = {}
    for item in pending_message.get("clarification_questions") or []:
        if isinstance(item, dict) and item.get("id"):
            question_lookup[item["id"]] = item
    for answer in clarification_payload["answers"]:
        question_meta = question_lookup.get(answer.get("question_id"))
        if not question_meta:
            continue
        answer["question"] = question_meta.get("question") or question_meta.get("prompt") or ""
        answer["options"] = question_meta.get("options") or []

    async def event_generator():
        try:
            storage.mark_pending_intent_submitted(
                conversation_id,
                clarification_payload,
            )

            # Phase 3: Final intent analysis
            yield f"data: {json.dumps({'type': 'stage0_start'})}\n\n"
            intent_analysis = await stage0_finalize_intent(
                user_query,
                pending_message.get("intent_draft", {}),
                clarification_payload,
                history,
                analysis_model=chairman_model,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'stage0_complete', 'data': {'analysis': intent_analysis}})}\n\n"

            # Stage 0.5: Brainstorm experts
            yield f"data: {json.dumps({'type': 'brainstorm_start'})}\n\n"
            brainstorm_content, experts = await stage_brainstorm_experts(
                user_query,
                intent_analysis,
                history,
                expert_models=expert_models,
                chairman_model=chairman_model,
                num_experts=num_experts,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'brainstorm_complete', 'data': {'brainstorm_content': brainstorm_content, 'experts': experts}})}\n\n"

            # Stage 1: Sequential Expert Contributions
            yield f"data: {json.dumps({'type': 'contributions_start'})}\n\n"

            contributions = []
            for i, expert in enumerate(experts):
                order = expert.get("order", i + 1)

                yield f"data: {json.dumps({'type': 'expert_start', 'data': {'order': order, 'expert': expert}})}\n\n"

                contribution = await get_expert_contribution(
                    user_query,
                    expert,
                    contributions,
                    order,
                    intent_analysis,
                    history,
                    expert_models=expert_models,
                    num_experts=num_experts,
                    thinking_by_model=thinking_by_model,
                )

                entry = {
                    "order": order,
                    "expert": expert,
                    "contribution": contribution,
                    "model": expert_models[(order - 1) % len(expert_models)],
                }
                contributions.append(entry)

                yield f"data: {json.dumps({'type': 'expert_complete', 'data': entry})}\n\n"

            yield f"data: {json.dumps({'type': 'contributions_complete', 'data': {'num_experts': len(contributions)}})}\n\n"

            # Stage 2.5: Verification
            yield f"data: {json.dumps({'type': 'verification_start'})}\n\n"
            verification_data = await stage_verification(
                user_query,
                contributions,
                history,
                analysis_model=chairman_model,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'verification_complete', 'data': verification_data})}\n\n"

            # Stage 2.75: Synthesis Planning
            yield f"data: {json.dumps({'type': 'planning_start'})}\n\n"
            synthesis_plan = await stage_synthesis_planning(
                user_query,
                contributions,
                intent_analysis,
                verification_data,
                history,
                analysis_model=chairman_model,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'planning_complete', 'data': synthesis_plan})}\n\n"

            # Stage 2.9: Editorial Guidelines
            yield f"data: {json.dumps({'type': 'editorial_start'})}\n\n"
            editorial_guidelines = await stage_editorial_guidelines(
                user_query,
                intent_analysis,
                contributions,
                synthesis_plan,
                history,
                analysis_model=chairman_model,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'editorial_complete', 'data': editorial_guidelines})}\n\n"

            # Stage 3: Final Synthesis
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                user_query,
                contributions,
                intent_analysis=intent_analysis,
                verification_data=verification_data,
                synthesis_plan=synthesis_plan,
                editorial_guidelines=editorial_guidelines,
                history=history,
                chairman_model=chairman_model,
                thinking_by_model=thinking_by_model,
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            metadata = {
                "intent_analysis": intent_analysis,
                "verification_data": verification_data,
                "synthesis_plan": synthesis_plan,
                "editorial_guidelines": editorial_guidelines,
                "num_experts": len(contributions),
                "model_selection": {
                    "chairman_model": chairman_model,
                    "expert_models": expert_models,
                    "thinking_by_model": thinking_by_model,
                },
                "clarification_answers": clarification_payload,
            }

            storage.finalize_intent_message(
                conversation_id,
                intent_analysis,
                experts,
                contributions,
                stage3_result,
                metadata,
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

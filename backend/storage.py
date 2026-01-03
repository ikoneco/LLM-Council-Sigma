"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Get the file path for a conversation."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": []
    }

    # Save to file
    path = get_conversation_path(conversation_id)
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w') as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                # Return metadata only
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"])
                })

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage0_personas: List[Dict[str, Any]],
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Dict[str, Any] = None
):
    """
    Add an assistant message with all stages to a conversation.
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "content": stage3["response"],
        "stage0": stage0_personas,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "metadata": metadata or {}
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def delete_conversation(conversation_id: str):
    """
    Delete a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation
    """
    path = get_conversation_path(conversation_id)
    if os.path.exists(path):
        os.remove(path)
    else:
        raise ValueError(f"Conversation {conversation_id} not found")


def add_assistant_message_debate(
    conversation_id: str,
    experts: List[Dict[str, Any]],
    contributions: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Dict[str, Any] = None
):
    """
    Add an assistant message with sequential contribution data to a conversation.
    
    Args:
        conversation_id: Conversation identifier
        experts: Expert team selected in Stage 0.5
        contributions: List of expert contributions
        stage3: Final synthesis result
        metadata: Additional metadata
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    safe_metadata = metadata or {}

    conversation["messages"].append({
        "role": "assistant",
        "content": stage3["response"],
        "stage0": {"analysis": safe_metadata.get("intent_analysis", "")},
        "experts": experts,
        "contributions": contributions,
        "debate": contributions,
        "stage3": stage3,
        "metadata": safe_metadata
    })

    save_conversation(conversation)


def add_assistant_message_intent_draft(
    conversation_id: str,
    intent_draft: Dict[str, Any],
    intent_display: Dict[str, Any],
    questions: List[Dict[str, Any]],
    metadata: Dict[str, Any] = None
):
    """
    Add an assistant message containing the intent draft and clarification questions.
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    stored_draft = intent_draft.get("draft_intent") if isinstance(intent_draft, dict) else intent_draft

    conversation["messages"].append({
        "role": "assistant",
        "status": "clarification_pending",
        "intent_draft": stored_draft,
        "intent_display": intent_display,
        "clarification_questions": questions,
        "metadata": metadata or {},
    })

    save_conversation(conversation)


def find_pending_intent_message(
    conversation_id: str,
    statuses: Optional[List[str]] = None,
) -> Optional[tuple]:
    """
    Find the most recent assistant message awaiting clarification.
    Returns (index, message) or None.
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        return None

    if statuses is None:
        statuses = ["clarification_pending", "clarification_submitted"]

    for idx in range(len(conversation["messages"]) - 1, -1, -1):
        msg = conversation["messages"][idx]
        if msg.get("role") == "assistant" and msg.get("status") in statuses:
            return idx, msg
    return None


def mark_pending_intent_submitted(
    conversation_id: str,
    clarification_payload: Dict[str, Any]
):
    """
    Mark the pending intent message as submitted and store clarification answers.
    """
    found = find_pending_intent_message(conversation_id)
    if found is None:
        raise ValueError(f"No pending intent message for {conversation_id}")

    idx, msg = found
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    msg["status"] = "clarification_submitted"
    msg["clarification_answers"] = clarification_payload
    conversation["messages"][idx] = msg
    save_conversation(conversation)


def finalize_intent_message(
    conversation_id: str,
    intent_analysis: str,
    experts: List[Dict[str, Any]],
    contributions: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Dict[str, Any]
):
    """
    Update the pending intent message with the full pipeline results.
    """
    found = find_pending_intent_message(conversation_id)
    if found is None:
        raise ValueError(f"No pending intent message for {conversation_id}")

    idx, msg = found
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    msg.update({
        "status": "complete",
        "content": stage3.get("response", ""),
        "stage0": {"analysis": intent_analysis},
        "experts": experts,
        "contributions": contributions,
        "debate": contributions,
        "stage3": stage3,
        "metadata": metadata or {},
    })

    conversation["messages"][idx] = msg
    save_conversation(conversation)

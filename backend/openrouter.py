"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional, Tuple
from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    OPENROUTER_SITE_URL,
    OPENROUTER_APP_TITLE,
    SEARCH_MODEL,
    SEARCH_TIMEOUT,
    SEARCH_CONTEXT_SIZE,
    THINKING_SUPPORTED_MODELS,
    THINKING_EFFORT,
    THINKING_MAX_TOKENS,
    REASONING_EFFORT_MODELS,
    REASONING_MAX_TOKENS_MODELS,
)

_SEARCH_MODELS_NO_TOOLS = {
    "openai/gpt-4o-mini-search-preview",
    "openai/gpt-4o-search-preview",
}


def _thinking_enabled_for_model(model: str, thinking_by_model: Optional[Dict[str, Any]]) -> bool:
    if not thinking_by_model:
        return False
    raw_value = thinking_by_model.get(model)
    if isinstance(raw_value, dict):
        return raw_value.get("enabled", True) is not False
    return bool(raw_value)


def _extract_reasoning_config(model: str, thinking_by_model: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not thinking_by_model:
        return None
    raw_value = thinking_by_model.get(model)
    if raw_value is None or raw_value is False:
        return None
    if raw_value is True:
        return {}
    if isinstance(raw_value, dict):
        if raw_value.get("enabled", True) is False:
            return None
        config = {}
        if "effort" in raw_value:
            config["effort"] = raw_value.get("effort")
        if "max_tokens" in raw_value:
            config["max_tokens"] = raw_value.get("max_tokens")
        if "exclude" in raw_value:
            config["exclude"] = raw_value.get("exclude")
        return config
    return None


def build_reasoning_payload(model: str, thinking_by_model: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not _thinking_enabled_for_model(model, thinking_by_model):
        return {}
    if model not in THINKING_SUPPORTED_MODELS:
        return {}
    config = _extract_reasoning_config(model, thinking_by_model) or {}
    reasoning: Dict[str, Any] = {}

    exclude = config.get("exclude")
    if isinstance(exclude, bool):
        reasoning["exclude"] = exclude

    user_effort = config.get("effort")
    user_max_tokens = config.get("max_tokens")

    if user_effort and user_max_tokens:
        if model in REASONING_MAX_TOKENS_MODELS:
            user_effort = None
        else:
            user_max_tokens = None

    if user_effort:
        reasoning["effort"] = user_effort
    elif isinstance(user_max_tokens, int):
        reasoning["max_tokens"] = user_max_tokens
    else:
        if model in REASONING_MAX_TOKENS_MODELS:
            reasoning["max_tokens"] = THINKING_MAX_TOKENS
        elif model in REASONING_EFFORT_MODELS:
            reasoning["effort"] = THINKING_EFFORT
        else:
            reasoning["enabled"] = True

    if not reasoning and config.get("exclude") is True:
        reasoning["enabled"] = True

    return {"reasoning": reasoning}


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    if not OPENROUTER_API_KEY:
        print("OpenRouter API key is missing. Skipping model call.")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_TITLE:
        headers["X-Title"] = OPENROUTER_APP_TITLE

    payload = {
        "model": model,
        "messages": messages,
    }
    if extra_body:
        payload.update(extra_body)
    reasoning_payload = payload.get("reasoning")
    if isinstance(reasoning_payload, dict):
        reasoning_max_tokens = reasoning_payload.get("max_tokens")
        if isinstance(reasoning_max_tokens, int):
            existing_max_tokens = payload.get("max_tokens")
            if not isinstance(existing_max_tokens, int) or existing_max_tokens <= reasoning_max_tokens:
                payload["max_tokens"] = reasoning_max_tokens + 512
    can_retry_without_reasoning = bool(extra_body and payload.get("reasoning"))

    import asyncio
    max_retries = 3
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 429:
                    # Rate limit - wait longer
                    delay = base_delay * (2 ** attempt)
                    print(f"Rate limited (429) for {model}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in (401, 403):
                    try:
                        data = response.json()
                    except Exception:
                        data = response.text
                    print(f"Authorization error ({response.status_code}) for {model}: {data}")
                    return {"content": None, "error": data, "status_code": response.status_code}

                if response.status_code in (400, 422) and can_retry_without_reasoning:
                    try:
                        data = response.json()
                    except Exception:
                        data = {}
                    error_message = str(
                        data.get("error", {}).get("message")
                        or data.get("message")
                        or data
                    ).lower()
                    if "reasoning" in error_message or "unsupported" in error_message:
                        print(f"Retrying {model} without reasoning payload.")
                        payload.pop("reasoning", None)
                        can_retry_without_reasoning = False
                        continue

                response.raise_for_status()

                data = response.json()
                if not data.get('choices'):
                    print(f"Invalid response from {model}: {data}")
                    return {"content": None, "error": data, "status_code": response.status_code}

                message = data['choices'][0]['message']

                return {
                    'content': message.get('content'),
                    'reasoning_details': message.get('reasoning_details'),
                    'annotations': message.get('annotations'),
                }

        except Exception as e:
            if can_retry_without_reasoning and isinstance(e, httpx.TimeoutException):
                print(f"Timeout for {model} with reasoning enabled. Retrying without reasoning payload.")
                payload.pop("reasoning", None)
                can_retry_without_reasoning = False
                continue

            delay = base_delay * (2 ** attempt)
            if attempt < max_retries - 1:
                print(f"Error querying model {model} (Attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                print(f"Final failure for model {model} after {max_retries} attempts: {e}")
                return None
    
    return None


async def query_search_model(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_tokens: int = 800,
) -> Optional[Dict[str, Any]]:
    """
    Query the search-enabled model with web search tooling.
    """
    search_model = model or SEARCH_MODEL
    search_timeout = timeout or SEARCH_TIMEOUT
    extra_body = {
        "temperature": 0,
        "max_tokens": max_tokens,
        "web_search_options": {"search_context_size": SEARCH_CONTEXT_SIZE},
    }
    if search_model not in _SEARCH_MODELS_NO_TOOLS:
        extra_body["tools"] = [{"type": "web_search"}]
        extra_body["tool_choice"] = "auto"
    return await query_model(
        search_model,
        messages,
        timeout=search_timeout,
        extra_body=extra_body,
    )



async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with the SAME messages.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_models_with_personas(
    model_persona_pairs: List[Tuple[str, List[Dict[str, str]]]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel, each with their own unique messages (personas).

    Args:
        model_persona_pairs: List of (model_id, messages_list) tuples

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all model-persona pairs
    tasks = [query_model(model, messages) for model, messages in model_persona_pairs]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for (model, _), response in zip(model_persona_pairs, responses)}

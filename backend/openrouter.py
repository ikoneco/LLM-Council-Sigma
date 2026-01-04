"""OpenRouter API client for making LLM requests."""

import httpx
from typing import List, Dict, Any, Optional, Tuple
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, SEARCH_MODEL, SEARCH_TIMEOUT, SEARCH_CONTEXT_SIZE


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
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }
    if extra_body:
        payload.update(extra_body)

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

                response.raise_for_status()

                data = response.json()
                if not data.get('choices'):
                    print(f"Invalid response from {model}: {data}")
                    return None

                message = data['choices'][0]['message']

                return {
                    'content': message.get('content'),
                    'reasoning_details': message.get('reasoning_details')
                }

        except Exception as e:
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
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "web_search_options": {"search_context_size": SEARCH_CONTEXT_SIZE},
    }
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

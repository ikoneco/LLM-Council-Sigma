"""Configuration for the LLM Council."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "LLM Council")

# Council members - default expert model pool
COUNCIL_MODELS = [
    "minimax/minimax-m2.1",
    "deepseek/deepseek-v3.2",
    "qwen/qwen2.5-vl-72b-instruct",
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2-0905",
    "qwen/qwen3-235b-a22b-2507",
    "openai/gpt-5.2",
    "google/gemini-3-flash-preview",
    "xiaomi/mimo-v2-flash:free",
    "mistralai/devstral-2512:free",
    "x-ai/grok-4.1-fast",
]

# Full list of selectable models (chairman + experts)
AVAILABLE_MODELS = [
    "minimax/minimax-m2.1",
    "deepseek/deepseek-v3.2",
    "qwen/qwen2.5-vl-72b-instruct",
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2-0905",
    "qwen/qwen3-235b-a22b-2507",
    "openai/gpt-5.2",
    "google/gemini-3-flash-preview",
    "xiaomi/mimo-v2-flash:free",
    "mistralai/devstral-2512:free",
    "x-ai/grok-4.1-fast",
]

# Models that support OpenRouter reasoning/thinking parameters
THINKING_SUPPORTED_MODELS = {
    "minimax/minimax-m2.1",
    "deepseek/deepseek-v3.2",
    "qwen/qwen2.5-vl-72b-instruct",
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2-0905",
    "openai/gpt-5.2",
    "xiaomi/mimo-v2-flash:free",
    "mistralai/devstral-2512:free",
    "x-ai/grok-4.1-fast",
}
THINKING_EFFORT = "medium"
THINKING_MAX_TOKENS = 2000
REASONING_EFFORT_LEVELS = ["minimal", "low", "medium", "high", "xhigh", "none"]
REASONING_MAX_TOKENS_MIN = 256
REASONING_MAX_TOKENS_MAX = 8000
REASONING_EFFORT_MODELS = {
    "openai/gpt-5.2",
    "x-ai/grok-4.1-fast",
}
REASONING_MAX_TOKENS_MODELS = {
    "qwen/qwen2.5-vl-72b-instruct",
}

# Selection rules
MIN_EXPERT_MODELS = 1
DEFAULT_NUM_EXPERTS = 6

# Search / verification
SEARCH_MODEL = "openai/gpt-4o-mini-search-preview"
SEARCH_QUERY_COUNT = 3
SEARCH_QUERY_MAX = 8
SEARCH_MAX_SOURCES = 3
SEARCH_TIMEOUT = 45.0
SEARCH_CONTEXT_SIZE = "high"

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "minimax/minimax-m2.1"

# Stage 0 intent analysis fallback models (OpenRouter-only).
INTENT_MODEL_FALLBACKS = [
    "google/gemini-3-flash-preview",
    "qwen/qwen3-235b-a22b-2507",
    "deepseek/deepseek-v3.2",
    "qwen/qwen2.5-vl-72b-instruct",
    "moonshotai/kimi-k2-0905",
]

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

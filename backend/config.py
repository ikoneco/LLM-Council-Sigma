"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
]

# Selection rules
MIN_EXPERT_MODELS = 1
DEFAULT_NUM_EXPERTS = 6

# Search / verification
SEARCH_MODEL = "openai/gpt-4o-mini-search-preview"
SEARCH_QUERY_COUNT = 3
SEARCH_MAX_SOURCES = 3
SEARCH_TIMEOUT = 45.0
SEARCH_CONTEXT_SIZE = "high"

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "minimax/minimax-m2.1"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

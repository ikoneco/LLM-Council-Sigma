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
]

# Selection rules
MIN_EXPERT_MODELS = 6

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "minimax/minimax-m2.1"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

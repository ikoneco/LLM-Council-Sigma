# 🧠 LLM Council

**LLM Council** is a sophisticated multi-agent orchestration system that simulates a "council of experts" to solve complex user queries. Instead of a single zero-shot response, it employs a rigorous multi-stage pipeline where users select the models and dynamic expert personas analyze, brainstorm, contribute, verify, and synthesize a high-quality final artifact.

## ✨ Key Features

- **Multi-Stage Orchestration**: Moves beyond simple prompting to a state-managed workflow.
- **Model Selection**: Users choose the Chairman model and a pool of expert models (minimum 6 of 8).
- **Dynamic Expert Selection**: Automatically identifies the specialized roles needed (e.g., "Senior Product Strategist", "Security Architect") based on the query.
- **Sequential Collaboration**: Experts build upon each other's work, providing deep, layered insights.
- **Verification & Reasoning Audit**: A dedicated stage checks claims, logic, gaps, and inconsistencies.
- **Editorial Synthesis**: A final "Chairman" synthesizes all contributions into a cohesive, style-calibrated response (Editorial/Council voice).
- **Google-Quality UX**: A clean, elegant, and accessible interface featuring:
  - **Smart Iconography**: Dynamic detection of header context (Intent, Claim, Strategy) to display relevant Lucide icons.
  - **Typography**: Professional serif headers (`Merriweather`) paired with clean sans-serif body text.
  - **Modern Design**: Glassmorphism, subtle shadows, and a refined color palette.

## 🔄 The Council Workflow

0. **Model Selection**: Choose the Chairman model and a pool of expert models (minimum 6).
1. **🎯 Intent Analysis**: The "Master Intent Architect" decodes the explicit and implicit goals of the user.
2. **🧠 Expert Brainstorm**: Multiple models propose the ideal team of experts.
3. **👥 Sequential Contributions**: Selected experts (simulated by LLMs) contribute linearly, reviewing and building on prior work.
4. **🔬 Factual Verification**: A "Meticulous Fact-Checker" validates key claims.
5. **📋 Synthesis Planning**: A "Synthesis Architect" outlines the structure for the final answer.
6. **✍️ Editorial Guidelines**: An "Editorial Director" defines the voice, tone, and formatting.
7. **🏆 Final Synthesis**: The Chairman produces the final response, integrating all insights.

## 🛠️ Tech Stack

### Frontend

- **Framework**: React 19 + Vite
- **Styling**: Vanilla CSS (Variables-based design system)
- **Icons**: Lucide React (Smart context-aware rendering)
- **Rendering**: React Markdown + Remark GFM

### Backend

- **Runtime**: Python 3.10+
- **Framework**: FastAPI + Uvicorn
- **Orchestration**: Custom async pipeline handling SSE (Server-Sent Events)
- **AI Provider**: OpenRouter (Minimax, DeepSeek, Qwen, Z-AI GLM, Kimi, GPT-5.2, Gemini 3 Flash Preview)
- **Package Manager**: `uv`

## Getting Started

### Prerequisites

- Node.js (v18+)
- Python (v3.10+)
- `uv` (Python package manager)
- An OpenRouter API Key

### Backend Setup

1. Navigate to the project root:

    ```bash
    cd Council
    ```

2. Create a `.env` file with your API key:

    ```env
    OPENROUTER_API_KEY=sk-or-your-key-here
    ```

3. Run the backend (dependencies are handled by `uv`):

    ```bash
    lsof -ti:8001 | xargs kill -9  # Optional: clear port
    uv run python -m backend.main
    ```

    The server will start at `http://localhost:8001`.

### Frontend Setup

1. Navigate to the frontend directory:

    ```bash
    cd frontend
    ```

2. Install dependencies:

    ```bash
    npm install
    ```

3. Start the development server:

    ```bash
    npm run dev
    ```

    The app will open at `http://localhost:5173`.

## 📂 Project Structure

```
Council/
├── backend/
│   ├── main.py          # FastAPI entry point
│   ├── council.py       # Core orchestration logic & prompts
│   ├── config.py        # Model configurations
│   └── openrouter.py    # API client
├── frontend/
│   ├── src/
│   │   ├── components/  # Stage components + ModelSelector
│   │   ├── App.jsx      # Main state & SSE handling
│   │   └── index.css    # Global design system
│   └── package.json
└── README.md
```

## 🎨 Design Philosophy

The UI follows a rigid "Quality Bar" focused on:

- **Clarity**: High contrast, readable measures, and ample whitespace.
- **Elegance**: Purposeful use of serif fonts for headings to convey authority.
- **Feedback**: Clear loading states and progression indicators for the complex backend process.
- **Consistency**: Unified design language for all stages and artifacts.

---
*Built by the Google Deepmind Advanced Agentic Coding Team.*

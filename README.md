# 🧠 LLM Council

**LLM Council** is a sophisticated multi-agent orchestration system that simulates a "council of experts" to solve complex user queries. Instead of a single zero-shot response, it employs a rigorous multi-stage pipeline where users select the models and dynamic expert personas analyze, brainstorm, contribute, verify, and synthesize a high-quality final artifact.

## ✨ Key Features

- **Multi-Stage Orchestration**: Moves beyond simple prompting to a state-managed workflow.
- **Model Selection**: Users choose the Chairman model, any number of expert models, and optionally enable per-model “thinking” (models are reused to staff 6 experts if fewer are selected).
- **No Preselection**: New threads start with no models selected so the user explicitly controls the panel before running.
- **Dynamic Expert Selection**: Automatically identifies the specialized roles needed (e.g., "Senior Product Strategist", "Security Architect") based on the query.
- **Intent Clarification Loop**: Draft intent understanding + 3–6 high-impact questions (skippable) before the pipeline runs.
- **Sequential Collaboration**: Experts build upon each other's work, providing deep, layered insights.
- **Verification & Reasoning Audit**: A dedicated stage checks claims, logic, gaps, and inconsistencies.
- **Editorial Synthesis**: A final "Chairman" synthesizes all contributions into a cohesive, style-calibrated response (Editorial/Council voice).
- **Context-Aware Continuation**: Continue a thread using prior Chairman outputs as the baseline context, or start a fresh thread.
- **Google-Quality UX**: A clean, elegant, and accessible interface featuring:
  - **Smart Iconography**: Dynamic detection of header context (Intent, Claim, Strategy) to display relevant Lucide icons.
  - **Typography**: Professional serif headers (`Merriweather`) paired with clean sans-serif body text.
  - **Modern Design**: Glassmorphism, subtle shadows, and a refined color palette.

## 🔄 The Council Workflow

0. **Model Selection**: Choose the Chairman model and any number of expert models; optionally enable per-model thinking. The system always staffs 6 experts and reuses models if needed.
1. **🎯 Intent Draft + Clarifications**: The system summarizes its understanding and asks 3–6 high-impact questions (or you can skip).
2. **✅ Brainstorm Intent Brief**: A concise brief (no assumptions) guides expert brainstorming.
3. **🧠 Expert Brainstorm**: Multiple models propose the ideal team of experts.
4. **👥 Sequential Contributions**: Selected experts (simulated by LLMs) contribute linearly, reviewing and building on prior work.
5. **🔬 Verification & Reasoning Audit**: A "Meticulous Fact-Checker" validates claims and reasoning.
6. **📋 Synthesis Planning**: A "Synthesis Architect" outlines the structure for the final answer.
7. **✍️ Editorial Guidelines**: An "Editorial Director" defines the voice, tone, and formatting.
8. **🏆 Final Synthesis**: The Chairman produces the final response, integrating all insights.

## 🔁 Continuing a Thread

- **Continue**: Add new instructions to evolve the latest Chairman output; the system treats the most recent Chairman response as the baseline context for the next cycle.
- **Start New**: Begin a fresh thread to reset context and model selection.

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
- **AI Provider**: OpenRouter (Minimax, DeepSeek, Qwen, Z-AI GLM, Kimi, GPT-5.2, Gemini 3 Flash Preview, Mimo, Devstral)
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
│   │   ├── components/  # Stage components + ModelSelector + Intent Clarification UI
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

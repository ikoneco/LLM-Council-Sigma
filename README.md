# LLM Council

![llmcouncil](header.jpg)

**LLM Council** is a next-generation AI orchestration platform that doesn't just answer questions—it assembles a bespoke team of AI experts to solve them.

Instead of a single LLM responding to your prompt, LLM Council orchestrates a **7-Stage Sequential Collaboration** where multiple top-tier models (Gemini, Claude, GPT-4, etc.) brainstorm, research, verify, and synthesize a single, world-class artifact.

## 🚀 Key Features

- **7-Stage Cognitive Pipeline**:
    1. **Intent Analysis**: Deeply understands what you *really* want.
    2. **Global Brainstorming**: All models propose expert roles tailored to your query.
    3. **Team Assembly**: A Chairman model selects the perfect 6-person expert team.
    4. **Sequential Collaboration**: Experts build on each other's work (not just debate).
    5. **Real-time Verification**: Claims are fact-checked mid-stream.
    6. **Strategic Planning**: A "Synthesis Architect" & "Editorial Director" plan the final output.
    7. **Final Synthesis**: A unified, high-quality response (no chat threads to read).
- **Multi-Model Intelligence**: Leverages the best models via OpenRouter (Gemini 2.0, DeepSeek v3, Qwen 2.5, Minimax, etc.).
- **Transparent Process**: Watch the "mind" of the council work in real-time on the frontend.

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - Deep dive into the 7-stage pipeline.
- [API Reference](docs/API.md) - Backend API endpoints.
- [Contributing Guide](CONTRIBUTING.md) - How to help us improve.

## 🛠️ Setup

### 1. Prerequisites

- [uv](https://docs.astral.sh/uv/) (for Python)
- Node.js & npm (for Frontend)
- [OpenRouter](https://openrouter.ai/) API Key

### 2. Installation

**Backend:**

```bash
uv sync
```

**Frontend:**

```bash
cd frontend
npm install
cd ..
```

### 3. Configuration

Create a `.env` file in the root:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

(Optional) Customize models in `backend/config.py`.

## 🏃‍♂️ Running the Application

**Option 1: Quick Start**

```bash
./start.sh
```

**Option 2: Manual Start**
Terminal 1 (Backend):

```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) to consult the council.

## 🏗️ Architecture

The system uses a **FastAPI** backend to orchestrate the cognitive workflow and a **React** frontend to visualize the streaming process via Server-Sent Events (SSE).

State is managed via `council.py` (logic) and `storage.py` (JSON persistence).

## License

MIT License. Vibe coded with love.

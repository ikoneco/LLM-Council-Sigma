# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and implementation notes for future development sessions.

## Project Overview

LLM Council is a multi-stage sequential collaboration system where multiple LLMs collectively answer user questions. The workflow begins with user model selection and then runs an intent analysis, expert brainstorming, sequential contributions, verification, planning, editorial guidelines, and final synthesis.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- `COUNCIL_MODELS`: Default expert model pool (used if no selection provided)
- `AVAILABLE_MODELS`: Full selectable model list for chairman + experts (8 total)
- `MIN_EXPERT_MODELS`: Minimum expert model count (6)
- `CHAIRMAN_MODEL`: Default chairman model
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- Backend runs on **port 8001**

**`openrouter.py`**
- `query_model()`: Single async model query
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with `content` and optional `reasoning_details`
- Graceful degradation: returns None on failure, continues with successful responses

**`council.py`** - The Core Logic
- `stage0_analyze_intent()`: Intent analysis
- `stage_brainstorm_experts()`: All selected expert models brainstorm; chairman synthesizes final expert team
- `stage1_sequential_contributions()`: Experts contribute sequentially with quality reviews
- `stage_verification()`: Fact-checking + reasoning audit with optional DuckDuckGo evidence
- `stage_synthesis_planning()`: Creates a structured synthesis plan
- `stage_editorial_guidelines()`: Defines tone and formatting rules
- `stage3_synthesize_final()`: Chairman synthesizes final response
- `build_default_experts()`: Fallback expert list if synthesis fails

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, messages[]}`
- Assistant messages store: `stage0`, `experts`, `contributions`, `stage3`, and `metadata`
- Legacy: `debate` may still appear on older records

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- `GET /api/models` exposes available models, defaults, and minimum expert count
- `POST /api/conversations/{id}/message/stream` accepts `model_selection` and streams all stages
- Metadata includes model selection, verification, planning, and editorial outputs

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Orchestrates conversation state and SSE event handling
- Loads `/api/models` and persists the selected model set in memory per session

**`components/ModelSelector.jsx`**
- Pre-Intent UI for selecting chairman and expert models
- Enforces minimum expert model count before sending

**`components/ChatInterface.jsx`**
- Renders the model selection summary, stages, and final output
- Enter to send, Shift+Enter for new line
- User messages wrapped in `markdown-content` for padding

**`components/ContributionsStage.jsx`**
- Timeline view of sequential expert contributions

**`components/Stage0.jsx`**
- Intent analysis display + expert team cards

**`components/Stage3.jsx`**
- Final synthesized answer from chairman

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #0F52BA (blue)
- Global markdown styling in `index.css` with `.markdown-content` class

## Key Design Decisions

### Model Selection Phase
- Users select a Chairman model and at least 6 expert models from 8 total options
- The selection is attached to each message request and stored in metadata
- If no selection is provided, defaults from `config.py` apply

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All intermediate outputs are displayed with explicit stage headers
- Model selection summary is shown before Stage 0
- Users can validate the flow stage-by-stage

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Port Configuration
- Backend: 8001
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Model Selection Validation**: Backend enforces minimum expert models and rejects unknown models
4. **Storage Schema**: Stored assistant messages use `debate` for contributions and legacy `stage0.first_expert` naming

## Future Enhancement Ideas

- Persist model selection per conversation (not just per message)
- Export conversations to markdown/PDF
- Model performance analytics over time
- Streaming responses for each expert contribution
- Richer verification sources beyond DuckDuckGo

## Data Flow Summary

```
Model Selection
    ↓
Stage 0: Intent Analysis
    ↓
Stage 0.5: Expert Brainstorm → Expert Team
    ↓
Stage 1: Sequential Contributions
    ↓
Stage 2.5: Verification
    ↓
Stage 2.75: Synthesis Planning
    ↓
Stage 2.9: Editorial Guidelines
    ↓
Stage 3: Final Synthesis
    ↓
Return: {stage0, experts, contributions, stage3, metadata}
    ↓
Frontend: Stage-by-stage rendering + model selection summary
```

The entire flow is async/parallel where possible to minimize latency.

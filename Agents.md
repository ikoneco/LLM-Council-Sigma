# AGENTS.md - LLM Council Handoff Guide

## Purpose
This file is the handoff guide for agents and maintainers. It documents how the system works, where to make changes, and the operational constraints that matter most.

## Quickstart

Backend (FastAPI, port 8001):

```bash
uv run python -m backend.main
```

Frontend (Vite, port 5173):

```bash
cd frontend
npm install
npm run dev
```

Environment:
- `OPENROUTER_API_KEY` in `.env`

## [CONFIG] Project Configuration (Actual Stack)
Agents must prioritize these values over generic templates.

```yaml
PROJECT_LANGUAGE: JavaScript (React) + Python
LANGUAGE_MODE: Existing JS/JSX + Python 3.10+
FRONTEND_FRAMEWORK: React 19 + Vite
STATE_MANAGEMENT: React state (App.jsx orchestration)
STYLING_SOLUTION: Vanilla CSS (design tokens in index.css)
DESIGN_TOKEN_PATH: frontend/src/index.css
COMPONENT_LIBRARY_PATH: frontend/src/components/
ARCHITECTURE_PATTERN: Layered (backend / frontend / docs)
TEST_RUNNER_COMMAND: none (manual checks only)
LINT_COMMAND: none
FORMAT_COMMAND: none
TYPECHECK_COMMAND: none
FULL_BUILD_COMMAND: frontend: npm run build
```

## System Summary
LLM Council runs an 8-stage pipeline with an explicit model selection phase upfront:

0. Model Selection (chairman + expert pool, per-model thinking toggles)
1. Intent Draft + Clarifications (skippable)
2. Brainstorm Intent Brief (assumption-free brief)
3. Expert Brainstorm (parallel; chairman selects team)
4. Sequential Contributions (6 experts, round-robin model reuse)
5. Verification & Reasoning Audit (chairman model)
6. Synthesis Planning (chairman model)
7. Editorial Guidelines (chairman model)
8. Final Synthesis (chairman model)

Threads can continue using prior Chairman outputs as baseline context, or restart fresh.

## Key Files

Backend:
- `backend/council.py`: Core orchestration, prompts, stage logic
- `backend/main.py`: FastAPI routes, SSE streaming, model selection validation
- `backend/openrouter.py`: OpenRouter client + per-model reasoning payloads
- `backend/config.py`: Model lists, search config, defaults
- `backend/storage.py`: JSON conversation storage in `data/conversations/`

Frontend:
- `frontend/src/App.jsx`: Orchestrates SSE events and state
- `frontend/src/components/ModelSelector.jsx`: Model selection UI + per-model thinking toggles
- `frontend/src/components/ChatInterface.jsx`: Renders all stages and final output
- `frontend/src/utils/markdown.js`: Markdown and table normalization
- `frontend/src/index.css`: Global typography and markdown styles

Docs:
- `docs/ARCHITECTURE.md`: System design and pipeline details
- `docs/API.md`: API endpoints and SSE event types

## Core Mandate (Principal Engineer + Product Founder)
Prioritize long-term health and a top-quality user experience:

- Architecture: modular, testable, and easy to extend.
- Code quality: readable, consistent, minimal technical debt.
- UX: clear, fast, accessible, and delightful.

## Architecture and Modularity
- Keep backend orchestration in `backend/council.py`, not scattered across files.
- Keep UI state flow in `frontend/src/App.jsx` and stage rendering in components.
- Avoid cross-layer coupling: backend prompts should not assume frontend rendering details.

## Code Hygiene and Standards
- Prefer explicit, deterministic logic when parsing or normalizing model output.
- Do not hard-code secrets or access tokens.
- Keep prompts and JSON schemas stable; changes must be reflected in docs.
- Use small, composable helpers rather than large monolith functions.
- Use comments only when they clarify non-obvious logic.

## UI/UX Directives
- Use design tokens from `frontend/src/index.css` (no hard-coded colors or fonts).
- Maintain consistent heading hierarchy and spacing.
- Prefer readable, scannable layouts with progressive disclosure.
- Ensure interactive elements are keyboard-friendly and visually clear.

## Agent Workflow and Autonomy
- Execute P2/P3 improvements (code quality + UX polish) without extra confirmation.
- Ask before: new dependencies, major architecture changes, deleting core files, or commits/pushes.
- If scope is ambiguous, present 2–3 options with trade-offs and ask for a decision.

## Personal Quality Gate (Self-Review)
- Correctness: does it meet the request end-to-end?
- Safety: no secrets, no unsafe inputs.
- Performance: no unnecessary loops or heavy operations.
- Readability: consistent naming and structure.
- UI/UX: no regressions; visually consistent.
- Use "Nit:" for non-critical polish suggestions.

## Model Selection Rules
- Users must select at least 1 expert model.
- The system always runs 6 experts; selected models are reused round-robin if fewer than 6 are chosen.
- Per-model thinking is optional and only enabled for models listed in `THINKING_SUPPORTED_MODELS`.
- Model selection is stored in message metadata and used across the full cycle.

## Verification + Web Search
- Verification runs on the user-selected chairman model.
- Web search uses `openai/gpt-4o-mini-search-preview` via OpenRouter.
- Search scope is an exhaustive audit map built from contributions and is used only to generate search targets.
- Query count scales with scope size (min 3, max 8) via `SEARCH_QUERY_COUNT` and `SEARCH_QUERY_MAX`.
- Verification output is trimmed to only:
  - `## Search Status` (optional)
  - `## Verification & Reasoning Audit`
- Keep the `## Verification & Reasoning Audit` heading intact if you edit prompts.

## Conversation Storage
- Conversations are stored under `data/conversations/` as JSON.
- Assistant messages include `stage0`, `experts`, `contributions`, `stage3`, and `metadata`.
- `metadata.model_selection.thinking_by_model` stores per-model reasoning toggles.

## Editing Guidance
- Prompts are in `backend/council.py` and can have downstream effects. Verify output formats after edits.
- JSON extraction is regex-based in several stages; avoid adding extra wrapping text in JSON outputs.
- Frontend expects markdown in most stages; keep headings consistent for rendering and trimming rules.

## Common Tasks
- Add a model: update `AVAILABLE_MODELS` and `COUNCIL_MODELS` in `backend/config.py`.
- Enable thinking: add the model ID to `THINKING_SUPPORTED_MODELS`.
- Update search limits: adjust `SEARCH_QUERY_COUNT`, `SEARCH_QUERY_MAX`, or `SEARCH_MAX_SOURCES`.

## Known Pitfalls
- Run backend as `python -m backend.main` from repo root to avoid import errors.
- CORS must include frontend ports in `backend/main.py`.
- If verification returns extra content, it will be trimmed; keep headings stable.

## Testing
No automated tests are configured. Manual sanity checks:
- Run a full cycle and verify all stages stream correctly.
- Confirm verification shows Search Status when search fails.
- Confirm planning/editorial follow the chairman model selection.

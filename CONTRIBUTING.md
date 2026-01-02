# Contributing to LLM Council

We welcome contributions to correct bugs, improve prompts, or add new models! Because this is a highly automated agentic system, small changes in prompts can have large downstream effects.

## Development Workflow

1. **Fork & Clone**: Clone the repository locally.
2. **Environment Setup**:
    - Backend: Install `uv` and run `uv sync`.
    - Frontend: Install `npm` dependencies with `npm install`.
    - Create `.env` with your `OPENROUTER_API_KEY`.
3. **Run Locally**:
    - Backend: `uv run python -m backend.main`
    - Frontend: `npm run dev`

## Core Logic Locations

- **Logic**: If you want to change *how* the council thinks (prompts, stages, flow), edit `backend/council.py`.
- **Models**: If you want to change *who* is in the council, edit `backend/config.py`.
- **UI**: If you want to change how it *looks*, check `frontend/src/components/chatInterface.jsx`.

## Pull Request Guidelines

1. **Test Full Flow**: Before submitting, run a complete query aimed at checking all stages (e.g., "Analyze the geopolitical implications of Bitcoin"). Ensure all stages (Brainstorm, Contribution, Verification, Planning, Editorial, Synthesis) fire correctly.
2. **Check Prompts**: If you modify prompts, please verify that the output format remains valid JSON where expected. The backend currently uses regex to extract JSON, which can be fragile if models deviate.
3. **Keep it Simple**: We prefer monolithic simplicity over microservices complexity for this project.

## Adding New Models

To add a new model, simply append its OpenRouter ID to the `COUNCIL_MODELS` list in `backend/config.py`. Ensure the model is capable of instruction following and JSON output if used for structured tasks.

## License

This project is open source. Hack away!

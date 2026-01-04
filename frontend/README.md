# LLM Council Frontend

React 19 + Vite UI for LLM Council. The frontend streams stage updates from the backend and renders the full pipeline, including the model selection phase.

## Setup

```bash
npm install
npm run dev
```

The app runs on `http://localhost:5173` and expects the backend at `http://localhost:8001`.

## Scripts

- `npm run dev`: Start the dev server
- `npm run build`: Build for production
- `npm run preview`: Preview the production build
- `npm run lint`: Run ESLint

## Notes

- Model selection is loaded from `/api/models`.
- New threads start with no preselected models; users choose a chairman + experts.
- Per-model “thinking” toggles are available for supported models.
- Streaming responses are handled in `src/api.js`.

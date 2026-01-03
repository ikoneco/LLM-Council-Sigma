# LLM Council API Reference

Base URL: `http://localhost:8001` (Default)

## Content-Type

All API requests (except GET) expect `Content-Type: application/json`.

## Endpoints

### 1. List Models

Retrieve the available models and default selections.

- **URL**: `/api/models`
- **Method**: `GET`
- **Response**: `200 OK`

  ```json
  {
    "available_models": ["model-a", "model-b"],
    "default_expert_models": ["model-a", "model-b"],
    "default_chairman_model": "model-a",
    "min_expert_models": 1
  }
  ```

### 2. List Conversations

Retrieve a summary list of all existing conversations.

- **URL**: `/api/conversations`
- **Method**: `GET`
- **Response**: `200 OK`

  ```json
  [
    {
      "id": "uuid-string",
      "created_at": "ISO-8601 string",
      "title": "Conversation Title",
      "message_count": 5
    }
  ]
  ```

### 3. Create Conversation

Start a new empty conversation session.

- **URL**: `/api/conversations`
- **Method**: `POST`
- **Body**: (Empty JSON body) `{}`
- **Response**: `200 OK`

  ```json
  {
    "id": "uuid-string",
    "created_at": "ISO-8601 string",
    "title": "New Conversation",
    "messages": []
  }
  ```

### 4. Get Conversation Details

Retrieve the full message history and metadata for a specific conversation.

- **URL**: `/api/conversations/{conversation_id}`
- **Method**: `GET`
- **Response**: `200 OK`

  ```json
  {
    "id": "uuid-string",
    "messages": [
      {
        "role": "user",
        "content": "Why is the sky blue?"
      },
      {
        "role": "assistant",
        "status": "clarification_pending",
        "intent_draft": {...},
        "intent_display": {...},
        "clarification_questions": [...],
        "clarification_answers": {...},
        "stage0": {...},
        "experts": [...],
        "contributions": [...],
        "stage3": {...},
        "metadata": {
          "model_selection": {
            "chairman_model": "minimax/minimax-m2.1",
            "expert_models": ["..."]
          }
        }
      }
    ]
  }
  ```

  Notes:
  - `status` values include `clarification_pending`, `clarification_submitted`, and `complete`.
  - `intent_draft` / `intent_display` / `clarification_questions` appear before the pipeline runs.
  - `stage0.analysis` contains the intent brief used to guide brainstorming.

### 5. Send Message (Stream)

Send a user query and receive the intent draft + clarification questions.

- **URL**: `/api/conversations/{conversation_id}/message/stream`
- **Method**: `POST`
- **Body**:

  ```json
  {
    "content": "Explain quantum computing to a 5 year old",
    "model_selection": {
      "chairman_model": "minimax/minimax-m2.1",
      "expert_models": [
        "minimax/minimax-m2.1",
        "deepseek/deepseek-v3.2",
        "qwen/qwen2.5-vl-72b-instruct",
        "z-ai/glm-4.7",
        "moonshotai/kimi-k2-0905",
        "qwen/qwen3-235b-a22b-2507"
      ]
    }
  }
  ```

  Notes:
  - `model_selection` is optional; defaults apply if omitted.
  - `expert_models` must include at least 1 valid model.
  - The initial stream ends after `clarification_required`; use the continue endpoint to run the full pipeline.

- **Response**: `text/event-stream`
  
  **Event Types**:
  - `intent_draft_start` / `intent_draft_complete`: Draft intent analysis + clarification questions
  - `clarification_required`: Client should prompt the user for answers or skip
  - `title_complete`: Conversation title updated
  - `complete`: Stream finished
  - `error`: Stream failed

### 6. Continue Message (Stream)

Continue a message after clarifications (or skip) and run the full pipeline.

- **URL**: `/api/conversations/{conversation_id}/message/continue`
- **Method**: `POST`
- **Body**:

  ```json
  {
    "answers": [
      {
        "question_id": "q1",
        "selected_options": ["Option text", "Another option"],
        "other_text": ""
      }
    ],
    "free_text": "Optional extra context",
    "skip": false
  }
  ```

  Notes:
  - `skip: true` bypasses clarifications and proceeds with best-effort intent analysis.
  - `selected_options` supports multi-select responses per question.
  - The pipeline always executes 6 experts; if fewer models are selected, models are reused round-robin.

- **Response**: `text/event-stream`

  **Event Types**:
  - `stage0_start` / `stage0_complete`: Brainstorm intent brief (post-clarification)
  - `brainstorm_start` / `brainstorm_complete`: Expert brainstorming & selection (Contains `brainstorm_content` and `experts` list)
  - `contributions_start`: Sequence begins
  - `expert_start` / `expert_complete`: Individual expert contributions (Contains `expert` details and `contribution` text)
  - `contributions_complete`: Review finished
  - `verification_start` / `verification_complete`: Fact-checking verification
  - `planning_start` / `planning_complete`: Synthesis plan creation
  - `editorial_start` / `editorial_complete`: Editorial guidelines creation
  - `stage3_start` / `stage3_complete`: Final synthesis artifact regeneration
  - `complete`: Stream finished
  - `error`: Stream failed

### 7. Delete Conversation

Permanently remove a conversation and its data.

- **URL**: `/api/conversations/{conversation_id}`
- **Method**: `DELETE`
- **Response**: `200 OK`

  ```json
  { "status": "deleted" }
  ```

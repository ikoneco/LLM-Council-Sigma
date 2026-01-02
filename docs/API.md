# LLM Council API Reference

Base URL: `http://localhost:8001` (Default)

## Content-Type

All API requests (except GET) expect `Content-Type: application/json`.

## Endpoints

### 1. List Conversations

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

### 2. Create Conversation

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

### 3. Get Conversation Details

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
        "stage0": {...},
        "contributions": [...],
        "stage3": {...}
      }
    ]
  }
  ```

### 4. Send Message (Stream)

Send a user query and receive the streaming 7-stage execution process.

- **URL**: `/api/conversations/{conversation_id}/message/stream`
- **Method**: `POST`
- **Body**:

  ```json
  {
    "content": "Explain quantum computing to a 5 year old"
  }
  ```

- **Response**: `text/event-stream`
  
  **Event Types**:
  - `stage0_start` / `stage0_complete`: Intent Analysis
  - `brainstorm_start` / `brainstorm_complete`: Expert brainstorming & selection (Contains `brainstorm_content` and `experts` list)
  - `contributions_start`: Sequence begins
  - `expert_start` / `expert_complete`: Individual expert contributions (Contains `expert` details and `contribution` text)
  - `contributions_complete`: Review finished
  - `verification_start` / `verification_complete`: Fact-checking verification
  - `planning_start` / `planning_complete`: Synthesis plan creation
  - `editorial_start` / `editorial_complete`: Editorial guidelines creation
  - `stage3_start` / `stage3_complete`: Final synthesis artifact regeneration
  - `title_complete`: Conversation title updated
  - `complete`: Stream finished
  - `error`: Stream failed

### 5. Delete Conversation

Permanently remove a conversation and its data.

- **URL**: `/api/conversations/{conversation_id}`
- **Method**: `DELETE`
- **Response**: `200 OK`

  ```json
  { "status": "deleted" }
  ```

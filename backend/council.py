"""LLM Council orchestration with sequential expert collaboration."""

from typing import List, Dict, Any, Tuple, Optional
import json
import re
import asyncio
from .openrouter import query_model, query_search_model
from .config import (
    COUNCIL_MODELS,
    CHAIRMAN_MODEL,
    DEFAULT_NUM_EXPERTS,
    SEARCH_QUERY_COUNT,
    SEARCH_MAX_SOURCES,
)

SUPPORTED_OUTPUT_TYPES = [
    "plan",
    "summary",
    "checklist",
    "draft",
    "table",
    "critique",
    "rewrite",
    "research",
    "extraction",
    "troubleshooting",
    "recommendation",
]


def build_default_experts(num_experts: int) -> List[Dict[str, Any]]:
    """Build a fallback expert list sized to the requested expert count."""
    base_experts = [
        {"name": "Strategic Analyst", "description": "Task: Set strategic direction. Objective: Define approach.", "objectives": ["Define strategy"], "order": 1},
        {"name": "Technical Architect", "description": "Task: Technical foundation. Objective: Ensure feasibility.", "objectives": ["Ensure feasibility"], "order": 2},
        {"name": "Domain Specialist", "description": "Task: Domain expertise. Objective: Add depth.", "objectives": ["Add domain depth"], "order": 3},
        {"name": "Implementation Expert", "description": "Task: Practical application. Objective: Actionable guidance.", "objectives": ["Provide guidance"], "order": 4},
        {"name": "Risk Analyst", "description": "Task: Identify risks. Objective: Surface concerns.", "objectives": ["Identify risks"], "order": 5},
        {"name": "Quality Reviewer", "description": "Task: Critical review. Objective: Ensure completeness.", "objectives": ["Ensure quality"], "order": 6},
    ]

    if num_experts <= len(base_experts):
        return base_experts[:num_experts]

    extras = []
    for i in range(len(base_experts) + 1, num_experts + 1):
        extras.append({
            "name": f"Expert {i}",
            "description": "Task: Provide complementary analysis. Objective: Strengthen coverage.",
            "objectives": ["Add complementary depth"],
            "order": i,
        })
    return base_experts + extras


def format_conversation_history(history: List[Dict[str, Any]]) -> str:
    """Format previous conversation history for context handling."""
    if not history:
        return ""
    
    formatted = []
    for msg in history:
        role = msg.get("role")
        if role == "user":
            formatted.append(f"### 👤 User:\n{msg.get('content', '')}")
        elif role == "assistant":
            # Extract stage3 response if available, otherwise generic content
            response = ""
            if "stage3" in msg and msg["stage3"]:
                response = msg["stage3"].get("response", "")
            elif "content" in msg:
                response = msg["content"]
            
            if response:
                formatted.append(f"### 🤖 Chairman (Previous Output - Baseline Context):\n{response}")
                
    return "\n".join(formatted)

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    payload = match.group()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*\}", "}", payload)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def _extract_citations(annotations: Any) -> List[Dict[str, str]]:
    citations = []
    if not isinstance(annotations, list):
        return citations
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        if annotation.get("type") != "url_citation":
            continue
        data = annotation.get("url_citation") or {}
        citations.append({
            "title": data.get("title") or "Source",
            "url": data.get("url") or "",
            "snippet": data.get("snippet") or "",
        })
    return citations


def _strip_uncertain_intent_fields(intent_draft: Any) -> Dict[str, Any]:
    if not isinstance(intent_draft, dict):
        return {}
    draft = intent_draft.get("draft_intent")
    if isinstance(draft, dict):
        base = dict(draft)
    else:
        base = dict(intent_draft)
    base.pop("assumptions", None)
    base.pop("ambiguities", None)
    return base


def _build_fallback_questions() -> List[Dict[str, Any]]:
    return [
        {
            "id": "q1",
            "question": "What should the result enable you to do? (Select all that apply)",
            "options": [
                "Decide between options",
                "Execute a plan",
                "Communicate to stakeholders",
                "Learn/understand a topic",
                "Produce a draft or outline",
                "Other / I'll type it",
            ],
        },
        {
            "id": "q2",
            "question": "Who is the intended audience?",
            "options": [
                "Me (individual use)",
                "A cross-functional team",
                "Executives/stakeholders",
                "Customers/end-users",
                "Other / I'll type it",
            ],
        },
        {
            "id": "q3",
            "question": "What format should I produce?",
            "options": [
                "Step-by-step plan",
                "Bullet summary",
                "Table comparison",
                "Draft document",
                "Other / I'll type it",
            ],
        },
        {
            "id": "q4",
            "question": "How deep or rigorous should this be?",
            "options": [
                "Quick overview",
                "Standard depth",
                "Deep and detailed (edge cases)",
                "Other / I'll type it",
            ],
        },
        {
            "id": "q5",
            "question": "Any hard constraints I must follow? (Select all that apply)",
            "options": [
                "Use only what I provided",
                "Include citations/sources",
                "Timeboxed or short output",
                "Avoid specific topics/approaches",
                "Other / I'll type it",
            ],
        },
    ]


def _normalize_intent_draft(raw: Optional[Dict[str, Any]], user_query: str) -> Dict[str, Any]:
    fallback_questions = _build_fallback_questions()

    if not raw:
        return {
            "draft_intent": {
                "primary_intent": user_query,
                "task_type": "explanation",
                "deliverable": {
                    "format": "bullet summary",
                    "depth": "standard",
                    "tone": "neutral",
                },
                "explicit_constraints": [],
                "latent_intent_hypotheses": [],
                "ambiguities": [],
                "assumptions": [],
                "confidence": "low",
            },
            "display": {
                "understanding": [user_query],
                "assumptions": [],
                "unclear": [],
            },
            "questions": fallback_questions,
        }

    draft = raw.get("draft_intent") or raw.get("draft") or raw.get("intent_draft") or {}
    display = raw.get("display") or raw.get("summary") or {}
    questions = raw.get("questions") or raw.get("clarification_questions") or []

    if not isinstance(questions, list):
        questions = []

    normalized_questions = []
    for idx, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue
        q_id = item.get("id") or f"q{idx}"
        question_text = item.get("question") or item.get("prompt") or ""
        options = item.get("options") or []
        if not isinstance(options, list):
            options = []
        if "Other / I'll type it" not in options:
            options.append("Other / I'll type it")
        normalized_questions.append({
            "id": q_id,
            "question": question_text.strip() or f"Clarification {idx}",
            "options": options[:6],
        })

    if len(normalized_questions) < 3:
        needed = 3 - len(normalized_questions)
        for fallback in fallback_questions:
            if needed <= 0:
                break
            if fallback["question"] in {q["question"] for q in normalized_questions}:
                continue
            normalized_questions.append(fallback)
            needed -= 1

    normalized_questions = normalized_questions[:6]

    deliverable_raw = draft.get("deliverable") or {}
    if not isinstance(deliverable_raw, dict):
        deliverable_raw = {}

    deliverable = {
        "format": deliverable_raw.get("format") or "bullet summary",
        "depth": deliverable_raw.get("depth") or "standard",
        "tone": deliverable_raw.get("tone") or "neutral",
        "structure": deliverable_raw.get("structure") or "",
        "required_elements": deliverable_raw.get("required_elements") or [],
    }
    if not isinstance(deliverable["required_elements"], list):
        deliverable["required_elements"] = []

    explicit_constraints = draft.get("explicit_constraints") or []
    if not isinstance(explicit_constraints, list):
        explicit_constraints = []

    constraints_raw = draft.get("constraints") or {}
    if not isinstance(constraints_raw, dict):
        constraints_raw = {}

    constraints = {
        "must": constraints_raw.get("must") or [],
        "should": constraints_raw.get("should") or [],
        "must_not": constraints_raw.get("must_not") or [],
    }
    for key in ("must", "should", "must_not"):
        if not isinstance(constraints[key], list):
            constraints[key] = []

    if explicit_constraints:
        existing = {item for item in constraints["must"] if isinstance(item, str)}
        for item in explicit_constraints:
            if isinstance(item, str) and item not in existing:
                constraints["must"].append(item)

    quality_bar = draft.get("quality_bar") or {}
    if not isinstance(quality_bar, dict):
        quality_bar = {}

    success_criteria = draft.get("success_criteria") or []
    if not isinstance(success_criteria, list):
        success_criteria = []

    latent_hypotheses = draft.get("latent_intent_hypotheses") or []
    if not isinstance(latent_hypotheses, list):
        latent_hypotheses = []

    ambiguities = draft.get("ambiguities") or []
    if not isinstance(ambiguities, list):
        ambiguities = []

    assumptions = draft.get("assumptions") or []
    if not isinstance(assumptions, list):
        assumptions = []

    draft_intent = {
        "primary_intent": draft.get("primary_intent") or draft.get("primary_goal") or user_query,
        "goal_outcome": draft.get("goal_outcome") or draft.get("goal") or draft.get("outcome") or user_query,
        "task_type": draft.get("task_type") or "explanation",
        "deliverable": deliverable,
        "audience": draft.get("audience") or draft.get("target_audience") or "",
        "constraints": constraints,
        "quality_bar": quality_bar,
        "success_criteria": success_criteria,
        "explicit_constraints": explicit_constraints,
        "latent_intent_hypotheses": latent_hypotheses,
        "ambiguities": ambiguities,
        "assumptions": assumptions,
        "confidence": draft.get("confidence") or "medium",
    }

    understanding = display.get("understanding") or []
    if not isinstance(understanding, list):
        understanding = []
    if not understanding:
        understanding = [draft_intent["primary_intent"]]

    assumptions_display = display.get("assumptions") or []
    if not isinstance(assumptions_display, list):
        assumptions_display = []

    unclear_display = display.get("unclear") or []
    if not isinstance(unclear_display, list):
        unclear_display = []

    display_payload = {
        "understanding": understanding,
        "assumptions": assumptions_display,
        "unclear": unclear_display,
    }

    return {
        "draft_intent": draft_intent,
        "display": display_payload,
        "questions": normalized_questions,
    }


async def stage0_generate_intent_draft(
    user_query: str,
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Phase 1: Draft intent analysis + clarification questions.
    Returns a structured draft payload for UI display.
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    product_context = {
        "supported_output_types": SUPPORTED_OUTPUT_TYPES,
        "capabilities": [
            "multi-stage reasoning pipeline",
            "intent clarification loop",
            "model selection for chairman and experts",
        ],
        "limitations": [
            "no direct access to private user files unless provided",
            "web search limited to verification stage",
        ],
    }

    intent_prompt = f"""<system>You are an Intent Analyst + Clarification Designer.</system>

<task>
Turn the raw user request into a draft intent model and 3-6 high-impact clarification questions.
Optimize for correctness. Go beyond surface-level by inferring likely motivations, context, audience, constraints, success criteria, dependencies, and risk tolerance.
Separate explicit statements from inferred hypotheses and label uncertainty clearly.
Ask fewer, higher-leverage questions that resolve the highest-impact unknowns.
Provide options + "Other / I'll type it". Multi-select options are allowed when appropriate.
If there is conversation context, treat the most recent Chairman output as the baseline and interpret the new query as additional instructions or refinements.
</task>

<user_query>{user_query}</user_query>
{context_section}

<product_context>
{json.dumps(product_context, indent=2)}
</product_context>

<output_format>
Return a JSON object ONLY with this schema:
{{
  "draft_intent": {{
    "primary_intent": "1 sentence",
    "goal_outcome": "What success enables or produces",
    "task_type": "explanation|recommendation|plan|critique|rewrite|research|extraction|troubleshooting",
    "deliverable": {{
      "format": "bullets|table|steps|outline|doc|etc",
      "depth": "quick|standard|deep",
      "tone": "string or null",
      "structure": "key sections or outline (optional)",
      "required_elements": ["optional bullets"]
    }},
    "audience": "string or null",
    "constraints": {{
      "must": ["..."],
      "should": ["..."],
      "must_not": ["..."]
    }},
    "quality_bar": {{
      "rigor": "quick|standard|deep",
      "evidence": "none|light|strict",
      "completeness": "core|standard|comprehensive",
      "risk_tolerance": "low|medium|high"
    }},
    "success_criteria": ["..."],
    "explicit_constraints": ["..."],
    "latent_intent_hypotheses": ["..."],
    "ambiguities": ["..."],
  "assumptions": [{{"assumption": "...", "risk": "high|medium|low", "why_it_matters": "..."}}],
    "confidence": "high|medium|low"
  }},
  "display": {{
    "understanding": ["2-4 short bullets in plain language"],
    "assumptions": ["2-3 concise bullets that include why the assumption matters"],
    "unclear": ["2-3 concise bullets of biggest open decisions"]
  }},
  "questions": [
    {{
      "id": "q1",
      "question": "text",
      "options": ["2-5 options", "Other / I'll type it"]
    }}
  ]
}}
</output_format>

Rules:
- Provide 3-6 questions.
- Each question addresses ONE dimension only.
- Target the highest-impact uncertainties (goal/outcome, scope boundaries, audience, format, constraints, quality bar).
- Order ambiguities, assumptions, and questions by impact (highest first).
- Options must be distinct and actionable. Multi-select is allowed when it helps (do not force exclusivity).
- Avoid vague prompts; every option should imply a different execution path.
- Always include "Other / I'll type it".
- Keep the display output human-friendly and scannable; reserve depth for the draft_intent fields.

Generate the JSON now:"""

    messages = [{"role": "user", "content": intent_prompt}]
    model_name = analysis_model or CHAIRMAN_MODEL
    response = await query_model(model_name, messages)

    if response is None:
        return _normalize_intent_draft(None, user_query)

    parsed = _extract_json(response.get("content", ""))
    return _normalize_intent_draft(parsed, user_query)


async def stage0_finalize_intent(
    user_query: str,
    intent_draft: Dict[str, Any],
    clarification_payload: Dict[str, Any],
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
) -> str:
    """
    Phase 3: Final intent packet after clarification (or skip).
    Returns Markdown intended for display and downstream use.
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""

    intent_prompt = f"""<system>You are an Intent Analyst + Clarification Designer.</system>

<task>
Incorporate the clarifications (if any) into a final intent packet.
Treat selections as authoritative unless they conflict with explicit user text.
If the user skipped clarifications, proceed with best-effort and mark remaining uncertainty as assumptions.
Clarification answers may include multiple selected options per question.
Ensure the final intent summary uses ALL available input: user query, conversation context, draft intent fields, and clarifications.
Do NOT ask more questions.
</task>

<user_query>{user_query}</user_query>
{context_section}

<intent_draft>
{json.dumps(_strip_uncertain_intent_fields(intent_draft), indent=2)}
</intent_draft>

<clarifications>
{json.dumps(clarification_payload, indent=2)}
</clarifications>

<output_format>
Return Markdown ONLY using this template:

## Intent Brief (Proxy for User Input)

### Executive Summary
- One-sentence synthesis of what the user needs and why.

### Core Instruction (Write as Direct Guidance)
- Act as if the user asked you to: ...
- Primary objective: ...
- Secondary objectives: ...

### User Intent (High-Confidence)
- Explicit ask: ...
- Implied success criteria: ...
- Implied goals strongly supported by the input: ...

### Audience & Context
- Audience: ...
- Context to account for: ...

### Constraints & Preferences
- Must: ...
- Should: ...
- Must not: ...

### Deliverable Expectations
- Format:
- Depth:
- Tone:
- Structure / required elements:

### Quality Bar
- Rigor:
- Evidence:
- Completeness:
- Risk tolerance:

### Scope Boundaries
- In scope (must cover): ...
- Out of scope (exclude): ...

### Execution Guidance (All Stages)
- Priorities to optimize for: ...
- Key angles to address: ...
- De-prioritize / avoid: ...

### Confidence
- Overall confidence: high|medium|low
</output_format>

Rules:
- Use only the sections above (no extra headings, no JSON).
- Ensure every section is present (use "None noted" if empty).
- Do not include assumptions, guesses, or open questions. If uncertain, omit the item.
- Ignore draft assumptions/ambiguities unless they were explicitly resolved by user clarifications.
- Synthesize all available input into a concise, instructive brief that guides all stages.
- The brief must be self-contained: avoid references like "as mentioned above" or relying on external context.
- Write as actionable instructions that any stage can execute immediately.

Provide the intent brief now:"""

    messages = [{"role": "user", "content": intent_prompt}]
    model_name = analysis_model or CHAIRMAN_MODEL
    response = await query_model(model_name, messages)

    if response is None:
        return "Intent analysis unavailable."

    return response.get("content", "Intent analysis unavailable.")


async def stage_brainstorm_experts(
    user_query: str,
    intent_analysis: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    num_experts: int = DEFAULT_NUM_EXPERTS,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Stage 0.5: All models brainstorm to define experts.
    Each model suggests experts, then chairman synthesizes final team.
    Returns: (brainstorm_content, experts_list)
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""

    brainstorm_prompt = f"""<task>
You are brainstorming the OPTIMAL expert team for this specific query.
Your suggestions must be HIGHLY RELEVANT to the query's unique requirements.
</task>

<user_query>{user_query}</user_query>
{context_section}

<intent_analysis>
{intent_analysis}
</intent_analysis>

<brainstorm_requirements>
For each expert you suggest, provide:
1. **Role**: A SPECIFIC professional title relevant to THIS query (not generic titles)
2. **Why Needed**: Why this expertise is critical for this specific query
3. **Goals**: 2-3 specific goals this expert must achieve
4. **Deliverables**: What tangible output this expert will contribute

Examples of GOOD vs BAD:
- BAD: "Technical Expert" with vague goals
- GOOD: "Senior Cloud Security Architect" with goals like "Identify authentication vulnerabilities" and "Recommend zero-trust implementation patterns"
</brainstorm_requirements>

<output_format>
Provide 2-3 expert suggestions in this format:

### Expert 1: [Specific Role Title]
**Why Needed**: [Why this expertise is essential for this query]
**Goals**:
1. [Specific goal 1]
2. [Specific goal 2]
3. [Specific goal 3]
**Key Deliverables**: [What they will produce]

### Expert 2: [Specific Role Title]
...
</output_format>

Provide your expert suggestions now:"""

    models = expert_models or COUNCIL_MODELS
    chairman = chairman_model or CHAIRMAN_MODEL

    # Collect brainstorm from all models in parallel
    import asyncio
    tasks = [
        query_model(model, [{"role": "user", "content": brainstorm_prompt}])
        for model in models
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Format brainstorm content for display
    brainstorm_sections = []
    all_suggestions_for_synthesis = []
    
    for i, resp in enumerate(responses):
        model_name = models[i].split('/')[-1]  # Get short model name
        if isinstance(resp, Exception) or resp is None:
            brainstorm_sections.append(f"### 🤖 {model_name}\n*Failed to respond*\n")
            continue
        content = resp.get('content', '')
        brainstorm_sections.append(f"### 🤖 {model_name}\n{content}\n")
        all_suggestions_for_synthesis.append(f"=== Suggestions from {model_name} ===\n{content}")
    
    brainstorm_display = "## Expert Brainstorm Results\n\n" + "\n---\n\n".join(brainstorm_sections)
    
    # Chairman synthesizes the final expert team
    synthesis_prompt = f"""<task>
You are the Chairman forming the FINAL expert team from brainstorm suggestions.
Create a team of {num_experts} HIGHLY RELEVANT experts with SPECIFIC roles aligned to this query.
</task>

<user_query>{user_query}</user_query>
{context_section}

<intent_analysis>
{intent_analysis}
</intent_analysis>

<brainstorm_suggestions>
{chr(10).join(all_suggestions_for_synthesis)}
</brainstorm_suggestions>

<team_formation_requirements>
1. Select EXACTLY {num_experts} experts
2. Each expert MUST have:
   - A SPECIFIC role title (not generic like "Domain Expert")
   - A DETAILED task description (50+ words explaining what they will do)
   - CLEAR objectives (2-3 measurable goals)
3. Ensure COMPLEMENTARY coverage - each expert addresses a DIFFERENT dimension
4. Order strategically: Foundation builders first, quality reviewers last
5. Draw from the BEST suggestions across all models
</team_formation_requirements>

<output_format>
Respond with a valid JSON object ONLY:
{{
    "team_rationale": "2-3 sentences explaining why this specific team was chosen for this query",
    "experts": [
        {{
            "role": "Specific Professional Title",
            "task": "Detailed 50+ word description of exactly what this expert will analyze, create, or contribute. Be specific about methodologies, frameworks, or approaches they will use.",
            "objectives": ["Measurable goal 1", "Measurable goal 2", "Measurable goal 3"],
            "order": 1
        }},
        {{
            "role": "Specific Professional Title",
            "task": "Detailed description...",
            "objectives": ["Goal 1", "Goal 2"],
            "order": 2
        }},
        ... (continue for all {num_experts} experts)
    ]
}}
</output_format>

Create the optimal expert team now:"""

    messages = [{"role": "user", "content": synthesis_prompt}]
    response = await query_model(chairman, messages)
    
    default_experts = build_default_experts(num_experts)
    
    if response is None:
        return brainstorm_display, default_experts
    
    content = response.get('content', '')
    try:
        import json
        import re
        # Find the first { and the last } to extract JSON block
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Try to fix common JSON issues like trailing commas
                cleaned_json = re.sub(r',\s*\}', '}', json_match.group())
                cleaned_json = re.sub(r',\s*\]', ']', cleaned_json)
                data = json.loads(cleaned_json)
            
            experts = data.get("experts", [])
            rationale = data.get("team_rationale", "")
            
            normalized = []
            for i, e in enumerate(experts[:num_experts]):
                # Be flexible with key names
                role = e.get("role") or e.get("name") or e.get("title") or f"Expert {i+1}"
                task = e.get("task") or e.get("description") or e.get("details") or "Contribute expertise"
                objectives = e.get("objectives", [])
                if isinstance(objectives, str):
                    objectives_str = objectives
                else:
                    objectives_str = " | ".join(objectives) if objectives else "Add value"
                
                normalized.append({
                    "name": role,
                    "description": task,
                    "objectives": objectives_str,
                    "order": e.get("order", i + 1)
                })
            
            while len(normalized) < num_experts:
                normalized.append(default_experts[len(normalized)])
            
            # Append team rationale to brainstorm display
            if rationale:
                brainstorm_display += f"\n\n---\n\n## 👔 Chairman's Team Selection\n\n{rationale}"
            
            return brainstorm_display, normalized
    except Exception as e:
        print(f"Error parsing brainstorm synthesis: {e}. Raw content: {content[:200]}...")
    
    return brainstorm_display, default_experts


async def get_expert_contribution(
    user_query: str, 
    expert: Dict[str, str], 
    contributions: List[Dict[str, Any]], 
    order: int,
    intent_analysis: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    num_experts: int = DEFAULT_NUM_EXPERTS,
) -> str:
    """
    Get a contribution from an expert, building on previous work with rigorous quality focus.
    """
    context_str = format_conversation_history(history or [])
    conversation_context = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    if contributions:
        prior_work = "\n\n---\n\n".join([
            f"**Expert {entry['order']}: {entry['expert']['name']}**\n{entry['contribution']}"
            for entry in contributions
        ])
        context_section = f"""<prior_contributions>
{prior_work}
</prior_contributions>

<your_role>
You are Expert {order} of {num_experts}. Your job is to CRITICALLY REVIEW and then BUILD UPON the prior work.
Your unique mandate: {expert['description']}
</your_role>

<quality_review_requirements>
Before adding your contribution, you MUST:
1. **Identify Inaccuracies**: Flag any factual errors or misleading statements.
2. **Surface Assumptions**: Call out unstated assumptions that may not hold.
3. **Detect Reasoning Errors**: Point out logical fallacies, gaps, or weak arguments.
4. **Challenge Opportunities**: Question areas where the approach could be stronger.
5. **Correct and Improve**: Fix any issues you found, then add your unique value.
</quality_review_requirements>"""
    else:
        context_section = f"""<your_role>
You are Expert {order} of {num_experts}. You are the FIRST expert laying the FOUNDATION.
Subsequent experts will review your work for errors and build upon it, so be rigorous.
Your mandate: {expert['description']}
</your_role>

<foundation_requirements>
As the first expert, you MUST:
1. **State Key Assumptions**: Be explicit about what you're assuming.
2. **Be Rigorous**: Avoid weak claims or unsupported assertions.
3. **Set Clear Direction**: Provide a solid framework others can build on.
4. **Anticipate Gaps**: Acknowledge areas that need further expertise.
</foundation_requirements>"""
    
    models = expert_models or COUNCIL_MODELS
    model = models[(order - 1) % len(models)]
    
    expert_prompt = f"""<system>You are {expert['name']}, a world-class professional contributing to a rigorous collaborative process.</system>

<mission>
Help produce the HIGHEST QUALITY artifact that fully addresses the user's intent.
Your contribution must move the reasoning quality, richness, and depth FORWARD.
</mission>

<user_query>{user_query}</user_query>
{conversation_context}

<intent_analysis>
{intent_analysis}
</intent_analysis>

{context_section}

<contribution_framework>
Structure your response as follows:

{"**## Quality Review**" if contributions else ""}
{"- Flag any inaccuracies, assumptions, or reasoning errors in prior work" if contributions else ""}
{"- Note areas of opportunity that need strengthening" if contributions else ""}

**## My Contribution: {expert['name']}**
- Add your unique value and expertise
- Be specific, actionable, and evidence-based
- Integrate with and enhance prior work
- Target 250-400 words

**## Key Assumptions** (if any)
- State any assumptions you're making
</contribution_framework>

<quality_standards>
- **Accuracy**: Every claim must be correct and defensible.
- **Depth**: Go beyond surface-level—provide real insight.
- **Actionability**: The user should be able to act on this.
- **Coherence**: Build a unified artifact, not disconnected pieces.
</quality_standards>

Provide your rigorous expert contribution now:"""

    messages = [{"role": "user", "content": expert_prompt}]
    response = await query_model(model, messages)
    
    if response is None:
        return "Expert contribution unavailable."
    
    return response.get('content', 'Expert contribution unavailable.')


async def stage1_sequential_contributions(
    user_query: str, 
    experts: List[Dict[str, str]],
    intent_analysis: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    num_experts: int = DEFAULT_NUM_EXPERTS,
) -> List[Dict[str, Any]]:
    """
    Stage 1: Sequential expert contributions.
    Each expert builds upon the previous expert's work.
    """
    contributions = []
    
    for i, expert in enumerate(experts):
        order = expert.get('order', i + 1)
        
        contribution = await get_expert_contribution(
            user_query, 
            expert, 
            contributions, 
            order,
            intent_analysis,
            history,
            expert_models=expert_models,
            num_experts=num_experts,
        )
        
        contributions.append({
            "order": order,
            "expert": expert,
            "contribution": contribution,
            "model": (expert_models or COUNCIL_MODELS)[(order - 1) % len(expert_models or COUNCIL_MODELS)]
        })
    
    return contributions


async def stage_verification(
        user_query: str, 
        contributions: List[Dict[str, Any]],
        history: List[Dict[str, Any]] = None
) -> str:
    """Stage 2.5: Verify claims and audit reasoning across all contributions."""
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    summary = "\n".join([
        f"- Expert {entry['order']} ({entry['expert']['name']}): \"{entry['contribution']}...\""
        for entry in contributions
    ])
    
    # 1. Generate Search Targets
    query_gen_prompt = f"""<task>
You are a Fact-Check Strategist dedicated to eliminating hallucinations and weak reasoning.
Review the expert contributions and flag specific data points that are prone to hallucination (e.g., pricing, release dates, version numbers, technical specs).
Generate EXACTLY {SEARCH_QUERY_COUNT} high-risk verification targets with precise search queries.
</task>

<user_query>{user_query}</user_query>
{context_section}

<expert_contributions>
{summary}
</expert_contributions>

<output_format>
Return ONLY a JSON array of objects:
[
  {{
    "claim": "verbatim claim to verify",
    "why_high_risk": "why this is likely to be wrong or outdated",
    "query": "focused search query",
    "preferred_sources": ["official docs", "vendor site", "standards body"]
  }}
]
</output_format>"""

    search_targets = []
    try:
        messages = [{"role": "user", "content": query_gen_prompt}]
        response = await query_model("google/gemini-2.0-flash-001", messages)
        content = response.get('content', '[]')
        import json
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            search_targets = json.loads(json_match.group())
    except Exception as e:
        print(f"Error generating search targets: {e}")

    # 2. Execute Search via gpt-4o-mini-search-preview
    search_evidence = ""
    if search_targets:
        try:
            evidence_blocks = []
            for target in search_targets[:SEARCH_QUERY_COUNT]:
                if not isinstance(target, dict):
                    continue
                claim = target.get("claim", "").strip()
                query = target.get("query", "").strip() or claim
                preferred_sources = target.get("preferred_sources", [])
                if isinstance(preferred_sources, str):
                    preferred_sources = [preferred_sources]

                sources_hint = ""
                if preferred_sources:
                    sources_hint = f"Preferred sources: {', '.join(preferred_sources)}"

                search_prompt = f"""<task>
Use web search to verify the claim. Return sources with URLs and a short evidence summary.
</task>

<claim>{claim}</claim>
<query>{query}</query>
{sources_hint}

<output_format>
Return JSON:
{{
  "claim": "{claim}",
  "query": "{query}",
  "verdict": "supports|refutes|unclear",
  "summary": "1-2 sentence evidence summary",
  "sources": [
    {{"title": "Source Title", "url": "https://...", "snippet": "Relevant excerpt"}}
  ]
}}
</output_format>"""

                search_response = await query_search_model([{"role": "user", "content": search_prompt}])
                raw_content = search_response.get("content", "") if search_response else ""
                annotations = search_response.get("annotations") if search_response else None
                evidence = _extract_json(raw_content) or {}

                verdict = evidence.get("verdict") or "unclear"
                summary_text = evidence.get("summary") or evidence.get("analysis") or raw_content or "No evidence summary available."
                sources = evidence.get("sources") or _extract_citations(annotations)

                formatted_sources = []
                if isinstance(sources, list):
                    for source in sources[:SEARCH_MAX_SOURCES]:
                        if not isinstance(source, dict):
                            continue
                        title = source.get("title", "Unknown Source")
                        url = source.get("url", "")
                        snippet = source.get("snippet", "")
                        if url:
                            formatted_sources.append(f"- [{title}]({url}) — {snippet}")
                        else:
                            formatted_sources.append(f"- {title} — {snippet}")

                if not formatted_sources:
                    formatted_sources.append("- No sources returned.")

                block = "\n".join([
                    f"Claim: {claim}",
                    f"Query: {query}",
                    f"Verdict: {verdict}",
                    f"Summary: {summary_text}",
                    "Sources:",
                    *formatted_sources,
                ])
                evidence_blocks.append(block)

            if evidence_blocks:
                search_evidence = "\n\n".join(evidence_blocks)
        except Exception as e:
            print(f"Search execution failed: {e}")
            search_evidence = "Search unavailable."

    # 3. Final Verification with Evidence
    evidence_section = ""
    if search_evidence:
        evidence_section = f"""
<search_evidence>
{search_evidence}
</search_evidence>

<instructions>
Use the Search Evidence to VALIDATE or DEBUNK the claims.
- **Prioritize Reputable Sources**: Rely on official documentation, major news outlets, and academic sources.
- **Corrective Action**: If a claim is wrong, provide the CORRECT information with citations.
- **Reasoning**: Explain why the expert's claim might be inaccurate.
- **CITATION FORMAT**: You MUST cite sources as markdown links: [Source Name](URL). Example: "According to [OpenAI Pricing](https://openai.com/pricing), the cost is..."
</instructions>
"""

    verification_prompt = f"""<task>
You are a Meticulous Fact-Checker AND Reasoning Auditor. Verify the expert contributions against the provided Search Evidence (if available) and your own knowledge.
Focus on accurate numbers, dates, pricing, and technical facts, AND identify reasoning issues: logical flaws, gaps, inconsistencies, and unsupported assumptions.
</task>

<user_query>{user_query}</user_query>
{context_section}

<expert_contributions>
{summary}
</expert_contributions>

{evidence_section}

<output_format>
## Verification & Reasoning Audit

### Finding 1: [Claim or Reasoning Issue]
- **Type**: Factual / Logical / Inconsistency / Gap / Assumption
- **Verdict**: Verified / Partially Accurate / Incorrect / Needs Clarification
- **Corrective Information**: [Accurate facts from search or corrected logic. CITE SOURCE if factual: [Name](URL)]
- **Reasoning**: [Explain conflict, gap, or flawed logic]
- **Source Reliability**: [High/Medium/Low/N-A]

### Finding 2: [Claim or Reasoning Issue]
- **Type**: ...
- **Verdict**: ...
- **Corrective Information**: ...
- **Reasoning**: ...
- **Source Reliability**: ...

### Finding 3: [Claim or Reasoning Issue]
- **Type**: ...
- **Verdict**: ...
- **Corrective Information**: ...
- **Reasoning**: ...
- **Source Reliability**: ...
</output_format>

Provide your verification report now. Include both factual and reasoning issues:"""

    messages = [{"role": "user", "content": verification_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages)
    return response.get('content', 'Verification unavailable.') if response else "Verification unavailable."


async def stage_synthesis_planning(
    user_query: str,
    contributions: List[Dict[str, Any]],
    intent_analysis: str,
    verification_data: str,
    history: List[Dict[str, Any]] = None
) -> str:
    """
    Stage 2.75: Create a structured plan for the chairman.
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""

    contributions_summary = "\n".join([
        f"- Expert {entry['order']} ({entry['expert']['name']}): {entry['contribution'][:300]}..."
        for entry in contributions
    ])
    
    planning_prompt = f"""<task>
You are the Synthesis Architect. Create a STRUCTURED PLAN for the Chairman's final synthesis.
</task>

<user_query>{user_query}</user_query>
{context_section}

<intent_analysis>
{intent_analysis}
</intent_analysis>

<expert_contributions>
{contributions_summary}
</expert_contributions>

<verification_report>
{verification_data}
</verification_report>

<output_format>
## Synthesis Plan for Chairman

### Critical Missing Elements
- [What wasn't addressed]

### Reasoning Gaps to Address
- [Logic needing deeper analysis]

### Additional Expertise/Data Needed
- [Missing facts or evidence]

### Recommended Structure
- [Outline for final artifact]

### Quality Checklist
- [ ] [Requirement 1]
- [ ] [Requirement 2]

### Critical Actions for Chairman
1. [Must-do 1]
2. [Must-do 2]
</output_format>

Provide the synthesis plan now:"""

    messages = [{"role": "user", "content": planning_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages)
    return response.get('content', 'Planning unavailable.') if response else "Planning unavailable."


async def stage_editorial_guidelines(
    user_query: str,
    intent_analysis: str,
    contributions: List[Dict[str, Any]],
    synthesis_plan: str,
    history: List[Dict[str, Any]] = None
) -> str:
    """
    Stage 2.9: Create editorial guidelines for the chairman's writing style.
    Defines tone, voice, style, and formatting for the final synthesis.
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    editorial_prompt = f"""<task>
You are the Editorial Director. Create detailed writing guidelines for the Chairman's final synthesis.
The guidelines must ensure the final output's style perfectly matches the user's intent and context.
</task>

<user_query>{user_query}</user_query>
{context_section}

<intent_analysis>
{intent_analysis}
</intent_analysis>

<synthesis_plan>
{synthesis_plan}
</synthesis_plan>

<editorial_analysis>
Consider:
1. What is the user's likely expertise level? (beginner → expert)
2. What is the appropriate formality level? (casual → highly formal)
3. What tone would be most effective? (encouraging, authoritative, cautious, etc.)
4. What is the optimal length and depth?
5. What formatting would enhance readability?
</editorial_analysis>

<output_format>
## Editorial Guidelines for Chairman

### Voice & Persona
- [How should the Chairman "sound"? What character/authority level?]

### Tone
- [e.g., Authoritative but accessible, Technical but clear, etc.]

### Audience Calibration
- **Expertise Level**: [Beginner/Intermediate/Expert]
- **Assumed Context**: [What the user likely knows]
- **Avoid**: [Jargon to skip, concepts to not over-explain]

### Style Guidelines
- **Sentence Structure**: [Short and punchy vs. flowing and detailed]
- **Use of Examples**: [When and how to include them]
- **Technical Depth**: [How deep to go]

### Formatting Instructions
- **Length Target**: [word count or section count]
- **Structure**: [How to organize the response]
- **Visual Elements**: [Use of headers, bullets, bold, etc.]

### Style Anti-Patterns
- **Avoid**: [What to explicitly AVOID in the writing]

### Quality Bar
- [What makes this response "excellent" vs. "adequate"]
</output_format>

Do NOT wrap the output in markdown code blocks (```). Provide raw markdown only.
Provide the editorial guidelines now:"""

    messages = [{"role": "user", "content": editorial_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages)
    return response.get('content', 'Editorial guidelines unavailable.').replace("```markdown", "").replace("```", "") if response else "Editorial guidelines unavailable."


async def stage3_synthesize_final(
    user_query: str,
    contributions: List[Dict[str, Any]],
    intent_analysis: str = "",
    verification_data: str = "",
    synthesis_plan: str = "",
    editorial_guidelines: str = "",
    history: List[Dict[str, Any]] = None,
    chairman_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage 3: Chairman synthesizes all contributions following the plan and editorial guidelines."""
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    contributions_text = "\n\n---\n\n".join([
        f"**Expert {entry['order']}: {entry['expert']['name']}**\n{entry['contribution']}"
        for entry in contributions
    ])

    chairman_prompt = f"""<system>
You are the final synthesis editor responsible for producing the best possible answer.
Your job is to integrate all verified inputs into one coherent, user-ready artifact that fulfills the user's intent.
Resolve conflicts with judgment and prioritize accuracy, completeness, and usefulness.
</system>

<mission>
Deliver a response that fully addresses the user's intent with accuracy, depth, and clarity.
Balance the Synthesis Plan and Editorial Guidelines with the actual context and evidence.
Maintain continuity with prior final outputs if present.
</mission>

<inputs>
<user_query>{user_query}</user_query>
{context_section}

<intent_brief>
{intent_analysis}
</intent_brief>

<expert_contributions>
{contributions_text}
</expert_contributions>

<verification_report>
{verification_data}
</verification_report>

<synthesis_plan>
{synthesis_plan}
</synthesis_plan>

<editorial_guidelines>
{editorial_guidelines}
</editorial_guidelines>
</inputs>

<context_priority>
1. User query + intent brief define the authoritative goals and scope.
2. Verification report is the truth filter; correct or remove any conflicting claims.
3. Conversation context preserves continuity; defer to the latest intent if conflicts exist.
4. Expert contributions provide ideas and evidence to integrate or reject with justification.
5. Synthesis plan suggests structure; adapt when the content demands a better flow.
6. Editorial guidelines govern tone and format; clarity and usefulness come first.
</context_priority>

<chairman_guidance>
1. Follow the Synthesis Plan as your primary structure, but adapt it when the context warrants a better organization.
2. Honor the Editorial Guidelines for tone, voice, and format while keeping clarity and usefulness first.
3. Use the Verification Report as a truth filter: correct or remove incorrect claims and add missing context when clarification is required.
4. Integrate every expert contribution by incorporating, refining, or explicitly rejecting key points with justification.
5. Resolve conflicts between experts and make final judgment calls when needed.
6. Keep the output self-contained and directly actionable for the user.
</chairman_guidance>

<quality_bar>
- Completeness: covers all material intent dimensions.
- Accuracy: aligned to verification report.
- Depth: meaningful insight, not surface summary.
- Coherence: one unified voice.
- Actionability: user can proceed immediately.
</quality_bar>

<output>
Return the final artifact in the editorial format that best matches the user's intent and context.
Do not include meta-commentary about the process.
</output>"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are the final synthesis editor responsible for producing the best possible answer. "
                "Integrate all verified inputs into one coherent, user-ready artifact that fulfills the user's intent."
            ),
        },
        {"role": "user", "content": chairman_prompt},
    ]
    chairman = chairman_model or CHAIRMAN_MODEL
    response = await query_model(chairman, messages)
    return {"model": chairman, "response": response.get('content', 'Error: Synthesis failed.') if response else "Error: Synthesis failed."}


async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation."""
    title_prompt = f"""<task>Generate a concise title (3-5 words) for this query.</task>
<query>{user_query}</query>
<rules>No quotes/punctuation. Be specific.</rules>
Title:"""
    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages, timeout=30.0)
    if response is None:
        return "New Conversation"
    title = response.get('content', 'New Conversation').strip().strip('"\'')
    return title[:47] + "..." if len(title) > 50 else title


async def run_full_council(
    user_query: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    num_experts: Optional[int] = None,
) -> Tuple[str, List, List, str, str, str, Dict, Dict]:
    """
    Run the complete sequential expert collaboration process.
    
    Returns:
        Tuple of (intent_analysis, experts, contributions, verification_data, synthesis_plan, editorial_guidelines, stage3_result, metadata)
    """
    # Stage 0: Draft + finalize intent (skip clarifications for full run)
    intent_draft = await stage0_generate_intent_draft(
        user_query,
        history,
        analysis_model=chairman_model,
    )
    intent_analysis = await stage0_finalize_intent(
        user_query,
        intent_draft,
        {"skip": True, "answers": [], "free_text": ""},
        history,
        analysis_model=chairman_model,
    )
    
    models = expert_models or COUNCIL_MODELS
    expert_count = num_experts or DEFAULT_NUM_EXPERTS

    # Stage 0.5: Brainstorm and form expert team
    brainstorm_content, experts = await stage_brainstorm_experts(
        user_query,
        intent_analysis,
        history,
        expert_models=models,
        chairman_model=chairman_model,
        num_experts=expert_count,
    )
    
    # Stage 1: Sequential expert contributions
    contributions = await stage1_sequential_contributions(
        user_query,
        experts,
        intent_analysis,
        history,
        expert_models=models,
        num_experts=expert_count,
    )
    
    if not contributions:
        return intent_analysis, experts, [], "", "", "", {
            "model": "error",
            "response": "Collaboration failed. Please try again."
        }, {}
    
    # Stage 2.5: Verification
    verification_data = await stage_verification(user_query, contributions, history)
    
    # Stage 2.75: Synthesis Planning
    synthesis_plan = await stage_synthesis_planning(
        user_query, 
        contributions, 
        intent_analysis, 
        verification_data,
        history
    )
    
    # Stage 2.9: Editorial Guidelines
    editorial_guidelines = await stage_editorial_guidelines(
        user_query,
        intent_analysis,
        contributions,
        synthesis_plan,
        history
    )
    
    # Stage 3: Final Synthesis
    stage3_result = await stage3_synthesize_final(
        user_query, 
        contributions, 
        intent_analysis=intent_analysis,
        verification_data=verification_data,
        synthesis_plan=synthesis_plan,
        editorial_guidelines=editorial_guidelines,
        history=history,
        chairman_model=chairman_model,
    )
    
    metadata = {
        "intent_analysis": intent_analysis,
        "verification_data": verification_data,
        "synthesis_plan": synthesis_plan,
        "editorial_guidelines": editorial_guidelines,
        "num_experts": len(contributions)
    }
    
    return intent_analysis, experts, contributions, verification_data, synthesis_plan, editorial_guidelines, stage3_result, metadata

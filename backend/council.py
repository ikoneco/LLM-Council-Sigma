"""LLM Council orchestration with sequential expert collaboration."""

from typing import List, Dict, Any, Tuple, Optional
import json
import re
import asyncio
from .openrouter import query_model, query_search_model, build_reasoning_payload
from .config import (
    COUNCIL_MODELS,
    CHAIRMAN_MODEL,
    DEFAULT_NUM_EXPERTS,
    INTENT_MODEL_FALLBACKS,
    SEARCH_QUERY_COUNT,
    SEARCH_QUERY_MAX,
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


def _coerce_expert_order(value: Any, max_order: int) -> Optional[int]:
    if value is None:
        return None
    try:
        order = int(value)
    except (TypeError, ValueError):
        return None
    if order < 1 or order > max_order:
        return None
    return order


def _normalize_expert_team(
    raw_experts: List[Dict[str, Any]],
    num_experts: int,
    default_experts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    used_orders = set()
    normalized: List[Dict[str, Any]] = []

    for idx, expert in enumerate(raw_experts[:num_experts]):
        role = expert.get("role") or expert.get("name") or expert.get("title") or f"Expert {idx + 1}"
        task = expert.get("task") or expert.get("description") or expert.get("details") or "Contribute expertise"
        objectives = expert.get("objectives", [])
        if isinstance(objectives, str):
            objectives_str = objectives
        else:
            objectives_str = " | ".join(objectives) if objectives else "Add value"

        order_value = _coerce_expert_order(expert.get("order"), num_experts)
        if order_value in used_orders:
            order_value = None
        if order_value is not None:
            used_orders.add(order_value)

        normalized.append({
            "name": role,
            "description": task,
            "objectives": objectives_str,
            "order": order_value,
        })

    remaining_orders = [order for order in range(1, num_experts + 1) if order not in used_orders]
    for item in normalized:
        if item.get("order") is None and remaining_orders:
            item["order"] = remaining_orders.pop(0)

    defaults_by_order = {expert.get("order"): expert for expert in default_experts if expert.get("order")}
    for order in remaining_orders:
        fallback = defaults_by_order.get(order)
        if fallback:
            normalized.append(fallback)
        else:
            normalized.append({
                "name": f"Expert {order}",
                "description": "Task: Provide complementary analysis. Objective: Strengthen coverage.",
                "objectives": "Add complementary depth",
                "order": order,
            })

    normalized = normalized[:num_experts]
    normalized.sort(key=lambda item: item.get("order") or 999)
    return normalized


def format_conversation_history(history: List[Dict[str, Any]]) -> str:
    """Format previous conversation history for context handling."""
    if not history:
        return ""

    user_entries = []
    chairman_outputs = []

    for msg in history:
        role = msg.get("role")
        if role == "user":
            content = msg.get("content", "")
            if content:
                user_entries.append(content)
        elif role == "assistant":
            response = ""
            if "stage3" in msg and msg["stage3"]:
                response = msg["stage3"].get("response", "")
            elif "content" in msg:
                response = msg["content"]
            if response:
                chairman_outputs.append(response)

    formatted = []
    if chairman_outputs:
        formatted.append(
            "### 🤖 Chairman (Most Recent Output - Baseline Context):\n"
            + chairman_outputs[-1]
        )
        if len(chairman_outputs) > 1:
            prior = "\n\n---\n\n".join(chairman_outputs[:-1])
            formatted.append(
                "### 📜 Earlier Chairman Outputs (for continuity):\n"
                + prior
            )

    if user_entries:
        formatted.append(
            "### 👤 Prior User Requests:\n" + "\n\n".join(user_entries)
        )

    return "\n\n".join(formatted)

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                payload = text[start:idx + 1]
                for candidate in (payload, re.sub(r",\s*\}", "}", payload), re.sub(r",\s*\]", "]", payload)):
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                return None
    return None


def _extract_json_array(text: str) -> Optional[List[Any]]:
    if not text:
        return None
    match = re.search(r"\[[\s\S]*?\]", text)
    if not match:
        return None
    payload = match.group()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*\]", "]", payload)
        cleaned = re.sub(r",\s*\}", "}", cleaned)
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


def _trim_verification_report(text: str) -> str:
    if not text:
        return text
    heading_pattern = re.compile(r"^##\s+", re.MULTILINE)
    search_match = re.search(r"^##\s+Search Status", text, re.IGNORECASE | re.MULTILINE)
    audit_match = re.search(r"^##\s+Verification\s*(?:&|and)\s*Reasoning\s+Audit", text, re.IGNORECASE | re.MULTILINE)

    if not audit_match:
        return text.strip()

    def slice_section(start_index: int) -> str:
        next_heading = None
        for match in heading_pattern.finditer(text):
            if match.start() > start_index:
                next_heading = match.start()
                break
        if next_heading is None:
            return text[start_index:].strip()
        return text[start_index:next_heading].strip()

    parts = []
    if search_match and search_match.start() < audit_match.start():
        search_section = slice_section(search_match.start())
        if search_section:
            parts.append(search_section)

    audit_section = slice_section(audit_match.start())
    if audit_section:
        parts.append(audit_section)

    return "\n\n".join(parts) if parts else text.strip()


def _compute_search_query_count(scope_payload: Optional[Dict[str, Any]]) -> int:
    base_count = SEARCH_QUERY_COUNT
    if not isinstance(scope_payload, dict):
        return base_count

    items = set()
    for key in [
        "claims_to_verify",
        "areas_of_concern",
        "assumptions_to_check",
        "entities_and_sources",
        "critical_metrics",
    ]:
        values = scope_payload.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized:
                items.add(normalized.lower())

    scope_size = len(items)
    if scope_size == 0:
        return base_count

    proposed = (scope_size + 5) // 6
    if proposed < base_count:
        proposed = base_count
    if proposed > SEARCH_QUERY_MAX:
        return SEARCH_QUERY_MAX
    return proposed


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


def _build_fallback_questions(
    user_query: str = "",
    draft_intent: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    lowered = user_query.lower()
    audience = ""
    deliverable = {}
    explicit_constraints = []
    goal_outcome = ""
    task_type = ""
    if isinstance(draft_intent, dict):
        audience = str(draft_intent.get("audience") or "").strip()
        deliverable = draft_intent.get("deliverable") or {}
        explicit_constraints = draft_intent.get("explicit_constraints") or []
        goal_outcome = str(draft_intent.get("goal_outcome") or draft_intent.get("primary_intent") or "").strip()
        task_type = str(draft_intent.get("task_type") or "").strip()

    has_series = "series" in lowered or "episode" in lowered
    has_audience = bool(audience) or "audience" in lowered
    has_format = any(term in lowered for term in ["outline", "synopsis", "summary", "table", "list", "plan", "draft"])
    has_depth = any(term in lowered for term in ["detailed", "deep", "comprehensive", "brief", "quick"])
    has_sources = any(term in lowered for term in ["source", "cite", "citation", "references"])
    has_examples = any(term in lowered for term in ["example", "case study", "real-world", "grounded"])
    has_substack = "substack" in lowered or "substak" in lowered
    has_leadership = any(term in lowered for term in ["leader", "leadership", "executive", "director", "vp"])
    wants_non_obvious = "not obvious" in lowered or "non-obvious" in lowered
    topic_hint = _extract_first_match(
        [r"(?:about|on|regarding)\s+([^.\n;]+)"],
        user_query,
    )

    def short_phrase(text: str, max_words: int = 8) -> str:
        words = re.findall(r"[A-Za-z0-9]+", text or "")
        return " ".join(words[:max_words]).strip()

    if not topic_hint:
        topic_hint = short_phrase(goal_outcome) or short_phrase(user_query)

    audience_hint = audience or "the intended audience"
    deliverable_format = str(deliverable.get("format") or "").strip()
    deliverable_hint = deliverable_format or "output"
    topic_label = topic_hint or "the topic"

    questions: List[Dict[str, Any]] = []

    def add_question(question_id: str, question: str, options: List[str]) -> None:
        if any(q["question"] == question for q in questions):
            return
        if "Other / I'll type it" not in options:
            options.append("Other / I'll type it")
        questions.append({
            "id": question_id,
            "question": question,
            "options": options,
        })

    if has_series:
        add_question(
            "q1",
            f"How should the series on {topic_label} be structured for {audience_hint}?",
            [
                "A cohesive narrative arc across all parts",
                "Standalone essays with a shared theme",
                "Hybrid: arc + standalone value",
            ],
        )

    add_question(
        "q2",
        f"What should this {deliverable_hint} enable {audience_hint} to do about {topic_label}?",
        [
            "Make strategic decisions",
            "Adopt specific practices or frameworks",
            "Align stakeholders around a direction",
            "Train or upskill a team",
        ],
    )

    if not has_depth:
        add_question(
            "q3",
            f"What depth is most useful for each {deliverable_hint} item?",
            [
                "Concise but substantive (2-4 paragraphs)",
                "Detailed (5-8 paragraphs)",
                "Deep-dive (full-length essay outline)",
            ],
        )

    if not has_audience:
        add_question(
            "q4",
            "Who is the primary audience for this deliverable?",
            [
                "Senior product/design leaders",
                "Product design practitioners",
                "Cross-functional leadership teams",
                "Founders/executives",
            ],
        )

    if not has_format:
        add_question(
            "q5",
            f"What structure should each {deliverable_hint} item follow?",
            [
                "Title + thesis + detailed synopsis",
                "Problem → insight → implications",
                "Framework + examples + actions",
            ],
        )

    if not has_sources:
        add_question(
            "q6",
            f"How should the guidance be grounded for {audience_hint}?",
            [
                "Yes, include concrete examples and cases",
                "Cite sources or evidence where claims are made",
                "Prefer conceptual frameworks without examples",
                "Mix: one example per item where relevant",
            ],
        )

    if has_substack:
        add_question(
            "q7",
            f"What voice should the {deliverable_hint} use?",
            [
                "Thought-leadership essays (Substack-style)",
                "Strategic internal memo tone",
                "Teaching-style playbook with clear takeaways",
            ],
        )

    if has_leadership:
        add_question(
            "q8",
            "Which decision context matters most?",
            [
                "Strategic direction and prioritization",
                "Org design and team capability",
                "Product execution and delivery",
                "Market positioning and differentiation",
            ],
        )

    if wants_non_obvious or (explicit_constraints and any("avoid" in str(item).lower() for item in explicit_constraints)):
        add_question(
            "q9",
            f"What should be explicitly avoided in this {deliverable_hint}?",
            [
                "Generic AI hype or trend summaries",
                "Overly technical or engineering-heavy detail",
                "Speculative futurecasting without business grounding",
            ],
        )

    return questions[:6]


def _human_join(items: List[str]) -> str:
    items = [str(item).strip() for item in items if str(item).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _token_set(text: str) -> set:
    normalized = _normalize_text(text)
    if not normalized:
        return set()
    return {token for token in normalized.split() if len(token) > 2}


def _overlap_ratio(text: str, reference: str) -> float:
    tokens_a = _token_set(text)
    tokens_b = _token_set(reference)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _is_near_duplicate(text: str, reference: str) -> bool:
    if not text or not reference:
        return False
    normalized_text = _normalize_text(text)
    normalized_ref = _normalize_text(reference)
    if not normalized_text or not normalized_ref:
        return False
    if normalized_text in normalized_ref or normalized_ref in normalized_text:
        return True
    return _overlap_ratio(text, reference) >= 0.78


def _is_verbatim_like(text: str, reference: str) -> bool:
    if not text or not reference:
        return False
    normalized_text = _normalize_text(text)
    normalized_ref = _normalize_text(reference)
    if not normalized_text or not normalized_ref:
        return False
    len_ratio = len(normalized_text) / max(len(normalized_ref), 1)
    if normalized_text in normalized_ref or normalized_ref in normalized_text:
        return 0.7 <= len_ratio <= 1.3
    return _overlap_ratio(text, reference) >= 0.9 and 0.8 <= len_ratio <= 1.4


def _format_deliverable_phrase(deliverable: Dict[str, Any]) -> str:
    if not isinstance(deliverable, dict):
        return "a response"
    depth = str(deliverable.get("depth") or "").strip()
    fmt = str(deliverable.get("format") or "").strip()
    if depth and fmt:
        return f"a {depth} {fmt}"
    if fmt:
        return f"a {fmt}"
    if depth:
        return f"a {depth} response"
    return "a response"


def _strip_code_fence(text: str) -> str:
    if not text:
        return ""
    fence_match = re.match(r"^```[a-zA-Z0-9_-]*\n(.+?)\n```$", text.strip(), re.S)
    if fence_match:
        return fence_match.group(1).strip()
    return text.strip()


def _safe_content(response: Optional[Dict[str, Any]]) -> Optional[str]:
    if not response or not isinstance(response, dict):
        return None
    content = response.get("content")
    if not content or not isinstance(content, str):
        return None
    return content


def _intent_model_candidates(primary_model: Optional[str]) -> List[str]:
    seen = set()
    ordered = []
    seed_models = []
    if primary_model in INTENT_MODEL_FALLBACKS:
        seed_models.append(primary_model)
    seed_models.extend(INTENT_MODEL_FALLBACKS)
    for model in seed_models:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


async def _repair_intent_json(
    raw_text: str,
    schema_json: str,
    candidate_models: List[str],
    thinking_by_model: Optional[Dict[str, bool]] = None,
) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    repair_system = (
        "You are a JSON repair tool. "
        "Return ONLY valid JSON that matches the provided schema. "
        "Do not add commentary or markdown."
    )
    repair_prompt = (
        "The following text should contain a JSON object but is malformed or non-compliant.\n"
        "Fix it and return valid JSON only.\n\n"
        "Schema:\n"
        f"{schema_json}\n\n"
        "Raw text:\n"
        f"{raw_text}"
    )
    messages = [
        {"role": "system", "content": repair_system},
        {"role": "user", "content": repair_prompt},
    ]
    for model in candidate_models:
        response = await query_model(
            model,
            messages,
            timeout=30.0,
            extra_body={"max_tokens": 1200, "temperature": 0},
        )
        parsed = _extract_json(_safe_content(response) or "")
        if parsed:
            return parsed
    return None


def _extract_first_match(patterns: List[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .;:\n")
    return ""


def _infer_series_count(text: str) -> str:
    for match in re.finditer(r"\b(\d{1,2})\b", text):
        value = int(match.group(1))
        if 1 <= value <= 50:
            return str(value)
    return ""


def _infer_deliverable(user_query: str) -> str:
    lowered = user_query.lower()
    if "synopsis" in lowered or "synopsys" in lowered:
        return "a detailed synopsis"
    if "summary" in lowered:
        return "a clear summary"
    if "outline" in lowered:
        return "a structured outline"
    if "plan" in lowered:
        return "a structured plan"
    if "table" in lowered:
        return "a comparative table"
    if "draft" in lowered:
        return "a draft document"
    if "list" in lowered:
        return "a curated list"
    return "a structured response"


def _infer_quality_signals(user_query: str) -> List[str]:
    lowered = user_query.lower()
    mapping = [
        ("detailed", "detailed and substantive"),
        ("deep", "deep and thorough"),
        ("non-obvious", "non-obvious and differentiated"),
        ("not obvious", "non-obvious and differentiated"),
        ("professional", "professional and polished"),
        ("accessible", "accessible and clear"),
        ("grounded", "grounded in real-world context"),
        ("inspiring", "inspiring but credible"),
        ("useful", "useful and actionable"),
        ("informative", "informative and specific"),
    ]
    signals = []
    for key, value in mapping:
        if key in lowered and value not in signals:
            signals.append(value)
    return signals


def _ambiguity_heading_for(item: str) -> str:
    lowered = item.lower()
    if any(term in lowered for term in ["scope", "breadth", "boundary", "range"]):
        return "#### Scope & Boundaries"
    if any(term in lowered for term in ["depth", "detail", "level", "granularity"]):
        return "#### Depth & Detail"
    if any(term in lowered for term in ["audience", "reader", "stakeholder"]):
        return "#### Audience Fit"
    if any(term in lowered for term in ["format", "structure", "outline", "series", "chapter"]):
        return "#### Structure & Format"
    if any(term in lowered for term in ["example", "evidence", "source", "citation", "grounding"]):
        return "#### Evidence & Examples"
    if any(term in lowered for term in ["tone", "voice", "style"]):
        return "#### Voice & Tone"
    return "#### Clarification"


def _format_ambiguities_section(items: List[str]) -> str:
    items = [item.strip().rstrip(".") for item in items if item and str(item).strip()]
    if not items:
        return ""
    lines = []
    used_headings = set()
    for item in items[:3]:
        heading = _ambiguity_heading_for(item)
        if heading in used_headings:
            heading = "#### Additional Clarification"
        used_headings.add(heading)
        sentence = (
            f"Clarify {item} so the output can be tuned for the right level of specificity and usefulness."
        )
        lines.extend([heading, sentence, ""])
    return "\n".join(lines).strip()


def _build_display_from_query(user_query: str) -> Dict[str, Any]:
    lowered = user_query.lower()
    audience = _extract_first_match(
        [
            r"audience(?:\s+will\s+be|\s+is|:)\s*([^.\n;]+)",
            r"for\s+([^.\n;]+)",
        ],
        user_query,
    )
    topic = _extract_first_match(
        [r"(?:about|on|regarding)\s+([^.\n;]+)"],
        user_query,
    )
    count = _infer_series_count(user_query)
    deliverable = _infer_deliverable(user_query)
    quality_signals = _infer_quality_signals(user_query)
    quality_text = ", ".join(quality_signals) if quality_signals else "clear, high-value, and decision-ready"
    platform = "Substack" if "substack" in lowered or "substak" in lowered else ""
    year_marker = "2026" if "2026" in lowered else ""
    voice_hint = "from a product design leader's perspective" if "product design leader" in lowered else ""
    avoid_generic = "avoid generic or obvious points" if "not obvious" in lowered or "non-obvious" in lowered else ""

    deliverable_phrase = deliverable
    if count and "series" in lowered:
        deliverable_phrase = f"a {count}-part series outline"
    topic_phrase = topic or "the stated topic"
    audience_phrase = audience or "the intended audience"
    platform_phrase = "designed for Substack publication" if platform else ""
    time_phrase = "grounded in 2026 business reality" if year_marker else ""
    context_bits = [item for item in [platform_phrase, time_phrase] if item]
    context_phrase = f"{', '.join(context_bits)}" if context_bits else ""
    voice_phrase = f"written {voice_hint}" if voice_hint else ""
    context_clauses = ", ".join([item for item in [context_phrase, voice_phrase] if item])
    context_clause = f", {context_clauses}" if context_clauses else ""

    reconstructed = (
        f"Create {deliverable_phrase} on {topic_phrase} tailored for {audience_phrase}. "
        f"It should be {quality_text}{context_clause}, reflecting the user's stated priorities."
    )

    paragraph_one = (
        f"You want {deliverable_phrase} that frames {topic_phrase} in a way that speaks directly to {audience_phrase}. "
        f"Each item should feel like a distinct chapter in a coherent series, not a loose list of ideas{context_phrase}. "
        "The underlying aim is to surface what is changing, why it matters now, and how design leaders should respond."
    )
    paragraph_two = (
        f"Success depends on being {quality_text}. The output should read like it comes from an experienced leader, "
        f"offering practical insight with a clear point of view{', ' + voice_phrase if voice_phrase else ''}. "
        "It should balance inspiration with grounded execution guidance, so the reader can apply it immediately. "
        f"{'It should ' + avoid_generic + '.' if avoid_generic else ''}"
    ).strip()
    paragraph_three = (
        "This request implies a senior audience that values rigor, clarity, and strategic relevance. "
        "The content should connect product design decisions to real business constraints and emerging realities, "
        "while avoiding superficial trends or speculative hype. "
        "The most important calibration is the balance between strategic narrative and concrete, usable detail."
    )
    deep_read = "\n\n".join([paragraph_one, paragraph_two, paragraph_three])

    unclear_items = [
        "Preferred depth per item versus breadth across topics",
        "Whether the output should read as publish-ready copy or a strategic outline",
    ]
    decision_focus = _format_ambiguities_section(unclear_items)

    return {
        "reconstructed_ask": reconstructed,
        "deep_read": deep_read,
        "decision_focus": decision_focus,
        "understanding": [
            f"Primary objective: deliver {deliverable_phrase} on {topic_phrase}.",
            f"Audience focus: {audience_phrase}.",
            f"Quality bar: {quality_text}.",
        ],
        "assumptions": [
            "The user expects an output that can be used without major rewriting (why it matters: it drives structure and completeness).",
            "The output should prioritize differentiated insights over generic coverage (why it matters: it changes depth and angle).",
        ],
        "unclear": unclear_items,
    }


def _display_payload_to_markdown(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    ask = str(payload.get("reconstructed_ask") or "").strip()
    deep_read = str(payload.get("deep_read") or "").strip()
    decision_focus = str(payload.get("decision_focus") or "").strip()
    if not any([ask, deep_read, decision_focus]):
        return ""
    sections = []
    if ask:
        sections.extend(["### Your Request, Refined", ask, ""])
    if deep_read:
        sections.extend(["### Deep Intent Read", deep_read, ""])
    if decision_focus:
        sections.extend(["### Ambiguities and Areas to Clarify", decision_focus])
    return "\n".join(section for section in sections if section is not None).strip()


def _normalize_intent_draft(raw: Optional[Dict[str, Any]], user_query: str) -> Dict[str, Any]:

    if not raw:
        fallback_questions = _build_fallback_questions(user_query)
        fallback_display = _build_display_from_query(user_query)
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
            "display": fallback_display,
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
        cleaned_options = []
        seen_options = set()
        for option in options:
            option_text = str(option).strip()
            if not option_text:
                continue
            normalized_key = option_text.lower()
            if normalized_key in seen_options:
                continue
            cleaned_options.append(option_text)
            seen_options.add(normalized_key)
        if "other / i'll type it" not in seen_options:
            cleaned_options.append("Other / I'll type it")
        normalized_questions.append({
            "id": q_id,
            "question": question_text.strip() or f"Clarification {idx}",
            "options": cleaned_options[:6],
        })

    fallback_questions = _build_fallback_questions(user_query, draft if isinstance(draft, dict) else None)

    def is_generic_question(text: str) -> bool:
        lowered_text = text.lower()
        patterns = [
            "any hard constraints",
            "what format should i produce",
            "who is the intended audience",
            "how deep or rigorous",
            "what should the result enable you to do",
            "tell me more",
            "anything else",
        ]
        return any(pattern in lowered_text for pattern in patterns)

    query_tokens = _token_set(user_query)
    context_bits = []
    if isinstance(draft, dict):
        if draft.get("audience"):
            context_bits.append(str(draft.get("audience")))
        deliverable_context = draft.get("deliverable") or {}
        if isinstance(deliverable_context, dict):
            for key in ("format", "structure"):
                if deliverable_context.get(key):
                    context_bits.append(str(deliverable_context.get(key)))
        goal_hint = draft.get("goal_outcome") or draft.get("primary_intent") or ""
        if goal_hint:
            context_bits.append(str(goal_hint))
    topic_hint = _extract_first_match([r"(?:about|on|regarding)\s+([^.\n;]+)"], user_query)
    if topic_hint:
        context_bits.append(topic_hint)
    context_tokens = _token_set(" ".join(context_bits))

    def question_score(text: str) -> int:
        lowered_text = text.lower()
        score = 0
        if len(text.split()) >= 8:
            score += 2
        if query_tokens and len(set(lowered_text.split()) & query_tokens) >= 2:
            score += 2
        if context_tokens and len(set(lowered_text.split()) & context_tokens) >= 2:
            score += 2
        if any(term in lowered_text for term in ["series", "audience", "structure", "depth", "examples", "voice", "scope"]):
            score += 1
        if any(term in lowered_text for term in ["avoid", "exclude", "not", "must"]):
            score += 1
        if is_generic_question(text):
            score -= 3
        return score

    ranked = sorted(
        normalized_questions,
        key=lambda q: question_score(q.get("question", "")),
        reverse=True,
    )
    filtered = [q for q in ranked if question_score(q.get("question", "")) >= 2]
    if len(filtered) < 2:
        filtered = ranked[:2]

    normalized_questions = filtered
    existing_questions = {q["question"].lower() for q in normalized_questions}
    if len(normalized_questions) < 3:
        for fallback in fallback_questions:
            if len(normalized_questions) >= 3:
                break
            if fallback["question"].lower() in existing_questions:
                continue
            normalized_questions.append(fallback)
            existing_questions.add(fallback["question"].lower())

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
    understanding = [str(item).strip() for item in understanding if str(item).strip()]

    assumptions_display = display.get("assumptions") or []
    if not isinstance(assumptions_display, list):
        assumptions_display = []
    assumptions_display = [str(item).strip() for item in assumptions_display if str(item).strip()]

    unclear_display = display.get("unclear") or []
    if not isinstance(unclear_display, list):
        unclear_display = []
    unclear_display = [str(item).strip() for item in unclear_display if str(item).strip()]

    reconstructed_ask = display.get("reconstructed_ask") or ""
    if not isinstance(reconstructed_ask, str):
        reconstructed_ask = ""

    deep_read = display.get("deep_read") or ""
    if not isinstance(deep_read, str):
        deep_read = ""

    decision_focus = display.get("decision_focus") or ""
    if not isinstance(decision_focus, str):
        decision_focus = ""

    display_markdown = display.get("markdown") or display.get("display_markdown") or ""
    if not isinstance(display_markdown, str):
        display_markdown = ""

    display_payload = {
        "reconstructed_ask": reconstructed_ask.strip(),
        "understanding": understanding,
        "assumptions": assumptions_display,
        "unclear": unclear_display,
        "deep_read": deep_read.strip(),
        "decision_focus": decision_focus.strip(),
        "markdown": display_markdown.strip(),
    }

    def _filter_duplicates(items: List[str]) -> List[str]:
        return [item for item in items if not _is_verbatim_like(item, user_query)]

    display_payload["understanding"] = _filter_duplicates(display_payload["understanding"])
    display_payload["assumptions"] = _filter_duplicates(display_payload["assumptions"])
    display_payload["unclear"] = _filter_duplicates(display_payload["unclear"])
    if _is_verbatim_like(display_payload["deep_read"], user_query):
        display_payload["deep_read"] = ""
    if _is_verbatim_like(display_payload["decision_focus"], user_query):
        display_payload["decision_focus"] = ""
    if _is_verbatim_like(display_payload["reconstructed_ask"], user_query):
        display_payload["reconstructed_ask"] = ""

    if not display_payload["reconstructed_ask"]:
        audience_hint = f" for {draft_intent['audience']}" if draft_intent.get("audience") else ""
        deliverable_phrase = _format_deliverable_phrase(deliverable)
        success_hint = _human_join(success_criteria)
        constraints_hint = _human_join(explicit_constraints)
        goal_text = draft_intent.get("goal_outcome") or draft_intent["primary_intent"]
        if _is_verbatim_like(goal_text, user_query) or not goal_text:
            goal_text = "meets the user's objective"
        reconstructed = f"Create {deliverable_phrase} that {goal_text}"
        if audience_hint:
            reconstructed += audience_hint
        if success_hint:
            reconstructed += f", optimized for {success_hint}"
        if constraints_hint:
            reconstructed += f", while honoring {constraints_hint}"
        display_payload["reconstructed_ask"] = f"{reconstructed}."

    if not display_payload["understanding"]:
        core_ask = draft_intent.get("primary_intent") or ""
        if _is_verbatim_like(core_ask, user_query) or not core_ask:
            core_ask = "Deliver a response that achieves the user's stated objective."
        understanding_items = [f"Core ask: {core_ask}"]
        if draft_intent.get("audience"):
            understanding_items.append(f"Audience focus: {draft_intent['audience']}.")
        if deliverable.get("format") or deliverable.get("depth"):
            understanding_items.append(f"Deliverable: {_format_deliverable_phrase(deliverable)}.")
        if success_criteria:
            understanding_items.append(f"Success criteria: {_human_join(success_criteria)}.")
        if explicit_constraints:
            understanding_items.append(f"Constraints to honor: {_human_join(explicit_constraints)}.")
        if len(understanding_items) < 3:
            understanding_items.append("The output should feel decision-ready and non-obvious, not generic.")
        display_payload["understanding"] = understanding_items

    if not display_payload["deep_read"]:
        fallback_display = fallback_display if "fallback_display" in locals() else _build_display_from_query(user_query)
        display_payload["deep_read"] = fallback_display["deep_read"]

    def _build_decision_focus(unclear_items: List[str]) -> str:
        return _format_ambiguities_section(unclear_items)

    decision_focus_candidate = _build_decision_focus(display_payload.get("unclear", []))

    if not display_payload["decision_focus"]:
        if decision_focus_candidate:
            display_payload["decision_focus"] = decision_focus_candidate
        else:
            fallback_display = fallback_display if "fallback_display" in locals() else _build_display_from_query(user_query)
            display_payload["decision_focus"] = fallback_display["decision_focus"]

    if _is_verbatim_like(display_payload["reconstructed_ask"], user_query):
        display_payload["reconstructed_ask"] = ""
    if not display_payload["reconstructed_ask"]:
        fallback_display = _build_display_from_query(user_query)
        display_payload["reconstructed_ask"] = fallback_display["reconstructed_ask"]

    if display_payload["understanding"] and all(
        _is_verbatim_like(item, user_query) for item in display_payload["understanding"]
    ):
        display_payload["understanding"] = []
    if not display_payload["understanding"]:
        fallback_display = fallback_display if "fallback_display" in locals() else _build_display_from_query(user_query)
        display_payload["understanding"] = fallback_display.get("understanding", [])

    if display_payload["assumptions"] and all(
        _is_verbatim_like(item, user_query) for item in display_payload["assumptions"]
    ):
        display_payload["assumptions"] = []
    if not display_payload["assumptions"]:
        fallback_display = fallback_display if "fallback_display" in locals() else _build_display_from_query(user_query)
        display_payload["assumptions"] = fallback_display["assumptions"]

    if display_payload["unclear"] and all(
        _is_verbatim_like(item, user_query) for item in display_payload["unclear"]
    ):
        display_payload["unclear"] = []
    if not display_payload["unclear"]:
        fallback_display = fallback_display if "fallback_display" in locals() else _build_display_from_query(user_query)
        display_payload["unclear"] = fallback_display["unclear"]

    if not display_payload["assumptions"]:
        display_payload["assumptions"] = [
            "The user wants a non-obvious, high-value result (why it matters: it changes rigor and originality).",
            "The output should be ready to use without heavy editing (why it matters: it changes structure and completeness).",
        ]

    if not display_payload["unclear"]:
        display_payload["unclear"] = [
            "Preferred balance between breadth and depth for each item.",
            "Whether the output should read as publish-ready copy or strategic briefing notes.",
        ]

    if not display_payload.get("markdown"):
        display_payload["markdown"] = _display_payload_to_markdown(display_payload)

    return {
        "draft_intent": draft_intent,
        "display": display_payload,
        "questions": normalized_questions,
    }


def build_intent_draft_fallback(user_query: str) -> Dict[str, Any]:
    return _normalize_intent_draft(None, user_query)


async def stage0_generate_intent_draft(
    user_query: str,
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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

    json_system_prompt = (
        "You are an Intent Analyst + Clarification Designer. "
        "Infer deeper intent, constraints, audience, and success criteria. "
        "Make bold but defensible inferences and surface what the user is trying to avoid. "
        "Never echo the user query verbatim; always rephrase with clearer, richer language. "
        "Clarification questions must be context-specific, tied to actual ambiguities in THIS request. "
        "Avoid generic questions that could fit any task. "
        "Return JSON only."
    )

    output_schema = {
        "draft_intent": {
            "primary_intent": "1 sentence",
            "goal_outcome": "What success enables or produces",
            "task_type": "explanation|recommendation|plan|critique|rewrite|research|extraction|troubleshooting",
            "deliverable": {
                "format": "bullets|table|steps|outline|doc|etc",
                "depth": "quick|standard|deep",
                "tone": "string or null",
                "structure": "key sections or outline (optional)",
                "required_elements": ["optional bullets"],
            },
            "audience": "string or null",
            "constraints": {
                "must": ["..."],
                "should": ["..."],
                "must_not": ["..."],
            },
            "quality_bar": {
                "rigor": "quick|standard|deep",
                "evidence": "none|light|strict",
                "completeness": "core|standard|comprehensive",
                "risk_tolerance": "low|medium|high",
            },
            "success_criteria": ["..."],
            "explicit_constraints": ["..."],
            "latent_intent_hypotheses": ["..."],
            "ambiguities": ["..."],
            "assumptions": [
                {"assumption": "...", "risk": "high|medium|low", "why_it_matters": "..."}
            ],
            "confidence": "high|medium|low",
        },
        "questions": [
            {
                "id": "q1",
                "question": "text",
                "options": ["2-5 options", "Other / I'll type it"],
            }
        ],
    }
    output_schema_json = json.dumps(output_schema, indent=2)

    intent_prompt = f"""<task>
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
{output_schema_json}
</output_format>

Rules:
- Choose how many questions to ask within 3-6 based on ambiguity (clearer requests = fewer questions).
- Each question addresses ONE dimension only.
- Target the highest-impact uncertainties (goal/outcome, scope boundaries, audience, format, constraints, quality bar).
- If the user already specified audience, format, depth, or constraints, do NOT ask about them unless there is a conflict or tradeoff.
- Each question must reference the user's topic, audience, or deliverable so it feels tailored to this request.
- Order ambiguities, assumptions, and questions by impact (highest first).
- Options must be distinct and actionable. Multi-select is allowed when it helps (do not force exclusivity).
- Avoid vague prompts; every option should imply a different execution path.
- Always include "Other / I'll type it".

Generate the JSON now:"""

    display_system_prompt = (
        "You are a Deep Intent Synthesizer. "
        "Reconstruct the user's request into a clearer, richer version that surfaces implicit goals, constraints, and what they want to avoid. "
        "Use the user's voice and intent, but do not copy their wording verbatim."
    )

    display_prompt = f"""Rewrite the request into markdown with this structure:
### Your Request, Refined
(1 paragraph)

Then choose 2-4 additional section headings that best organize the analysis for THIS request.
Use H3 headings (###) and make them context-specific (e.g., “Audience & Decision Context”, “Scope & Boundaries”, “Evidence & Examples”, “Constraints & Quality Bar”).
One of the headings MUST be:
### Ambiguities and Areas to Clarify
In that section, include 2-3 H4 subheadings (####) that group the uncertainties, and write one sentence under each (no bullets). Each sentence should state a specific low-confidence inference or gap the user can clarify.

Rules:
- No bullet lists anywhere.
- Each heading is one paragraph only.
- Choose the number of analysis headings based on complexity (2-4 total after the first section).
- Make bold but defensible inferences; surface implicit goals, quality bar, and constraints.
- Do not echo full sentences from the user query.
- Do not provide solutions.

User input:
{user_query}
{context_section}
"""

    json_messages = [
        {"role": "system", "content": json_system_prompt},
        {"role": "user", "content": intent_prompt},
    ]
    display_messages = [
        {"role": "system", "content": display_system_prompt},
        {"role": "user", "content": display_prompt},
    ]
    model_name = analysis_model or CHAIRMAN_MODEL

    candidate_models = _intent_model_candidates(model_name)
    intent_response = None
    display_response = None
    intent_model_used = None
    display_model_used = None
    attempt_log: List[Dict[str, Any]] = []
    intent_errors: List[str] = []
    display_errors: List[str] = []

    for candidate in candidate_models:
        if not intent_response or not intent_response.get("content"):
            json_extra = {"max_tokens": 1200, "temperature": 0}
            json_extra.update(build_reasoning_payload(candidate, thinking_by_model))
            intent_response = await query_model(
                candidate,
                json_messages,
                timeout=30.0,
                extra_body=json_extra,
            )
            intent_ok = bool(intent_response and intent_response.get("content"))
            intent_error = (
                str(intent_response.get("error"))
                if isinstance(intent_response, dict) and intent_response.get("error")
                else None
            )
            attempt_log.append({
                "model": candidate,
                "intent_ok": intent_ok,
                "intent_error": intent_error,
            })
            if intent_error:
                intent_errors.append(f"{candidate}: {intent_error}")
            if intent_response and intent_response.get("content"):
                intent_model_used = candidate

        if not display_response or not display_response.get("content"):
            display_extra = {"max_tokens": 700, "temperature": 0.3}
            display_extra.update(build_reasoning_payload(candidate, thinking_by_model))
            display_response = await query_model(
                candidate,
                display_messages,
                timeout=30.0,
                extra_body=display_extra,
            )
            display_ok = bool(display_response and display_response.get("content"))
            display_error = (
                str(display_response.get("error"))
                if isinstance(display_response, dict) and display_response.get("error")
                else None
            )
            attempt_log[-1]["display_ok"] = display_ok
            attempt_log[-1]["display_error"] = display_error
            if display_error:
                display_errors.append(f"{candidate}: {display_error}")
            if display_response and display_response.get("content"):
                display_model_used = candidate

        if intent_response and intent_response.get("content") and display_response and display_response.get("content"):
            break

    intent_content = _safe_content(intent_response)
    parsed = _extract_json(intent_content or "")
    if not parsed and intent_content:
        parsed = await _repair_intent_json(intent_content, output_schema_json, candidate_models, thinking_by_model)
    if not parsed:
        error_detail = "; ".join(intent_errors) if intent_errors else "no model returned JSON content"
        raise RuntimeError(f"Intent draft JSON generation failed: {error_detail}")

    display_content = _safe_content(display_response)
    if not display_content:
        error_detail = "; ".join(display_errors) if display_errors else "no model returned display content"
        raise RuntimeError(f"Intent display generation failed: {error_detail}")

    display_markdown = _strip_code_fence(display_content)

    raw = parsed if isinstance(parsed, dict) else {}
    display_block = raw.get("display") if isinstance(raw, dict) else {}
    if not isinstance(display_block, dict):
        display_block = {}
    display_block["markdown"] = display_markdown
    if isinstance(raw, dict):
        raw["display"] = display_block

    normalized = _normalize_intent_draft(raw if isinstance(raw, dict) else None, user_query)
    normalized["debug"] = {
        "requested_model": model_name,
        "intent_model_used": intent_model_used,
        "display_model_used": display_model_used,
        "attempts": attempt_log,
    }
    return normalized


async def stage0_finalize_intent(
    user_query: str,
    intent_draft: Dict[str, Any],
    clarification_payload: Dict[str, Any],
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
    reasoning_payload = build_reasoning_payload(model_name, thinking_by_model)
    response = await query_model(
        model_name,
        messages,
        extra_body=reasoning_payload,
    )

    content = _safe_content(response)
    if not content or not content.strip():
        # Retry without reasoning config if the model returned empty content.
        response = await query_model(
            model_name,
            messages,
            extra_body={"max_tokens": 1400},
        )
        content = _safe_content(response)

    if not content or not content.strip():
        # Try fallback intent models to ensure we return a usable intent brief.
        for candidate in _intent_model_candidates(model_name):
            if candidate == model_name:
                continue
            response = await query_model(
                candidate,
                messages,
                extra_body={"max_tokens": 1400, "temperature": 0},
            )
            content = _safe_content(response)
            if content and content.strip():
                break

    if not content or not content.strip():
        return "Intent analysis unavailable."

    return content


async def stage_brainstorm_experts(
    user_query: str,
    intent_analysis: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    num_experts: int = DEFAULT_NUM_EXPERTS,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
        query_model(
            model,
            [{"role": "user", "content": brainstorm_prompt}],
            extra_body=build_reasoning_payload(model, thinking_by_model),
        )
        for model in models
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Format brainstorm content for display
    brainstorm_sections = []
    all_suggestions_for_synthesis = []
    
    for i, resp in enumerate(responses):
        model_name = models[i].split('/')[-1]  # Get short model name
        if isinstance(resp, Exception) or not _safe_content(resp):
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
4. Order for synergy and progressive quality: early experts establish framing and assumptions, middle experts deepen and stress-test, final experts integrate, validate, and polish
5. The order MUST be a strict 1..{num_experts} sequence with no duplicates or gaps
6. Draw from the BEST suggestions across all models
7. Provide a brief sequence rationale explaining why this order maximizes synergy and avoids early lock-in
</team_formation_requirements>

<output_format>
Respond with a valid JSON object ONLY:
{{
    "team_rationale": "2-3 sentences explaining why this specific team was chosen for this query",
    "sequence_rationale": "2-3 sentences explaining why the order maximizes synergy and progressive quality",
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
    response = await query_model(
        chairman,
        messages,
        extra_body=build_reasoning_payload(chairman, thinking_by_model),
    )
    
    default_experts = build_default_experts(num_experts)
    
    if not _safe_content(response):
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
            sequence_rationale = data.get("sequence_rationale", "")

            normalized = _normalize_expert_team(experts, num_experts, default_experts)
            
            # Append team rationale to brainstorm display
            if rationale or sequence_rationale:
                brainstorm_display += "\n\n---\n\n## 👔 Chairman's Team Selection\n\n"
                if rationale:
                    brainstorm_display += f"{rationale}\n\n"
                if sequence_rationale:
                    brainstorm_display += f"### Ordering Rationale\n\n{sequence_rationale}"
            
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
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
6. **Prevent Anchoring**: Challenge at least one earlier recommendation or framing to keep the thinking evolving.
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
5. **Leave Room for Evolution**: Make it explicit where later experts should challenge or expand.
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
{"- Explicitly challenge at least one earlier assumption or recommendation to avoid anchoring" if contributions else ""}

**## My Contribution: {expert['name']}**
- Add your unique value and expertise
- Be specific, actionable, and evidence-based
- Integrate with and enhance prior work
- Introduce at least two NEW angles, frameworks, or considerations not covered yet
- Anchor every point to the user's intent, goals, and success criteria
- Target 300-450 words and deliver a complete, field-expert-level contribution (not a shortlist of ideas)
- Write in full paragraphs (not fragments or bullet-only lists)

**## Evolution Note (Keep / Change / Add)**
- Keep: ...
- Change: ...
- Add: ...

**## Key Assumptions** (if any)
- State any assumptions you're making
</contribution_framework>

<quality_standards>
- **Accuracy**: Every claim must be correct and defensible.
- **Depth**: Go beyond surface-level—provide real insight.
- **Actionability**: The user should be able to act on this.
- **Coherence**: Build a unified artifact, not disconnected pieces.
- **Grounding**: Stay anchored to the user’s intent; avoid unrelated domains or unnecessary complexity.
- **Completeness**: Fully cover your expert mandate; do not omit critical steps or caveats for your domain.
</quality_standards>

Provide your rigorous expert contribution now:"""

    messages = [{"role": "user", "content": expert_prompt}]
    response = await query_model(
        model,
        messages,
        extra_body=build_reasoning_payload(model, thinking_by_model),
    )
    
    if not _safe_content(response):
        return "Expert contribution unavailable."
    
    return response.get('content', 'Expert contribution unavailable.')


async def stage1_sequential_contributions(
    user_query: str, 
    experts: List[Dict[str, str]],
    intent_analysis: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    num_experts: int = DEFAULT_NUM_EXPERTS,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
            thinking_by_model=thinking_by_model,
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
        history: List[Dict[str, Any]] = None,
        analysis_model: Optional[str] = None,
        thinking_by_model: Optional[Dict[str, bool]] = None,
) -> str:
    """Stage 2.5: Verify claims and audit reasoning across all contributions."""
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    summary = "\n".join([
        f"- Expert {entry['order']} ({entry['expert']['name']}): \"{entry['contribution']}\""
        for entry in contributions
    ])

    search_status_notes = []
    search_scope = ""
    preferred_sources_global: List[str] = []
    search_query_target_count = SEARCH_QUERY_COUNT

    # 1. Build an exhaustive verification scope (used ONLY for search targeting)
    scope_prompt = f"""<task>
You are a Verification Scope Synthesizer. Build an exhaustive, lossless audit map for web validation.
Extract EVERY factual claim, number, date, price, version, benchmark, proper noun, regulation, external dependency, and risky assumption that could be wrong or outdated.
Include implicit assumptions and uncertainties that should be checked. Do NOT omit anything; if unsure, include it.
</task>

<user_query>{user_query}</user_query>
{context_section}

<expert_contributions>
{summary}
</expert_contributions>

<output_format>
Return JSON:
{{
  "claims_to_verify": ["..."],
  "areas_of_concern": ["..."],
  "assumptions_to_check": ["..."],
  "entities_and_sources": ["..."],
  "critical_metrics": ["..."],
  "preferred_sources": ["official docs", "vendor sites", "standards bodies", "peer-reviewed research", "government data"]
}}
</output_format>"""

    try:
        model = analysis_model or CHAIRMAN_MODEL
        scope_response = await query_model(
            model,
            [{"role": "user", "content": scope_prompt}],
            extra_body=build_reasoning_payload(model, thinking_by_model),
        )
        scope_payload = _extract_json(_safe_content(scope_response) or "")
        if scope_payload:
            search_query_target_count = _compute_search_query_count(scope_payload)
            preferred_sources = scope_payload.get("preferred_sources")
            if isinstance(preferred_sources, list):
                preferred_sources_global = [item for item in preferred_sources if isinstance(item, str) and item.strip()]

            scope_sections = []
            for label, key in [
                ("Claims to verify", "claims_to_verify"),
                ("Areas of concern", "areas_of_concern"),
                ("Assumptions to check", "assumptions_to_check"),
                ("Entities and sources", "entities_and_sources"),
                ("Critical metrics", "critical_metrics"),
            ]:
                items = scope_payload.get(key)
                if isinstance(items, list) and items:
                    scope_sections.append(
                        f"{label}:\n" + "\n".join(f"- {item}" for item in items if isinstance(item, str) and item.strip())
                    )
            if scope_sections:
                search_scope = "\n\n".join(scope_sections)
        if not search_scope:
            search_status_notes.append("Search scope generation returned no usable coverage; proceeding without web evidence.")
    except Exception as e:
        print(f"Search scope generation failed: {e}")
        search_status_notes.append("Search scope generation failed; proceeding without web evidence.")

    # 2. Generate Search Targets from the scope
    search_targets = []
    if search_scope:
        sources_hint_global = ""
        if preferred_sources_global:
            sources_hint_global = f"Preferred sources: {', '.join(preferred_sources_global)}"

        query_gen_prompt = f"""<task>
You are a Fact-Check Strategist dedicated to eliminating hallucinations and weak reasoning.
Use the Verification Scope to select EXACTLY {search_query_target_count} high-risk verification targets.
Targets must collectively cover the MOST critical and failure-prone items without missing key risk areas.
Prefer high-quality, authoritative sources. {sources_hint_global}
</task>

<user_query>{user_query}</user_query>
{context_section}

<verification_scope>
{search_scope}
</verification_scope>

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

        try:
            messages = [{"role": "user", "content": query_gen_prompt}]
            model = analysis_model or CHAIRMAN_MODEL
            response = await query_model(
                model,
                messages,
                extra_body=build_reasoning_payload(model, thinking_by_model),
            )
            content = response.get('content', '[]') if _safe_content(response) else "[]"
            parsed_targets = _extract_json_array(content) or []
            search_targets = [target for target in parsed_targets if isinstance(target, dict)]
            if not search_targets:
                search_status_notes.append("Search target generation returned no valid targets; proceeding without web evidence.")
        except Exception as e:
            print(f"Error generating search targets: {e}")
            search_status_notes.append("Search target generation failed; proceeding without web evidence.")
    elif not search_status_notes:
        search_status_notes.append("Search scope unavailable; proceeding without web evidence.")

    # 3. Execute Search via gpt-4o-mini-search-preview
    search_evidence = ""
    if search_targets:
        try:
            evidence_blocks = []
            for target in search_targets[:search_query_target_count]:
                if not isinstance(target, dict):
                    continue
                claim = target.get("claim", "").strip()
                query = target.get("query", "").strip() or claim
                preferred_sources = target.get("preferred_sources", [])
                if isinstance(preferred_sources, str):
                    preferred_sources = [preferred_sources]
                if not preferred_sources and preferred_sources_global:
                    preferred_sources = preferred_sources_global

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
                raw_content = search_response.get("content", "") if _safe_content(search_response) else ""
                annotations = search_response.get("annotations") if _safe_content(search_response) else None
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
            else:
                search_status_notes.append("Search returned no evidence; verification relies on model knowledge.")
        except Exception as e:
            print(f"Search execution failed: {e}")
            search_status_notes.append("Search execution failed; proceeding without web evidence.")
            search_evidence = ""

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
    model = analysis_model or CHAIRMAN_MODEL
    response = await query_model(
        model,
        messages,
        extra_body=build_reasoning_payload(model, thinking_by_model),
    )
    verification_content = response.get('content', 'Verification unavailable.') if _safe_content(response) else "Verification unavailable."
    if search_status_notes:
        status_block = "## Search Status\n" + "\n".join(f"- {note}" for note in search_status_notes)
        verification_content = f"{status_block}\n\n{verification_content}"
    return _trim_verification_report(verification_content)


async def stage_synthesis_planning(
    user_query: str,
    contributions: List[Dict[str, Any]],
    intent_analysis: str,
    verification_data: str,
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
    model = analysis_model or CHAIRMAN_MODEL
    response = await query_model(
        model,
        messages,
        extra_body=build_reasoning_payload(model, thinking_by_model),
    )
    return response.get('content', 'Planning unavailable.') if _safe_content(response) else "Planning unavailable."


async def stage_editorial_guidelines(
    user_query: str,
    intent_analysis: str,
    contributions: List[Dict[str, Any]],
    synthesis_plan: str,
    history: List[Dict[str, Any]] = None,
    analysis_model: Optional[str] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
    model = analysis_model or CHAIRMAN_MODEL
    response = await query_model(
        model,
        messages,
        extra_body=build_reasoning_payload(model, thinking_by_model),
    )
    if not _safe_content(response):
        return "Editorial guidelines unavailable."
    return response.get('content', 'Editorial guidelines unavailable.').replace("```markdown", "").replace("```", "")


async def stage3_synthesize_final(
    user_query: str,
    contributions: List[Dict[str, Any]],
    intent_analysis: str = "",
    verification_data: str = "",
    synthesis_plan: str = "",
    editorial_guidelines: str = "",
    history: List[Dict[str, Any]] = None,
    chairman_model: Optional[str] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
    response = await query_model(
        chairman,
        messages,
        extra_body=build_reasoning_payload(chairman, thinking_by_model),
    )
    if not _safe_content(response):
        return {"model": chairman, "response": "Error: Synthesis failed."}
    return {"model": chairman, "response": response.get('content', 'Error: Synthesis failed.')}


async def generate_conversation_title(user_query: str) -> str:
    """Generate a short title for a conversation."""
    title_prompt = f"""<task>Generate a concise title (3-5 words) for this query.</task>
<query>{user_query}</query>
<rules>No quotes/punctuation. Be specific.</rules>
Title:"""
    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages, timeout=30.0)
    if not _safe_content(response):
        return "New Conversation"
    title = response.get('content', 'New Conversation').strip().strip('"\'')
    return title[:47] + "..." if len(title) > 50 else title


async def run_full_council(
    user_query: str,
    history: List[Dict[str, Any]] = None,
    expert_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    num_experts: Optional[int] = None,
    thinking_by_model: Optional[Dict[str, bool]] = None,
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
        thinking_by_model=thinking_by_model,
    )
    intent_analysis = await stage0_finalize_intent(
        user_query,
        intent_draft,
        {"skip": True, "answers": [], "free_text": ""},
        history,
        analysis_model=chairman_model,
        thinking_by_model=thinking_by_model,
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
        thinking_by_model=thinking_by_model,
    )
    
    # Stage 1: Sequential expert contributions
    contributions = await stage1_sequential_contributions(
        user_query,
        experts,
        intent_analysis,
        history,
        expert_models=models,
        num_experts=expert_count,
        thinking_by_model=thinking_by_model,
    )
    
    if not contributions:
        return intent_analysis, experts, [], "", "", "", {
            "model": "error",
            "response": "Collaboration failed. Please try again."
        }, {}
    
    # Stage 2.5: Verification
    verification_data = await stage_verification(
        user_query,
        contributions,
        history,
        analysis_model=chairman_model,
        thinking_by_model=thinking_by_model,
    )
    
    # Stage 2.75: Synthesis Planning
    synthesis_plan = await stage_synthesis_planning(
        user_query, 
        contributions, 
        intent_analysis, 
        verification_data,
        history,
        analysis_model=chairman_model,
        thinking_by_model=thinking_by_model,
    )
    
    # Stage 2.9: Editorial Guidelines
    editorial_guidelines = await stage_editorial_guidelines(
        user_query,
        intent_analysis,
        contributions,
        synthesis_plan,
        history,
        analysis_model=chairman_model,
        thinking_by_model=thinking_by_model,
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
        thinking_by_model=thinking_by_model,
    )
    
    metadata = {
        "intent_analysis": intent_analysis,
        "verification_data": verification_data,
        "synthesis_plan": synthesis_plan,
        "editorial_guidelines": editorial_guidelines,
        "num_experts": len(contributions)
    }
    
    return intent_analysis, experts, contributions, verification_data, synthesis_plan, editorial_guidelines, stage3_result, metadata

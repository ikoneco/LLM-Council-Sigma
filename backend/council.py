"""LLM Council orchestration with sequential expert collaboration."""

from typing import List, Dict, Any, Tuple, Optional
import asyncio
from .openrouter import query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL

NUM_EXPERTS = 6


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
                formatted.append(f"### 🤖 Chairman (Previous Output):\n{response}")
                
    return "\n".join(formatted)


async def stage0_analyze_intent(user_query: str, history: List[Dict[str, Any]] = None) -> str:
    """
    Stage 0: Master Intent Architect.
    Analyze the user's intent deeply - expert selection happens in brainstorm stage.
    """
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""

    intent_prompt = f"""<system>You are the Master Intent Architect, an elite cognitive strategist.</system>

<task>
Deeply analyze the user query to understand their EXPLICIT and IMPLICIT intent.
Do NOT select experts yet - that happens in a later brainstorm stage.
If there is conversation context, analyze how this new query evolves the previous discussion.
</task>

<query>{user_query}</query>
{context_section}

<analysis_framework>
1. **Surface Intent**: What is the user literally asking?
2. **Deep Intent**: What is the user's ultimate goal? What would "success" look like?
3. **Critical Dimensions**: What aspects must be covered for a world-class answer?
4. **Key Assumptions**: What must we assume?
5. **User Context**: What context clues suggest their expertise level, urgency, or constraints?
6. **Success Criteria**: How will we know the response fully addressed their need?
</analysis_framework>

<output_format>
Provide your analysis in Markdown format:

### Core Intent
[Explicit + Implicit goals]

### Critical Dimensions
- **Strategic**: ...
- **Tactical**: ...
- **Technical**: ...
- **Risks/Edge Cases**: ...

### Key Assumptions
1. ...
2. ...

### Success Criteria
- [What must the final artifact achieve?]
</output_format>

Provide your deep intent analysis now:"""
    
    messages = [{"role": "user", "content": intent_prompt}]
    response = await query_model("google/gemini-2.0-flash-001", messages)
    
    if response is None:
        return "Analyzing query requirements..."
    
    return response.get('content', 'Analyzing query requirements...')


async def stage_brainstorm_experts(user_query: str, intent_analysis: str, history: List[Dict[str, Any]] = None) -> Tuple[str, List[Dict[str, str]]]:
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

    # Collect brainstorm from all models in parallel
    import asyncio
    tasks = [
        query_model(model, [{"role": "user", "content": brainstorm_prompt}])
        for model in COUNCIL_MODELS
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Format brainstorm content for display
    brainstorm_sections = []
    all_suggestions_for_synthesis = []
    
    for i, resp in enumerate(responses):
        model_name = COUNCIL_MODELS[i].split('/')[-1]  # Get short model name
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
Create a team of {NUM_EXPERTS} HIGHLY RELEVANT experts with SPECIFIC roles aligned to this query.
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
1. Select EXACTLY {NUM_EXPERTS} experts
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
        ... (continue for all {NUM_EXPERTS} experts)
    ]
}}
</output_format>

Create the optimal expert team now:"""

    messages = [{"role": "user", "content": synthesis_prompt}]
    response = await query_model(CHAIRMAN_MODEL, messages)
    
    default_experts = [
        {"name": "Strategic Analyst", "description": "Task: Set strategic direction. Objective: Define approach.", "objectives": ["Define strategy"], "order": 1},
        {"name": "Technical Architect", "description": "Task: Technical foundation. Objective: Ensure feasibility.", "objectives": ["Ensure feasibility"], "order": 2},
        {"name": "Domain Specialist", "description": "Task: Domain expertise. Objective: Add depth.", "objectives": ["Add domain depth"], "order": 3},
        {"name": "Implementation Expert", "description": "Task: Practical application. Objective: Actionable guidance.", "objectives": ["Provide guidance"], "order": 4},
        {"name": "Risk Analyst", "description": "Task: Identify risks. Objective: Surface concerns.", "objectives": ["Identify risks"], "order": 5},
        {"name": "Quality Reviewer", "description": "Task: Critical review. Objective: Ensure completeness.", "objectives": ["Ensure quality"], "order": 6}
    ]
    
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
            for i, e in enumerate(experts[:NUM_EXPERTS]):
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
            
            while len(normalized) < NUM_EXPERTS:
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
    history: List[Dict[str, Any]] = None
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
You are Expert {order} of {NUM_EXPERTS}. Your job is to CRITICALLY REVIEW and then BUILD UPON the prior work.
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
You are Expert {order} of {NUM_EXPERTS}. You are the FIRST expert laying the FOUNDATION.
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
    
    model = COUNCIL_MODELS[(order - 1) % len(COUNCIL_MODELS)]
    
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
    history: List[Dict[str, Any]] = None
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
            history
        )
        
        contributions.append({
            "order": order,
            "expert": expert,
            "contribution": contribution,
            "model": COUNCIL_MODELS[(order - 1) % len(COUNCIL_MODELS)]
        })
    
    return contributions


async def stage_verification(
        user_query: str, 
        contributions: List[Dict[str, Any]],
        history: List[Dict[str, Any]] = None
) -> str:
    """Stage 2.5: Verify key claims using simple web search context."""
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    summary = "\n".join([
        f"- Expert {entry['order']} ({entry['expert']['name']}): \"{entry['contribution']}...\""
        for entry in contributions
    ])
    
    # 1. Generate Search Queries
    query_gen_prompt = f"""<task>
You are a Fact-Check Strategist dedicated to eliminating hallucinations. 
Review the expert contributions and flag specific data points that are prone to hallucination (e.g., pricing, release dates, version numbers, technical specs).
Generate EXACTLY 3 targeted web search queries to rigorously verify these high-risk claims.
</task>

<user_query>{user_query}</user_query>
{context_section}

<expert_contributions>
{summary}
</expert_contributions>

<output_format>
Return ONLY a JSON array of strings:
["query 1", "query 2", "query 3"]
</output_format>"""

    search_queries = []
    try:
        messages = [{"role": "user", "content": query_gen_prompt}]
        response = await query_model("google/gemini-2.0-flash-001", messages)
        content = response.get('content', '[]')
        import json
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            search_queries = json.loads(json_match.group())
    except Exception as e:
        print(f"Error generating search queries: {e}")

    # 2. Execute Search (Non-blocking)
    search_evidence = ""
    if search_queries:
        try:
            def _run_search(queries):
                from duckduckgo_search import DDGS
                results = []
                # Use DDGS context manager
                with DDGS() as ddgs:
                    for q in queries:
                        try:
                            # Fetch results (blocking IO)
                            r = list(ddgs.text(q, max_results=3)) # Increased to 3
                            if r:
                                formatted_hits = []
                                for hit in r:
                                    title = hit.get('title', 'Unknown Source')
                                    href = hit.get('href', '#')
                                    body = hit.get('body', '')
                                    formatted_hits.append(f"Source: {title}\nURL: {href}\nSnippet: {body}")
                                
                                results.append(f"Query: {q}\n" + "\n---\n".join(formatted_hits))
                        except Exception:
                            continue
                return results

            # Run in thread pool to avoid blocking async loop
            results = await asyncio.to_thread(_run_search, search_queries[:3])
            
            if results:
                search_evidence = "\n\n".join(results)
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
You are a Meticulous Fact-Checker. Verify the expert contributions against the provided Search Evidence (if available) and your own knowledge.
Focus on accurate numbers, dates, pricing, and technical facts.
</task>

<user_query>{user_query}</user_query>
{context_section}

<expert_contributions>
{summary}
</expert_contributions>

{evidence_section}

<output_format>
## Factual Verification Report

### Claim 1: [Statement]
- **Verdict**: Verified / Partially Accurate / Incorrect
- **Corrective Information**: [Accurate facts from search. CITE SOURCE: [Name](URL)]
- **Reasoning**: [Explain conflict or gap]
- **Source Reliability**: [High/Medium/Low]

### Claim 2: [Statement]
- **Verdict**: ...
- **Corrective Information**: ...
- **Reasoning**: ...
- **Source Reliability**: ...

### Claim 3: [Statement]
- **Verdict**: ...
- **Corrective Information**: ...
- **Reasoning**: ...
- **Source Reliability**: ...
</output_format>

Provide your verification report now:"""

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
    history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Stage 3: Chairman synthesizes all contributions following the plan and editorial guidelines."""
    context_str = format_conversation_history(history or [])
    context_section = f"\n<conversation_context>\n{context_str}\n</conversation_context>" if context_str else ""
    
    contributions_text = "\n\n---\n\n".join([
        f"**Expert {entry['order']}: {entry['expert']['name']}**\n{entry['contribution']}"
        for entry in contributions
    ])

    chairman_prompt = f"""<system>You are the Council Chairman, the master synthesizer responsible for producing a TOP QUALITY final artifact.</system>

<mission>
Synthesize all expert contributions into a definitive, world-class artifact that FULLY addresses the user's intent.
You MUST follow BOTH the Synthesis Plan AND the Editorial Guidelines precisely.
Maintain continuity with the previous conversation context if it exists.
</mission>

<user_query>{user_query}</user_query>
{context_section}

<intent_analysis>
{intent_analysis}
</intent_analysis>

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

<chairman_mandate>
You MUST:
1. **Address ALL Missing Elements** from the synthesis plan
2. **Fill ALL Reasoning Gaps** with rigorous analysis
3. **Follow the Editorial Guidelines** for tone, voice, and style
4. **Match the recommended structure** from the plan
5. **Satisfy ALL Quality Checkpoints**
6. **Meet the Quality Bar** defined in editorial guidelines
7. **STRICTLY ADHERE TO VERIFICATION**: Use the <verification_report> to filter untrue claims. If a claim is marked 'Incorrect', exclude it. If 'Partially Accurate', provide nuance. Do not hallucinate data.
</chairman_mandate>

<synthesis_protocol>
1. **BLUF (Bottom Line Up Front)**: Start with a definitive 1-2 sentence answer.
2. **Comprehensive Coverage**: Address every dimension of user intent.
3. **Follow Editorial Voice**: Match the tone and style guidelines exactly.
4. **Evidence-Based**: Support claims with reasoning and data.
5. **Actionable Conclusion**: End with clear, specific next steps.
</synthesis_protocol>

<quality_standards>
- **Completeness**: User intent must be FULLY addressed
- **Accuracy**: All claims must be verified and correct
- **Depth**: Provide real insight, not surface-level responses
- **Coherence**: One unified voice, not a patchwork of opinions
- **Actionability**: User must be able to act on this immediately
- **Style Match**: Must match Editorial Guidelines perfectly
</quality_standards>

Provide the final TOP QUALITY synthesized artifact now:"""

    messages = [
        {"role": "system", "content": "You are the master synthesizer. Follow both the synthesis plan AND editorial guidelines precisely."},
        {"role": "user", "content": chairman_prompt}
    ]
    response = await query_model(CHAIRMAN_MODEL, messages)
    return {"model": CHAIRMAN_MODEL, "response": response.get('content', 'Error: Synthesis failed.') if response else "Error: Synthesis failed."}


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


async def run_full_council(user_query: str, history: List[Dict[str, Any]] = None) -> Tuple[str, List, List, str, str, str, Dict, Dict]:
    """
    Run the complete sequential expert collaboration process.
    
    Returns:
        Tuple of (intent_analysis, experts, contributions, verification_data, synthesis_plan, editorial_guidelines, stage3_result, metadata)
    """
    # Stage 0: Analyze intent
    intent_analysis = await stage0_analyze_intent(user_query, history)
    
    # Stage 0.5: Brainstorm and form expert team
    brainstorm_content, experts = await stage_brainstorm_experts(user_query, intent_analysis, history)
    
    # Stage 1: Sequential expert contributions
    contributions = await stage1_sequential_contributions(user_query, experts, intent_analysis, history)
    
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
        history=history
    )
    
    metadata = {
        "intent_analysis": intent_analysis,
        "verification_data": verification_data,
        "synthesis_plan": synthesis_plan,
        "editorial_guidelines": editorial_guidelines,
        "num_experts": len(contributions)
    }
    
    return intent_analysis, experts, contributions, verification_data, synthesis_plan, editorial_guidelines, stage3_result, metadata

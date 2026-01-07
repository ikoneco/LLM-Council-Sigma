import asyncio
import json
import os
import sys

sys.path.insert(0, ".")

from backend.council import stage0_generate_intent_draft


async def main():
    user_query = (
        "Explore, brainstorm and list 10 article series by a product design leader on substak "
        "about AI native product design. Final output will be a synopsys of these 10 article "
        "that are useful, inspiring, grounded in 2026 business reality and from the perspective "
        "of tech leader from a point of view of product design. Audience will be product design "
        "leaders and product leaders. Make sure the content is NOT obvious and still very useful "
        "and informative and accessible and professional. Synopsis should be very detailed."
    )

    model = os.getenv("INTENT_TEST_MODEL", "qwen/qwen3-235b-a22b-2507")
    thinking_enabled = os.getenv("INTENT_TEST_THINKING", "false").lower() in ("1", "true", "yes")
    thinking_by_model = {model: True} if thinking_enabled else {}

    result = await stage0_generate_intent_draft(
        user_query=user_query,
        history=[],
        analysis_model=model,
        thinking_by_model=thinking_by_model,
    )

    display = result.get("display", {})
    print("MODEL DEBUG:")
    print(json.dumps(result.get("debug", {}), indent=2))
    print("\nDISPLAY MARKDOWN (first 600 chars):")
    print((display.get("markdown") or "")[:600])


if __name__ == "__main__":
    asyncio.run(main())

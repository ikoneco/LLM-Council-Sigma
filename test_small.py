import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.council import stage0_analyze_intent, stage1_collect_responses
from backend.config import COUNCIL_MODELS

async def test_small():
    query = "What are three key principles of sustainable architecture?"
    print(f"\n--- Testing Query: {query} ---\n")
    
    print("Stage 0: Analyzing intent...")
    personas = await stage0_analyze_intent(query)
    for p in personas:
        print(f"  Expert: {p['name']}")
    
    print("\nStage 1: Collecting expert responses...")
    results = await stage1_collect_responses(query, personas)
    
    for res in results:
        print(f"\nModel: {res['model']}")
        print(f"Expert Persona: {res['persona']['name']}")
        if res['response']:
            print(f"Response Preview: {res['response'][:150]}...")
        else:
            print("FAILED: No response received.")

if __name__ == "__main__":
    asyncio.run(test_small())

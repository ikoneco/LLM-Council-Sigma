import asyncio
import sys
import os

# Add the project root to sys.path to allow relative imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.council import stage0_analyze_intent, stage1_collect_responses
from backend.config import COUNCIL_MODELS

async def test_intent_and_personas():
    test_queries = [
        "How do I fix a memory leak in a React application?",
        "Should I invest in Bitcoin or gold right now?",
        "Write a summary of the French Revolution for a middle school student.",
        "What are the best practices for designing a scalable microservices architecture?"
    ]
    
    for query in test_queries:
        print(f"\n--- Testing Query: {query} ---")
        
        # Test Stage 0
        print("Running Stage 0: Intent Analysis...")
        personas = await stage0_analyze_intent(query)
        print(f"Generated {len(personas)} personas:")
        for i, p in enumerate(personas):
            print(f"  {i+1}. {p['name']}: {p['description']}")
            
        # Verify number of personas matches council models
        assert len(personas) >= len(COUNCIL_MODELS), f"Expected at least {len(COUNCIL_MODELS)} personas, got {len(personas)}"
        
        # Test Stage 1 with personas
        print("\nRunning Stage 1: Collecting Responses with Personas...")
        # We only query the first model for brevity in testing if needed, 
        # but here we'll test the orchestration logic.
        results = await stage1_collect_responses(query, personas)
        
        print(f"Collected {len(results)} responses.")
        for res in results:
            persona = res.get('persona')
            print(f"  Model: {res['model']}")
            if persona:
                print(f"  Assigned Persona: {persona['name']}")
            else:
                print("  NO PERSONA ASSIGNED!")
            
            # Print first 100 chars of response
            response_preview = res['response'][:100].replace('\n', ' ')
            print(f"  Response Preview: {response_preview}...")

if __name__ == "__main__":
    asyncio.run(test_intent_and_personas())

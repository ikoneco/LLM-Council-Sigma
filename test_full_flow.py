import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.council import stage0_analyze_intent, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

async def test_full():
    query = "Why is the sky blue?"
    print(f"\n--- Testing Full Flow: {query} ---\n")
    
    try:
        print("Stage 0: Analyzing intent...")
        personas = await stage0_analyze_intent(query)
        print(f"  Personas: {[p['name'] for p in personas]}")
        
        print("\nStage 1: Collecting responses...")
        s1 = await stage1_collect_responses(query, personas)
        print(f"  Responses: {len(s1)} collected from {[r['model'] for r in s1]}")
        
        print("\nStage 2: Collecting rankings...")
        s2, label_to_model = await stage2_collect_rankings(query, s1)
        print(f"  Rankings: {len(s2)} collected")
        
        print("\nStage 3: Synthesizing final answer...")
        s3 = await stage3_synthesize_final(query, s1, s2)
        print(f"  Synthesis Success: {bool(s3['response'])}")
        
        aggregate = calculate_aggregate_rankings(s2, label_to_model)
        print("\nAggregate Rankings:")
        for rank in aggregate:
            print(f"  {rank['model']}: {rank['average_rank']}")
                
    except Exception as e:
        print(f"\nERROR during full flow: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full())

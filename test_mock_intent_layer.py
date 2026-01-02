import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, patch

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.council import stage0_analyze_intent, stage1_collect_responses, run_full_council

class TestIntentLayerLogic(unittest.IsolatedAsyncioTestCase):
    
    @patch('backend.council.query_model')
    async def test_stage0_parsing(self, mock_query):
        # Mock a successful JSON response from Stage 0
        mock_query.return_value = {
            'content': '```json\n[\n  {"name": "Python Expert", "description": "Focus on clean code"},\n  {"name": "Database Guru", "description": "Focus on optimization"},\n  {"name": "Security Auditor", "description": "Focus on vulnerabilities"},\n  {"name": "UI Designer", "description": "Focus on UX"}\n]\n```'
        }
        
        personas = await stage0_analyze_intent("How to build a secure web app?")
        
        self.assertEqual(len(personas), 4)
        self.assertEqual(personas[0]['name'], "Python Expert")
        self.assertEqual(personas[2]['name'], "Security Auditor")

    @patch('backend.council.query_models_with_personas')
    async def test_stage1_persona_assignment(self, mock_query_with_personas):
        # Mock response from Stage 1
        mock_query_with_personas.return_value = {
            "model/a": {"content": "Response A content"},
            "model/b": {"content": "Response B content"},
            "model/c": {"content": "Response C content"},
            "model/d": {"content": "Response D content"}
        }
        
        personas = [
            {"name": "Expert A", "description": "Desc A"},
            {"name": "Expert B", "description": "Desc B"},
            {"name": "Expert C", "description": "Desc C"},
            {"name": "Expert D", "description": "Desc D"}
        ]
        
        results = await stage1_collect_responses("Test query", personas)
        
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0]['persona']['name'], "Expert A")
        self.assertEqual(results[3]['persona']['name'], "Expert D")
        
        # Verify personas were passed to models correctly
        call_args = mock_query_with_personas.call_args[0][0]
        self.assertIn("Expert A", call_args[0][1][0]['content'])
        self.assertIn("Expert D", call_args[3][1][0]['content'])

    @patch('backend.council.stage0_analyze_intent')
    @patch('backend.council.stage1_collect_responses')
    @patch('backend.council.stage2_collect_rankings')
    @patch('backend.council.stage3_synthesize_final')
    async def test_full_orchestration(self, mock_s3, mock_s2, mock_s1, mock_s0):
        # Setup mocks
        mock_s0.return_value = [{"name": "Mock Expert", "description": "Mock Desc"}] * 4
        mock_s1.return_value = [{"model": "m1", "response": "r1", "persona": {"name": "Mock Expert", "description": "Mock Desc"}}]
        mock_s2.return_value = ([], {})
        mock_s3.return_value = {"model": "chairman", "response": "synthesis"}
        
        query = "Test integration"
        s1, s2, s3, meta = await run_full_council(query)
        
        # Verify Stage 0 was called
        mock_s0.assert_called_once_with(query)
        # Verify Stage 1 was called with personas from Stage 0
        mock_s1.assert_called_once_with(query, mock_s0.return_value)
        
        self.assertEqual(s3['response'], "synthesis")

if __name__ == "__main__":
    unittest.main()

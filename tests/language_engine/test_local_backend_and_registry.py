import unittest
from evaluation.language.candidate_registry import load_registry, eligible_foundations
from language_engine import GenerationRequest, IranLanguageEngine
from language_engine.backends.local_http import LocalHTTPBackend


class LocalBackendAndRegistryTests(unittest.TestCase):
    def test_backend_rejects_remote_endpoint(self):
        with self.assertRaises(ValueError):
            LocalHTTPBackend("model",endpoint="https://example.com/v1/chat/completions")

    def test_backend_contract_with_injected_transport(self):
        backend=LocalHTTPBackend("fixture-local",transport=lambda payload:{
            "choices":[{"message":{"content":"سلام"}}],"usage":{"completion_tokens":1}})
        result=IranLanguageEngine(backend).generate(
            GenerationRequest([{"role":"user","content":"سلام"}],language="fa"))
        self.assertEqual(result.text,"سلام")
        self.assertTrue(result.metadata["offline"])

    def test_only_pinned_foundation_candidates_are_promotable(self):
        registry=load_registry()
        ids={x.candidate_id for x in eligible_foundations(registry)}
        self.assertEqual(ids,{"qwen35-9b","gemma4-12b"})
        refs={x["candidate_id"] for x in registry["candidates"] if x["role"]!="foundation_candidate"}
        self.assertIn("tiny-aya-global",refs)
        self.assertIn("mistral-small-4",refs)


if __name__=="__main__":
    unittest.main()

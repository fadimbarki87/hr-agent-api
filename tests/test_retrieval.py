import unittest

from hr_agent.database import HRDatabase
from hr_agent.retrieval import ReviewRetriever


class FakeEmbeddingClient:
    def __init__(self):
        self.embedding_inputs = []
        self.rerank_responses = []

    def embed_texts(self, texts):
        self.embedding_inputs.append(list(texts))
        if len(texts) == 1:
            return [[1.0, 0.0, 0.0]]
        vectors = []
        for index, _text in enumerate(texts):
            angle = index / max(1, len(texts) - 1)
            vectors.append([1.0 - angle, angle, 0.1])
        return vectors

    def embed_text(self, text):
        return self.embed_texts([text])[0]

    def chat_json(self, system_prompt, user_prompt, *, max_tokens):
        return self.rerank_responses.pop(0)


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = HRDatabase.from_project_files()

    def test_index_embeds_raw_reviews_in_one_batch(self):
        client = FakeEmbeddingClient()
        retriever = ReviewRetriever(self.database, client)
        self.assertTrue(retriever.ready)
        self.assertEqual(1, len(client.embedding_inputs))
        self.assertEqual(15, len(client.embedding_inputs[0]))
        for document in client.embedding_inputs[0]:
            self.assertTrue(document.startswith("Performance review: "))
            self.assertNotIn("Semantic tags:", document)

    def test_reranker_controls_final_evidence_order(self):
        client = FakeEmbeddingClient()
        retriever = ReviewRetriever(self.database, client)
        client.rerank_responses = [
            {
                "decisions": [
                    {
                        "employee_id": record["employee_id"],
                        "relevance": (
                            3
                            if record["employee_id"] == 3
                            else 2
                            if record["employee_id"] == 1
                            else 0
                        ),
                    }
                    for record in retriever.metadata
                ]
            }
        ]
        matches = retriever.search_and_rerank(
            "is highly organized",
            "current_strength",
            max_results=5,
        )
        self.assertEqual([3, 1], [item["employee_id"] for item in matches])

    def test_invalid_reranker_id_is_retried_and_fails_closed(self):
        client = FakeEmbeddingClient()
        retriever = ReviewRetriever(self.database, client)
        client.rerank_responses = [
            {"decisions": [{"employee_id": 999, "relevance": 3}]},
            {"decisions": [{"employee_id": 999, "relevance": 3}]},
        ]
        self.assertIsNone(
            retriever.search_and_rerank(
                "is highly organized",
                "current_strength",
                max_results=5,
            )
        )

    def test_result_limit_is_enforced_locally(self):
        client = FakeEmbeddingClient()
        retriever = ReviewRetriever(self.database, client)
        client.rerank_responses = [
            {
                "decisions": [
                    {
                        "employee_id": record["employee_id"],
                        "relevance": (
                            3 if record["employee_id"] in {1, 2, 3, 4} else 0
                        ),
                    }
                    for record in retriever.metadata
                ]
            }
        ]
        matches = retriever.search_and_rerank(
            "evidence",
            "neutral",
            max_results=2,
        )
        self.assertEqual([1, 2], [item["employee_id"] for item in matches])

    def test_incomplete_valid_decisions_exclude_omitted_candidates(self):
        client = FakeEmbeddingClient()
        retriever = ReviewRetriever(self.database, client)
        partial = {
            "decisions": [
                {"employee_id": 2, "relevance": 3},
                {"employee_id": 3, "relevance": 0},
            ]
        }
        client.rerank_responses = [partial, partial]
        matches = retriever.search_and_rerank(
            "direct evidence",
            "neutral",
            max_results=5,
        )
        self.assertEqual([2], [item["employee_id"] for item in matches])


if __name__ == "__main__":
    unittest.main()

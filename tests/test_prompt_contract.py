from hashlib import sha256
import json
from pathlib import Path
import re
import unittest

from route_eval_cases import ROUTE_EVAL_CASES
from blind_holdout_cases import BLIND_HOLDOUT_CASES
from blind_holdout_cases_v2 import BLIND_HOLDOUT_CASES_V2
from ui_eval_cases import UI_EVAL_CASES

from hr_agent.database import HRDatabase
from hr_agent.guidance import (
    UNSUPPORTED_GUIDANCE_PROMPT_SHA256,
    UNSUPPORTED_GUIDANCE_SYSTEM_PROMPT,
)
from hr_agent.planner import (
    PLAN_AUDIT_PROMPT_SHA256,
    PLAN_AUDIT_SYSTEM_PROMPT,
    AUDIT_REPAIR_INSTRUCTIONS,
    PLAN_REPAIR_POLICY_SHA256,
    PLANNER_PROMPT_SHA256,
    PLANNER_SYSTEM_PROMPT,
)
from hr_agent.retrieval import RERANK_PROMPT_SHA256, RERANK_SYSTEM_PROMPT


class PromptContractTests(unittest.TestCase):
    def test_recorded_prompt_hashes_match_exact_prompt_text(self):
        self.assertEqual(
            sha256(PLANNER_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            PLANNER_PROMPT_SHA256,
        )
        self.assertEqual(
            sha256(RERANK_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            RERANK_PROMPT_SHA256,
        )
        self.assertEqual(
            sha256(PLAN_AUDIT_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            PLAN_AUDIT_PROMPT_SHA256,
        )
        self.assertEqual(
            sha256(
                UNSUPPORTED_GUIDANCE_SYSTEM_PROMPT.encode("utf-8")
            ).hexdigest(),
            UNSUPPORTED_GUIDANCE_PROMPT_SHA256,
        )
        repair_policy = json.dumps(
            AUDIT_REPAIR_INSTRUCTIONS,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            sha256(repair_policy.encode("utf-8")).hexdigest(),
            PLAN_REPAIR_POLICY_SHA256,
        )

    def test_existing_route_questions_are_not_few_shot_examples(self):
        normalized_prompt = re.sub(r"\s+", " ", PLANNER_SYSTEM_PROMPT).casefold()
        for question, _route in ROUTE_EVAL_CASES:
            normalized_question = re.sub(r"\s+", " ", question).casefold()
            self.assertNotIn(normalized_question, normalized_prompt)

    def test_product_ui_questions_are_not_few_shot_examples(self):
        html = (
            Path(__file__).resolve().parents[1] / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        questions = re.findall(r"<li>(.*?)</li>", html)
        self.assertEqual(
            [case.question for case in UI_EVAL_CASES],
            questions,
        )
        normalized_prompt = re.sub(r"\s+", " ", PLANNER_SYSTEM_PROMPT).casefold()
        for question in questions:
            normalized_question = re.sub(r"\s+", " ", question).casefold()
            self.assertNotIn(normalized_question, normalized_prompt)

    def test_product_ui_does_not_publish_frozen_holdout_questions(self):
        ui_questions = {case.question.casefold() for case in UI_EVAL_CASES}
        frozen_questions = {
            item["question"].casefold()
            for item in (*BLIND_HOLDOUT_CASES, *BLIND_HOLDOUT_CASES_V2)
        }
        self.assertTrue(ui_questions.isdisjoint(frozen_questions))

    def test_auditor_prompt_contains_no_evaluation_questions(self):
        prompt = re.sub(r"\s+", " ", PLAN_AUDIT_SYSTEM_PROMPT).casefold()
        for question, _route in ROUTE_EVAL_CASES:
            normalized_question = re.sub(r"\s+", " ", question).casefold()
            self.assertNotIn(normalized_question, prompt)

    def test_reranker_prompt_does_not_copy_dataset_reviews(self):
        prompt = RERANK_SYSTEM_PROMPT.casefold()
        for record in HRDatabase.from_project_files().review_records():
            review = str(record["performance_review"]).strip().casefold()
            self.assertNotIn(review, prompt)


if __name__ == "__main__":
    unittest.main()

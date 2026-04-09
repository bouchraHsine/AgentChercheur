import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from core.llm_openai import OpenAILLM
from core.utils import save_json, save_text

from agents.planner_agent import PlannerAgent
from agents.search_agent import SearchAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.comparator_agent import ComparatorAgent
from agents.hypothesis_agent import HypothesisAgent
from agents.experiment_agent import ExperimentAgent
from agents.report_agent import ReportAgent


class Orchestrator:
    def __init__(self):
        self.llm = OpenAILLM()

        self.planner = PlannerAgent()
        self.searcher = SearchAgent()
        self.analyzer = AnalyzerAgent()
        self.comparator = ComparatorAgent()
        self.hypo = HypothesisAgent()
        self.exper = ExperimentAgent()
        self.reporter = ReportAgent()

        self.MAX_TOKENS_ANALYZE = int(os.getenv("MAX_TOKENS_ANALYZE", "260"))
        self.MAX_TOKENS_HYP = int(os.getenv("MAX_TOKENS_HYP", "700"))
        self.MAX_TOKENS_EXP = int(os.getenv("MAX_TOKENS_EXP", "520"))
        self.MAX_TOKENS_REPORT = int(os.getenv("MAX_TOKENS_REPORT", "900"))

    def _hypotheses_to_markdown(self, hyps: List[Dict[str, Any]]) -> str:
        if not hyps:
            return "_No hypotheses generated._"
        lines = ["# Hypotheses\n"]
        for i, h in enumerate(hyps, start=1):
            stmt = (h.get("statement") or "").strip()
            if stmt:
                lines.append(f"{i}. {stmt}")
        return "\n".join(lines).strip()

    def run(
        self,
        topic: str,
        results_per_query: int = 15,
        final_k: int = 3,
        required_keywords: List[str] = None,
        strict_filter: bool = True,
    ) -> Dict[str, Any]:
        required_keywords = required_keywords or []

        # 1) Plan
        plan = self.planner.plan(topic)
        save_json("outputs/plan.json", plan)

        # 2) Search pool
        pool: List[Dict[str, Any]] = []
        for q in plan.get("queries", []):
            pool.extend(self.searcher.search(q, limit=results_per_query))

        # 3) Select best K
        selected = self.searcher.select_best(
            topic=topic,
            articles=pool,
            final_k=final_k,
            required_keywords=required_keywords,
            strict=strict_filter,
        )
        save_json("outputs/articles.json", selected)

        if not selected:
            raise RuntimeError("Aucun article pertinent après filtrage. Désactive Strict filter ou reformule en anglais.")

        # 4) Analyze in parallel
        analyses = []
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as ex:
            futs = [ex.submit(self.analyzer.analyze, self.llm, a, self.MAX_TOKENS_ANALYZE) for a in selected]
            for f in as_completed(futs):
                analyses.append(f.result())
        save_json("outputs/analyses.json", analyses)

        # 5) Compare
        comparison_md = self.comparator.compare(self.llm, analyses)
        save_text("outputs/comparison.md", comparison_md)

        # 6) Hypotheses (JSON -> markdown)
        hypotheses_items = self.hypo.generate(
            self.llm,
            topic,
            comparison_md,
            selected,
            max_items=7,
            max_tokens=self.MAX_TOKENS_HYP,
        )
        save_json("outputs/hypotheses.json", hypotheses_items)

        hypotheses_md = self._hypotheses_to_markdown(hypotheses_items)
        save_text("outputs/hypotheses.md", hypotheses_md)

        # 7) Experiments
        experiments_md = self.exper.plan(self.llm, topic, hypotheses_md)
        save_text("outputs/experiments.md", experiments_md)

        # 8) Report
        report_md = self.reporter.build(
            self.llm,
            topic,
            selected,
            comparison_md,
            hypotheses_md,
            experiments_md,
        )
        save_text("outputs/report.md", report_md)

        return {
            "plan": plan,
            "articles": selected,
            "analyses": analyses,
            "comparison": comparison_md,
            "hypotheses_items": hypotheses_items,
            "hypotheses_md": hypotheses_md,
            "experiments": experiments_md,
            "report": report_md,
        }

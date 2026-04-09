from typing import Dict

class PlannerAgent:
    def plan(self, topic: str) -> Dict:
        t = (topic or "").strip()
        queries = [
            f"{t} review",
            f"{t} survey",
            f"recent advances {t}",
            f"{t} methodology",
        ]
        return {
            "topic": t,
            "queries": queries,
            "notes": "Planner heuristique : review/survey/recent/methodology."
        }

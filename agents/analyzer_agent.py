from typing import Dict, Any, List
from pydantic import BaseModel, Field
from core.utils import normalize_ws

class PaperFacts(BaseModel):
    title: str
    year: int | None = None
    problem: str = Field(..., description="Problème / objectif du papier")
    method: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    contributions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

class AnalyzerAgent:
    SYS = (
        "You are a rigorous research analyst. "
        "Return ONLY a JSON object that matches the schema. "
        "Never add markdown fences. If unknown, use empty list or short string."
    )

    SYS_FIX = (
        "You repair broken JSON. Output ONLY valid JSON. "
        "Do not add explanations or markdown."
    )

    def _clip(self, text: str, max_chars: int = 2500) -> str:
        text = normalize_ws(text or "")
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."

    def analyze(self, llm, article: Dict[str, Any], max_tokens: int = 260) -> Dict[str, Any]:
        title = normalize_ws(article.get("title") or "")
        year = article.get("year")
        abstract = self._clip(article.get("abstract") or "", max_chars=2400)
        concepts = article.get("concepts") or []

        base_text = (
            f"TITLE: {title}\n"
            f"YEAR: {year}\n"
            f"CONCEPTS: {', '.join(concepts)}\n"
            f"ABSTRACT: {abstract}\n"
        )

        user = (
            "Extract facts from the text. Output ONLY JSON (no markdown).\n"
            "Schema fields: title, year, problem, method, data, metrics, contributions, limitations, keywords.\n\n"
            f"{base_text}"
        )

        try:
            facts = llm.parse(PaperFacts, system=self.SYS, user=user, max_output_tokens=max_tokens, temperature=0.0)
            out = facts.model_dump()
        except Exception:
            raw = llm.generate(system=self.SYS, user=user, max_output_tokens=max_tokens, temperature=0.0)
            fix_user = (
                "The following JSON is broken/truncated. Repair it into a valid JSON object that matches the schema.\n"
                "If a field is incomplete, replace it with a shorter string or empty list.\n\n"
                f"BROKEN_JSON:\n{raw}"
            )
            fixed = llm.generate(system=self.SYS_FIX, user=fix_user, max_output_tokens=max_tokens, temperature=0.0)
            try:
                out = PaperFacts.model_validate_json(fixed).model_dump()
            except Exception:
                out = {
                    "title": title,
                    "year": year,
                    "problem": "N/A",
                    "method": [],
                    "data": [],
                    "metrics": [],
                    "contributions": [],
                    "limitations": [],
                    "keywords": [],
                }

        out["url"] = article.get("url", "")
        out["doi"] = article.get("doi", "")
        out["oa_url"] = article.get("oa_url", "")
        out["landing_page"] = article.get("landing_page", "")
        out["is_oa"] = bool(article.get("is_oa"))
        out["authors"] = article.get("authors") or []
        return out

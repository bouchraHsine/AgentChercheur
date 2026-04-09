# agents/hypothesis_agent.py
import re
import json
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field

# Pydantic v2 root model support (fallback if v1)
try:
    from pydantic import RootModel  # pydantic v2
except Exception:
    RootModel = None


class EvidenceItem(BaseModel):
    title: str = Field(default="")
    excerpt: str = Field(default="")


class HypothesisItem(BaseModel):
    statement: str = Field(default="")
    testability: str = Field(default="")
    data: str = Field(default="")
    success_metric: str = Field(default="")
    evidence: List[EvidenceItem] = Field(default_factory=list)
    why_bullets: List[str] = Field(default_factory=list)


# Root list schema
if RootModel is not None:
    class HypothesisList(RootModel[List[HypothesisItem]]):
        pass
else:
    class HypothesisList(BaseModel):
        __root__: List[HypothesisItem]


class HypothesisAgent:
    # ✅ IMPORTANT: force JSON ONLY (array)
    SYS = (
        "You are a senior research scientist.\n"
        "Return ONLY a valid JSON ARRAY (not an object), matching the schema.\n"
        "No markdown. No explanations. No extra text.\n"
        "If a field is unknown, use empty string or empty list.\n"
    )

    # ✅ JSON repair like AnalyzerAgent
    SYS_FIX = (
        "You repair broken/truncated JSON.\n"
        "Output ONLY valid JSON ARRAY that matches the schema.\n"
        "No explanations. No markdown.\n"
        "If incomplete, shorten strings or use empty lists.\n"
    )

    def _clean_text(self, s: str) -> str:
        s = (s or "").strip()
        s = s.replace("**", "")
        return s

    def _extract_sentences(self, text: str) -> List[str]:
        if not text:
            return []
        text = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?<=[\.\?\!])\s+", text)
        cleaned = []
        for p in parts:
            p = p.strip()
            if 40 <= len(p) <= 240:
                cleaned.append(p)
        return cleaned

    def _pick_evidence_sentences(self, articles: List[Dict[str, Any]], k: int = 4) -> List[Dict[str, str]]:
        evidences = []
        for a in (articles or []):
            title = self._clean_text(a.get("title") or "")
            abstract = a.get("abstract") or ""
            sents = self._extract_sentences(abstract)
            if not sents:
                continue
            evidences.append({"title": title, "excerpt": self._clean_text(sents[0])})
        return evidences[:k]

    def _extract_json_array_slice(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw = raw.strip()
        i = raw.find("[")
        j = raw.rfind("]")
        if i == -1 or j == -1 or j <= i:
            return None
        return raw[i:j+1]

    def generate(
        self,
        llm,
        topic: str,
        comparison_md: str,
        articles: List[Dict[str, Any]],
        *,
        max_items: int = 7,
        max_tokens: int = 900,
    ) -> List[Dict[str, Any]]:
        """
        Returns list of dicts:
        {
          "id": "H1",
          "statement": "...",
          "testability": "...",
          "data": "...",
          "success_metric": "...",
          "evidence": [{"title": "...", "excerpt": "..."}],
          "why_bullets": ["...", "..."]
        }
        """

        evidence_pool = self._pick_evidence_sentences(articles, k=4)
        evidence_text = json.dumps(evidence_pool, ensure_ascii=False, indent=2)

        user = (
            f"TOPIC:\n{topic}\n\n"
            f"COMPARISON (can be long):\n{comparison_md}\n\n"
            "EVIDENCE EXCERPTS (pick 2–3 per hypothesis if available):\n"
            f"{evidence_text}\n\n"
            f"Generate up to {max_items} hypotheses.\n\n"
            "For EACH hypothesis provide these fields exactly:\n"
            "- statement (1 sentence)\n"
            "- testability (what to measure)\n"
            "- data (dataset / protocol)\n"
            "- success_metric (confirm/refute)\n"
            "- evidence: 0–3 objects {title, excerpt} from the pool\n"
            "- why_bullets: 3–5 bullet strings\n\n"
            "HARD RULES:\n"
            "- Output MUST be a JSON ARRAY only.\n"
            "- No markdown, no extra text.\n"
        )

        items: List[Any] = []

        # 1) Best: structured parse
        try:
            parsed = llm.parse(
                HypothesisList,
                system=self.SYS,
                user=user,
                max_output_tokens=max_tokens,
                temperature=0.25,
            )
            if RootModel is not None:
                items = parsed.root
            else:
                items = parsed.__root__
        except Exception:
            # 2) Generate raw JSON array
            raw = llm.generate(
                system=self.SYS,
                user=user,
                max_output_tokens=max_tokens,
                temperature=0.25,
            )

            # Try to slice JSON array
            sliced = self._extract_json_array_slice(raw)
            candidate = sliced or raw

            # 3) If broken, repair with LLM
            fix_user = (
                "Repair this into a valid JSON ARRAY matching the schema.\n\n"
                f"BROKEN_JSON:\n{candidate}"
            )
            fixed = llm.generate(
                system=self.SYS_FIX,
                user=fix_user,
                max_output_tokens=max_tokens,
                temperature=0.0,
            )

            sliced2 = self._extract_json_array_slice(fixed)
            final_json = sliced2 or fixed

            # 4) Validate via Pydantic (robust)
            try:
                if RootModel is not None:
                    items = HypothesisList.model_validate_json(final_json).root
                else:
                    items = HypothesisList.model_validate_json(final_json).__root__
            except Exception:
                # last resort: try json.loads directly
                try:
                    arr = json.loads(final_json)
                    if isinstance(arr, list):
                        items = arr
                    else:
                        items = []
                except Exception:
                    items = []

        if not items:
            return []

        out: List[Dict[str, Any]] = []
        for i, h in enumerate(items[:max_items], start=1):
            if isinstance(h, dict):
                h_obj = HypothesisItem(**h)
            else:
                h_obj = h

            statement = self._clean_text(h_obj.statement)
            if not statement:
                continue

            evidence_out = []
            for ev in (h_obj.evidence or [])[:3]:
                evidence_out.append({
                    "title": self._clean_text(ev.title),
                    "excerpt": self._clean_text(ev.excerpt),
                })

            why_bullets = [self._clean_text(x) for x in (h_obj.why_bullets or []) if self._clean_text(x)]

            out.append({
                "id": f"H{i}",
                "statement": statement,
                "testability": self._clean_text(h_obj.testability),
                "data": self._clean_text(h_obj.data),
                "success_metric": self._clean_text(h_obj.success_metric),
                "evidence": evidence_out,
                "why_bullets": why_bullets[:6],
            })

        return out

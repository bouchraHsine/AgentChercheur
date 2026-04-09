# agents/terminology_agent.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class TermItem(BaseModel):
    term: str = Field(default="")
    definition: str = Field(default="")
    simple_example: str = Field(default="")
    why_it_matters: str = Field(default="")


class TermsResponse(BaseModel):
    terms: List[TermItem] = Field(default_factory=list)


class TerminologyAgent:
    SYS = (
        "You are a scientific terminology assistant.\n"
        "Extract key technical terms from the given text and explain them.\n"
        "Return ONLY valid JSON matching the schema.\n"
        "No markdown, no extra text.\n"
        "Rules:\n"
        "- Keep definitions short and accurate.\n"
        "- If a term is too generic, skip it.\n"
        "- Do not invent facts not supported by the text.\n"
    )

    def extract(self, llm, text: str, *, max_terms: int = 10, max_output_tokens: int = 550) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"terms": []}

        # Keep prompt bounded
        text_clip = text[:3500]

        user = (
            "TASK:\n"
            f"- Extract up to {max_terms} important technical terms.\n"
            "- For each term provide:\n"
            "  term, definition, simple_example, why_it_matters\n\n"
            "TEXT:\n"
            f"{text_clip}\n"
        )

        parsed: TermsResponse = llm.parse(
            TermsResponse,
            system=self.SYS,
            user=user,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
        )

        out = parsed.model_dump()

        # Post-clean: remove empties and cap max_terms
        cleaned = []
        for t in (out.get("terms") or []):
            if not (t.get("term") or "").strip():
                continue
            cleaned.append({
                "term": (t.get("term") or "").strip(),
                "definition": (t.get("definition") or "").strip(),
                "simple_example": (t.get("simple_example") or "").strip(),
                "why_it_matters": (t.get("why_it_matters") or "").strip(),
            })

        return {"terms": cleaned[:max_terms]}

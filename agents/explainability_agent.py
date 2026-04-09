from typing import List, Dict, Any
import re

from pydantic import BaseModel, Field


class XAIResponse(BaseModel):
    bullets: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ExplainabilityAgent:
    """
    XAI Agent: produit une explication courte + preuves + score de confiance.
    Utilise llm.parse() pour fiabiliser la structure JSON.
    """

    SYSTEM = (
        "You are an Explainable AI (XAI) assistant.\n"
        "You produce short, factual explanations grounded in the provided context.\n"
        "Never invent evidence. If context is insufficient, say so briefly.\n"
        "Return strictly valid JSON matching the required schema."
    )

    def explain(
        self,
        llm,
        *,
        step_name: str,
        decision: str,
        context: str,
        max_bullets: int = 4,
        max_evidence: int = 3,
        max_output_tokens: int = 220,
        fast_mode: bool = True,
        with_confidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Returns dict {bullets:[], evidence:[], confidence:float}
        """

        # On tronque le contexte pour éviter tokens énormes
        ctx = (context or "").strip()
        if fast_mode:
            ctx = ctx[:1800]
        else:
            ctx = ctx[:3500]

        user = f"""
Step: {step_name}

Decision:
{decision}

Context (evidence source):
{ctx}

Task:
Explain why this decision was made, grounded in the context.

Rules:
- bullets: max {max_bullets} items, each <= 18 words
- evidence: max {max_evidence} short quotes/phrases copied from context (<= 18 words each)
- confidence: number between 0 and 1 (higher = better supported by context)
- If context is insufficient, keep bullets short and lower confidence.
- Output MUST be valid JSON ONLY.
"""

        # Schema output
        parsed: XAIResponse = llm.parse(
            XAIResponse,
            system=self.SYSTEM,
            user=user,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
        )

        # Post-cleaning
        bullets = [b.strip() for b in (parsed.bullets or []) if b and b.strip()]
        evidence = [e.strip() for e in (parsed.evidence or []) if e and e.strip()]

        bullets = bullets[:max_bullets]
        evidence = evidence[:max_evidence]

        conf = float(parsed.confidence) if with_confidence else 0.0
        conf = min(max(conf, 0.0), 1.0)

        return {"bullets": bullets, "evidence": evidence, "confidence": conf}

    @staticmethod
    def to_markdown_block(xai: Dict[str, Any]) -> str:
        bullets = xai.get("bullets", [])
        evidence = xai.get("evidence", [])
        conf = xai.get("confidence", None)

        md = []
        md.append("**Why?**")
        if bullets:
            for b in bullets:
                md.append(f"- {b}")
        else:
            md.append("- Insufficient context to justify this decision.")

        if evidence:
            md.append("\n**Evidence:**")
            for ev in evidence:
                md.append(f"> {ev}")

        if conf is not None:
            md.append(f"\n**Confidence:** `{conf:.2f}`")

        return "\n".join(md)

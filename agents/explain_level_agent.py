# agents/explain_level_agent.py
from typing import Literal


class ExplainLevelAgent:
    SYS = (
        "You are a scientific explainer.\n"
        "Explain the provided text clearly for the requested audience level.\n"
        "Output Markdown ONLY (no code fences). Avoid bold markers like **text**.\n"
        "Do not invent missing facts; if unclear, say it briefly.\n"
    )

    def explain(
        self,
        llm,
        text: str,
        *,
        level: Literal["kid", "master", "expert"] = "master",
        max_output_tokens: int = 650,
    ) -> str:
        text = (text or "").strip()
        if not text:
            return "_No text provided._"

        text_clip = text[:4200]

        level_instructions = {
            "kid": (
                "Audience: child (ELI5).\n"
                "- Use very simple words.\n"
                "- 5 to 8 short bullet points.\n"
                "- One tiny analogy.\n"
            ),
            "master": (
                "Audience: Master student.\n"
                "- Explain concepts precisely.\n"
                "- Structure: short intro, key points bullets, and a short conclusion.\n"
                "- Add 2-4 important terms with short definitions.\n"
            ),
            "expert": (
                "Audience: expert.\n"
                "- Focus on assumptions, limitations, methodology implications.\n"
                "- Add a short 'Potential pitfalls' section.\n"
                "- Keep it concise but technical.\n"
            ),
        }

        user = (
            f"{level_instructions.get(level, level_instructions['master'])}\n"
            "TEXT:\n"
            f"{text_clip}\n"
        )

        md = llm.generate(
            system=self.SYS,
            user=user,
            max_output_tokens=max_output_tokens,
            temperature=0.2 if level != "kid" else 0.1,
        )

        # Soft cleanup: remove markdown bold if model adds it
        md = (md or "").replace("**", "").strip()
        return md if md else "_Empty output._"

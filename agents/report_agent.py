import json

class ReportAgent:
    SYS = (
        "You are a senior research writer.\n"
        "Write a COMPLETE academic report in Markdown.\n"
        "You MUST follow the required structure exactly.\n"
        "Do NOT skip sections. Do NOT start in the middle.\n"
        "End with <<<END>>>.\n"
    )

    def build(
        self,
        llm,
        topic,
        articles,
        comparison_md,
        hypotheses_md,
        experiments_md,
        max_tokens: int = 0,
    ):
        articles_small = [
            {"title": (a.get("title") or ""), "year": a.get("year"), "url": a.get("url"), "doi": a.get("doi")}
            for a in (articles or [])
        ]

        user = (
            f"# Topic\n{topic}\n\n"
            "You will write the report STRICTLY using the following ordered sections.\n"
            "Start EXACTLY from Section 1.\n\n"
            "## 1. Title\n"
            "## 2. Abstract\n"
            "## 3. Introduction\n"
            "## 4. Related Work Summary\n"
            "## 5. Comparative Synthesis\n"
            "## 6. Hypotheses\n"
            "## 7. Experimental Plan\n"
            "## 8. Conclusion\n"
            "## 9. References\n\n"
            "MANDATORY RULES:\n"
            "- Do NOT include any 'Confidence' lines.\n"
            "- Do NOT invent author names if not provided.\n"
            "- End the document with <<<END>>>.\n\n"
            "INPUT MATERIAL:\n\n"
            f"ARTICLES:\n{json.dumps(articles_small, ensure_ascii=False, indent=2)}\n\n"
            f"COMPARISON:\n{comparison_md}\n\n"
            f"HYPOTHESES:\n{hypotheses_md}\n\n"
            f"EXPERIMENTS:\n{experiments_md}\n"
        )

        return llm.generate_long_markdown(
            system=self.SYS,
            user=user,
            finish_token="<<<END>>>",
            temperature=0.2,
            chunk_tokens=900,
            max_chunks=12,
        )

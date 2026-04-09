class ComparatorAgent:
    SYS = (
        "You are an academic writer. Produce a COMPLETE markdown comparison.\n"
        "Do not use placeholders. End with <<<END>>>."
    )

    def compare(self, llm, analyses, max_tokens: int = 0):
        user = (
            "Write a detailed Markdown comparison table and narrative synthesis.\n"
            "Include: methods, datasets, metrics, contributions, limitations.\n"
            "End with <<<END>>>.\n\n"
            f"ANALYSES_JSON:\n{analyses}"
        )
        return llm.generate_long_markdown(system=self.SYS, user=user, finish_token="<<<END>>>", max_chunks=8)

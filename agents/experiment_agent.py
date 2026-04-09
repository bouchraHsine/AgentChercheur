class ExperimentAgent:
    SYS = (
        "You are an experimental designer. Produce COMPLETE experiment plans in Markdown.\n"
        "End with <<<END>>>."
    )

    def plan(self, llm, topic: str, hypotheses_md: str, max_tokens: int = 0):
        user = (
            f"Topic: {topic}\n\n"
            "Design experiments to test the hypotheses below.\n"
            "Include: protocol, datasets/materials, metrics, baselines, ablations, expected results.\n"
            "End with <<<END>>>.\n\n"
            f"HYPOTHESES:\n{hypotheses_md}"
        )
        return llm.generate_long_markdown(system=self.SYS, user=user, finish_token="<<<END>>>", max_chunks=8)

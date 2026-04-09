import os
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Type

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass
class LLMConfig:
    api_key: str
    model: str

class OpenAILLM:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY manquante. Ajoute-la dans .env à la racine du projet.")
        self.cfg = LLMConfig(api_key=api_key, model=model)
        self.client = OpenAI(api_key=self.cfg.api_key)

    def generate(self, system: str, user: str, max_output_tokens: int = 600, temperature: float = 0.2) -> str:
        last_err = None
        for attempt in range(3):
            try:
                resp = self.client.responses.create(
                    model=self.cfg.model,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
                return (resp.output_text or "").strip()
            except Exception as e:
                last_err = e
                time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"OAI generate failed: {last_err}")

    def parse(
        self,
        schema: Type[BaseModel],
        system: str,
        user: str,
        max_output_tokens: int = 450,
        temperature: float = 0.0,
    ) -> BaseModel:
        last_err = None
        for attempt in range(3):
            try:
                resp = self.client.responses.parse(
                    model=self.cfg.model,
                    input=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    text_format=schema,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
                return resp.output_parsed
            except Exception as e:
                last_err = e
                time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"OAI parse failed: {last_err}")

    @staticmethod
    def _looks_like_mid_document(text: str) -> bool:
        t = (text or "").lstrip()
        if not t:
            return False
        if re.match(r"^(?:#{1,3}\s*)?(?:4|5|6|7|8|9|10)\.", t):
            return True
        if t.lower().startswith(("follow-up", "datasets", "materials", "protocol", "expected results")):
            return True
        return False

    def generate_long_markdown(
        self,
        system: str,
        user: str,
        *,
        finish_token: str = "<<<END>>>",
        temperature: float = 0.2,
        chunk_tokens: int = 900,
        max_chunks: int = 10,
    ) -> str:
        parts = []
        accumulated = ""
        prompt = user
        restarted = False

        for i in range(max_chunks):
            chunk = self.generate(
                system=system,
                user=prompt,
                max_output_tokens=chunk_tokens,
                temperature=temperature,
            )

            if not chunk:
                break

            if i == 0 and (not restarted) and self._looks_like_mid_document(chunk):
                restarted = True
                prompt = (
                    "RESTART from the VERY BEGINNING.\n"
                    "You started in the middle previously. This is not allowed.\n"
                    f"Your final output MUST end with {finish_token}.\n\n"
                    f"{user}"
                )
                parts = []
                accumulated = ""
                continue

            parts.append(chunk)
            accumulated = "\n\n".join(parts)

            if finish_token in chunk:
                accumulated = accumulated.replace(finish_token, "").strip()
                return accumulated

            tail = accumulated[-7000:]
            prompt = (
                "Continue EXACTLY where you stopped.\n"
                "- Do NOT repeat any previous sentences.\n"
                "- Keep the same formatting.\n"
                f"- Your final output MUST end with {finish_token}.\n\n"
                "Text already written (do not repeat):\n"
                f"{tail}\n\n"
                "Continue now:"
            )

        return accumulated.strip()

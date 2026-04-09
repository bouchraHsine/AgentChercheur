import os
import time
import requests
from typing import List, Dict, Any
from core.utils import normalize_ws, contains_all_keywords, overlap_score

class SearchAgent:
    BASE = "https://api.openalex.org/works"

    def __init__(self):
        self.mailto = os.getenv("OPENALEX_MAILTO", "").strip()

    def _abstract_from_inverted_index(self, inverted_index: Dict[str, List[int]]) -> str:
        if not inverted_index:
            return ""
        positions = []
        for word, idxs in inverted_index.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort(key=lambda x: x[0])
        return " ".join([w for _, w in positions])

    def search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        params = {"search": query, "per_page": min(max(limit, 1), 200)}
        if self.mailto:
            params["mailto"] = self.mailto

        last_err = None
        for attempt in range(3):
            try:
                r = requests.get(self.BASE, params=params, timeout=25)
                r.raise_for_status()
                data = r.json()
                res = []
                for w in data.get("results", []):
                    abstract = ""
                    inv = w.get("abstract_inverted_index")
                    if inv:
                        abstract = self._abstract_from_inverted_index(inv)

                    primary = w.get("primary_location") or {}
                    oa = (w.get("open_access") or {})

                    doi = w.get("doi")
                    doi_url = f"https://doi.org/{doi.replace('https://doi.org/','')}" if doi else ""

                    res.append({
                        "id": w.get("id"),
                        "title": normalize_ws(w.get("title") or ""),
                        "year": w.get("publication_year"),
                        "authors": [a.get("author", {}).get("display_name") for a in (w.get("authorships") or []) if a.get("author")],
                        "concepts": [c.get("display_name") for c in (w.get("concepts") or [])[:6] if c.get("display_name")],
                        "abstract": normalize_ws(abstract),
                        "url": w.get("id"),
                        "doi": doi_url,
                        "oa_url": oa.get("oa_url") or primary.get("pdf_url") or "",
                        "landing_page": primary.get("landing_page_url") or "",
                        "is_oa": bool(oa.get("is_oa")),
                    })
                return res
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"OpenAlex search failed: {last_err}")

    def select_best(
        self,
        topic: str,
        articles: List[Dict[str, Any]],
        final_k: int = 3,
        required_keywords: List[str] = None,
        strict: bool = True,
    ) -> List[Dict[str, Any]]:
        required_keywords = required_keywords or []
        seen = set()
        uniq = []
        for a in articles:
            pid = a.get("id") or a.get("title")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            uniq.append(a)

        scored = []
        for a in uniq:
            text = f"{a.get('title','')} {a.get('abstract','')} {' '.join(a.get('concepts',[]))}"
            if required_keywords and not contains_all_keywords(text, required_keywords):
                continue
            score = overlap_score(topic, text)
            if strict and score < 0.20:
                continue
            scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:final_k]]

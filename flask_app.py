from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
import hashlib
import re
from datetime import datetime
import markdown  # pip install markdown

from core.orchestrator import Orchestrator
from core.utils import load_json, read_text, clear_outputs, save_json, save_text

# ✅ NEW agents
from agents.terminology_agent import TerminologyAgent
from agents.explain_level_agent import ExplainLevelAgent

app = Flask(__name__)
app.secret_key = "change_me_secret_key"

orch = Orchestrator()

# ✅ Instantiate new agents (independent from pipeline)
term_agent = TerminologyAgent()
explain_agent = ExplainLevelAgent()

RESULTS_PER_QUERY = 15

SECTIONS = ["Article", "Comparaison", "Hypothèses", "Experiments", "Report"]
CACHE_META_PATH = "outputs/last_run_meta.json"


def parse_required(text: str):
    return [x.strip() for x in (text or "").split(",") if x.strip()]


def _sanitize_md(md_text: str) -> str:
    if not md_text:
        return ""

    md_text = re.sub(
        r"(?im)^\s*(?:\*\*|__)?\s*confidence\s*(?:\*\*|__)?\s*:\s*.*$",
        "",
        md_text,
    )
    md_text = re.sub(
        r"(?im)^\s*#{1,6}\s*(?:\*\*|__)?\s*confidence\s*(?:\*\*|__)?\s*$",
        "",
        md_text,
    )
    md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()
    return md_text


def md_to_html(md_text: str) -> str:
    md_text = _sanitize_md(md_text)
    return markdown.markdown(
        md_text or "",
        extensions=["fenced_code", "tables", "toc", "sane_lists", "nl2br"],
    )


def md_to_clean_html(md_text: str) -> str:
    html = md_to_html(md_text)
    html = re.sub(r"</?strong>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"</?em>", "", html, flags=re.IGNORECASE)
    return html


def make_cache_key(topic: str, mode: str, final_papers: int, required_keywords: str, strict_filter: bool) -> str:
    payload = json.dumps(
        {
            "topic": topic.strip(),
            "mode": mode,
            "final_papers": int(final_papers),
            "required_keywords": (required_keywords or "").strip(),
            "strict_filter": bool(strict_filter),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_is_valid(cache_key: str) -> bool:
    if not os.path.exists(CACHE_META_PATH):
        return False
    try:
        meta = load_json(CACHE_META_PATH, default={})
        if meta.get("cache_key") != cache_key:
            return False
        needed = [
            "outputs/articles.json",
            "outputs/comparison.md",
            "outputs/hypotheses.md",
            "outputs/experiments.md",
            "outputs/report.md",
        ]
        return all(os.path.exists(p) for p in needed)
    except Exception:
        return False


def save_cache_meta(cache_key: str, payload: dict):
    meta = {
        "cache_key": cache_key,
        "payload": payload,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(CACHE_META_PATH, meta)


def get_section_content(section: str):
    extra = {"pdf_exists": os.path.exists("outputs/report.pdf")}

   
    if section == "Article":
        arts = load_json("outputs/articles.json", default=[])
        return {"articles": arts, "html": None, "extra": extra}

    path_map = {
        "Comparaison": "outputs/comparison.md",
        "Hypothèses": "outputs/hypotheses.md",
        "Experiments": "outputs/experiments.md",
        "Report": "outputs/report.md",
    }
    md = read_text(path_map.get(section, ""), "")

    if section == "Report":
        md_stripped = (md or "").lstrip()
        if md_stripped and not md_stripped.startswith("#"):
            md = f"# Report\n\n{md}"

    if not (md or "").strip():
        if section == "Hypothèses":
            md = "_Aucune hypothèse détectée. Lance **Full pipeline** puis reviens ici._"
        else:
            md = "_Aucun contenu._"

    return {"articles": None, "html": md_to_html(md), "extra": extra}


@app.get("/")
def index():
    section = request.args.get("section", "Article")
    if section not in SECTIONS:
        section = "Article"

    content = get_section_content(section)

    ui = {
        "topic": request.args.get("topic", ""),
        "mode": request.args.get("mode", "Search only"),
        "final_papers": int(request.args.get("final_papers", 3)),
        "required_keywords": request.args.get("required_keywords", ""),
        "strict_filter": request.args.get("strict_filter", "1") == "1",
        "clear_old_result": request.args.get("clear_old_result", "0") == "1",
    }

    return render_template("index.html", section=section, sections=SECTIONS, content=content, ui=ui)


@app.post("/run")
def run_pipeline():
    topic = request.form.get("topic", "").strip()
    mode = request.form.get("mode", "Search only")
    final_papers = int(request.form.get("final_papers", 3))
    required_keywords = request.form.get("required_keywords", "")
    strict_filter = request.form.get("strict_filter") == "on"
    clear_old_result = request.form.get("clear_old_result") == "on"
    section = request.form.get("section", "Article")

    if not topic:
        flash("Veuillez saisir un Scientific topic.", "warning")
        return redirect(url_for("index", section=section))

    cache_key = make_cache_key(topic, mode, final_papers, required_keywords, strict_filter)
    payload = {
        "topic": topic,
        "mode": mode,
        "final_papers": final_papers,
        "required_keywords": required_keywords,
        "strict_filter": strict_filter,
    }

    if clear_old_result:
        clear_outputs(keep_pdfs=True)
    else:
        if mode == "Full pipeline" and cache_is_valid(cache_key):
            flash("Résultat déjà généré (cache). Aucune exécution relancée.", "success")
            return redirect(url_for(
                "index",
                section=section,
                topic=topic,
                mode=mode,
                final_papers=final_papers,
                required_keywords=required_keywords,
                strict_filter="1" if strict_filter else "0",
                clear_old_result="0",
            ))

    try:
        if mode == "Search only":
            plan = orch.planner.plan(topic)
            pool = []
            for q in plan["queries"]:
                pool.extend(orch.searcher.search(q, limit=int(RESULTS_PER_QUERY)))

            selected = orch.searcher.select_best(
                topic=topic,
                articles=pool,
                final_k=int(final_papers),
                required_keywords=parse_required(required_keywords),
                strict=bool(strict_filter),
            )
            save_json("outputs/articles.json", selected)
            flash("Done. Articles updated.", "success")

        else:
            orch.run(
                topic=topic,
                results_per_query=int(RESULTS_PER_QUERY),
                final_k=int(final_papers),
                required_keywords=parse_required(required_keywords),
                strict_filter=bool(strict_filter),
            )
            save_cache_meta(cache_key, payload)
            flash("Done. All sections updated.", "success")

    except Exception as e:
        flash(f"Erreur: {e}", "danger")

    return redirect(url_for(
        "index",
        section=section,
        topic=topic,
        mode=mode,
        final_papers=final_papers,
        required_keywords=required_keywords,
        strict_filter="1" if strict_filter else "0",
        clear_old_result="1" if clear_old_result else "0",
    ))


@app.post("/api/why", endpoint="api_why_v2")
def api_why_v2():
    try:
        data = request.get_json(force=True) or {}
        kind = (data.get("kind") or "").strip().lower()
        topic = (data.get("topic") or "").strip()

        if kind == "article":
            title = (data.get("title") or "").strip()
            abstract = (data.get("abstract") or "").strip()
            if not title and not abstract:
                return jsonify({"ok": False, "error": "Missing article content"}), 400

            prompt = (
                "Explain WHY this paper is relevant to the given topic.\n"
                "Return 3 to 6 bullet points.\n"
                "Do NOT include any Confidence line.\n"
                "Do NOT use markdown bold (**text**).\n"
                "Keep it short and concrete.\n\n"
                f"TOPIC: {topic}\n"
                f"TITLE: {title}\n"
                f"ABSTRACT: {abstract}\n"
            )

        elif kind == "hypothesis":
            hyp = (data.get("hypothesis") or "").strip()
            if not hyp:
                return jsonify({"ok": False, "error": "Missing hypothesis"}), 400

            prompt = (
                "Explain WHY this hypothesis is reasonable for the topic.\n"
                "Format:\n"
                "- Why (3-5 bullet points)\n"
                "- Evidence (2-4 short items)\n"
                "Do NOT include any Confidence line.\n"
                "Do NOT use markdown bold (**text**).\n\n"
                f"TOPIC: {topic}\n"
                f"HYPOTHESIS: {hyp}\n"
            )
        else:
            return jsonify({"ok": False, "error": "Invalid kind"}), 400

        raw = orch.llm.generate(
            system="You are a helpful research assistant. Be clear and concise.",
            user=prompt,
            max_output_tokens=450,
            temperature=0.2,
        )

        html = md_to_clean_html(raw)
        return jsonify({"ok": True, "html": html})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/hypotheses")
def api_hypotheses():
    md = read_text("outputs/hypotheses.md", "")
    md = _sanitize_md(md)

    items = []
    for line in (md or "").splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line.strip())
        if m:
            items.append(m.group(2).strip())

    return jsonify({"ok": True, "items": items})


# ============================================================
# ✅ Explain Like I'm 5 / Master / Expert
# ============================================================
@app.post("/api/explain")
def api_explain():
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text") or "").strip()
        level = (data.get("level") or "master").strip().lower()

        if level not in ("kid", "master", "expert"):
            level = "master"

        if not text:
            return jsonify({"ok": False, "error": "Empty text"}), 400

        md = explain_agent.explain(orch.llm, text, level=level, max_output_tokens=650)
        save_text("outputs/explain_last.md", md)

        return jsonify({"ok": True, "html": md_to_clean_html(md)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ============================================================
# ✅ NEW: Explain ONLY the selected word/term (no other terms!)
# ============================================================
@app.post("/api/term_one")
def api_term_one():
    try:
        data = request.get_json(force=True) or {}
        term = (data.get("term") or "").strip()
        context = (data.get("context") or "").strip()

        if not term:
            return jsonify({"ok": False, "error": "Empty term"}), 400

        # Important: force the model to ONLY explain this term
        prompt = (
            "You are a Scientific Terminology Assistant.\n"
            "Task: Explain ONLY the target term below. Do NOT explain any other term.\n"
            "If CONTEXT is provided, use it only to disambiguate meaning.\n\n"
            "Output format (plain text or markdown, no bold):\n"
            "Term: <term>\n"
            "Definition: <1-2 lines>\n"
            "Simple explanation: <2-4 lines>\n"
            "Example: <1 short example>\n"
            "In this paper/context: <1 line about how it is used>\n\n"
            f"TARGET TERM: {term}\n"
        )
        if context:
            prompt += f"\nCONTEXT:\n{context}\n"

        raw = orch.llm.generate(
            system="Be precise, short, and follow the format strictly.",
            user=prompt,
            max_output_tokens=350,
            temperature=0.2,
        )

        md = raw.strip() if raw else "_No output._"
        save_text("outputs/term_one_last.md", md)
        return jsonify({"ok": True, "html": md_to_clean_html(md)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ============================================================
# ✅ Terminology (multi-terms) extraction for long selection
# ============================================================
@app.post("/api/terms")
def api_terms():
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text") or "").strip()
        max_terms = int(data.get("max_terms") or 8)

        max_terms = max(3, min(max_terms, 20))
        if not text:
            return jsonify({"ok": False, "error": "Empty text"}), 400

        out = term_agent.extract(orch.llm, text, max_terms=max_terms, max_output_tokens=650)
        terms = out.get("terms") or []

        if not terms:
            md = "_No technical terms detected._"
        else:
            lines = ["# Terminology\n"]
            for i, t in enumerate(terms, start=1):
                lines.append(f"{i}. {t.get('term','')}")
                if t.get("definition"):
                    lines.append(f"   - Definition: {t['definition']}")
                if t.get("simple_example"):
                    lines.append(f"   - Example: {t['simple_example']}")
                if t.get("why_it_matters"):
                    lines.append(f"   - Why it matters: {t['why_it_matters']}")
                lines.append("")
            md = "\n".join(lines).strip()

        save_text("outputs/terms_last.md", md)
        save_json("outputs/terms_last.json", {"terms": terms})

        return jsonify({"ok": True, "html": md_to_clean_html(md), "terms": terms})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

import json
import re
from pathlib import Path
from typing import Any, List

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUT_DIR = ROOT / "outputs"

def ensure_dirs():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def save_json(path: str, obj: Any):
    ensure_dirs()
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def load_json(path: str, default: Any = None):
    p = ROOT / path
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_text(path: str, text: str):
    ensure_dirs()
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text or "", encoding="utf-8")

def read_text(path: str, default: str = "") -> str:
    p = ROOT / path
    if not p.exists():
        return default
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default

def clear_outputs(keep_pdfs: bool = True):
    ensure_dirs()
    for ext in ("*.md", "*.json", "*.txt"):
        for f in OUT_DIR.glob(ext):
            try:
                f.unlink()
            except Exception:
                pass

def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def contains_all_keywords(text: str, required: List[str]) -> bool:
    t = (text or "").lower()
    return all(k.lower() in t for k in required)

def tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    parts = [p.strip() for p in s.split() if len(p.strip()) >= 3]
    return parts

def overlap_score(topic: str, text: str) -> float:
    a = set(tokenize(topic))
    b = set(tokenize(text))
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    return inter / max(1, len(a))

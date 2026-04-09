import base64
import requests
import streamlit as st
from core.utils import PDF_DIR, ensure_dirs


st.set_page_config(
    page_title="PDF Viewer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
      section[data-testid="stSidebar"] { display:none !important; }
      div[data-testid="stSidebarCollapsedControl"] { display:none !important; }

      .block-container { max-width: 1280px; padding-top: 1.2rem; padding-bottom: 2rem; }

      .stApp {
        background: linear-gradient(180deg, #0B1020 0%, #070A14 100%);
        color: #E7EAF0;
      }

      header[data-testid="stHeader"] { background: transparent; }
      footer { visibility: hidden; }

      .muted { color: rgba(231,234,240,0.60); }

      div[data-testid="stVerticalBlockBorderWrapper"]{
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 14px !important;
      }

      .stButton > button, a[data-testid="stLinkButton"]{
        height: 40px !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        background: rgba(255,255,255,0.04) !important;
        color: #E7EAF0 !important;
        font-weight: 600 !important;
      }
      .stButton > button:hover, a[data-testid="stLinkButton"]:hover{
        background: rgba(255,255,255,0.07) !important;
        border-color: rgba(255,255,255,0.18) !important;
      }
      .primary button{
        background: #2563EB !important;
        border-color: rgba(37,99,235,0.6) !important;
      }
    </style>
    """,
    unsafe_allow_html=True
)

ensure_dirs()

st.markdown("# PDF Viewer")

pdf_url = st.session_state.get("pdf_url", "")
title = st.session_state.get("pdf_title", "Document")

if not pdf_url:
    st.warning("Aucun PDF sélectionné. Retourne à la page principale et clique sur 'View'.")
    st.stop()

with st.container(border=True):
    st.markdown(f"### {title}")
    st.markdown('<div class="muted">Source:</div>', unsafe_allow_html=True)
    st.code(pdf_url)

    safe_name = "".join([c for c in (title or "paper") if c.isalnum() or c in (" ", "-", "_")]).strip().replace(" ", "_")
    local_path = PDF_DIR / f"{safe_name}.pdf"

    c1, c2, c3 = st.columns([1, 1, 1], gap="small")
    with c1:
        st.markdown('<div class="primary">', unsafe_allow_html=True)
        cache_btn = st.button("Cache locally", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    c2.link_button("Open in new tab", pdf_url, use_container_width=True)
    back = c3.button("Back", use_container_width=True)

    if back:
        st.switch_page("app.py")

    if cache_btn:
        try:
            r = requests.get(pdf_url, timeout=30)
            r.raise_for_status()
            local_path.write_bytes(r.content)
            st.success(f"Saved: {local_path}")
        except Exception as e:
            st.error(f"Download failed: {e}")

with st.container(border=True):
    if local_path.exists():
        pdf_bytes = local_path.read_bytes()
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        iframe = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="900" type="application/pdf"></iframe>'
        st.components.v1.html(iframe, height=920, scrolling=True)
    else:
        st.markdown('<div class="muted">Tip: use "Cache locally" if the browser blocks PDF embedding.</div>', unsafe_allow_html=True)
        iframe = f'<iframe src="{pdf_url}" width="100%" height="900"></iframe>'
        st.components.v1.html(iframe, height=920, scrolling=True)

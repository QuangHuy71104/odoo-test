"""
KMS Team 02 Week 12 - Streamlit chat interface.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from rag_engine import VALID_ROLES, ask, resolve_persist_dir


def _provider_index(provider: str) -> int:
    options = ["ollama", "mock"]
    return options.index(provider) if provider in options else 0


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return

    with st.expander("Sources", expanded=False):
        for index, source in enumerate(sources, start=1):
            score = source.get("score")
            score_text = "n/a" if score is None else f"{score:.4f}"
            st.markdown(
                f"**{index}. {source.get('title', 'Untitled')}**  \n"
                f"`{source.get('workspace_dimension', 'unknown')}` | "
                f"`{source.get('access_role', 'unknown')}` | score `{score_text}`"
            )
            st.caption(source.get("snippet", ""))


st.set_page_config(page_title="Triple H & T Knowledge Assistant", layout="wide")

st.title("Triple H & T Knowledge Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Runtime")
    user_role = st.selectbox("Access role", sorted(VALID_ROLES), index=0)
    top_k = st.slider("Top-K", min_value=1, max_value=8, value=4)
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

    env_provider = os.getenv("LLM_PROVIDER", "mock").lower()
    provider = st.selectbox(
        "LLM provider",
        ["ollama", "mock"],
        index=_provider_index(env_provider),
    )
    model = st.text_input("Model override", value="")

    db_path = resolve_persist_dir()
    st.text_input("Vector DB", value=str(db_path), disabled=True)
    if not Path(db_path).exists():
        st.warning("Vector DB not found. Run `python ingest_to_vector.py` first.")

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("fallback_reason"):
            st.warning(message["fallback_reason"])
        render_sources(message.get("sources", []))

prompt = st.chat_input("Ask a corporate knowledge question")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving context"):
            try:
                response = ask(
                    question=prompt,
                    user_role=user_role,
                    top_k=top_k,
                    temperature=temperature,
                    provider=provider,
                    model=model.strip() or None,
                )
                st.markdown(response.answer)
                if response.fallback_reason:
                    st.warning(response.fallback_reason)
                render_sources(response.sources)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response.answer,
                        "fallback_reason": response.fallback_reason,
                        "sources": response.sources,
                    }
                )
            except Exception as exc:
                error = f"Unable to generate an answer: {exc}"
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": error})

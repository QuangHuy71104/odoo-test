"""
KMS Team 02 Week 12 - Retrieval-Augmented Generation engine.

The engine loads the Week 11 Chroma vector store, applies role-based metadata
filters, builds the BA-approved prompt, and sends the grounded request to an LLM.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # Allows guardrail tests before dependencies are installed.
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "kms_collection")
DEFAULT_TOP_K = 4
DEFAULT_TEMPERATURE = 0.2
VALID_ROLES = {"public", "it_staff", "hr_manager"}
FALLBACK_ANSWER = (
    "I do not have enough approved corporate knowledge context to answer that. "
    "Please check the official Odoo Knowledge base or ask the responsible owner."
)

MASTER_SYSTEM_PROMPT = """You are the internal Knowledge Management chatbot for KMS Team 02.

Persona:
- Be factual, concise, and professional.
- Answer in the same language as the user when possible.
- Use only the approved corporate context provided in the prompt.

Grounding rules:
1. Do not invent facts, procedures, prices, people, salaries, vendors, or policies.
2. If the context is missing, irrelevant, or not specific enough, answer with the fallback message.
3. Respect the user's access role. Do not reveal HR-only or IT-only content unless it appears in the approved retrieved context for that role.
4. Do not answer competitor-comparison requests, credential/API-key requests, or restricted salary/payroll questions for unauthorized roles.
5. Include source titles when giving a substantive answer.

Fallback message:
I do not have enough approved corporate knowledge context to answer that. Please check the official Odoo Knowledge base or ask the responsible owner.
"""

USER_PROMPT_TEMPLATE = """User role: {user_role}
Question: {question}

Approved retrieved context:
{context}

Write the final answer. If you cannot answer from the approved retrieved context, use the fallback message exactly.
"""

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "so", "that", "the", "this",
    "to", "we", "what", "when", "where", "who", "why", "with", "you",
}


@dataclass
class Source:
    title: str
    access_role: str
    workspace_dimension: str
    score: float | None
    snippet: str


@dataclass
class RAGResponse:
    answer: str
    fallback: bool
    fallback_reason: str
    provider: str
    sources: list[dict]
    context: str


def _path_from_env(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None
    path = Path(raw_value)
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


def resolve_persist_dir() -> Path:
    configured = _path_from_env(os.getenv("CHROMA_PERSIST_DIR"))
    local = BASE_DIR / "chroma_db"
    if configured and configured.exists():
        return configured

    if local.exists():
        return local

    week11_store = BASE_DIR.parent / "KMS_TEAM_02_W11" / "chroma_db"
    default_configured = configured is None or configured == local.resolve()
    if default_configured and week11_store.exists():
        return week11_store

    return configured or local


def get_embedding_function():
    provider = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers")
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=os.getenv("HF_EMBEDDING_MODEL", "all-MiniLM-L6-v2"))


def load_vector_db(persist_dir: str | Path | None = None):
    from langchain_chroma import Chroma

    db_path = Path(persist_dir).resolve() if persist_dir else resolve_persist_dir()
    if not db_path.exists():
        raise FileNotFoundError(
            f"ChromaDB folder not found: {db_path}. Run ingest_to_vector.py first."
        )

    return Chroma(
        persist_directory=str(db_path),
        collection_name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )


def role_filter(user_role: str) -> dict:
    role = user_role if user_role in VALID_ROLES else "public"
    if role == "it_staff":
        return {"$or": [{"access_role": "it_staff"}, {"access_role": "public"}]}
    if role == "hr_manager":
        return {"$or": [{"access_role": "hr_manager"}, {"access_role": "public"}]}
    return {"access_role": "public"}


def detect_guardrail_violation(question: str, user_role: str) -> str:
    q = question.lower()

    competitor_terms = [
        "competitor comparison",
        "compare with competitor",
        "compare us to",
        "rival company",
    ]
    if any(term in q for term in competitor_terms):
        return "Competitor-comparison requests are outside the chatbot boundary."

    secret_terms = ["api key", "password", "secret token", "private key", "database password"]
    reveal_terms = ["show", "reveal", "print", "tell me", "give me", "what is"]
    if any(secret in q for secret in secret_terms) and any(verb in q for verb in reveal_terms):
        return "Credential and secret disclosure requests are not allowed."

    hr_restricted_terms = [
        "salary",
        "payroll",
        "salary history",
        "performance warning",
        "employee hr file",
        "employee discipline record",
    ]
    if user_role != "hr_manager" and any(term in q for term in hr_restricted_terms):
        return "HR salary, payroll, and personnel records require the hr_manager role."

    return ""


def _dedupe_docs(docs_with_scores: Iterable[tuple]) -> list[tuple]:
    seen = set()
    unique = []
    for doc, score in docs_with_scores:
        title = doc.metadata.get("title", "")
        marker = (title, doc.page_content[:160])
        if marker in seen:
            continue
        seen.add(marker)
        unique.append((doc, score))
    return unique


def retrieve_context(
    question: str,
    user_role: str = "public",
    top_k: int = DEFAULT_TOP_K,
    min_relevance: float | None = None,
    persist_dir: str | Path | None = None,
) -> list[tuple]:
    db = load_vector_db(persist_dir)
    safe_top_k = max(1, min(int(top_k), 10))
    search_filter = role_filter(user_role)
    docs_with_scores = db.similarity_search_with_relevance_scores(
        question,
        k=safe_top_k * 3,
        filter=search_filter,
    )
    unique = _dedupe_docs(docs_with_scores)

    threshold = (
        float(os.getenv("RAG_MIN_RELEVANCE", "0.0"))
        if min_relevance is None
        else float(min_relevance)
    )
    if threshold > 0:
        unique = [(doc, score) for doc, score in unique if score is None or score >= threshold]

    return unique[:safe_top_k]


def build_context(docs_with_scores: list[tuple], max_chars: int | None = None) -> tuple[str, list[Source]]:
    limit = max_chars or int(os.getenv("RAG_MAX_CONTEXT_CHARS", "6000"))
    blocks = []
    sources: list[Source] = []
    used_chars = 0

    for index, (doc, score) in enumerate(docs_with_scores, start=1):
        metadata = doc.metadata
        title = metadata.get("title", "Untitled")
        access_role = metadata.get("access_role", "unknown")
        workspace = metadata.get("workspace_dimension", "unknown")
        content = re.sub(r"\s+", " ", doc.page_content).strip()
        block = (
            f"[Source {index}]\n"
            f"Title: {title}\n"
            f"Workspace: {workspace}\n"
            f"Access role: {access_role}\n"
            f"Content: {content}\n"
        )

        if used_chars + len(block) > limit:
            remaining = max(0, limit - used_chars)
            if remaining > 250:
                blocks.append(block[:remaining] + "\n[Context truncated]\n")
            break

        blocks.append(block)
        used_chars += len(block)
        sources.append(
            Source(
                title=title,
                access_role=access_role,
                workspace_dimension=workspace,
                score=round(float(score), 4) if score is not None else None,
                snippet=content[:240],
            )
        )

    return "\n".join(blocks).strip(), sources


def build_messages(question: str, user_role: str, context: str) -> list[dict]:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        user_role=user_role,
        question=question,
        context=context or "NO APPROVED CONTEXT RETRIEVED.",
    )
    return [
        {"role": "system", "content": MASTER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _call_openai(messages: list[dict], temperature: float, model: str | None) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your-"):
        raise RuntimeError("OPENAI_API_KEY is not configured. Use LLM_PROVIDER=mock for local demo.")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _call_ollama(messages: list[dict], temperature: float, model: str | None) -> str:
    import requests

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    response = requests.post(
        f"{base_url}/api/chat",
        json={
            "model": model or os.getenv("OLLAMA_MODEL", "llama3.1"),
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def _mock_answer(question: str, sources: list[Source]) -> str:
    if not sources:
        return FALLBACK_ANSWER

    source_titles = ", ".join(source.title for source in sources[:3])
    first = sources[0]
    return (
        "Mock grounded answer: based on the retrieved corporate knowledge, "
        f"the most relevant source is '{first.title}'. "
        f"Key context: {first.snippet}...\n\nSources: {source_titles}"
    )


def generate_answer(
    question: str,
    user_role: str,
    context: str,
    sources: list[Source],
    temperature: float = DEFAULT_TEMPERATURE,
    provider: str | None = None,
    model: str | None = None,
) -> tuple[str, str]:
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
    messages = build_messages(question, user_role, context)

    if selected_provider == "openai":
        return _call_openai(messages, temperature, model), selected_provider
    if selected_provider == "ollama":
        return _call_ollama(messages, temperature, model), selected_provider
    if selected_provider == "mock":
        return _mock_answer(question, sources), selected_provider

    raise ValueError("LLM_PROVIDER must be one of: openai, ollama, mock")


def ask(
    question: str,
    user_role: str = "public",
    top_k: int = DEFAULT_TOP_K,
    temperature: float = DEFAULT_TEMPERATURE,
    provider: str | None = None,
    model: str | None = None,
    persist_dir: str | Path | None = None,
) -> RAGResponse:
    clean_question = question.strip()
    clean_role = user_role if user_role in VALID_ROLES else "public"
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()

    if not clean_question:
        return RAGResponse(
            answer=FALLBACK_ANSWER,
            fallback=True,
            fallback_reason="Empty question.",
            provider=selected_provider,
            sources=[],
            context="",
        )

    violation = detect_guardrail_violation(clean_question, clean_role)
    if violation:
        return RAGResponse(
            answer=FALLBACK_ANSWER,
            fallback=True,
            fallback_reason=violation,
            provider=selected_provider,
            sources=[],
            context="",
        )

    docs_with_scores = retrieve_context(
        question=clean_question,
        user_role=clean_role,
        top_k=top_k,
        persist_dir=persist_dir,
    )
    context, source_objects = build_context(docs_with_scores)

    if not source_objects:
        return RAGResponse(
            answer=FALLBACK_ANSWER,
            fallback=True,
            fallback_reason="No approved context was retrieved for this role.",
            provider=selected_provider,
            sources=[],
            context="",
        )

    answer, actual_provider = generate_answer(
        question=clean_question,
        user_role=clean_role,
        context=context,
        sources=source_objects,
        temperature=temperature,
        provider=selected_provider,
        model=model,
    )
    fallback = FALLBACK_ANSWER in answer

    return RAGResponse(
        answer=answer,
        fallback=fallback,
        fallback_reason="LLM returned fallback message." if fallback else "",
        provider=actual_provider,
        sources=[asdict(source) for source in source_objects],
        context=context,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a KMS Team 02 RAG query.")
    parser.add_argument("question", help="Question to ask the RAG chatbot")
    parser.add_argument("--role", default="public", choices=sorted(VALID_ROLES))
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    response = ask(
        question=args.question,
        user_role=args.role,
        top_k=args.top_k,
        temperature=args.temperature,
        provider=args.provider,
        model=args.model,
    )
    print(response.answer)
    if response.fallback_reason:
        print(f"\nFallback reason: {response.fallback_reason}")
    if response.sources:
        print("\nSources:")
        for source in response.sources:
            print(f"- {source['title']} ({source['access_role']}, score={source['score']})")


if __name__ == "__main__":
    main()

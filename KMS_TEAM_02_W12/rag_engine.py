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
VALID_ROLES = {"public", "customer_service", "it_staff", "hr_manager"}
ROLE_ACCESS = {
    "public": {"public"},
    "customer_service": {"public"},
    "it_staff": {"it_staff", "public"},
    "hr_manager": {"hr_manager", "public"},
}
FALLBACK_ANSWER = (
    "I could not find enough information in the Triple H & T knowledge base to answer this question accurately. "
    "Please create a Helpdesk ticket or ask the responsible department to document this issue."
)
RESTRICTED_ACCESS_TEMPLATE = (
    "Access restricted. This information belongs to {workspace_dimension} and requires {access_role} permission. "
    "Please contact the authorized manager or system administrator."
)

MASTER_SYSTEM_PROMPT = """You are the internal Knowledge Management Assistant for Triple H & T.

Persona:
- Be factual, concise, and professional.
- Answer in the same language as the user when possible.
- Answer ONLY based on the approved retrieved company knowledge context.
- Do not invent facts, procedures, prices, people, salaries, vendors, or policies.
- Return only the final answer. Do not paste raw source blocks, prompt labels,
  retrieved context, or fallback instructions.

Grounding rules:
1. If the context is missing, irrelevant, or not specific enough, output only the fallback message exactly.
2. Respect the user's access role. Do not reveal content from an article unless the user's role is allowed to access it.
3. If access is restricted, output only the restricted-access message exactly.
4. Do not answer competitor-comparison requests, credential/API-key requests, or restricted salary/payroll questions for unauthorized roles.
5. Mention the article title or SOP name used from the retrieved context.
6. Keep every section grounded in the retrieved context. If one section is not covered by the context, say the knowledge base does not contain enough information for that section.

Required answer format when relevant context is available:
1. Direct Answer
Give a short and clear answer to the user's question.

2. Relevant Knowledge Source
Mention the article title or SOP name used from the retrieved context.

3. Business Context
Explain when this SOP or knowledge should be used.

4. Recommended Steps
List the action steps that the employee should follow.

5. Validation Checklist
List what the employee must check before closing the issue.

6. Risk / Warning
Mention any important risk, restriction, or escalation point.

7. Final Note
End with a short practical conclusion. If information is missing, tell the user to contact the responsible department or create a Helpdesk ticket.

Restricted-access message:
Access restricted. This information belongs to [workspace_dimension] and requires [access_role] permission. Please contact the authorized manager or system administrator.

Fallback message:
I could not find enough information in the Triple H & T knowledge base to answer this question accurately. Please create a Helpdesk ticket or ask the responsible department to document this issue.
"""

USER_PROMPT_TEMPLATE = """User role: {user_role}
Question: {question}

Approved retrieved context:
{context}

Write only the final answer for the user.
- If the context contains a relevant source, answer using the required 7-section format.
- Do not paste the source blocks or the fallback instructions.
- If the answer is not supported by the context, output only the fallback message exactly.
- If the user's role is not allowed to access a retrieved article, output only the restricted-access message with that article's Workspace and Access role.
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
    if role == "customer_service":
        return {
            "$and": [
                {"access_role": "public"},
                {"workspace_dimension": "customer_service"},
            ]
        }
    if role == "it_staff":
        return {"$or": [{"access_role": "it_staff"}, {"access_role": "public"}]}
    if role == "hr_manager":
        return {"$or": [{"access_role": "hr_manager"}, {"access_role": "public"}]}
    return {"access_role": "public"}


def restricted_access_answer(workspace_dimension: str, access_role: str) -> str:
    return RESTRICTED_ACCESS_TEMPLATE.format(
        workspace_dimension=workspace_dimension or "unknown",
        access_role=access_role or "unknown",
    )


def role_can_access(user_role: str, access_role: str) -> bool:
    clean_role = user_role if user_role in VALID_ROLES else "public"
    return access_role in ROLE_ACCESS.get(clean_role, {"public"})


def detect_restricted_access_request(question: str, user_role: str) -> tuple[str, str] | None:
    q = question.lower()
    hr_restricted_terms = [
        "salary",
        "payroll",
        "salary history",
        "performance warning",
        "employee hr file",
        "employee discipline record",
        "disciplinary",
        "employee offboarding",
        "resignation handover",
        "role transition",
        "knowledge transfer",
        "exit interview",
        "handover checklist",
        "departing employee",
        "candidate evaluation",
        "hiring notes",
        "interview review",
        "recruitment decision",
        "applicant assessment",
        "confidential hiring",
        "selection panel",
    ]
    if user_role != "hr_manager" and any(term in q for term in hr_restricted_terms):
        return "hr", "hr_manager"

    it_restricted_terms = [
        "it onboarding",
        "it engineer onboarding",
        "new it engineer",
        "new engineer setup",
        "new developer",
        "developer onboarding",
        "github account",
        "repository access",
        "vpn setup",
        "ssh key",
        "admin access",
        "privilege review",
        "elevated permission",
        "system access approval",
        "temporary admin",
        "account deactivation",
        "asset return",
        "laptop return",
        "remove access",
        "disable account",
        "system access removal",
    ]
    if user_role != "it_staff" and any(term in q for term in it_restricted_terms):
        return "it", "it_staff"

    return None


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
                snippet=content[:700],
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


def _source_titles(sources: list[Source], limit: int = 3) -> str:
    titles = []
    for source in sources:
        if source.title and source.title not in titles:
            titles.append(source.title)
    return ", ".join(titles[:limit])


def _clean_snippet(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(
        r"\b(Purpose|Problem|Analysis / Root Cause|Verified Solution / SOP Steps|Checklist|Canned Response / Shortcut|Response):",
        r". \1:",
        cleaned,
    )
    return cleaned.strip(" .")


SECTION_LABELS = (
    "Purpose",
    "Problem",
    "Analysis / Root Cause",
    "Root Cause",
    "Verified Solution / SOP Steps",
    "SOP Steps",
    "Checklist",
    "Canned Response / Shortcut",
    "Response",
    "New Developer Checklist",
    "Network Security Incident Response",
    "Acceptable Workplace Behavior",
    "HR Disciplinary Procedure",
    "Payroll Review",
)
SECTION_LABEL_PATTERN = "|".join(re.escape(label) for label in SECTION_LABELS)


def _truncate_sentence(text: str, max_chars: int = 320) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" .;-")
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars].rsplit(" ", 1)[0].strip(" .;-")
    return f"{truncated}."


def _missing_section(section_name: str) -> str:
    return f"The retrieved context does not contain enough information to specify {section_name}."


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _extract_labeled_text(sources: list[Source], labels: tuple[str, ...]) -> str:
    for source in sources:
        text = re.sub(r"\s+", " ", source.snippet).strip()
        for label in labels:
            match = re.search(
                rf"{re.escape(label)}:\s*(.*?)(?=\s+(?:{SECTION_LABEL_PATTERN}):|$)",
                text,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            value = _truncate_sentence(match.group(1))
            if len(value) >= 25:
                return value
    return ""


def _extract_numbered_items_from_text(text: str, max_items: int = 5) -> list[str]:
    items = []
    normalized = re.sub(r"\s+", " ", text).strip()
    for match in re.finditer(r"\(\d+\)\s*(.*?)(?=\s*\(\d+\)|$)", normalized):
        item = re.split(rf"\s+(?:{SECTION_LABEL_PATTERN}):", match.group(1), maxsplit=1)[0]
        item = _truncate_sentence(item, 180)
        if len(item) >= 10 and item not in items:
            items.append(item)
        if len(items) >= max_items:
            break
    return items


def _extract_labeled_items(sources: list[Source], labels: tuple[str, ...], max_items: int = 5) -> list[str]:
    for source in sources:
        text = re.sub(r"\s+", " ", source.snippet).strip()
        for label in labels:
            match = re.search(
                rf"{re.escape(label)}:\s*(.*?)(?=\s+(?:{SECTION_LABEL_PATTERN}):|$)",
                text,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            numbered_items = _extract_numbered_items_from_text(match.group(1), max_items=max_items)
            if numbered_items:
                return numbered_items

            sentence_items = [
                _truncate_sentence(part, 180)
                for part in re.split(r"(?<=[.!?])\s+|;\s+", match.group(1))
                if len(part.strip()) >= 25
            ]
            if sentence_items:
                return sentence_items[:max_items]
    return []


def _extract_numbered_items(sources: list[Source], max_items: int = 5) -> list[str]:
    items = []
    for source in sources:
        for item in _extract_numbered_items_from_text(source.snippet, max_items=max_items):
            if item not in items:
                items.append(item)
            if len(items) >= max_items:
                return items
    return items


def _extract_warning_points(sources: list[Source], max_points: int = 3) -> list[str]:
    keywords = (
        "must",
        "mandatory",
        "requires",
        "require",
        "only",
        "confidential",
        "restricted",
        "escalation",
        "escalate",
        "approval",
        "warning",
        "never",
        "not allowed",
    )
    warnings = []
    for source in sources:
        snippet = _clean_snippet(source.snippet)
        for sentence in re.split(r"(?<=[.!?])\s+", snippet):
            candidate = _truncate_sentence(sentence, 220)
            if len(candidate) < 30:
                continue
            if any(keyword in candidate.lower() for keyword in keywords) and candidate not in warnings:
                warnings.append(candidate)
            if len(warnings) >= max_points:
                return warnings
    return warnings


def _extract_key_points(sources: list[Source], max_points: int = 5) -> list[str]:
    points = []
    for source in sources:
        snippet = _clean_snippet(source.snippet)
        candidates = re.split(r"(?<=[.!?])\s+|\s+\(\d+\)\s+", snippet)
        for candidate in candidates:
            point = candidate.strip(" -")
            if len(point) < 45:
                continue
            if point.lower().startswith(("parent workspace", "workspace dimension", "access role", "tags")):
                continue
            if point not in points:
                points.append(point)
            if len(points) >= max_points:
                return points
    return points


def _source_grounded_answer(question: str, sources: list[Source]) -> str:
    if not sources:
        return FALLBACK_ANSWER

    points = _extract_key_points(sources)
    if not points and not any(source.snippet.strip() for source in sources):
        return FALLBACK_ANSWER

    direct_answer = points[0] if points else _missing_section("a direct answer")
    business_context = (
        _extract_labeled_text(sources, ("Purpose", "Problem", "Response"))
        or (points[1] if len(points) > 1 else _missing_section("the business context"))
    )
    recommended_steps = (
        _extract_labeled_items(
            sources,
            (
                "Verified Solution / SOP Steps",
                "SOP Steps",
                "New Developer Checklist",
                "Network Security Incident Response",
                "HR Disciplinary Procedure",
            ),
        )
        or _extract_numbered_items(sources)
        or points[:3]
        or [_missing_section("recommended steps")]
    )
    validation_checklist = (
        _extract_labeled_items(sources, ("Checklist",), max_items=5)
        or [_missing_section("a validation checklist")]
    )
    risk_warning = _extract_warning_points(sources) or [_missing_section("risks, restrictions, or escalation points")]

    return (
        "1. Direct Answer\n"
        f"{direct_answer}\n\n"
        "2. Relevant Knowledge Source\n"
        f"{_source_titles(sources)}\n\n"
        "3. Business Context\n"
        f"{business_context}\n\n"
        "4. Recommended Steps\n"
        f"{_format_bullets(recommended_steps[:5])}\n\n"
        "5. Validation Checklist\n"
        f"{_format_bullets(validation_checklist[:5])}\n\n"
        "6. Risk / Warning\n"
        f"{_format_bullets(risk_warning[:3])}\n\n"
        "7. Final Note\n"
        "Use the cited Triple H & T knowledge source as the working guidance. "
        "If the retrieved information does not fully match the issue, contact the responsible department or create a Helpdesk ticket."
    )


def _clean_generated_answer(answer: str) -> str:
    text = answer.strip()
    if not text:
        return text

    for label in ("Fallback message:", "Restricted-access message:"):
        if text.startswith(label):
            text = text.split(":", 1)[1].strip()

    for marker in ("\nFallback message:", "\nApproved retrieved context:", "\nUser role:", "\nQuestion:"):
        if marker in text and text.split(marker, 1)[0].strip():
            text = text.split(marker, 1)[0].strip()

    source_match = re.search(r"\n\s*\[Source\s+\d+\]", text)
    if source_match and text[: source_match.start()].strip():
        text = text[: source_match.start()].strip()

    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _is_fallback_answer(answer: str) -> bool:
    normalized = re.sub(r"\s+", " ", answer).strip()
    fallback = re.sub(r"\s+", " ", FALLBACK_ANSWER).strip()
    return normalized == fallback or fallback in normalized


REQUIRED_ANSWER_SECTIONS = (
    "1. Direct Answer",
    "2. Relevant Knowledge Source",
    "3. Business Context",
    "4. Recommended Steps",
    "5. Validation Checklist",
    "6. Risk / Warning",
    "7. Final Note",
)


def _has_required_answer_format(answer: str) -> bool:
    normalized = re.sub(r"\s+", " ", answer).strip()
    return all(section in normalized for section in REQUIRED_ANSWER_SECTIONS)


def _has_relevant_source(question: str, sources: list[Source]) -> bool:
    if not sources:
        return False

    top_score = sources[0].score
    if top_score is None or top_score >= float(os.getenv("RAG_EXTRACTIVE_MIN_SCORE", "0.25")):
        return True

    question_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", question.lower())
        if len(term) > 2 and term not in STOPWORDS
    }
    source_terms = set(re.findall(r"[a-z0-9]+", " ".join(source.snippet.lower() for source in sources[:2])))
    return len(question_terms & source_terms) >= 2


def _mock_answer(question: str, sources: list[Source]) -> str:
    return _source_grounded_answer(question, sources)


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

    restricted_request = detect_restricted_access_request(clean_question, clean_role)
    if restricted_request:
        workspace_dimension, access_role = restricted_request
        return RAGResponse(
            answer=restricted_access_answer(workspace_dimension, access_role),
            fallback=True,
            fallback_reason="Access role is not allowed for the requested knowledge.",
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

    restricted_sources = [
        source for source in source_objects if not role_can_access(clean_role, source.access_role)
    ]
    if restricted_sources:
        source = restricted_sources[0]
        return RAGResponse(
            answer=restricted_access_answer(source.workspace_dimension, source.access_role),
            fallback=True,
            fallback_reason="Retrieved context is restricted for this role.",
            provider=selected_provider,
            sources=[],
            context="",
        )

    if not _has_relevant_source(clean_question, source_objects):
        return RAGResponse(
            answer=FALLBACK_ANSWER,
            fallback=True,
            fallback_reason="Retrieved context was not relevant enough for the question.",
            provider=selected_provider,
            sources=[],
            context="",
        )

    raw_answer, actual_provider = generate_answer(
        question=clean_question,
        user_role=clean_role,
        context=context,
        sources=source_objects,
        temperature=temperature,
        provider=selected_provider,
        model=model,
    )
    answer = _clean_generated_answer(raw_answer)
    fallback = _is_fallback_answer(answer)
    fallback_reason = "LLM returned fallback message." if fallback else ""
    if fallback and actual_provider == "ollama" and _has_relevant_source(clean_question, source_objects):
        answer = _source_grounded_answer(clean_question, source_objects)
        fallback = False
        fallback_reason = ""
    if not fallback and actual_provider == "ollama" and not _has_required_answer_format(answer):
        answer = _source_grounded_answer(clean_question, source_objects)

    return RAGResponse(
        answer=answer,
        fallback=fallback,
        fallback_reason=fallback_reason,
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

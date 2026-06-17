import json
import os
import re
import subprocess
from pathlib import Path

from markupsafe import Markup, escape

from odoo import http
from odoo.http import request
from odoo.tools import html2plaintext, plaintext2html


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent
RAG_PROJECT_DIR = WORKSPACE_ROOT / "KMS_TEAM_02_W12"
RAG_PYTHON = RAG_PROJECT_DIR / ".venv" / "Scripts" / "python.exe"

RAG_FALLBACK = (
    "I do not have enough approved corporate knowledge context to answer that. "
    "Please check the official Odoo Knowledge base or ask the responsible owner."
)


class KmsRagLivechatController(http.Controller):
    def _get_bot_partner(self):
        partner_model = request.env["res.partner"].sudo()
        bot_partner = partner_model.search([("email", "=", "kms-rag-bot@example.local")], limit=1)
        if bot_partner:
            return bot_partner

        return partner_model.create(
            {
                "name": "KMS RAG Bot",
                "email": "kms-rag-bot@example.local",
                "comment": "Technical partner used by the KMS Team 02 RAG livechat demo.",
            }
        )

    def _looks_vietnamese(self, text):
        normalized = f" {text.lower()} "
        vietnamese_chars = "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
        vietnamese_terms = [
            " tôi ",
            " mình ",
            " bạn ",
            " không ",
            " được ",
            " giúp ",
            " như thế nào ",
            " làm sao ",
        ]
        return any(char in normalized for char in vietnamese_chars) or any(
            term in normalized for term in vietnamese_terms
        )

    def _source_titles(self, sources, limit=3):
        titles = []
        for source in sources:
            title = source.get("title")
            if title and title not in titles:
                titles.append(title)
        return titles[:limit]

    def _snippet_points(self, source, limit=3):
        title = (source.get("title") or "").strip().lower()
        snippet = re.sub(r"\s+", " ", source.get("snippet", "")).strip()
        snippet = re.sub(r"^[A-Z0-9-]+\s+-\s+", "", snippet)
        snippet = re.sub(r"\b(Purpose|Problem|Root Cause|Analysis|Solution|Steps?|Checklist):", r". \1:", snippet)
        raw_parts = re.split(r"(?<=[.!?])\s+", snippet)
        points = []
        for index, part in enumerate(raw_parts):
            part = part.strip()
            if index == len(raw_parts) - 1 and not re.search(r"[.!?]$", part):
                continue
            part = part.strip(" .;-")
            if len(part) < 24 or part.lower() == title:
                continue
            if len(part) > 180:
                part = part[:177].rstrip() + "..."
            if not part.endswith((".", "!", "?")):
                part += "."
            points.append(part)
            if len(points) >= limit:
                break
        return points

    def _format_livechat_payload(self, question, payload):
        sources = payload.get("sources") or []
        answer = (payload.get("answer") or RAG_FALLBACK).replace("Mock grounded answer: ", "", 1).strip()
        fallback = bool(payload.get("fallback")) or RAG_FALLBACK in answer
        is_vi = self._looks_vietnamese(question)

        if fallback or not sources:
            text = (
                "Mình chưa có đủ dữ liệu đã được duyệt để trả lời câu này. "
                "Vui lòng kiểm tra Odoo Knowledge hoặc hỏi người phụ trách."
                if is_vi
                else RAG_FALLBACK
            )
            reason = payload.get("fallback_reason")
            if reason:
                text = f"{text}\n\nReason: {reason}"
            return Markup(plaintext2html(text))

        titles = self._source_titles(sources)
        first_source = sources[0]
        points = self._snippet_points(first_source)
        internal_terms = ["developer", "onboarding", "new engineer", "it staff", "nhân viên", "lập trình viên"]
        public_only_note = any(term in question.lower() for term in internal_terms)

        if is_vi:
            intro = (
                "Khung chat website chỉ dùng dữ liệu public. Nếu cần quy trình IT nội bộ đầy đủ, "
                "hãy dùng chatbot nội bộ với role it_staff."
                if public_only_note
                else "Mình trả lời dựa trên dữ liệu public đã được duyệt."
            )
            main_label = "Nguồn chính"
            points_label = "Ý chính"
            sources_label = "Nguồn tham khảo"
        else:
            intro = (
                "This website chat only uses public knowledge. For full IT onboarding steps, "
                "use the internal chatbot with the it_staff role."
                if public_only_note
                else "I can answer from the approved public knowledge base."
            )
            main_label = "Main source"
            points_label = "Key points"
            sources_label = "Sources"

        html = [f"<p>{escape(intro)}</p>"]
        html.append(f"<p><strong>{escape(main_label)}:</strong><br>{escape(first_source.get('title', 'Untitled'))}</p>")
        if points:
            html.append(f"<p><strong>{escape(points_label)}:</strong></p><ul>")
            html.extend(f"<li>{escape(point)}</li>" for point in points)
            html.append("</ul>")
        if titles:
            html.append(f"<p><strong>{escape(sources_label)}:</strong></p><ul>")
            html.extend(f"<li>{escape(title)}</li>" for title in titles)
            html.append("</ul>")
        return Markup("".join(str(part) for part in html))

    def _call_rag_engine(self, question):
        if not RAG_PYTHON.exists() or not (RAG_PROJECT_DIR / "rag_engine.py").exists():
            return {
                "answer": (
                    "RAG runtime is not ready. Please start the KMS Team 02 Week 12 chatbot "
                    "environment first."
                ),
                "fallback": True,
                "fallback_reason": "RAG runtime is not ready.",
                "sources": [],
            }

        runner = r"""
import json
import sys

import rag_engine

payload = json.loads(sys.stdin.read() or "{}")
response = rag_engine.ask(
    question=payload.get("question", ""),
    user_role=payload.get("user_role", "public"),
    top_k=payload.get("top_k", 4),
    temperature=payload.get("temperature", 0.2),
    provider=payload.get("provider"),
)
print(json.dumps({
    "answer": response.answer,
    "fallback": response.fallback,
    "fallback_reason": response.fallback_reason,
    "sources": response.sources,
}, ensure_ascii=False))
"""
        env = os.environ.copy()
        env.setdefault("EMBEDDING_PROVIDER", "sentence-transformers")
        completed = subprocess.run(
            [str(RAG_PYTHON), "-c", runner],
            cwd=str(RAG_PROJECT_DIR),
            input=json.dumps(
                {
                    "question": question,
                    "user_role": "public",
                    "top_k": 4,
                    "temperature": 0.2,
                    "provider": None,
                }
            ),
            text=True,
            capture_output=True,
            timeout=120,
            env=env,
        )
        if completed.returncode != 0:
            return {
                "answer": RAG_FALLBACK,
                "fallback": True,
                "fallback_reason": "RAG process failed.",
                "sources": [],
            }

        output = completed.stdout.strip().splitlines()[-1]
        return json.loads(output)

    @http.route(
        "/kms_rag_livechat/respond",
        methods=["POST"],
        type="json",
        auth="public",
        csrf=False,
    )
    def respond(self, thread_id=None, message_body=None, **kwargs):
        question = html2plaintext(message_body or "").strip()
        if not thread_id or not question:
            return {"ok": False, "reason": "Missing thread_id or message_body."}

        channel = request.env["discuss.channel"].sudo().browse(int(thread_id)).exists()
        if not channel or channel.channel_type != "livechat":
            return {"ok": False, "reason": "Not a livechat channel."}

        payload = self._call_rag_engine(question)
        answer_html = self._format_livechat_payload(question, payload)
        author = self._get_bot_partner()
        message = channel.with_context(mail_create_nosubscribe=True).sudo().message_post(
            author_id=author.id,
            body=answer_html,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        return {"ok": True, "message": message.message_format()[0]}

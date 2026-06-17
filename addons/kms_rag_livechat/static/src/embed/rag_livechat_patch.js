/** @odoo-module */

import { Thread } from "@mail/core/common/thread_model";
import { ThreadService } from "@mail/core/common/thread_service";
import { patch } from "@web/core/utils/patch";

const KMS_RAG_BOT_NAME = "KMS RAG Chatbot";
const KMS_RAG_BOT_PERSONA_ID = -2021202;
const KMS_RAG_BOT_AVATAR = "/kms_rag_livechat/static/src/img/kms_bot_avatar.svg";
const KMS_RAG_BOT_PERSONA = {
    type: "partner",
    id: KMS_RAG_BOT_PERSONA_ID,
    name: KMS_RAG_BOT_NAME,
    displayName: KMS_RAG_BOT_NAME,
    im_status: "bot",
};

patch(Thread, {
    _insert(data) {
        const thread = super._insert(...arguments);
        if (thread.type === "livechat") {
            thread.operator = KMS_RAG_BOT_PERSONA;
        }
        return thread;
    },
});

patch(Thread.prototype, {
    get displayName() {
        if (this.type === "livechat") {
            return KMS_RAG_BOT_NAME;
        }
        return super.displayName;
    },

    get imgUrl() {
        if (this.type === "livechat") {
            return KMS_RAG_BOT_AVATAR;
        }
        return super.imgUrl;
    },
});

patch(ThreadService.prototype, {
    _kmsRagTypingMember(thread) {
        const threadId = Number.isInteger(thread.id) ? thread.id : 1;
        return this.store.ChannelMember.insert({
            id: -2021203000 - threadId,
            persona: KMS_RAG_BOT_PERSONA,
            thread: {
                id: thread.id,
                model: thread.model || "discuss.channel",
            },
        });
    },

    _kmsRagStartTyping(thread) {
        const typingService = this.env.services["discuss.typing"];
        if (!typingService) {
            return;
        }
        this._kmsRagPendingCount = (this._kmsRagPendingCount || 0) + 1;
        this._kmsRagCurrentTypingMember = this._kmsRagTypingMember(thread);
        typingService.addTypingMember(this._kmsRagCurrentTypingMember);
    },

    _kmsRagStopTyping() {
        const typingService = this.env.services["discuss.typing"];
        if (!typingService || !this._kmsRagCurrentTypingMember) {
            return;
        }
        this._kmsRagPendingCount = Math.max((this._kmsRagPendingCount || 1) - 1, 0);
        if (this._kmsRagPendingCount === 0) {
            typingService.removeTypingMember(this._kmsRagCurrentTypingMember);
            this._kmsRagCurrentTypingMember = null;
        }
    },

    async post(thread, body, params) {
        const wasLivechat = thread?.type === "livechat";
        const message = await super.post(thread, body, params);
        if (!wasLivechat || !message || !body?.trim()) {
            return message;
        }
        const threadId = message.res_id || message.originThread?.id || thread.id;
        if (!threadId || typeof threadId === "string") {
            return message;
        }
        this._kmsRagPendingIds ||= new Set();
        if (this._kmsRagPendingIds.has(message.id)) {
            return message;
        }
        this._kmsRagPendingIds.add(message.id);
        this._kmsRagStartTyping(thread);
        this.rpc(
            "/kms_rag_livechat/respond",
            {
                thread_id: threadId,
                message_body: body,
            },
            { silent: true }
        ).catch((error) => {
            console.warn("KMS RAG livechat response failed", error);
        }).finally(() => {
            window.setTimeout(() => {
                this._kmsRagStopTyping();
                this._kmsRagPendingIds.delete(message.id);
            }, 600);
        });
        return message;
    },
});

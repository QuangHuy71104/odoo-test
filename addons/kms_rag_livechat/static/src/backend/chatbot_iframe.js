/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";

export class KmsChatbotIframeAction extends Component {
    static template = "kms_rag_livechat.KmsChatbotIframeAction";

    setup() {
        this.state = useState({ chatbotUrl: this.props.action.params?.chatbot_url || "http://localhost:8501" });
        onWillStart(async () => {
            const baseUrl = this.props.action.params?.chatbot_url || "http://localhost:8501";
            const userRole = await this._resolveUserRole();
            const separator = baseUrl.includes("?") ? "&" : "?";
            this.state.chatbotUrl = `${baseUrl}${separator}user_role=${encodeURIComponent(userRole)}&locked_role=1`;
        });
    }

    async _resolveUserRole() {
        if (await user.hasGroup("base.group_system")) {
            return "admin";
        }
        return "public";
    }
}

registry.category("actions").add("kms_rag_livechat.chatbot_iframe", KmsChatbotIframeAction);

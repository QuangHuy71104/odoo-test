# -*- coding: utf-8 -*-
{
    "name": "KMS RAG Livechat",
    "version": "17.0.1.0.0",
    "summary": "Connect KMS Team 02 RAG answers to the Odoo livechat widget",
    "category": "Website/Live Chat",
    "depends": ["web", "website_livechat"],
    "data": [
        "views/kms_chatbot_menu.xml",
    ],
    "installable": True,
    "application": False,
    "assets": {
        "web.assets_backend": [
            "kms_rag_livechat/static/src/backend/chatbot_iframe.js",
            "kms_rag_livechat/static/src/backend/chatbot_iframe.xml",
            "kms_rag_livechat/static/src/backend/chatbot_iframe.scss",
        ],
        "im_livechat.assets_embed_core": [
            "kms_rag_livechat/static/src/embed/rag_livechat_patch.js",
            "kms_rag_livechat/static/src/embed/rag_livechat_patch.scss",
            "kms_rag_livechat/static/src/embed/rag_livechat_template_patch.xml",
        ],
    },
    "license": "LGPL-3",
}

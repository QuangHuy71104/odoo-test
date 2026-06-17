# -*- coding: utf-8 -*-
{
    "name": "KMS RAG Livechat",
    "version": "17.0.1.0.0",
    "summary": "Connect KMS Team 02 RAG answers to the Odoo livechat widget",
    "category": "Website/Live Chat",
    "depends": ["website_livechat"],
    "installable": True,
    "application": False,
    "assets": {
        "im_livechat.assets_embed_core": [
            "kms_rag_livechat/static/src/embed/rag_livechat_patch.js",
            "kms_rag_livechat/static/src/embed/rag_livechat_patch.scss",
            "kms_rag_livechat/static/src/embed/rag_livechat_template_patch.xml",
        ],
    },
    "license": "LGPL-3",
}

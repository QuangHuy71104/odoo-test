from odoo import Command, models


KMS_RAG_BOT_NAME = "KMS RAG Chatbot"
KMS_RAG_BOT_EMAIL = "kms-rag-bot@example.local"


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    def _get_kms_rag_bot_partner(self):
        partner_model = self.env["res.partner"].sudo()
        bot_partner = partner_model.search([("email", "=", KMS_RAG_BOT_EMAIL)], limit=1)
        if bot_partner:
            return bot_partner

        return partner_model.create(
            {
                "name": "KMS RAG Bot",
                "email": KMS_RAG_BOT_EMAIL,
                "comment": "Technical partner used by the KMS Team 02 RAG livechat demo.",
            }
        )

    def _get_livechat_discuss_channel_vals(
        self,
        anonymous_name,
        previous_operator_id=None,
        chatbot_script=None,
        user_id=None,
        country_id=None,
        lang=None,
    ):
        vals = super()._get_livechat_discuss_channel_vals(
            anonymous_name,
            previous_operator_id=previous_operator_id,
            chatbot_script=chatbot_script,
            user_id=user_id,
            country_id=country_id,
            lang=lang,
        )
        if vals:
            bot_partner = self._get_kms_rag_bot_partner()
            members_to_add = [Command.create({"partner_id": bot_partner.id, "is_pinned": False})]
            if user_id:
                visitor_user = self.env["res.users"].browse(user_id)
                if visitor_user and visitor_user.active and visitor_user.partner_id != bot_partner:
                    members_to_add.append(Command.create({"partner_id": visitor_user.partner_id.id}))

            vals["name"] = KMS_RAG_BOT_NAME
            vals["livechat_operator_id"] = bot_partner.id
            vals["channel_member_ids"] = members_to_add
        return vals

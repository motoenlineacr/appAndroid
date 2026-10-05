from odoo import models , fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    agent_ia_api_key = fields.Char(string="Agent IA API Key", config_parameter='agent_ia.agent_ia_api_key')
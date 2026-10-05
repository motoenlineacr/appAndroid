from odoo import models , fields


class Chats(models.Model):
    _name = "chat.ia"
    
    name = fields.Char(string="#")
    partner_id = fields.Many2one("res.partner",string="Usuario")
    messages_ids = fields.One2many("message.history","chat_id",string="Mensages")
    
    


class MessagesHistory(models.Model):
    _name = "message.history"
    
    chat_id = fields.Many2one("chat.ia")
    type_message = fields.Selection(
        [
            ("user","user"),
            ("ia","ia")
        ]
    )
    message = fields.Text(string="Mensaje")
    
    

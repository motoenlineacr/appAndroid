from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    
    
    
    def EnterPickup(self):
        pass
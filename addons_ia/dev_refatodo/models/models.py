# from odoo import models, fields, api


# class dev_refatodo(models.Model):
#     _name = 'dev_refatodo.dev_refatodo'
#     _description = 'dev_refatodo.dev_refatodo'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100


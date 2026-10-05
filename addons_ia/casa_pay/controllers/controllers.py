# from odoo import http


# class CasaPay(http.Controller):
#     @http.route('/casa_pay/casa_pay', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/casa_pay/casa_pay/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('casa_pay.listing', {
#             'root': '/casa_pay/casa_pay',
#             'objects': http.request.env['casa_pay.casa_pay'].search([]),
#         })

#     @http.route('/casa_pay/casa_pay/objects/<model("casa_pay.casa_pay"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('casa_pay.object', {
#             'object': obj
#         })


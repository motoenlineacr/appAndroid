from odoo import http
from odoo.http import request
import json

class SalesAPI(http.Controller):

    @http.route("/api/productos_vendidos", type="http", auth="user", csrf=False)
    def get_sold_products(self):
        lines = request.env["sale.order.line"].sudo().search_read(
            domain=[('state', 'in', ['sale', 'done'])],
            fields=["product_id", "product_uom_qty", "order_id", "create_date"],
        )

        product_ids = list(set([l['product_id'][0] for l in lines if l['product_id']]))
        
        products = request.env["product.product"].sudo().search_read(
            [('id', 'in', product_ids)], 
            ['qty_available', 'categ_id']
        )
        
        product_info = {p['id']: p for p in products}
        categories = request.env["product.category"].sudo().search_read([], ['id', 'name'])

        items = []
        for line in lines:
            if line['product_id']:
                p_id = line['product_id'][0]
                info = product_info.get(p_id, {})
                
      
                cat_data = info.get('categ_id')
                category_id = cat_data[0] if isinstance(cat_data, (list, tuple)) else 0

                items.append({
                    "id": p_id, 
                    "name": line['product_id'][1],
                    "qty_sold": line['product_uom_qty'],
                    "order_id": line['order_id'][0],
                    "qty_available": info.get('qty_available', 0),
                    "category_id": category_id,
                    "date_order": line['create_date'].strftime("%Y-%m-%d") if line['create_date'] else "",
                })

        return request.make_response(
            json.dumps({"items": items, "categories": categories}, default=str), 
            headers=[('Content-Type', 'application/json')]
        )
# -*- coding: utf-8 -*-
import json
import re
from odoo.http import Controller, route, request
from openai import OpenAI


ALLOWED_MODELS = {
    "res.partner",
    "sale.order",
    "sale.order.line",
    "product.product",
    "product.template",
    "account.move",
}

ALLOWED_ACTIONS = {
    "search_read",
    "search_count",
    "create",
    "write",
    "unlink",
    "read",
    "call_kw",
}


class UserController(Controller):

    # -------------------------
    # Helpers
    # -------------------------
    def _m2o_name(self, value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return value[1]
        return None

    def _m2o_id(self, value):
        if isinstance(value, (list, tuple)) and len(value) >= 1:
            return value[0]
        return None

    def _format_amount(self, amount):
        try:
            return f"{float(amount):,.2f}"
        except Exception:
            return str(amount)

    def _currency_label(self, currency_m2o):
        cur_id = self._m2o_id(currency_m2o)
        cur_name = self._m2o_name(currency_m2o) or ""
        if not cur_id:
            return cur_name

        cur = request.env["res.currency"].sudo().browse(cur_id)
        if cur.exists():
            symbol = cur.symbol or cur_name
            position = cur.position or "after"
            return (symbol, position)
        return cur_name

    def _extract_sale_order_ref(self, text):
        if not text:
            return None
        m = re.search(r"\bS\d{3,}\b", text.upper())
        return m.group(0) if m else None

    # (Opcional) mantiene tu auto-fields para ayudar cuando el modelo mande fields vacíos
    def _ensure_fields(self, plan, question: str):
        if plan.get("type") != "orm":
            return
        if plan.get("action") != "search_read":
            return

        model = plan.get("model")
        q = (question or "").strip().lower()
        fields = set(plan.get("fields") or [])

        DEFAULT_FIELDS = {
            "sale.order": {"name", "partner_id", "amount_total", "currency_id", "state"},
            "sale.order.line": {"order_id", "product_id", "price_unit", "price_total", "price_subtotal"},
            "res.partner": {"name", "email", "phone"},
            "account.move": {"name", "move_type", "partner_id", "invoice_date", "amount_total", "state"},
            "product.product": {"display_name", "default_code", "lst_price", "qty_available"},
            "product.template": {"name", "list_price", "default_code"},
        }

        if model in DEFAULT_FIELDS and not fields:
            fields = set(DEFAULT_FIELDS[model])

        # Si el usuario pide cosas específicas, intenta asegurar campos clave
        if model == "sale.order":
            if any(k in q for k in ("total", "monto", "importe", "valor")):
                fields.update({"name", "amount_total", "currency_id"})
            if any(k in q for k in ("cliente", "comprador", "partner")):
                fields.update({"name", "partner_id"})

        if model == "sale.order.line":
            if any(k in q for k in ("producto", "nombre")):
                fields.add("product_id")
            if any(k in q for k in ("caro", "costo", "precio", "monto", "valor")):
                fields.update({"price_unit", "price_total", "price_subtotal"})
            fields.add("order_id")

        if not fields:
            fields = {"id"}

        plan["fields"] = list(fields)

    # -------------------------
    # Validación
    # -------------------------
    def _validate_multi(self, plan):
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps:
            return False, {
                "type": "ask",
                "question": "No entendí los pasos. ¿Qué necesitas que busque en Odoo?",
                "required": [],
                "meta": {"why": "multi_steps_missing"},
            }

        # Límite de seguridad
        if len(steps) > 5:
            return False, {
                "type": "ask",
                "question": "Esa solicitud requiere muchos pasos. ¿La acotamos (por fecha o top 10)?",
                "required": [],
                "meta": {"why": "multi_too_many_steps", "n": len(steps)},
            }

        for i, step in enumerate(steps):
            ok, ask = self._validate_plan(step)
            if not ok:
                ask["meta"] = {**ask.get("meta", {}), "step_index": i}
                return False, ask
        return True, None

    def _validate_plan(self, plan):
        if not isinstance(plan, dict):
            return False, {
                "type": "ask",
                "question": "No entendí la instrucción. ¿Puedes repetir?",
                "required": [],
                "meta": {"why": "plan_not_dict"},
            }

        ptype = plan.get("type")

        # ✅ nuevo tipo multi
        if ptype == "multi":
            return self._validate_multi(plan)

        if ptype not in ("orm", "ask", "text", "noop"):
            return False, {
                "type": "ask",
                "question": "Tu solicitud no está clara. ¿Qué necesitas que haga en Odoo?",
                "required": [],
                "meta": {"why": "invalid_type", "got": ptype},
            }

        if ptype in ("text", "noop", "ask"):
            if ptype == "ask" and not plan.get("question"):
                plan["question"] = "Necesito más información para continuar. ¿Qué dato me das?"
            return True, None

        action = plan.get("action")
        model = plan.get("model")

        if not action or not model:
            return False, {
                "type": "ask",
                "question": "Me falta información para ejecutar en Odoo. Indica qué modelo y acción necesitas.",
                "required": ["model", "action"],
                "meta": {"why": "missing_model_or_action", "original_plan": plan},
            }

        if action not in ALLOWED_ACTIONS:
            return False, {
                "type": "ask",
                "question": f"Esa acción no está permitida ({action}). ¿Qué quieres hacer exactamente?",
                "required": [],
                "meta": {"why": "action_not_allowed", "original_plan": plan},
            }

        if model not in ALLOWED_MODELS:
            return False, {
                "type": "ask",
                "question": f"Ese modelo no está permitido ({model}). ¿Sobre qué quieres trabajar?",
                "required": [],
                "meta": {"why": "model_not_allowed", "original_plan": plan},
            }

        # ✅ search_read: permite domain vacío si es TOP (order+limit)
        if action in ("search_read", "search_count"):
            domain = plan.get("domain", None)

            if action == "search_read":
                has_order = bool(plan.get("order"))
                limit = int(plan.get("limit", 0) or 0)

                if (domain is None or domain == []) and not (has_order and limit > 0):
                    return False, {
                        "type": "ask",
                        "question": "Para buscar necesito un criterio (domain) o, si quieres un TOP, usar order+limit. ¿Lo quieres por todas las órdenes o por un período (ej: este mes)?",
                        "required": [],
                        "meta": {"why": "missing_domain_or_top_params", "original_plan": plan},
                    }

            if action == "search_count" and (domain is None or domain == []):
                return False, {
                    "type": "ask",
                    "question": "Para contar necesito un criterio (domain). ¿Qué filtro uso?",
                    "required": ["criterio_busqueda"],
                    "meta": {"why": "missing_domain_for_count", "original_plan": plan},
                }

        if action in ("read", "unlink", "call_kw"):
            ids = plan.get("ids", [])
            if not ids:
                return False, {
                    "type": "ask",
                    "question": "Necesito el ID del registro para continuar. ¿Cuál es el ID?",
                    "required": ["ids"],
                    "meta": {"why": "missing_ids", "original_plan": plan},
                }

        if action == "write":
            ids = plan.get("ids", [])
            values = plan.get("values", {})
            if not ids:
                return False, {
                    "type": "ask",
                    "question": "Para actualizar necesito el/los ID(s). ¿Cuál(es) es/son?",
                    "required": ["ids"],
                    "meta": {"why": "missing_ids_for_write", "original_plan": plan},
                }
            if not values:
                return False, {
                    "type": "ask",
                    "question": "¿Qué campos quieres cambiar y con qué valores?",
                    "required": ["values"],
                    "meta": {"why": "missing_values_for_write", "original_plan": plan},
                }

        if action == "create":
            values = plan.get("values", {})
            if not values:
                return False, {
                    "type": "ask",
                    "question": "¿Qué datos debo crear? Dime los campos y valores.",
                    "required": ["values"],
                    "meta": {"why": "missing_values_for_create", "original_plan": plan},
                }
            if model == "res.partner" and not values.get("name"):
                return False, {
                    "type": "ask",
                    "question": "Para crear un cliente necesito el nombre. ¿Cuál es el nombre del cliente?",
                    "required": ["name"],
                    "meta": {"why": "missing_partner_name", "original_plan": plan},
                }

        return True, None

    # -------------------------
    # Ejecución ORM
    # -------------------------
    def _execute_plan(self, plan):
        if plan.get("type") != "orm":
            return None

        action = plan.get("action")
        model_name = plan.get("model")

        Model = request.env[model_name].sudo()

        if action == "search_read":
            domain = plan.get("domain", []) or []
            fields = plan.get("fields", []) or []
            limit = int(plan.get("limit", 20) or 20)
            offset = int(plan.get("offset", 0) or 0)
            order = plan.get("order") or None
            data = Model.search_read(domain, fields, limit=limit, offset=offset, order=order)
            return {"data": data}

        if action == "search_count":
            domain = plan.get("domain", []) or []
            count = Model.search_count(domain)
            return {"count": count}

        if action == "create":
            values = plan.get("values", {})
            rec = Model.create(values)
            return {"id": rec.id}

        if action == "write":
            ids = plan.get("ids", [])
            values = plan.get("values", {})
            Model.browse(ids).write(values)
            return {"written": ids}

        if action == "unlink":
            ids = plan.get("ids", [])
            Model.browse(ids).unlink()
            return {"deleted": ids}

        if action == "read":
            ids = plan.get("ids", [])
            fields = plan.get("fields", [])
            data = Model.browse(ids).read(fields)
            return {"data": data}

        if action == "call_kw":
            ids = plan.get("ids", [])
            method = plan.get("method")
            args = plan.get("args", [])
            kw = plan.get("kwargs", {})
            recs = Model.browse(ids)
            if not method or not hasattr(recs, method):
                return {"error": f"Método inválido: {method}"}
            res = getattr(recs, method)(*args, **kw)
            return {"data": res}

        return {"error": "Acción no soportada"}

    def _execute_multi(self, plan):
        results = []
        for step in plan.get("steps", [])[:5]:
            # opcional: asegurar fields por step también
            self._ensure_fields(step, "")
            results.append(self._execute_plan(step))
        return {"steps": results}

    # -------------------------
    # IA para redactar respuesta FINAL (con resultados)
    # -------------------------
    def _finalize_with_ai(self, client, question, plan, orm_result):
        prompt = """
Eres RandyBot para Odoo.

Te doy:
- question (pregunta del usuario)
- plan (plan ejecutado; puede ser orm o multi con steps)
- result (resultado ORM JSON)

Reglas:
- Responde en español, claro y directo.
- SOLO usa datos presentes en "result". NO inventes.
- Si falta un dato necesario, responde type="ask" con una sola pregunta concreta.
- Si hay varios resultados, resume (top 5) y ofrece filtrar por fecha/cliente si aplica.

SALIDA: Un único JSON válido:
1) {"type":"text","message":"..."}
2) {"type":"ask","question":"...","required":[],"meta":{"why":"..."}}
"""
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({
                    "question": question,
                    "plan": plan,
                    "result": orm_result,
                }, ensure_ascii=False)}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    # -------------------------
    # Endpoint
    # -------------------------
    @route("/send/message", type="http", methods=["POST"], auth="public", csrf=False)
    # Recomendado producción:
    # @route("/send/message", type="http", methods=["POST"], auth="user", csrf=True)
    def sendMessage(self, **kwargs):
        payload = json.loads(request.httprequest.data.decode("utf-8") or "{}")

        api_key = request.env["ir.config_parameter"].sudo().get_param("agent_ia.agent_ia_api_key") or ""
        client = OpenAI(api_key=api_key)

        question = (payload.get("question") or "").strip()
        messages = payload.get("messages", [])

        system_prompt = """
Eres RandyBot para Odoo 19.

IMPORTANTE:
- Debes decidir por ti mismo si necesitas 1 o varias consultas.
- Cuando haga falta más de una consulta para responder, usa type="multi" con "steps".

SALIDA:
- SIEMPRE devuelve un ÚNICO JSON válido. Nada fuera del JSON.

TIPOS:
1) text:
{"type":"text","message":"..."}

2) ask:
{"type":"ask","question":"...","required":["..."],"meta":{"why":"..."}}

3) orm:
{
  "type":"orm",
  "action":"search_read|search_count|create|write|unlink|read|call_kw",
  "model":"res.partner|sale.order|sale.order.line|product.product|product.template|account.move",
  "domain":[["campo","operador","valor"]],
  "fields":["..."],
  "ids":[1,2],
  "values":{...},
  "limit":10,
  "offset":0,
  "order":"..."
}

4) multi:
{
  "type":"multi",
  "steps":[
     { ... orm step 1 ... },
     { ... orm step 2 ... }
  ]
}

REGLA:
- NO inventes datos, pero SÍ puedes hacer consultas adicionales si eso resuelve la pregunta.
- Puedes usar search_read con domain vacío SOLO si usas order+limit para un TOP.
  Ej: order:"amount_total desc", limit:1

EJEMPLOS:
- "Cliente y total de la orden S00016" =>
{"type":"orm","action":"search_read","model":"sale.order",
 "domain":[["name","=","S00016"]],
 "fields":["name","partner_id","amount_total","currency_id"],
 "limit":1}

- "¿Cuál orden hizo más dinero?" =>
{"type":"orm","action":"search_read","model":"sale.order",
 "domain":[],
 "fields":["name","partner_id","amount_total","currency_id","date_order"],
 "order":"amount_total desc","limit":1}

- "Producto más caro de la orden S00016 (nombre y precio)" =>
{"type":"orm","action":"search_read","model":"sale.order.line",
 "domain":[["order_id.name","=","S00016"]],
 "fields":["order_id","product_id","price_unit","price_total","price_subtotal"],
 "order":"price_unit desc","limit":1}

- Si necesitas varias consultas, usa multi steps.
"""

        chat_messages = [{"role": "system", "content": system_prompt}] + messages + [
            {"role": "user", "content": question}
        ]

        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=chat_messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        plan_text = resp.choices[0].message.content

        try:
            plan = json.loads(plan_text)
        except Exception:
            plan = {
                "type": "ask",
                "question": "No pude generar un JSON válido. ¿Puedes repetir tu solicitud?",
                "required": [],
                "meta": {"why": "invalid_json", "raw": plan_text},
            }

        ok, ask_payload = self._validate_plan(plan)
        if not ok and ask_payload:
            plan = ask_payload

        orm_result = None
        final_message = None

        if plan.get("type") == "orm":
            self._ensure_fields(plan, question)
            try:
                orm_result = self._execute_plan(plan)
            except Exception as e:
                orm_result = {"error": str(e)}

            final_obj = self._finalize_with_ai(client, question, plan, orm_result)
            final_message = final_obj.get("message") or final_obj.get("question") or "Listo."

        elif plan.get("type") == "multi":
            for step in plan.get("steps", []):
                self._ensure_fields(step, question)

            try:
                orm_result = self._execute_multi(plan)
            except Exception as e:
                orm_result = {"error": str(e)}

            final_obj = self._finalize_with_ai(client, question, plan, orm_result)
            final_message = final_obj.get("message") or final_obj.get("question") or "Listo."

        elif plan.get("type") == "ask":
            final_message = plan.get("question") or "Necesito más información para continuar."

        elif plan.get("type") == "text":
            final_message = plan.get("message") or "Entendido."

        else:
            final_message = "¿Qué necesitas que haga exactamente en Odoo?"

        return request.make_response(
            json.dumps({
                "type": "final",
                "message": final_message,
                "plan": plan,
                "result": orm_result,
            }, ensure_ascii=False),
            headers=[("Content-Type", "application/json")]
        )

/** @odoo-module **/
import { Component, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AgentIa extends Component {
  static template = "agent_ia.template";

  setup() {
    this.inputMessage = useRef("input_message");
    this.notification = useService("notification");
    this.state = useState({ messages: [] });
    this._msgId = 1;
  }

  async send_message() {
    const question = (this.inputMessage.el.value || "").trim();

    if (!question) {
      this.notification.add("Ingresa tu pregunta", { type: "danger" });
      return;
    }

    this.state.messages.push({
      id: this._msgId++,
      type: "user",
      message: question,
    });

    const loadingId = this._msgId++;
    this.state.messages.push({
      id: loadingId,
      type: "ia",
      message: "Escribiendo…",
      loading: true,
    });

    this.inputMessage.el.value = "";

    const history = this.state.messages
      .filter(m => m.type === "user" || (m.type === "ia" && !m.loading)) 
      .map(m => ({
        role: m.type === "user" ? "user" : "assistant",
        content: m.message,
      }));

    try {
      const resp = await fetch("/send/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, messages: history }),
      });

      if (!resp.ok) {
        throw new Error(await resp.text());
      }

      const result = await resp.json();

      const idx = this.state.messages.findIndex(m => m.id === loadingId);
      if (idx !== -1) {
        this.state.messages[idx] = {
          id: loadingId,
          type: "ia",
          message: result.message ?? "No entendí tu pregunta",
          loading: false,
        };
      }
    } catch (err) {
      const idx = this.state.messages.findIndex(m => m.id === loadingId);
      if (idx !== -1) {
        this.state.messages[idx] = {
          id: loadingId,
          type: "ia",
          message: "Error consultando la IA. Intenta de nuevo.",
          loading: false,
          error: true,
        };
      }
      this.notification.add("Error consultando la IA", { type: "danger" });
      console.error(err);
    }
  }
}

registry.category("actions").add("agent_ia.action_agent", AgentIa);

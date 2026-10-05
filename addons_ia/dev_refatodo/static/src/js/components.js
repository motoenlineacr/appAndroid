/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";

export class Report extends Component {
    static template = "dev_refatodo.Report";
    static components = { Layout };

    setup() {
        this.state = useState({
            allItems: [],
            categories: [],
            displayItems: [],
            count: 0,
            loading: true,
            filterFrom: "",
            filterTo: "",
            searchQuery: "",
            selectedCategory: { id: "all", name: "Todas" },
            categorySearch: "",
            isCategoryMenuOpen: false,
        });

        onWillStart(async () => {
            try {
                const res = await fetch("/api/productos_vendidos");
                const data = await res.json();
                this.state.allItems = data.items || [];
                this.state.categories = data.categories || [];
                this.updateDisplay();
            } catch (e) {
                console.error(e);
            } finally {
                this.state.loading = false;
            }
        });
    }

    get monthDiff() {
        if (!this.state.filterFrom || !this.state.filterTo) return 1;
        const d1 = new Date(this.state.filterFrom);
        const d2 = new Date(this.state.filterTo);
        let months = (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth());
        return months <= 0 ? 1 : months + 1;
    }

    get filteredCategories() {
        if (!this.state.categorySearch) return this.state.categories;
        const query = this.state.categorySearch.toLowerCase();
        return this.state.categories.filter(c => c.name.toLowerCase().includes(query));
    }

    selectCategory = (cat) => {
        this.state.selectedCategory = cat;
        this.state.isCategoryMenuOpen = false;
        this.state.categorySearch = ""; 
        this.updateDisplay();
    }

    updateDisplay() {
        const { filterFrom, filterTo, selectedCategory, searchQuery, allItems } = this.state;
        const numMeses = this.monthDiff;

        let filteredLines = allItems.filter(item => {
            if (filterFrom && item.date_order < filterFrom) return false;
            if (filterTo && item.date_order > filterTo) return false;
            if (selectedCategory.id !== "all" && item.category_id !== selectedCategory.id) return false;
            if (searchQuery && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
            return true;
        });

        const grouped = {};
        filteredLines.forEach(line => {
            if (!grouped[line.id]) {
                grouped[line.id] = { ...line, qty_sold: 0, order_set: new Set() };
            }
            grouped[line.id].qty_sold += line.qty_sold;
            grouped[line.id].order_set.add(line.order_id);
        });

        this.state.displayItems = Object.values(grouped).map(item => {
            const orders = item.order_set.size;
            const pieces = item.qty_sold;
            const valorMenor = Math.min(orders, pieces);
            const promedioMensual = (valorMenor / numMeses).toFixed(2);

            return {
                ...item,
                order_count: orders,
                promedio_mensual: promedioMensual
            };
        }).sort((a, b) => b.qty_sold - a.qty_sold);

        this.state.count = this.state.displayItems.length;
    }
}

registry.category("actions").add("dev_refatodo.report_action", Report);
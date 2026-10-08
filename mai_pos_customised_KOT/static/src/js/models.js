/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { renderToElement } from "@web/core/utils/render";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

// Función para sanitizar notas y evitar que cadenas vacías o corchetes como "[]" se impriman
function sanitizeNote(val) {
    if (!val) {
        return "";
    }
    if (typeof val === "string") {
        const trimmed = val.trim();
        if (
            !trimmed ||
            trimmed === "[]" ||
            trimmed === '""' ||
            trimmed === "''" ||
            trimmed === "{}" ||
            trimmed === "null" ||
            trimmed === "false"
        ) {
            return "";
        }
        try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) {
                return parsed
                    .map((x) => (typeof x === "string" ? x : (x && x.text) || ""))
                    .filter(Boolean)
                    .join(", ");
            }
        } catch (_) {}
        return trimmed;
    }
    if (Array.isArray(val)) {
        return val
            .map((x) => (typeof x === "string" ? x : (x && x.text) || ""))
            .filter(Boolean)
            .join(", ");
    }
    return String(val);
}

// Inyectar CSS dinámico para impresión térmica continua de 80mm sin desperdicio de papel
function ensureKOTPrintStyles() {
    const styleId = "kot-print-80mm-styles";
    let style = document.getElementById(styleId);
    if (!style) {
        style = document.createElement("style");
        style.id = styleId;
        document.head.appendChild(style);
    }
    style.innerHTML = `
        @media print {
            @page {
                size: 80mm auto !important;
                margin: 0mm !important;
            }
            body > *:not(#pos-kot-print-container) {
                display: none !important;
            }
            #pos-kot-print-container {
                display: block !important;
                width: 80mm !important;
                margin: 0 auto !important;
                padding: 0 !important;
                background: #fff !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            html, body {
                margin: 0 !important;
                padding: 0 !important;
                width: 80mm !important;
                background: #fff !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            .pos-receipt-container {
                width: 80mm !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            .pos-receipt {
                width: 72mm !important;
                max-width: 72mm !important;
                margin: 0 auto !important;
                padding: 2mm 0 4mm 0 !important;
                font-family: 'Courier New', Courier, monospace, sans-serif !important;
                font-size: 13px !important;
                line-height: 1.25 !important;
                color: #000 !important;
            }
            .pos-receipt.pt-5, .pos-receipt.mt-5 {
                padding-top: 1mm !important;
                margin-top: 0 !important;
            }
            .pos-receipt-body, .pos-receipt-body.pb-5 {
                padding-bottom: 2mm !important;
                margin-bottom: 0 !important;
            }
            .pos-receipt hr {
                border-top: 2px dashed #000 !important;
                margin: 4px 0 !important;
            }
        }
    `;
}

// 1. Patch a PosOrder para gestionar la impresión de comandas web seguras y bloqueo de líneas
patch(PosOrder.prototype, {
    async printChanges() {
        return this.printChangesWeb();
    },

    removeOrderline(line) {
        if (line && (line.printed_in_comanda || (line.combo_parent_id && line.combo_parent_id.printed_in_comanda))) {
            const dialog = this.env?.services?.dialog || this.pos?.dialog;
            if (dialog) {
                dialog.add(AlertDialog, {
                    title: _t("Línea Bloqueada"),
                    body: _t("No se puede eliminar un producto que ya fue enviado a cocina (comanda)."),
                });
            }
            return false;
        }
        return super.removeOrderline(...arguments);
    },

    async printChangesWeb(env, posInstance) {
        const pos = posInstance || this.pos || (env && env.services && env.services.pos) || (this.env && this.env.services && this.env.services.pos);
        const config = (pos && pos.config) || this.config || (this.models && this.models['pos.config'] && this.models['pos.config'].getFirst()) || {};
        const models = (pos && pos.models) || this.models || {};
        const dialogService = (env && env.services && env.services.dialog) ||
                              (pos && pos.dialog) ||
                              (this.env && this.env.services && this.env.services.dialog);
        const printerService = (env && env.services && env.services.printer) ||
                               (pos && pos.printer) ||
                               (this.env && this.env.services && this.env.services.printer);

        // Cliente (asignado o Mostrador por defecto)
        const partner = (typeof this.getPartner === 'function' && this.getPartner()) || this.partner_id || null;
        const client = partner ? (partner.name || 'Cliente') : 'Mostrador';

        const cashier = (pos && pos.get_cashier && pos.get_cashier().name) ||
                        (pos && pos.user && pos.user.name) ||
                        (this.employee_id && this.employee_id.name) || '';

        const d = new Date();
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const timeFormatted = `${day}/${month}/${year} ${hours}:${minutes}`;

        // Obtener líneas a imprimir
        let rawLines = [];
        if (typeof this.getOrderlines === 'function') {
            rawLines = this.getOrderlines();
        } else if (Array.isArray(this.lines)) {
            rawLines = this.lines;
        } else if (this.lines && typeof this.lines.getAll === 'function') {
            rawLines = this.lines.getAll();
        } else if (this.lines && typeof this.lines[Symbol.iterator] === 'function') {
            rawLines = Array.from(this.lines);
        } else if (this.lines) {
            rawLines = Object.values(this.lines);
        }
        const orderlines = rawLines || [];

        if (!orderlines.length) {
            if (dialogService) {
                dialogService.add(AlertDialog, {
                    title: _t('Orden Vacía'),
                    body: _t('Agregue productos a la orden antes de enviar a cocina.'),
                });
            }
            return false;
        }

        const linesToPrint = orderlines.map(line => {
            const product = (typeof line.getProduct === 'function' ? line.getProduct() : line.product_id) || {};
            const qty = (typeof line.getQuantity === 'function' ? line.getQuantity() : (line.qty || 1));
            const basicName = product.name || (typeof line.getFullProductName === 'function' ? line.getFullProductName() : (line.full_product_name || 'Producto'));

            // Atributos y personalizaciones (ej: Sin Queso, Extras, etc.)
            let attributeNames = [];
            if (line.attribute_value_ids && line.attribute_value_ids.length) {
                attributeNames = line.attribute_value_ids.map(att => {
                    if (typeof att === 'object' && att.name) return att.name;
                    const attObj = models && models['product.template.attribute.value'] ?
                                   models['product.template.attribute.value'].get(att) : null;
                    return attObj ? attObj.name : String(att);
                });
            }
            if (product && product.product_template_variant_value_ids) {
                const variantNames = product.product_template_variant_value_ids.map(v => (typeof v === 'object' && v.name ? v.name : String(v))).filter(Boolean);
                attributeNames = [...new Set([...variantNames, ...attributeNames])];
            }

            const rawNote = typeof line.getNote === 'function' ? line.getNote() : line.note;
            const rawCustomerNote = typeof line.getCustomerNote === 'function' ? line.getCustomerNote() : line.customer_note;
            const note = sanitizeNote(rawNote);
            const customerNote = sanitizeNote(rawCustomerNote);
            const comboParentUuid = line.combo_parent_id ? (line.combo_parent_id.uuid || 'combo') : null;

            return {
                quantity: qty,
                name: basicName,
                basic_name: basicName,
                attributes: attributeNames,
                attribute_value_names: attributeNames,
                note: note,
                customer_note: customerNote,
                is_combo_child: Boolean(line.combo_parent_id),
                combo_parent_uuid: comboParentUuid,
            };
        });

        this.printSequence = (this.printSequence || 0) + 1;
        this.lastPrintedDate = d;

        const operationalTitle = 'COMANDA COCINA';
        const trackingNum = this.tracking_number || '';
        let posRef = (typeof this.getName === 'function' ? this.getName() : this.name) || '';
        if (posRef === client || posRef.includes(client)) {
            posRef = trackingNum ? `Orden #${trackingNum}` : '';
        }

        const data = {
            preset_name: '',
            preset_time: '',
            config_name: config.name || 'SMASHACK POS',
            time: timeFormatted,
            employee_name: cashier,
            tracking_number: trackingNum,
            pos_reference: posRef,
            client: client,
            sequence: this.printSequence,
            lines: linesToPrint,
            changes: {
                title: operationalTitle,
                data: linesToPrint,
            },
        };

        // Inyectar estilos para rollo térmico continuo de 80mm sin desperdicio ni márgenes
        ensureKOTPrintStyles();

        // Renderizar comanda con la plantilla oficial autónoma de Smashack
        let receipt = null;
        try {
            receipt = renderToElement('mai_pos_customised_KOT.CashierOrderChangeReceipt', {
                data: data,
            });
        } catch (e) {
            console.warn("Aviso: Falló CashierOrderChangeReceipt, intentando OrderChangeReceipt:", e);
            try {
                receipt = renderToElement('point_of_sale.OrderChangeReceipt', {
                    data: data,
                });
            } catch (e2) {
                console.error("Error al renderizar OrderChangeReceipt:", e2);
            }
        }

        // Imprimir comanda térmica web montando el recibo en un iframe aislado del DOM de Odoo
        if (receipt) {
            let iframe = document.getElementById("pos-kot-isolated-iframe");
            if (iframe) {
                iframe.remove();
            }
            iframe = document.createElement("iframe");
            iframe.id = "pos-kot-isolated-iframe";
            iframe.style.position = "fixed";
            iframe.style.top = "-9999px";
            iframe.style.left = "-9999px";
            iframe.style.width = "80mm";
            iframe.style.height = "100px";
            document.body.appendChild(iframe);

            const doc = iframe.contentWindow.document;
            doc.open();
            doc.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Comanda Cocina</title>
                    <style>
                        @page {
                            size: 80mm auto;
                            margin: 0mm;
                        }
                        html, body {
                            width: 80mm;
                            margin: 0;
                            padding: 0;
                            background: #fff;
                            font-family: 'Courier New', Courier, monospace, sans-serif;
                            color: #000;
                        }
                        * {
                            box-sizing: border-box;
                            color: #000 !important;
                        }
                    </style>
                </head>
                <body>
                    ${receipt.outerHTML}
                </body>
                </html>
            `);
            doc.close();

            console.log("🖨️ [POS Cajero] Disparando comanda térmica (80mm) desde iframe aislado...");
            const cleanup = () => {
                if (iframe && iframe.parentNode) {
                    iframe.remove();
                }
                if (iframe.contentWindow) {
                    iframe.contentWindow.removeEventListener("afterprint", cleanup);
                }
            };

            try {
                iframe.contentWindow.addEventListener("afterprint", cleanup);
            } catch (e) {}

            setTimeout(() => {
                try {
                    iframe.contentWindow.focus();
                    iframe.contentWindow.print();
                } catch (e) {
                    console.warn("Error en iframe print():", e);
                }
            }, 250);

            setTimeout(cleanup, 15000);
        } else {
            console.error("No se pudo generar el elemento del recibo para imprimir.");
        }

        // Marcar todas las líneas impresas en comanda para bloquear modificaciones posteriores
        for (const line of orderlines) {
            line.printed_in_comanda = true;
            if (line.combo_line_ids) {
                for (const child of line.combo_line_ids) {
                    child.printed_in_comanda = true;
                }
            }
        }

        // Marcar cambios como impresos para limpiar el contador
        if (typeof this.updateLastOrderChange === 'function') {
            this.updateLastOrderChange();
        }

        // El cajero permanece en la orden actual para cobrar de inmediato
        return true;
    },
});

// 2. Patch a ActionpadWidget para ocultar el botón de comanda y permitir que 'Pago' ocupe el 100% de ancho
patch(ActionpadWidget.prototype, {
    get swapButton() {
        return false;
    },
    get totalChangesCount() {
        if (this.displayCategoryCount && this.displayCategoryCount.length) {
            return this.displayCategoryCount.reduce((acc, c) => acc + (c.count || 0), 0);
        }
        return (this.pos.getOrderChanges && this.pos.getOrderChanges().count) || 0;
    },
});

// 3. Patch a PosStore para anular advertencias antes del pago y gestionar el envío de comanda
patch(PosStore.prototype, {
    get defaultPage() {
        const orderUuid = this.openOrder?.uuid || (this.addNewOrder && this.addNewOrder().uuid);
        return {
            page: "ProductScreen",
            params: { orderUuid },
        };
    },

    navigate(page, params = {}) {
        if (page === "FloorScreen") {
            const orderUuid = this.openOrder?.uuid || (this.addNewOrder && this.addNewOrder().uuid);
            return super.navigate("ProductScreen", { orderUuid });
        }
        return super.navigate(page, params);
    },

    showDefault() {
        const page = this.defaultPage;
        this.navigate(page.page, page.params);
    },

    get idleTimeout() {
        const base = super.idleTimeout || [];
        return base.filter((item) => !String(item.action).includes("FloorScreen"));
    },

    async _askForPreparation() {
        // Permitir el paso directo al pago sin advertencias emergentes
        return;
    },

    async submitOrder() {
        const order = this.getOrder();
        if (!order) {
            return;
        }

        // Imprimir comanda web hacia POS-80-Series (192.168.0.87)
        try {
            await order.printChangesWeb(this.env, this);
        } catch (err) {
            console.error("Error imprimiendo comanda web:", err);
        }

        // Si hay pisos configurados y está en modo mesas, seguir el flujo normal
        if (this.config.floor_ids && this.config.floor_ids.length && this.config.default_screen === "tables") {
            return super.submitOrder(...arguments);
        }
    },

    async reprintOrder() {
        const order = this.getOrder();
        if (!order) {
            return;
        }
        try {
            await order.printChangesWeb(this.env, this);
        } catch (err) {
            console.error("Error reimprimiendo comanda web:", err);
        }
        if (this.config.floor_ids && this.config.floor_ids.length && this.config.default_screen === "tables") {
            return super.reprintOrder(...arguments);
        }
    },
});

// 4. Patch a OrderSummary para permitir reconfiguración con 1 clic y bloquear líneas post-comanda
patch(OrderSummary.prototype, {
    async clickLine(ev, orderline) {
        ev.stopPropagation();
        this.numberBuffer.reset();

        const mainLine = orderline.combo_parent_id || orderline;

        // 1. Si la línea ya fue enviada a cocina (comanda impresa), bloquear modificación
        if (mainLine.printed_in_comanda || orderline.printed_in_comanda) {
            this.pos.selectOrderLine(this.currentOrder, orderline);
            this.dialog.add(AlertDialog, {
                title: _t("Comanda ya Enviada"),
                body: _t("Esta orden ya fue enviada a la cocina. No se puede modificar ni reconfigurar."),
            });
            return;
        }

        // 2. Si es un combo o un producto configurable, abrir el popup para reconfigurarlo directamente
        const isCombo = Boolean(
            (mainLine.combo_line_ids && mainLine.combo_line_ids.length) ||
            mainLine.product_id?.combo_ids?.length ||
            mainLine.product_id?.product_tmpl_id?.combo_ids?.length
        );
        const isConfigurable = Boolean(
            (mainLine.product_id?.isConfigurable && mainLine.product_id.isConfigurable()) ||
            (mainLine.product_id?.product_tmpl_id?.isConfigurable && mainLine.product_id.product_tmpl_id.isConfigurable()) ||
            (mainLine.product_id?.product_tmpl_id?.attribute_line_ids && mainLine.product_id.product_tmpl_id.attribute_line_ids.length)
        );

        if (isCombo || isConfigurable) {
            this.pos.selectOrderLine(this.currentOrder, mainLine);
            return this.onOrderlineLongPress(ev, mainLine);
        }

        // 3. Para productos simples, comportamiento normal de selección
        return super.clickLine(...arguments);
    },

    async updateSelectedOrderline({ buffer, key }) {
        const order = this.currentOrder;
        const selectedLine = order?.getSelectedOrderline();
        if (selectedLine) {
            const mainLine = selectedLine.combo_parent_id || selectedLine;
            if (mainLine.printed_in_comanda || selectedLine.printed_in_comanda) {
                this.dialog.add(AlertDialog, {
                    title: _t("Línea Bloqueada"),
                    body: _t("Esta orden ya fue enviada a la cocina y no se puede modificar, eliminar ni alterar cantidad."),
                });
                this.numberBuffer.reset();
                return;
            }
        }
        return super.updateSelectedOrderline(...arguments);
    },
});

// 5. Patch a ProductScreen para bloquear entrada desde el teclado numérico si la línea fue enviada
patch(ProductScreen.prototype, {
    get swapButton() {
        return false;
    },

    _setValue(val) {
        const selectedLine = this.currentOrder?.getSelectedOrderline();
        if (selectedLine) {
            const mainLine = selectedLine.combo_parent_id || selectedLine;
            if (mainLine.printed_in_comanda || selectedLine.printed_in_comanda) {
                this.dialog.add(AlertDialog, {
                    title: _t("Línea Bloqueada"),
                    body: _t("Esta orden ya fue enviada a la cocina y no se puede modificar, eliminar ni alterar cantidad."),
                });
                this.numberBuffer.reset();
                return;
            }
        }
        return super._setValue(...arguments);
    },
});

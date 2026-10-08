/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onWillUnmount } from "@odoo/owl";

const INVOICE_TYPES = new Set([
    "out_invoice",
    "out_refund",
    "in_invoice",
    "in_refund",
    "out_receipt",
    "in_receipt",
]);

function m2oId(value) {
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    return value || false;
}

function asNumber(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n : 0;
}

function closeEnough(a, b, epsilon = 1e-9) {
    return Math.abs(asNumber(a) - asNumber(b)) <= epsilon;
}

function getInvoiceLineRecords(data) {
    const lines = data?.invoice_line_ids;
    if (!lines) {
        return [];
    }
    if (Array.isArray(lines?.records)) {
        return lines.records;
    }
    if (Array.isArray(lines?.data?.records)) {
        return lines.data.records;
    }
    if (Array.isArray(lines?.currentIds) && Array.isArray(lines?.recordsById)) {
        return lines.currentIds
            .map((id) => lines.recordsById[id])
            .filter((r) => !!r);
    }
    return [];
}

function computeFromInvoiceLines(data) {
    const records = getInvoiceLineRecords(data);
    if (!records.length) {
        return { untaxed: 0, total: 0, tax: 0, hasLines: false };
    }

    let untaxed = 0;
    let total = 0;
    for (const rec of records) {
        const lineData = rec?.data || rec;
        if (!lineData) {
            continue;
        }
        if (["line_section", "line_note"].includes(lineData.display_type)) {
            continue;
        }
        untaxed += asNumber(lineData.price_subtotal);
        total += asNumber(lineData.price_total);
    }
    return {
        untaxed,
        total,
        tax: total - untaxed,
        hasLines: true,
    };
}

function computeFromTaxTotals(data) {
    const taxTotals = data?.tax_totals;
    if (!taxTotals || typeof taxTotals !== "object") {
        return { untaxed: 0, total: 0, tax: 0, hasTotals: false };
    }

    const untaxed = asNumber(taxTotals.amount_untaxed);
    const total = asNumber(taxTotals.amount_total);
    let tax = asNumber(taxTotals.amount_tax);
    if (!tax && (untaxed || total)) {
        tax = total - untaxed;
    }

    const hasTotals = Boolean(untaxed || total || tax);
    return { untaxed, total, tax, hasTotals };
}

async function syncDualFooter(controller) {
    if (controller.__adcSyncingDualFooter) {
        return;
    }

    const record = controller.model && controller.model.root;
    if (!record || typeof record.update !== "function") {
        return;
    }

    const modelName = record.resModel || record.model || controller.props?.resModel;
    if (modelName !== "account.move") {
        return;
    }

    const data = record.data || {};
    if (!INVOICE_TYPES.has(data.move_type)) {
        return;
    }

    const taxToday = asNumber(data.tax_today);
    if (taxToday <= 0) {
        return;
    }

    let amountUntaxed = asNumber(data.amount_untaxed);
    let amountTax = asNumber(data.amount_tax);
    let amountTotal = asNumber(data.amount_total);

    if (amountUntaxed === 0 && amountTax === 0 && amountTotal === 0) {
        const fromTaxTotals = computeFromTaxTotals(data);
        if (fromTaxTotals.hasTotals) {
            amountUntaxed = fromTaxTotals.untaxed;
            amountTotal = fromTaxTotals.total;
            amountTax = fromTaxTotals.tax;
        } else {
            const fromLines = computeFromInvoiceLines(data);
            if (fromLines.hasLines) {
                amountUntaxed = fromLines.untaxed;
                amountTotal = fromLines.total;
                amountTax = fromLines.tax;
            }
        }
    }

    const currencyId = m2oId(data.currency_id);
    const companyCurrencyId = m2oId(data.company_currency_id);
    if (!currencyId || !companyCurrencyId) {
        return;
    }

    const updates = {};
    if (currencyId !== companyCurrencyId) {
        updates.amount_untaxed_usd = amountUntaxed;
        updates.amount_tax_usd = amountTax;
        updates.amount_total_usd = amountTotal;
        updates.amount_untaxed_bs = amountUntaxed * taxToday;
        updates.amount_tax_bs = amountTax * taxToday;
        updates.amount_total_bs = amountTotal * taxToday;
    } else {
        updates.amount_untaxed_usd = amountUntaxed / taxToday;
        updates.amount_tax_usd = amountTax / taxToday;
        updates.amount_total_usd = amountTotal / taxToday;
        updates.amount_untaxed_bs = amountUntaxed;
        updates.amount_tax_bs = amountTax;
        updates.amount_total_bs = amountTotal;
    }

    const needsUpdate = Object.entries(updates).some(([fieldName, newValue]) => {
        return !closeEnough(data[fieldName], newValue);
    });

    if (!needsUpdate) {
        return;
    }

    try {
        controller.__adcSyncingDualFooter = true;
        await record.update(updates);
    } finally {
        controller.__adcSyncingDualFooter = false;
    }
}

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        onWillUnmount(() => {
            if (this.__adcSyncTimer) {
                clearInterval(this.__adcSyncTimer);
                this.__adcSyncTimer = null;
            }
        });
    },

    async _onFieldChanged() {
        if (super._onFieldChanged) {
            await super._onFieldChanged(...arguments);
        }
        await syncDualFooter(this);
    },

    async _updateView() {
        await super._updateView(...arguments);
        await syncDualFooter(this);
    },
});

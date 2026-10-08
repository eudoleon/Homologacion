/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { roundDecimals } from "@web/core/utils/numbers";

patch(PosOrder.prototype, {
    setup() {
        super.setup ? super.setup(...arguments) : null;
        this.igtf_charge = this.igtf_charge || 0;
        this.set_igtf_charge(this.igtf_charge);
    },
    set_igtf_charge(entered_charge) {
        this.igtf_charge = entered_charge;
    },
    get_igtf_charge() {
        let charge = 0;
        let percentage = 3.0;
        let decimal_places = 2;
        
        if (this.company) percentage = this.company.igtf_percentage || 3.0;
        else if (this.pos && this.pos.company) percentage = this.pos.company.igtf_percentage || 3.0;
        
        if (this.currency) decimal_places = this.currency.decimal_places;
        else if (this.pos && this.pos.currency) decimal_places = this.pos.currency.decimal_places;

        let payment_lines = (typeof this.get_paymentlines === 'function') ? this.get_paymentlines() : (this.paymentlines || this.payment_ids || []);
        console.log("DEBUG IGTF: get_igtf_charge called. Payment lines:", payment_lines ? payment_lines.length : 0);
        // Siempre se recalcula a partir de las líneas actuales: si no hay líneas en USD el cargo es 0.
        // (Antes solo se recalculaba si había líneas y se devolvía el cargo viejo al borrarlas.)
        if (payment_lines && payment_lines.length > 0) {
            for (let line of payment_lines) {
                let method = line.payment_method || line.payment_method_id;
                if (method && (method.is_igtf || method.pago_usd || (method.name && method.name.includes('USD')))) {
                    let line_amount = 0;
                    if (typeof line.getAmount === 'function') line_amount = line.getAmount();
                    else if (typeof line.get_amount === 'function') line_amount = line.get_amount();
                    else line_amount = line.amount || 0;
                    charge += line_amount * (percentage / 100.0);
                }
            }
        }
        charge = roundDecimals(charge, decimal_places);
        if (this.igtf_charge !== charge) {
            this.igtf_charge = charge;
        }
        console.log("DEBUG IGTF: Calculated charge =", this.igtf_charge);
        console.log("DEBUG IGTF: Returning charge =", this.igtf_charge || 0);
        return this.igtf_charge || 0;
    },
    get totalDue() {
        return (super.totalDue || 0) + this.get_igtf_charge();
    },
    // Odoo 19: `change` del core usa priceIncl (sin IGTF) y compara sin redondear, lo que mostraba
    // un "Cambio" falso igual al IGTF. Se calcula contra totalDue (que ya incluye el IGTF).
    get change() {
        const total_due = this.totalDue;
        const isNegative = total_due < 0;
        const gap = this.currency.round(total_due - this.amountPaid);
        if ((isNegative && gap <= 0) || (!isNegative && gap >= 0)) {
            return 0;
        }
        let amount = isNegative ? -Math.abs(gap) : Math.abs(gap);
        if (this.shouldRoundChange && this.config && this.config.rounding_method) {
            amount = this.config.rounding_method.asymmetricRound(amount);
        }
        return amount;
    },
    get_change() {
        let decimal_places = 2;
        if (this.currency) decimal_places = this.currency.decimal_places;
        else if (this.pos && this.pos.currency) decimal_places = this.pos.currency.decimal_places;

        let change = -(typeof super.get_total_with_tax === 'function' ? super.get_total_with_tax() : (this.amount_total || 0)) - this.get_igtf_charge();
        const lines = (typeof this.get_paymentlines === 'function') ? this.get_paymentlines() : (this.paymentlines || this.payment_ids || []);
        for (let i = 0; i < lines.length; i++) {
            let line_amount = 0;
            if (typeof lines[i].getAmount === 'function') line_amount = lines[i].getAmount();
            else if (typeof lines[i].get_amount === 'function') line_amount = lines[i].get_amount();
            else line_amount = lines[i].amount || 0;
            change += line_amount;
        }
        return roundDecimals(Math.max(0, change), decimal_places);
    },
    get_total_with_tax() {
        let base_total = typeof super.get_total_with_tax === 'function' ? super.get_total_with_tax(...arguments) : (this.amount_total || 0);
        let final_total = base_total + (this.get_igtf_charge() || 0);
        return final_total;
    },
    get_amount_total() {
        let base = typeof super.get_amount_total === 'function' ? super.get_amount_total() : (this.amount_total || 0);
        return base + (this.get_igtf_charge() || 0);
    },
    get_total_paid() {
        let base_paid = typeof super.get_total_paid === 'function' ? super.get_total_paid() : 0;
        return base_paid;
    },
    get_total_with_igtf() {
        return this.get_total_with_tax();
    },
    add_paymentline(payment_method) {
        this.assert_editable();
        if (typeof this.electronic_payment_in_progress === 'function' && this.electronic_payment_in_progress()) {
            return false;
        }
        let newPaymentline = super.add_paymentline(...arguments);
        if (!newPaymentline) return false;

        // Calcular dinámicamente cuánto falta
        let due = 0;
        if (typeof this.get_due === 'function') {
            due = this.get_due();
        } else {
            due = this.totalDue || 0;
        }

        newPaymentline.set_amount ? newPaymentline.set_amount(due) : (newPaymentline.amount = due);
        let cash_rounding = false;
        if (this.config) cash_rounding = this.config.cash_rounding;
        else if (this.pos && this.pos.config) cash_rounding = this.pos.config.cash_rounding;

        if (cash_rounding && this.selected_paymentline) {
            this.selected_paymentline.set_amount ? this.selected_paymentline.set_amount(0) : (this.selected_paymentline.amount = 0);
            this.selected_paymentline.set_amount ? this.selected_paymentline.set_amount(due) : (this.selected_paymentline.amount = due);
        }

        if (payment_method.payment_terminal) {
            newPaymentline.set_payment_status('pending');
        }
        return newPaymentline;
    },
    is_paid() {
        let due = typeof this.get_due === 'function' ? this.get_due() : (this.totalDue || 0);
        return due.toFixed(2) <= 0;
    },
    export_as_JSON() {
        console.log("DEBUG IGTF: export_as_JSON called.");
        const json = super.export_as_JSON ? super.export_as_JSON(...arguments) : {};
        json.igtf_amount = this.get_igtf_charge() || 0;
        let total = 0;
        if (this.totalDue !== undefined) total = this.totalDue;
        else if (typeof this.get_total_with_tax === 'function') total = this.get_total_with_tax();
        json.amount_total = total;
        console.log("DEBUG IGTF: export_as_JSON returning amount_total =", total);
        return json;
    },
    serializeForORM(opts={}) {
        console.log("DEBUG IGTF: serializeForORM called.");
        const json = super.serializeForORM ? super.serializeForORM(...arguments) : {};
        json.igtf_amount = this.get_igtf_charge() || 0;
        console.log("DEBUG IGTF: serializeForORM returning igtf_amount =", json.igtf_amount);
        return json;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.igtf_charge = json.igtf_charge || 0.0;
        this.amount_total = json.amount_total || 0.0;
    },
    export_for_printing() {
        console.log("DEBUG IGTF: export_for_printing called.");
        const json = super.export_for_printing ? super.export_for_printing(...arguments) : {};
        json.igtf_charge = this.get_igtf_charge() || 0;
        let total = 0;
        if (typeof this.get_total_with_tax === 'function') {
            total = this.get_total_with_tax();
        } else {
            total = (this.amount_total || 0) + json.igtf_charge;
        }
        json.amount_total = total;
        json.total_with_tax = total;
        console.log("DEBUG IGTF: export_for_printing returning amount_total =", total, "igtf_charge =", json.igtf_charge);
        return json;
    }
});

/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

async function validateManager(env) {
    var managerEmployeeIDs = env.pos.config.manager_employee_ids || [];
    var cashier = env.pos.get_cashier();
    if (cashier && managerEmployeeIDs.includes(cashier.id)) {
        return true;
    }

    const password = await makeAwaitable(env.services.dialog, NumberPopup, {
        title: _t("Manager Validation"),
        isPassword: true,
    });

    if (password) {
        var employees = env.pos.employees;
        for (var i = 0; i < employees.length; i++) {
            if (managerEmployeeIDs.includes(employees[i].id) && !!employees[i].pin && window.Sha1.hash(password) === employees[i].pin) {
                return true;
            } else if (managerEmployeeIDs.includes(employees[i].id) && !!employees[i].barcode && window.Sha1.hash(password) === employees[i].barcode) {
                return true;
            }
        }
        env.services.dialog.add(AlertDialog, {
            title: _t("Access Denied"),
            body: _t("Incorrect manager PIN!"),
        });
    }
    return false;
}

patch(PosStore.prototype, {
    async closePos() {
        if (this.config.module_pos_hr && this.config.iface_employee_validate_close) {
            if (await validateManager(this.env)) {
                return super.closePos(...arguments);
            }
            return;
        }
        return super.closePos(...arguments);
    },
    async pay() {
        if (this.config.module_pos_hr && this.config.iface_employee_validate_payment) {
            if (await validateManager(this.env)) {
                return super.pay(...arguments);
            }
            return;
        }
        return super.pay(...arguments);
    }
});

patch(ProductScreen.prototype, {
    async updateSelectedOrderline({ buffer, key }) {
        if (this.pos.config.module_pos_hr) {
            var orderLines = this.currentOrder.get_orderlines();
            if (orderLines !== undefined && orderLines.length > 0) {
                var currentQty = this.currentOrder.get_selected_orderline().get_quantity();
                
                let needsValidation = false;
                
                if (this.pos.numpadMode === 'quantity') {
                    if (buffer === "" && key === "Backspace") {
                        if (this.pos.config.iface_employee_validate_delete_orderline) needsValidation = true;
                    } else if (!isNaN(parseFloat(buffer)) && parseFloat(buffer) < currentQty) {
                        if (this.pos.config.iface_employee_validate_decrease_quantity) needsValidation = true;
                    }
                } else if (this.pos.numpadMode === 'discount' && this.pos.config.iface_employee_validate_discount) {
                    if (!isNaN(parseFloat(buffer)) || (buffer === "" && key === "Backspace")) needsValidation = true;
                } else if (this.pos.numpadMode === 'price' && this.pos.config.iface_employee_validate_price) {
                    if (!isNaN(parseFloat(buffer)) || (buffer === "" && key === "Backspace")) needsValidation = true;
                }

                if (needsValidation) {
                    if (await validateManager(this.env)) {
                        return super.updateSelectedOrderline(...arguments);
                    }
                    // Reset buffer if validation failed
                    this.numberBuffer.reset();
                    return;
                }
            }
        }
        return super.updateSelectedOrderline(...arguments);
    }
});

patch(TicketScreen.prototype, {
    async _onDeleteOrder({ detail: order }) {
        if (this.pos.config.module_pos_hr && this.pos.config.iface_employee_validate_delete_order) {
            if (await validateManager(this.env)) {
                return super._onDeleteOrder(...arguments);
            }
            return;
        }
        return super._onDeleteOrder(...arguments);
    }
});

/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { patch } from "@web/core/utils/patch";
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// 1. Patch PosStore to store/load all discounts
patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        if (!this.db) {
            this.db = {};
        }
        // Safety mock for get_product_by_id to avoid crashes in other legacy/partially-migrated modules
        this.db.get_product_by_id = (id) => {
            return this.models["product.product"] ? this.models["product.product"].get(id) : null;
        };
        const discounts = this.models["pos.custom.discount"] ? this.models["pos.custom.discount"].getAll() : [];
        this.db.all_discounts = discounts || [];
    }
});

// 2. Patch PosOrderline to support custom properties
patch(PosOrderline.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.custom_discount = this.custom_discount || '';
        this.custom_discount_reason = this.custom_discount_reason || '';
        this.list_discount = this.list_discount || false;
        this.selected_list_discount = this.selected_list_discount || false;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.custom_discount = json.custom_discount || '';
        this.custom_discount_reason = json.custom_discount_reason || '';
        this.list_discount = json.list_discount || false;
        this.selected_list_discount = json.selected_list_discount || false;
    },
    export_as_JSON() {
        const loaded = super.export_as_JSON(...arguments);
        if (this.custom_discount_reason) {
            loaded.custom_discount_reason = this.custom_discount_reason;
        }
        if (this.custom_discount) {
            loaded.custom_discount = this.custom_discount;
        }
        if (this.list_discount) {
            loaded.list_discount = this.list_discount;
        }
        if (this.selected_list_discount) {
            loaded.selected_list_discount = this.selected_list_discount;
        }
        return loaded;
    },
    export_for_printing() {
        const dict = super.export_for_printing(...arguments);
        dict.custom_discount = this.custom_discount;
        dict.custom_discount_reason = this.custom_discount_reason;
        dict.list_discount = this.list_discount;
        dict.selected_list_discount = this.selected_list_discount;
        return dict;
    },
    get_custom_discount_reason() {
        return this.custom_discount_reason;
    }
});

// 3. OWL Custom Dialog Component for WkDiscountPopup
export class WkDiscountPopup extends Component {
    static template = "pos_custom_discounts.WkDiscountPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        selected_list_discount: { type: Object, optional: true },
        close: { type: Function },
    };
    setup() {
        this.pos = usePos();
        const discounts = this.pos.models["pos.custom.discount"] ? this.pos.models["pos.custom.discount"].getAll() : [];
        this.discounts = discounts;
        this.state = useState({
            selected_discount: this.props.selected_list_discount || false,
            wk_discount_percentage: this.props.selected_list_discount ? this.props.selected_list_discount.discount_percent : 0,
            show_error: false,
        });
    }

    get hasActiveDiscount() {
        const order = this.pos.selectedOrder;
        const selectedLine = order ? order.getSelectedOrderline() : null;
        return this.props.selected_list_discount || (selectedLine && selectedLine.discount > 0);
    }

    click_wk_product_discount(item) {
        this.state.selected_discount = item;
        this.state.wk_discount_percentage = item.discount_percent;
        this.state.show_error = false;
    }

    async click_customize() {
        const cashier = this.pos.getCashier();
        const pin = cashier.pin || (cashier.model && cashier.model.pin) || false;
        
        this.props.close();
        
        if (this.pos.config.allow_security_pin && pin) {
            const inputPin = await makeAwaitable(this.env.services.dialog, NumberPopup, {
                title: _t("Password?"),
                isPassword: true,
            });
            if (inputPin && window.Sha1.hash(inputPin) === pin) {
                this.env.services.dialog.add(WkCustomDiscountPopup, {
                    title: _t("Personalizar descuento"),
                });
            } else if (inputPin) {
                this.env.services.dialog.add(AlertDialog, {
                    title: _t("¡¡¡Contraseña incorrecta!!!"),
                    body: _t("La contraseña ingresada es incorrecta"),
                });
            }
        } else {
            this.env.services.dialog.add(WkCustomDiscountPopup, {
                title: _t("Personalizar descuento"),
            });
        }
    }

    click_apply() {
        if (this.state.wk_discount_percentage === 0) {
            this.state.show_error = true;
            return;
        }
        const order = this.pos.selectedOrder;
        const selectedLine = order ? order.getSelectedOrderline() : null;
        if (selectedLine) {
            selectedLine.setDiscount(this.state.wk_discount_percentage);
            selectedLine.custom_discount_reason = '';
            selectedLine.list_discount = true;
            selectedLine.selected_list_discount = this.state.selected_discount;
            selectedLine.custom_discount = false;
        }
        this.props.close();
    }

    click_apply_complete_order() {
        if (this.state.wk_discount_percentage === 0) {
            this.state.show_error = true;
            return;
        }
        const order = this.pos.selectedOrder;
        const lines = order ? (order.lines || order.get_orderlines() || []) : [];
        for (const line of lines) {
            line.setDiscount(this.state.wk_discount_percentage);
            line.custom_discount_reason = '';
            line.list_discount = true;
            line.selected_list_discount = this.state.selected_discount;
            line.custom_discount = false;
        }
        this.props.close();
    }

    click_remove_discount() {
        const order = this.pos.selectedOrder;
        const selectedLine = order ? order.getSelectedOrderline() : null;
        if (selectedLine) {
            selectedLine.setDiscount(0);
            selectedLine.list_discount = false;
            selectedLine.selected_list_discount = false;
            selectedLine.custom_discount = false;
            selectedLine.custom_discount_reason = '';
        }
        this.props.close();
    }
}

// 4. OWL Custom Dialog Component for WkCustomDiscountPopup
export class WkCustomDiscountPopup extends Component {
    static template = "pos_custom_discounts.WkCustomDiscountPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        discount: { type: Number, optional: true },
        custom_discount_reason: { type: String, optional: true },
        custom_discount: { type: Boolean, optional: true },
        close: { type: Function },
    };
    setup() {
        this.pos = usePos();
        this.state = useState({
            discount: this.props.discount || '',
            reason: this.props.custom_discount_reason || '',
            error_message: '',
        });
    }

    click_current_product() {
        const discountVal = parseFloat(this.state.discount);
        if (isNaN(discountVal) || discountVal > 100 || discountVal <= 0) {
            this.state.error_message = _t("El Porcentaje de Descuento debe estar entre 0 a 100.");
            return;
        }
        const order = this.pos.selectedOrder;
        const selectedLine = order ? order.getSelectedOrderline() : null;
        if (selectedLine) {
            selectedLine.setDiscount(discountVal);
            selectedLine.custom_discount_reason = this.state.reason;
            selectedLine.custom_discount = true;
            selectedLine.list_discount = false;
            selectedLine.selected_list_discount = false;
        }
        this.props.close();
    }

    click_whole_order() {
        const discountVal = parseFloat(this.state.discount);
        if (isNaN(discountVal) || discountVal > 100 || discountVal <= 0) {
            this.state.error_message = _t("El Porcentaje de Descuento debe estar entre 0 a 100.");
            return;
        }
        const order = this.pos.selectedOrder;
        const lines = order ? (order.lines || order.get_orderlines() || []) : [];
        for (const line of lines) {
            line.setDiscount(discountVal);
            line.custom_discount_reason = this.state.reason;
            line.custom_discount = true;
            line.list_discount = false;
            line.selected_list_discount = false;
        }
        this.props.close();
    }

    click_remove_discount() {
        const order = this.pos.selectedOrder;
        const selectedLine = order ? order.getSelectedOrderline() : null;
        if (selectedLine) {
            selectedLine.setDiscount(0);
            selectedLine.custom_discount = false;
            selectedLine.custom_discount_reason = '';
            selectedLine.list_discount = false;
            selectedLine.selected_list_discount = false;
        }
        this.props.close();
    }
}

// 5. Patch ProductScreen to intercept discount keypad input
patch(ProductScreen.prototype, {
    async onNumpadClick(buttonValue) {
        if (buttonValue === "discount") {
            const order = this.currentOrder;
            const selected_orderline = order ? order.getSelectedOrderline() : null;
            const hasDiscounts = this.pos.config.discount_ids.length > 0;
            const allowCustom = this.pos.config.allow_custom_discount;
            
            if (hasDiscounts || allowCustom) {
                if (selected_orderline) {
                    if (selected_orderline.list_discount && selected_orderline.selected_list_discount) {
                        this.dialog.add(WkDiscountPopup, {
                            title: _t("Listado de Descuentos"),
                            selected_list_discount: selected_orderline.selected_list_discount,
                        });
                    } else if (selected_orderline.custom_discount) {
                        this.dialog.add(WkCustomDiscountPopup, {
                            title: _t("Personalizar Descuento"),
                            discount: selected_orderline.discount,
                            custom_discount: true,
                            custom_discount_reason: selected_orderline.get_custom_discount_reason(),
                        });
                    } else {
                        this.dialog.add(WkDiscountPopup, {
                            title: _t("Listado de Descuentos"),
                        });
                    }
                } else {
                    this.dialog.add(AlertDialog, {
                        title: _t("No hay ninguna línea de pedido seleccionada"),
                        body: _t("No se ha seleccionado ninguna línea de pedido. Añada o seleccione una."),
                    });
                }
                return;
            } else {
                this.dialog.add(AlertDialog, {
                    title: _t("No hay Descuentos Disponibles"),
                    body: _t("No hay descuento disponible para el TPV actual. Añada el descuento desde la configuración."),
                });
                return;
            }
        }
        return super.onNumpadClick(...arguments);
    }
});

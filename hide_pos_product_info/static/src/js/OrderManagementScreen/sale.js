/** @odoo-module **/

import { SaleOrderManagementScreen } from "@pos_sale/app/order_management_screen/sale_order_management_screen";
import { patch } from "@web/core/utils/patch";

patch(SaleOrderManagementScreen.prototype, {
    // Elegant Interception Strategy!
    async _onClickSaleOrder(event) {
        const originalShowPopup = this.showPopup;
        this.showPopup = async (name, options) => {
            if (name === "SelectionPopup" && options?.list?.some(el => el.item === "settle")) {
                // Return our custom single option selection
                return originalShowPopup.call(this, "SelectionPopup", {
                    title: this.env._t("¿Qué deseas hacer?"),
                    list: [
                        {
                            id: "settle",
                            label: this.env._t("Facturar el pedido"),
                            item: "settle",
                        }
                    ]
                });
            }
            return originalShowPopup.apply(this, arguments);
        };
        try {
            await super._onClickSaleOrder(...arguments);
        } finally {
            this.showPopup = originalShowPopup;
        }
    }
});

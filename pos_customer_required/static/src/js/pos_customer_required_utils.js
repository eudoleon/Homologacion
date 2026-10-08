/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

const SCREEN_CLASSES = {
    ProductScreen,
    ReceiptScreen,
    PaymentScreen,
    TicketScreen,
};

const getPos = (component) => {
    const posService = component.env?.services?.pos;
    return posService?.pos || component.env?.pos || component.pos || posService || null;
};

export const getPosConfig = (component) => {
    const pos = getPos(component);
    return pos?.config || component.config || {};
};

export const getCurrentOrder = (component) => {
    const pos = getPos(component);
    return component.currentOrder || pos?.get_order?.() || pos?.selectedOrder || pos?.getOrder?.() || null;
};

export const getPartner = (order) => order?.getPartner?.() || order?.get_partner?.() || order?.partner || order?.partner_id || null;

export const openPartnerSelection = async (component, currentPartner = null) => {
    const params = { partner: currentPartner };

    if (typeof component.showTempScreen === "function") {
        return component.showTempScreen("PartnerListScreen", params);
    }
    if (typeof component.showScreen === "function") {
        return component.showScreen("PartnerListScreen", params);
    }

    const pos = getPos(component);
    if (typeof pos?.showTempScreen === "function") {
        return pos.showTempScreen("PartnerListScreen", params);
    }
    if (typeof pos?.showScreen === "function") {
        return pos.showScreen("PartnerListScreen", params);
    }

    return { confirmed: false, payload: null };
};

export const showScreenSafe = (component, nextScreen) => {
    // Always use the string name for Odoo 18+ compatibility (pos.showScreen expects string)
    const resolved = typeof nextScreen === "string" ? { name: nextScreen, props: {} } : nextScreen || {};
    const name = resolved.name || "ProductScreen";

    // Try component.pos first (set via usePos() hook in Odoo 18+ setup)
    const pos =
        component.pos ||
        component.env?.services?.pos ||
        component.env?.pos ||
        getPos(component);

    if (typeof pos?.showScreen === "function") {
        pos.showScreen(name);
        return;
    }

    // Fallback: component itself has showScreen (older versions)
    if (typeof component.showScreen === "function") {
        component.showScreen(name);
    }
};

export const resolveNextScreenAfterNewOrder = (createdNewOrder, nextScreen) => {
    const resolved = typeof nextScreen === "string" ? { name: nextScreen, props: {} } : nextScreen || {};
    if (
        createdNewOrder &&
        (!resolved.name || resolved.name === "ReceiptScreen" || resolved.name === "ReprintReceiptScreen")
    ) {
        return { name: "ProductScreen", props: {} };
    }
    return { name: resolved.name || "ProductScreen", props: resolved.props || {} };
};

export const addNewOrderSafe = (component) => {
    // Try component.pos first (Odoo 18+: set directly from usePos() hook in setup)
    const pos =
        component.pos ||
        component.env?.services?.pos ||
        component.env?.pos ||
        getPos(component);
    if (typeof pos?.addNewOrder === "function") {
        pos.addNewOrder();
        return true;
    }
    if (typeof pos?.addOrder === "function") {
        pos.addOrder();
        return true;
    }
    if (typeof pos?.add_new_order === "function") {
        pos.add_new_order();
        return true;
    }
    // Odoo 18/19 uses createNewOrder + set_order
    if (typeof pos?.createNewOrder === "function" && typeof pos?.set_order === "function") {
        pos.set_order(pos.createNewOrder());
        return true;
    }
    if (typeof component._addNewOrder === "function") {
        component._addNewOrder();
        return true;
    }
    return false;
};

export const removeOrderSafe = (component, order) => {
    const pos = getPos(component);
    if (typeof pos?.removeOrder === "function") {
        pos.removeOrder(order);
        return true;
    }
    if (typeof pos?.remove_order === "function") {
        pos.remove_order(order);
        return true;
    }
    return false;
};
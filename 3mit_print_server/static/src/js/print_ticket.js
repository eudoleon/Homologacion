/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

const SCREEN_CLASSES = {
    ProductScreen,
    ReceiptScreen,
    PaymentScreen,
    TicketScreen,
};

const fixMoney = (window.fixMoney = function fixMoney(n) {
	return Math.round(n * 100) / 100;
	//return round_di(n, 2);
});

// Desactivar y anular automáticamente cualquier Service Worker que intercepte peticiones al servidor fiscal local
if (typeof window !== "undefined" && typeof navigator !== "undefined" && "serviceWorker" in navigator) {
    try {
        navigator.serviceWorker.getRegistrations().then((registrations) => {
            for (const reg of registrations) {
                reg.unregister().catch(() => {});
            }
        }).catch(() => {});
    } catch (_) {}

    try {
        const dummyWorker = {
            postMessage: () => {},
            addEventListener: () => {},
            removeEventListener: () => {},
            state: "activated",
        };
        navigator.serviceWorker.register = function () {
            console.log("[3mit] Service Worker registration bypassed to prevent NS_ERROR_INTERCEPTION_FAILED");
            return Promise.resolve({
                installing: null,
                waiting: null,
                active: dummyWorker,
                addEventListener: () => {},
                removeEventListener: () => {},
                dispatchEvent: () => true,
                postMessage: () => {},
            });
        };
    } catch (_) {}
}

const toggleElementVisibility = (element, isVisible) => {
	if (!element) {
		return;
	}
	element.classList.toggle("is-hidden", !isVisible);
};

const toggleElementsVisibility = (elements, isVisible) => {
    for (const element of elements || []) {
        toggleElementVisibility(element, isVisible);
    }
};

const callRpc = async (component, model, method, args = [], kwargs = {}) => {
    const orm = component.orm || component.env?.services?.orm;
    if (orm && typeof orm.call === "function") {
        return orm.call(model, method, args, kwargs);
    }
    if (typeof component.rpc === "function") {
        return component.rpc({ model, method, args, kwargs });
    }
    throw new Error("Servicio RPC no disponible en este componente");
};

const getPosService = (component) => component.env?.services?.pos || null;

const getPos = (component) => {
    return component.env?.pos || component.pos || getPosService(component)?.pos || getPosService(component) || null;
};

const getPosConfig = (component) => getPos(component)?.config || {};

const resolveNextScreen = (nextScreen) => {
    if (typeof nextScreen === "string") {
        return { name: nextScreen, props: {} };
    }
    return { name: nextScreen?.name, props: nextScreen?.props };
};

const showScreenSafe = (component, nextScreen) => {
    console.log("[3mit] showScreenSafe invocado con nextScreen:", nextScreen);
    const { name } = resolveNextScreen(nextScreen || { name: "ProductScreen", props: {} });
    console.log("[3mit] Screen resuelta a:", name);
    if (!name) {
        console.warn("[3mit] showScreenSafe abortado: nombre de pantalla inválido");
        return;
    }
    const pos =
        component.pos ||
        component.env?.services?.pos ||
        component.env?.pos ||
        getPosService(component)?.pos ||
        getPos(component);
    
    console.log("[3mit] Objeto pos encontrado:", !!pos);
    
    if (typeof pos?.showScreen === "function") {
        console.log("[3mit] Llamando pos.showScreen(" + name + ")");
        pos.showScreen(name);
        return;
    }
    if (typeof component.showScreen === "function") {
        console.log("[3mit] Llamando component.showScreen(" + name + ")");
        component.showScreen(name);
        return;
    }
    console.error("[3mit] Falló showScreenSafe: No se encontró método showScreen");
};

const resolveNextScreenAfterNewOrder = (createdNewOrder, nextScreen) => {
    const resolved = resolveNextScreen(nextScreen || { name: "ProductScreen", props: {} });
    if (
        createdNewOrder &&
        (!resolved.name || resolved.name === "ReceiptScreen" || resolved.name === "ReprintReceiptScreen")
    ) {
        return { name: "ProductScreen", props: {} };
    }
    return resolved;
};

const addNewOrderSafe = (component) => {
    // Prioritize component.pos (set via usePos() in setup() in Odoo 18/19)
    const pos =
        component.pos ||
        component.env?.services?.pos ||
        component.env?.pos ||
        getPosService(component)?.pos ||
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

const removeOrderSafe = (component, order) => {
    const posService = component.env?.services?.pos;
    const pos = posService?.pos || getPos(component) || posService;
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

let _workingPrinterHost = null;

const getCandidateUrls = (rawUrl) => {
    try {
        const parsed = new URL(rawUrl);
        const urls = [];
        const port = parsed.port || "5000";

        if (_workingPrinterHost) {
            const u = new URL(rawUrl);
            u.host = _workingPrinterHost.includes(":") ? _workingPrinterHost : `${_workingPrinterHost}:${port}`;
            urls.push(u.toString());
        }

        if (!urls.includes(rawUrl)) {
            urls.push(rawUrl);
        }

        const uLocal1 = new URL(rawUrl);
        uLocal1.host = `localhost:${port}`;
        if (!urls.includes(uLocal1.toString())) {
            urls.push(uLocal1.toString());
        }

        const uLocal2 = new URL(rawUrl);
        uLocal2.host = `127.0.0.1:${port}`;
        if (!urls.includes(uLocal2.toString())) {
            urls.push(uLocal2.toString());
        }

        return urls;
    } catch (_) {
        return [rawUrl];
    }
};

const fetchWithFallback = async (rawUrl, options = {}, timeout = 10000) => {
    const urls = getCandidateUrls(rawUrl);
    let lastError = null;

    for (const targetUrl of urls) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(targetUrl, {
                ...options,
                signal: controller.signal,
            });
            clearTimeout(timeoutId);
            try {
                _workingPrinterHost = new URL(targetUrl).host;
            } catch (_) {}
            return response;
        } catch (err) {
            clearTimeout(timeoutId);
            lastError = err;
            console.warn(`[3mit] Falló petición a ${targetUrl}:`, err);
        }
    }
    throw lastError || new Error(`No se pudo conectar a ${rawUrl}`);
};

const postJsonWithTimeout = async (url, payload, timeout = 30000) => {
    const urls = getCandidateUrls(url);
    let lastError = null;

    for (const targetUrl of urls) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(targetUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
                signal: controller.signal,
            });
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            try {
                _workingPrinterHost = new URL(targetUrl).host;
            } catch (_) {}
            return await response.json();
        } catch (err) {
            clearTimeout(timeoutId);
            lastError = err;
            console.warn(`[3mit] Falló POST a ${targetUrl}:`, err);
        }
    }
    throw lastError || new Error(`No se pudo conectar a ${url}`);
};

const showErrorPopup = async (component, title, body) => {
    if (component.env && component.env.services && component.env.services.dialog) {
        return component.env.services.dialog.add(AlertDialog, { title, body });
    }
    const notification = component.notification || component.env?.services?.notification;
    if (notification && typeof notification.add === "function") {
        notification.add(`${title}: ${body}`, { type: "danger" });
        return;
    }
    console.error(title, body);
};

    patch(ReceiptScreen.prototype, {
        get currentOrder() {
            const pos = getPos(this);
            if (pos && typeof pos.get_order === "function") {
                return this.props?.order || pos.get_order();
            }
            return this.props?.order || pos?.selectedOrder || null;
        },

        mounted() {
            super.mounted(...arguments);
            this._syncReceiptActionButtons();
            
            // Ocultado agresivo para Editar Pago y Vista Previa del Recibo en POS
            const hideInterval = setInterval(() => {
                try {
                    // Ocultar botón de Editar Pago y botón de Imprimir Recibo Completo
                    const candidates = document.querySelectorAll('button, .btn, .button, div, span, a, .edit-order-payment');
                    candidates.forEach(b => {
                        // Never hide our custom green fiscal print button or blue next order button
                        if (
                            b.classList.contains('mit-fiscal-print') ||
                            b.classList.contains('mit-action-button--fiscal') ||
                            b.classList.contains('mit-receipt-new-order') ||
                            b.classList.contains('mit-action-button--next')
                        ) {
                            return;
                        }
                        const text = (b.innerText || b.textContent || "").toLowerCase().trim();
                        const isEditPayment = text.includes("editar pago") || text.includes("edit payment") || (text.includes("editar") && text.includes("pago")) || b.classList.contains("edit-order-payment");
                        const isPrintReceipt = text.includes("imprimir recibo") || text.includes("recibo completo") || text.includes("print receipt") || text === "imprimir recibo completo" || (b.classList.contains("print") && !b.classList.contains("fiscal-print"));
                        
                        if (isEditPayment || isPrintReceipt) {
                            // Ensure we only hide the button element itself (text length < 80) and not an outer section
                            if (text.length < 80 || b.tagName === 'BUTTON' || b.classList.contains('button') || b.classList.contains('btn')) {
                                b.style.setProperty("display", "none", "important");
                                b.style.setProperty("visibility", "hidden", "important");
                                b.style.setProperty("opacity", "0", "important");
                                b.style.setProperty("height", "0px", "important");
                                b.style.setProperty("min-height", "0px", "important");
                                b.style.setProperty("max-height", "0px", "important");
                                b.style.setProperty("margin", "0px", "important");
                                b.style.setProperty("padding", "0px", "important");
                                b.style.setProperty("overflow", "hidden", "important");
                            }
                        }
                    });

                    // Ocultar Vista Previa del Recibo / Ticket en el panel derecho
                    const receiptSelectors = [
                        '.pos-receipt-container',
                        '.pos-receipt',
                        '.order-receipt',
                        '.pos-receipt-print',
                        '.pos-receipt-preview',
                        '.receipt-container',
                        '.receipt-content',
                        '.o_pos_receipt',
                        '.o_receipt_preview',
                        '.pos-receipt-view',
                        '.pos-receipt-wrapper',
                        '[class*="pos-receipt"]',
                        '[class*="order-receipt"]',
                        '[class*="receipt-container"]'
                    ];
                    receiptSelectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            if (!el.classList.contains('mit-action-button') && !el.classList.contains('receipt-screen') && !el.classList.contains('pos-screen') && !el.classList.contains('pos')) {
                                el.style.setProperty("display", "none", "important");
                                el.style.setProperty("visibility", "hidden", "important");
                                el.style.setProperty("opacity", "0", "important");
                                el.style.setProperty("width", "0px", "important");
                                el.style.setProperty("height", "0px", "important");
                            }
                        });
                    });

                    // Ocultar la columna derecha en la disposición flex de la pantalla de recibo
                    const rightColumns = document.querySelectorAll(
                        '.receipt-screen .default-view > div:nth-child(2), .receipt-screen .screen-content > div:nth-child(2), .pos .default-view > div:nth-child(2), .pos-receipt-screen .default-view > div:nth-child(2), .pos .screen-content > div:nth-child(2)'
                    );
                    rightColumns.forEach(col => {
                        col.style.setProperty("display", "none", "important");
                        col.style.setProperty("visibility", "hidden", "important");
                        col.style.setProperty("width", "0px", "important");
                        col.style.setProperty("opacity", "0", "important");
                    });
                } catch(e) {
                    console.warn("[3mit] No se pudieron ocultar elementos del recibo", e);
                }
            }, 200);
            setTimeout(() => clearInterval(hideInterval), 15000);
        },

		_syncReceiptActionButtons() {
            const order = this.props?.order || this.currentOrder;
            const orderKey = order ? (order.uid || order.name || order.id) : null;
            const isStoredPrinted = orderKey ? localStorage.getItem('mit_printed_' + orderKey) === 'true' : false;
			const isPrinted = Boolean(order?.impresa || order?.ticket_fiscal || order?.serial_fiscal || order?._printed_fiscal || isStoredPrinted);
            if (order && isPrinted) {
                order.impresa = true;
            }
            const fiscalPrintBtns = [
                ...(this.el ? Array.from(this.el.querySelectorAll(".mit-fiscal-print")) : []),
                ...Array.from(document.querySelectorAll(".mit-fiscal-print"))
            ];
            const newOrderBtns = [
                ...(this.el ? Array.from(this.el.querySelectorAll(".mit-receipt-new-order")) : []),
                ...Array.from(document.querySelectorAll(".mit-receipt-new-order"))
            ];
            toggleElementsVisibility(fiscalPrintBtns, !isPrinted);
            toggleElementsVisibility(newOrderBtns, isPrinted);
        },

			async print_3mit(order) {
				const json = await this._3mit_prepare_json(order);
                const printer_host = getPosConfig(this).printer_host;
                console.log("[3mit] PAYLOAD A ENVIAR AL SERVIDOR LOCALHOST:", JSON.stringify(json, null, 2));
                try {
                    const rs = await postJsonWithTimeout(`http://${printer_host}/api/imprimir/factura`, json, 30000);
					
					if (rs.status == "OK") {
						return rs.data;
					} else {
						throw new Error(rs.message || "Error devuelto por la impresora fiscal.");
					}
                } catch (err) {
                    const msg = (err?.message || "").toLowerCase();
                    if (msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("timeout")) {
                        throw new Error("IMPRESORA DESCONECTADA. Por favor, verifique el cable, la conexión de red o si la impresora está encendida.");
                    }
                    throw new Error(err?.message || err?.statusText || "Error de comunicación con la impresora fiscal.");
                }
            },

        async printKitchenOrderOnly() {
            console.log("🍽️ [3mit] Botón 'Imprimir orden' presionado.");
            const order = this.props?.order || this.currentOrder || (this.pos && this.pos.getOrder && this.pos.getOrder()) || (this.pos && this.pos.selectedOrder);
            if (!order) {
                return;
            }
            if (typeof order.printChangesWeb === "function") {
                try {
                    const posInstance = this.pos || this.env?.services?.pos || getPos(this);
                    await order.printChangesWeb(this.env, posInstance);
                } catch (err) {
                    console.error("Error al imprimir orden en cocina:", err);
                    await showErrorPopup(this, "Error de Impresión", "No se pudo imprimir la orden de cocina.");
                }
            } else {
                console.warn("order.printChangesWeb no está disponible en la orden.");
            }
        },

        async printNewButtonFiscal() {
                console.log("🖨️ Botón de Imprimir Fiscal presionado.");
                try {
                    const printer_host = getPosConfig(this).printer_host;
                    const pingRes = await fetchWithFallback(`http://${printer_host}/api/ping`, {}, 3000).catch(()=>null);
                    if (!pingRes || !pingRes.ok) {
                        await showErrorPopup(this, "⚠️ IMPRESORA DESCONECTADA", "No se puede establecer comunicación con el servidor de impresión. Verifique que la impresora esté encendida y conectada.");
                        return;
                    }
                } catch(e) {
                    console.warn("Ping failed", e);
                }

                const isPrinted = await this._printNewButtonFiscal();

                if (isPrinted) {
                    const order = this.props?.order || this.currentOrder || (this.pos && this.pos.getOrder && this.pos.getOrder()) || (this.pos && this.pos.selectedOrder);
                    if (order) {
                        order.impresa = true;
                        order._printed_fiscal = true;
                        const orderKey = order.uid || order.name || order.id;
                        if (orderKey) {
                            try { localStorage.setItem('mit_printed_' + orderKey, 'true'); } catch(e) {}
                        }
                    }
                    this._syncReceiptActionButtons();
                    if (typeof this.render === "function") {
                        try { this.render(true); } catch(e) { this.render(); }
                    }
                    console.log("✅ Impresión finalizada, botón 'New Order' visible.");

                    // Auto-imprimir comanda en cocina de forma automática
                    if (order && typeof order.printChangesWeb === "function") {
                        try {
                            const posInstance = this.pos || this.env?.services?.pos || getPos(this);
                            await order.printChangesWeb(this.env, posInstance);
                        } catch (err) {
                            console.warn("Fallo impresión automática de comanda en cocina:", err);
                        }
                    }
                } else {
                    this._syncReceiptActionButtons();
                    console.log("❌ Impresión fallida, botón 'New Order' sigue oculto.");
                }
        },

        async _printNewButtonFiscal() {
                const order = this.props?.order || this.currentOrder;

                if (order._printed_fiscal || order._is_printing_fiscal) {
                    await showErrorPopup(this, "FACTURA", "LA FACTURA SE ESTA IMPRIMIENDO");
                    return true;
                }

                order._is_printing_fiscal = true;
                
                var json = order.export_for_printing();
                var orderReference = json.name || order.name || order.pos_reference || order.uid;
                var rate_order = await callRpc(this, "pos.order", "get_rate_order", [false, orderReference]);

                order.rate_order = rate_order;
                let dataFiscal;
                try {
                    dataFiscal = await this.print_3mit(order);
                } catch (err) {
                    order._is_printing_fiscal = false;
                    await showErrorPopup(this, "Alerta de Conexión Fiscal", err?.message || "No se pudo imprimir la factura fiscal.");
                    return false;
                }

                if (!dataFiscal || !dataFiscal.nroFiscal) {
                    order._is_printing_fiscal = false;
                    await showErrorPopup(
                        this,
                        "ERROR IMPRIMIENDO",
                        "IMPRESORA DESCONECTADA O CON ERROR. APAGUE Y ENCIENDA LA IMPRESORA Y REINTENTE IMPRIMIR.\n\nRespuesta: " + JSON.stringify(dataFiscal || {})
                    );
                    return false;
                }

                order._printed_fiscal = true;
                order.ticket_fiscal = dataFiscal.nroFiscal;
                order.serial_fiscal = dataFiscal.serial;
                order.impresa = true;

                try {
                    await callRpc(this, "pos.order", "setTicket", [
                        false,
                        {
                            orderUID: orderReference,
                            pos_reference: orderReference,
                            name: orderReference,
                            nroFiscal: dataFiscal.nroFiscal,
                            fecha: dataFiscal.fecha,
                            serial: dataFiscal.serial,
                        },
                    ]);
                } catch (err) {
                    await showErrorPopup(this, "ERROR INTERNO", "NO SE PUDO OBTENER LA INFORMACION FISCAL DE LA IMPRESORA");
                } finally {
                    return true;
                }
        },

        async actionOrderDone3mit() {
            console.log("🏁 [3mit] Iniciando actionOrderDone3mit (custom)...");
            const order = this.props?.order || this.currentOrder;

            if (order && !order.impresa) {
                console.log("🏁 [3mit] ERROR: El documento fiscal no ha sido impreso");
                await showErrorPopup(this, "Error", "Debe imprimir el documento fiscal");
                return;
            }

            const pos =
                this.pos ||
                this.env?.services?.pos ||
                this.env?.pos ||
                getPosService(this)?.pos ||
                getPos(this);

            if (pos && typeof pos.orderDone === "function") {
                console.log("🏁 [3mit] Delegando transición a pos.orderDone() nativo de Odoo 18+");
                await pos.orderDone(order);
                return;
            }

            console.log("🏁 [3mit] pos.orderDone no encontrado, usando fallback agresivo...");
            if (order) {
                try {
                    removeOrderSafe(this, order);
                } catch (e) {}
            }

            try {
                addNewOrderSafe(this);
            } catch (e) {}

            if (pos && typeof pos.closeScreen === "function") pos.closeScreen();
            if (pos && typeof pos.closeTempScreen === "function") pos.closeTempScreen();
            if (this.env?.services?.ui?.closePopup) await this.env.services.ui.closePopup().catch(() => {});
            
            showScreenSafe(this, "ProductScreen");
        },
            async _3mit_prepare_json(order) {
				var json = order.export_for_printing();
				console.log('order', order);
                const posConfig = getPosConfig(this);
				const partner = order.getPartner ? order.getPartner() : order.get_partner?.();
				let raw_id = partner?.vat || partner?.rif || partner?.identification_id || json.client?.vat || json.client?.rif || json.client?.identification_id || "";
				let nat = partner?.nationality || json.client?.nationality || "V";

                let partnerStreet = partner?.street || json.client?.street || "";
                let partnerPhone = partner?.phone || json.client?.phone || "";
                let partnerEmail = partner?.email || json.client?.email || "";
                let partnerCity = partner?.city || json.client?.city || "";

                if (partner && partner.id) {
                    try {
                        const partnerData = await callRpc(this, 'res.partner', 'search_read', [
                            [['id', '=', partner.id]], 
                            ['vat', 'identification_id', 'rif', 'nationality', 'street', 'phone', 'email', 'city']
                        ]);
                        if (partnerData && partnerData.length > 0) {
                            const p = partnerData[0];
                            raw_id = p.vat || p.rif || p.identification_id || raw_id;
                            nat = p.nationality || nat;
                            partnerStreet = p.street || partnerStreet;
                            partnerPhone = p.phone || partnerPhone;
                            partnerEmail = p.email || partnerEmail;
                            partnerCity = p.city || partnerCity;
                        }
                    } catch (e) {
                        console.warn("[3mit] Failed to fetch exact partner data", e);
                    }
                }

				let client_name = partner?.name || json.client?.name || "";
                let idFiscalVal = "";
				if (raw_id) {
				    let clean_id = String(raw_id).replace(/[^a-zA-Z0-9-]/g, '');
				    if (!clean_id.includes('-') && clean_id.match(/^\d+$/)) {
				        clean_id = nat + "-" + clean_id;
				    }
				    idFiscalVal = clean_id;
				}

                let razonExt = client_name || "";

				var receipt = {
					backendRef: json.name || null,
					razonSocial: razonExt.substring(0, 120),
					idFiscal: idFiscalVal,
					direccion: partnerStreet || "S/D",
					telefono: partnerPhone || null,
				};
				// items-products/
                const discount_product_id = Array.isArray(posConfig.discount_product_id)
                    ? posConfig.discount_product_id[0]
                    : posConfig.discount_product_id || null;
                const exportedLines = Array.isArray(json.orderlines) ? json.orderlines : [];
                const runtimeLines = typeof order.get_orderlines === "function"
                    ? order.get_orderlines().map((line) =>
                        typeof line.export_for_printing === "function" ? line.export_for_printing() : {}
                    )
                    : [];
                let orderlines = exportedLines.length ? exportedLines : runtimeLines;
                // Fallback: si no hay líneas en el cliente, intentar leer desde el servidor
                if ((!orderlines || orderlines.length === 0) && json.name) {
                    try {
                        console.debug('[3mit] orderlines vacías, consultando servidor para', json.name);
                        const orderIds = await callRpc(this, 'pos.order', 'search', [[['name', '=', json.name]]]);
                        if (orderIds && orderIds.length) {
                            // Usar solo el primer pedido encontrado (pedido actual)
                            const orderId = orderIds[0];
                            console.debug('[3mit] usando orderId:', orderId);
                            const serverLines = await callRpc(
                                this,
                                'pos.order.line',
                                'search_read',
                                [
                                    [['order_id', '=', orderId]],
                                    ['product_id', 'qty', 'price_unit', 'discount', 'name', 'tax_ids'],
                                ]
                            );
                            console.debug('[3mit] serverLines (pedido actual):', serverLines);

                            const taxIds = new Set();
                            if (Array.isArray(serverLines)) {
                                serverLines.forEach(l => {
                                    if (Array.isArray(l.tax_ids)) l.tax_ids.forEach(id => taxIds.add(id));
                                });
                            }
                            const taxesData = taxIds.size > 0 ? await callRpc(this, 'account.tax', 'search_read', [[['id', 'in', Array.from(taxIds)]], ['amount']]) : [];
                            const taxMap = {};
                            taxesData.forEach(t => taxMap[t.id] = t.amount);

                            orderlines = Array.isArray(serverLines)
                                ? serverLines.map((l) => ({
                                      product_name: (Array.isArray(l.product_id) && l.product_id[1]) || l.name || '',
                                      quantity: l.qty || l.quantity || 1,
                                      product_price: l.price_unit || 0,
                                      discount: l.discount || 0,
                                      customer_note: l.customer_note || '',
                                      product_id: Array.isArray(l.product_id) ? l.product_id[0] : l.product_id,
                                      iva_rate: (Array.isArray(l.tax_ids) && l.tax_ids.length > 0) ? Math.abs(taxMap[l.tax_ids[0]] || 0) : 0,
                                  }))
                                : [];
                        }
                    } catch (err) {
                        console.error('[3mit] error fetching server orderlines', err, err.data || err.message || err.code);
                    }
                }
                console.debug('[3mit] exportedLines:', exportedLines);
                console.debug('[3mit] runtimeLines:', runtimeLines);
                console.debug('[3mit] orderlines chosen:', orderlines);
                const prods = orderlines.filter((line) => {
                    if (!discount_product_id) {
                        return true;
                    }
                    const lineProductId = Array.isArray(line.product_id) ? line.product_id[0] : line.product_id;
                    // Keep the line when product id is not present to avoid dropping valid sale lines.
                    if (lineProductId === undefined || lineProductId === null) {
                        return true;
                    }
                    return lineProductId !== discount_product_id;
                });
                try {
                    console.debug('[3mit] discount_product_id:', discount_product_id);
                    console.debug('[3mit] prods after filter:', prods);
                } catch (err) { /* ignore */ }
				let models = [];
				if (typeof order.get_orderlines === 'function') {
					models = order.get_orderlines() || [];
				} else if (order.orderlines) {
					models = order.orderlines.models || order.orderlines || [];
				}
				
				let prod_models = models.filter((line) => {
					if (!discount_product_id) return true;
					let pid = line.product?.id || (typeof line.get_product === 'function' && line.get_product()?.id) || (Array.isArray(line.product_id) ? line.product_id[0] : line.product_id);
					return pid !== discount_product_id;
				});

				receipt.items = prods.map((r, i) => {
					let exact_precio = r.product_price || r.price || r.price_display || 0;
					let modelLine = prod_models[i] || r; // Fallback to r if model not found
					
					let extract_name = () => {
						// Extract directly from the model
						if (typeof modelLine.get_product === 'function' && modelLine.get_product()) {
							return modelLine.get_product().display_name || modelLine.get_product().name || modelLine.get_product().id;
						}
						if (typeof modelLine.get_full_product_name === 'function') return modelLine.get_full_product_name();
						if (modelLine.product && modelLine.product.display_name) return modelLine.product.display_name;
						if (modelLine.product && modelLine.product.name) return modelLine.product.name;
						if (modelLine.product_id && modelLine.product_id.display_name) return modelLine.product_id.display_name;
						if (modelLine.product_id && modelLine.product_id.name) return modelLine.product_id.name;
						if (modelLine.product_id && Array.isArray(modelLine.product_id) && modelLine.product_id.length > 1) return modelLine.product_id[1];
						if (modelLine.name) return modelLine.name;
						
						// Fallback to exported JSON
						if (r.productName) return r.productName;
						if (r.product_name) return r.product_name;
						if (r.full_product_name) return r.full_product_name;
						if (r.product && r.product.display_name) return r.product.display_name;
						if (r.product && r.product.name) return r.product.name;
						if (r.product_id && r.product_id.display_name) return r.product_id.display_name;
						if (r.product_id && r.product_id.name) return r.product_id.name;
						if (r.product_id && Array.isArray(r.product_id) && r.product_id.length > 1) return r.product_id[1];
						if (r.name) return r.name;
						
						return "Producto";
					};
					
					let final_name = extract_name();
					console.debug('[3mit] product name extracted for', r, '->', final_name);

					return {
						nombre: final_name,
						cantidad: r.quantity || r.qty || 1,
						precio: fixMoney(exact_precio),
						impuesto: r.iva_rate || 0,
						descuento: r.discount || 0,
						tipoDescuento: 'p',
						comentario: r.customer_note || "", // Aquí añadimos los comentarios de los productos
					};
				});
				
				if(order.pc_discount){
					receipt.descuento = order.pc_discount;
					receipt.tipoDescuento = 'p';
				}
			
				const bi_igtf = order.bi_igtf || 0;
				receipt.pagos = [];
				async function getPaymentMethodData(paymentMethodName) {
                    const paymentMethodId = await callRpc(
                        this,
                        'pos.payment.method',
                        'search',
                        [[['name', 'ilike', paymentMethodName]]]
                    );
                    if (!paymentMethodId.length) {
                        return {
                            dolar_active: false,
                            fiscal_print_code: '01',
                            name: paymentMethodName,
                        };
                    }
                    const paymentMethodData = await callRpc(
                        this,
                        'pos.payment.method',
                        'read',
                        [paymentMethodId, ['dolar_active', 'fiscal_print_code', 'name']]
                    );
                    return paymentMethodData[0];
				}
			
				// Consolida por código en la impresora
                const rawPaymentLines = (typeof order.get_paymentlines === "function") ? order.get_paymentlines() : (order.paymentlines || order.payment_ids || []);
                const pagos = await Promise.all(
                    rawPaymentLines.map(async (line) => {
                    let r = typeof line.export_for_printing === "function" ? line.export_for_printing() : {};
                    let methodObj = line.payment_method || line.payment_method_id;
                    if (typeof methodObj === 'number' || Array.isArray(methodObj)) {
                        let p_id = Array.isArray(methodObj) ? methodObj[0] : methodObj;
                        methodObj = order.pos?.payment_methods?.find(p => p.id === p_id) || null;
                    }
                    r.name = r.name || methodObj?.name || line.name || "Efectivo";
                    r.amount = r.amount !== undefined ? r.amount : (line.get_amount ? line.get_amount() : line.amount || 0);
                    
					let data_payment = await getPaymentMethodData.call(this, r.name);
					console.log(data_payment);
					console.log("dolar_active:",data_payment.dolar_active);
					console.log("Code:",data_payment.fiscal_print_code);
					console.log("Objeto r:", r);
			
					let monto = 0;
					let igtf = 0;
					let codigo = data_payment.fiscal_print_code || "01";
					if(data_payment.dolar_active == true){
						igtf = fixMoney(r.amount * 0.03);
						monto = fixMoney(r.amount);
						if (codigo === "01") {
							// Forzar un código de Divisas si Odoo estaba mal configurado o no lo mandó bien
							codigo = "20"; 
						}
					} else {
						monto = fixMoney(r.amount);
					}
					console.log('tasa', order.rate_order);
					console.log('igtf', igtf);
					console.log('amount', r.amount);
					console.log('monto', monto);
					console.log('codigo enviado a la impresora', codigo);
					return {
						codigo: codigo,
						nombre: r.name || data_payment.name || "Efectivo",
						monto: monto,
						igtf: igtf
					};
                    })
                );
				
				
				receipt.pagos = [];
				pagos.forEach((r) => {
					const p = receipt.pagos.find((f) => f.codigo == r.codigo);
					if (!p) {
						receipt.pagos.push(r);
					} else {
						p.monto += r.monto;
					}
				});
				
				// Los comentarios globales se enviarán ahora en el encabezado gracias a la modificación en HKA.txt
				receipt.comentarios = json.note ? [json.note] : [];
				
				if (posConfig.show_dual_currency && posConfig.show_currency_rate) {
					const rateValue = (1 / posConfig.show_currency_rate).toFixed(2);
					receipt.comentarios.push("Tasa del dia: " + rateValue);
				}

				// Nota: Las notas de producto (customer_note) ya se envían en el campo 'comentario' 
				// de cada artículo y el driver las imprime debajo de cada producto.
				
			        return receipt;
    },
});

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
        this.ticket_fiscal = this.ticket_fiscal || null;
        this.serial_fiscal = this.serial_fiscal || null;
        this.fecha_fiscal = this.fecha_fiscal || null;
        this.pc_discount = this.pc_discount || 0;
    },

    get impresa() {
        if (this._printed_fiscal || this._impresa) return true;
        if (this.ticket_fiscal || this.serial_fiscal || this.nroFiscal) return true;
        const keys = [this.uid, this.name, this.pos_reference, this.backendRef, this.id].filter(Boolean);
        for (const k of keys) {
            try {
                if (localStorage.getItem('mit_printed_' + k) === 'true') {
                    return true;
                }
            } catch(e) {}
        }
        return false;
    },

    set impresa(val) {
        this._impresa = Boolean(val);
        if (val) {
            this._printed_fiscal = true;
            const keys = [this.uid, this.name, this.pos_reference, this.backendRef, this.id].filter(Boolean);
            for (const k of keys) {
                try { localStorage.setItem('mit_printed_' + k, 'true'); } catch(e) {}
            }
        }
    },

    init_from_JSON(json) {
        const res = super.init_from_JSON(...arguments);
        if (json.ticket_fiscal) this.ticket_fiscal = json.ticket_fiscal;
        if (json.serial_fiscal) this.serial_fiscal = json.serial_fiscal;
        if (json.fecha_fiscal) this.fecha_fiscal = json.fecha_fiscal;
        if (json.pc_discount) this.pc_discount = json.pc_discount;
        if (json.impresa || json.ticket_fiscal || json.serial_fiscal) {
            this.impresa = true;
        }
        return res;
    },

    export_as_JSON() {
        const data = super.export_as_JSON(...arguments);
        data.ticket_fiscal = this.ticket_fiscal;
        data.serial_fiscal = this.serial_fiscal;
        data.fecha_fiscal = this.fecha_fiscal;
        data.pc_discount = this.pc_discount;
        data.impresa = this.impresa;
        return data;
    },

        export_for_printing() {
            const baseExport = Object.getPrototypeOf(PosOrder.prototype).export_for_printing;
            const receipt = typeof baseExport === "function" ? baseExport.apply(this, arguments) : {};
            
            receipt.name = receipt.name || this.name || this.uid || "";
            
            if (!receipt.orderlines || receipt.orderlines.length === 0) {
                const rawOrderLines = (typeof this.get_orderlines === "function") ? this.get_orderlines() : (this.orderlines || this.lines || []);
                receipt.orderlines = rawOrderLines.map((line) => {
                    let l = typeof line.export_for_printing === "function" ? line.export_for_printing() : {};
                    
                    l.product_name = l.product_name || (typeof line.get_product === "function" ? line.get_product()?.display_name : line.product?.display_name || line.product?.name || "Producto");
                    l.quantity = l.quantity !== undefined ? l.quantity : (typeof line.get_quantity === "function" ? line.get_quantity() : line.qty || line.quantity || 1);
                    l.price_display = l.price_display || (typeof line.get_display_price === "function" ? line.get_display_price() : line.price || line.price_unit || 0);
                    l.product_price = l.product_price || l.price_display;
                    l.discount = l.discount !== undefined ? l.discount : (line.discount || 0);
                    l.customer_note = l.customer_note || line.customer_note || "";
                    
                    let taxAmount = 0;
                    if (typeof line.get_taxes === "function") {
                        let t = line.get_taxes();
                        taxAmount = t.length > 0 ? t[0].amount : 0;
                    } else if (line.tax_ids && this.pos?.taxes_by_id) {
                        for (let tId of line.tax_ids) {
                            let tx = this.pos.taxes_by_id[tId] || this.pos.taxes_by_id[tId.id || tId];
                            if (tx && tx.amount) taxAmount = tx.amount;
                        }
                    }
                    
                    if (taxAmount === 0) {
                        let pWithTax = typeof line.get_price_with_tax === "function" ? line.get_price_with_tax() : (line.price_subtotal_incl || line.price_with_tax || 0);
                        let pWithoutTax = typeof line.get_price_without_tax === "function" ? line.get_price_without_tax() : (line.price_subtotal || line.price_without_tax || 0);
                        if (pWithTax > pWithoutTax && pWithoutTax > 0) {
                            taxAmount = Math.round(((pWithTax - pWithoutTax) / pWithoutTax) * 100);
                        }
                    }
                    l.iva_rate = l.iva_rate !== undefined && l.iva_rate !== 0 ? l.iva_rate : taxAmount;
                    return l;
                });
            }
            
            if (!receipt.paymentlines || receipt.paymentlines.length === 0) {
                const rawPaymentLines2 = (typeof this.get_paymentlines === "function") ? this.get_paymentlines() : (this.paymentlines || this.payment_ids || []);
                receipt.paymentlines = rawPaymentLines2.map((line) => {
                    let l = typeof line.export_for_printing === "function" ? line.export_for_printing() : {};
                    let methodObj = line.payment_method || line.payment_method_id;
                    if (typeof methodObj === 'number' || Array.isArray(methodObj)) {
                        let p_id = Array.isArray(methodObj) ? methodObj[0] : methodObj;
                        methodObj = this.pos?.payment_methods?.find(p => p.id === p_id) || null;
                    }
                    l.name = l.name || methodObj?.name || line.name || "Efectivo";
                    l.amount = l.amount !== undefined ? l.amount : (line.get_amount ? line.get_amount() : line.amount || 0);
                    return l;
                });
            } else {
                const rawPaymentLines3 = (typeof this.get_paymentlines === "function") ? this.get_paymentlines() : (this.paymentlines || this.payment_ids || []);
                receipt.paymentlines = receipt.paymentlines.map((l, idx) => {
                    const ml = rawPaymentLines3[idx];
                    let methodObj = ml?.payment_method || ml?.payment_method_id;
                    if (typeof methodObj === 'number' || Array.isArray(methodObj)) {
                        let p_id = Array.isArray(methodObj) ? methodObj[0] : methodObj;
                        methodObj = this.pos?.payment_methods?.find(p => p.id === p_id) || null;
                    }
                    l.name = l.name || methodObj?.name || ml?.name || "Efectivo";
                    return l;
                });
            }

            receipt.note = receipt.note || this.note || "";
            receipt.client = receipt.client || (this.getPartner ? this.getPartner() : this.get_partner?.());
            return receipt;
        },
    });

	patch(PosOrderline.prototype, {
        export_for_printing() {
            const baseExport = Object.getPrototypeOf(PosOrderline.prototype).export_for_printing;
            const line = typeof baseExport === "function" ? baseExport.apply(this, arguments) : {};
            
            line.product_name = line.product_name || (typeof this.get_product === "function" ? this.get_product()?.display_name : this.product?.display_name || this.product?.name || "");
            line.quantity = line.quantity !== undefined ? line.quantity : (typeof this.get_quantity === "function" ? this.get_quantity() : this.qty || 1);
            line.discount = line.discount !== undefined ? line.discount : (this.discount || 0);
            line.customer_note = line.customer_note || this.customer_note || "";
			
            let taxAmount = 0;
            if (typeof this.get_taxes === "function") {
                let t = this.get_taxes();
                taxAmount = t.length > 0 ? t[0].amount : 0;
            } else if (this.tax_ids && this.pos?.taxes_by_id) {
                for (let tId of this.tax_ids) {
                    let tx = this.pos.taxes_by_id[tId] || this.pos.taxes_by_id[tId.id || tId];
                    if (tx && tx.amount) taxAmount = tx.amount;
                }
            }
            if (taxAmount === 0) {
                let pWithTax = typeof this.get_price_with_tax === "function" ? this.get_price_with_tax() : (this.price_subtotal_incl || this.price_with_tax || 0);
                let pWithoutTax = typeof this.get_price_without_tax === "function" ? this.get_price_without_tax() : (this.price_subtotal || this.price_without_tax || 0);
                if (pWithTax > pWithoutTax && pWithoutTax > 0) {
                    taxAmount = Math.round(((pWithTax - pWithoutTax) / pWithoutTax) * 100);
                }
            }
			line.iva_rate = taxAmount;
			line.product_price = line.product_price || (typeof this.get_display_price === "function" ? this.get_display_price() : (this.price || this.price_unit || 0));
			
			const prod = typeof this.get_product === "function" ? this.get_product() : this.product;
			line.product_id = prod ? prod.id : (this.product_id || null);
			
			return line;
	    },
    });

    patch(TicketScreen.prototype, {
        shouldHideDeleteButton(order) {
            return super.shouldHideDeleteButton(order) || order.impresa || order.finalized;
        },

        async _onDeleteOrder({ detail: order }) {
            if (order.impresa) {
                await showErrorPopup(this, "Accion no permitida", "No puede eliminar pedidos con comprobante fiscal impreso");
                return;
            }
            await super._onDeleteOrder(...arguments);
        },
    });

    patch(PaymentScreen.prototype, {
        async validateOrder(isForceValidate = false) {
            const posConfig = getPosConfig(this);
            let printer_host = posConfig.printer_host;
            let expectedSerial = posConfig.printer_serial || posConfig.x_fiscal_printer_code || posConfig.x_pos_fiscal_printer_code; 

            // Buscar config via RPC si no está cargada en JS
            if (!printer_host || !expectedSerial) {
                try {
                    const configData = await callRpc(this, 'pos.config', 'search_read', [
                        [['id', '=', posConfig.id]],
                        ['printer_host', 'printer_serial', 'x_fiscal_printer_code']
                    ]);
                    if (configData && configData.length > 0) {
                        printer_host = printer_host || configData[0].printer_host;
                        expectedSerial = expectedSerial || configData[0].printer_serial || configData[0].x_fiscal_printer_code;
                    }
                } catch (e) {
                    console.warn("[3mit] No se pudo obtener la config de la impresora via RPC", e);
                }
            }

            // Validar de forma obligatoria si hay un host de impresora configurado (asumimos que usa impresora fiscal local)
            if (printer_host) {
                if (!expectedSerial) {
                    if (this.dialog) {
                        await this.dialog.add(AlertDialog, { title: "Error de Configuración", body: "No hay un serial configurado en los ajustes de esta caja para la impresora fiscal." });
                    }
                    return false;
                }

                try {
                    const response = await fetchWithFallback(`http://${printer_host}/api/data_z`, {
                        method: "GET",
                        cache: "no-store",
                        headers: { "Content-Type": "application/json" },
                    }, 5000);

                    if (!response.ok) throw new Error("Error HTTP " + response.status);
                    
                    const rs = await response.json();
                    if (rs.status === "OK" && rs.data) {
                        const serial = rs.data.numero_impresora;
                        if (!serial || !serial.includes(expectedSerial)) {
                            if (this.dialog) {
                                await this.dialog.add(AlertDialog, { title: "Error de Validación Fiscal", body: `La impresora conectada (${serial || 'Desconocido'}) no es la máquina asignada (${expectedSerial}).` });
                            }
                            return false;
                        }
                    } else {
                        if (this.dialog) {
                            await this.dialog.add(AlertDialog, { title: "Error de Validación Fiscal", body: "La impresora fiscal reportó un error o está apagada. " + (rs.message || "") });
                        }
                        return false;
                    }
                } catch (err) {
                    if (this.dialog) {
                        await this.dialog.add(AlertDialog, { title: "Sin Conexión Fiscal", body: "No se pudo conectar con el servidor de impresión local. Verifique que la impresora esté encendida y conectada.\nDetalle: " + err.message });
                    }
                    return false;
                }
            }

            return super.validateOrder(isForceValidate);
        }
    });

// Ocultador global para el botón de Precio en el teclado numérico (Numpad)
if (typeof window !== "undefined") {
    setInterval(() => {
        try {
            const allBtns = document.querySelectorAll('button, .btn, .mode-button, .numpad-button, div[role="button"], span[role="button"], [data-mode="price"], [value="Precio"], [value="Price"]');
            allBtns.forEach(btn => {
                const text = (btn.innerText || btn.textContent || "").toLowerCase().trim();
                const mode = (btn.getAttribute('data-mode') || btn.getAttribute('value') || btn.getAttribute('data-value') || btn.getAttribute('name') || "").toLowerCase().trim();
                
                if (
                    text === "precio" || 
                    text === "price" || 
                    mode === "price" || 
                    mode === "precio" || 
                    btn.classList.contains("price")
                ) {
                    btn.style.setProperty("visibility", "hidden", "important");
                    btn.style.setProperty("opacity", "0", "important");
                    btn.style.setProperty("pointer-events", "none", "important");
                }
            });
        } catch(e) {}
    }, 200);
}
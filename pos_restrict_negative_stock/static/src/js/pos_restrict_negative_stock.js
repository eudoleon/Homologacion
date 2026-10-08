/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Numpad } from "@point_of_sale/app/components/numpad/numpad";
import { StockRestrictionPopup } from "@pos_restrict_negative_stock/js/StockRestrictionPopup";
import { _t } from "@web/core/l10n/translation";

// Cache síncrono global para almacenar el stock disponible de todos los productos
const posStockCache = {};

/**
 * Extrae el objeto product.product real a partir de cualquier estructura de objeto o ID pasada por el POS.
 */
function extractProduct(target, pos) {
    if (!target) return null;
    let prod = null;

    if (typeof target.get_product === 'function') {
        prod = target.get_product();
    } else if (target.product && typeof target.product === 'object') {
        prod = target.product;
    } else if (target.product_id && typeof target.product_id === 'object') {
        prod = target.product_id;
    } else if (target.product_tmpl_id && typeof target.product_tmpl_id === 'object') {
        prod = target.product_tmpl_id.product_variant_id || (target.product_tmpl_id.product_variant_ids && target.product_tmpl_id.product_variant_ids[0]) || target.product_tmpl_id;
    } else {
        prod = target;
    }

    let pid = null;
    if (typeof prod === 'number' || typeof prod === 'string') {
        pid = parseInt(prod);
    } else if (prod && typeof prod === 'object' && prod.id) {
        pid = parseInt(prod.id);
    } else if (target && target.product_id) {
        pid = parseInt(target.product_id);
    }

    if (pid && pos) {
        let found = null;
        if (pos.db) {
            if (typeof pos.db.get_product_by_id === 'function') {
                found = pos.db.get_product_by_id(pid);
            }
            if (!found && pos.db.product_by_id && pos.db.product_by_id[pid]) {
                found = pos.db.product_by_id[pid];
            }
        }
        if (!found && pos.models) {
            if (pos.models["product.product"]) {
                if (typeof pos.models["product.product"].get === 'function') {
                    found = pos.models["product.product"].get(pid);
                } else if (Array.isArray(pos.models["product.product"])) {
                    found = pos.models["product.product"].find(p => p.id === pid);
                }
            }
            if (!found && typeof pos.models.get === 'function') {
                found = pos.models.get("product.product", pid);
            }
        }
        if (found) prod = found;
    }

    if (prod && typeof prod === 'object' && (prod.id || pid)) {
        if (!prod.id && pid) prod.id = pid;
        return prod;
    }

    return null;
}

/**
 * Determina si el producto requiere control de inventario.
 * Si el rastreo de inventario no está activo ("is_storable" es false) o si es de tipo servicio/combo,
 * NO requiere validaciones de stock.
 */
function isStorableProduct(product) {
    if (!product) return false;

    // Si tiene la propiedad is_storable definida (Odoo 18/19 o custom)
    if (product.is_storable !== undefined && product.is_storable !== null) {
        return Boolean(product.is_storable);
    }

    const type = (product.type || product.detailed_type || "").toString().toLowerCase().trim();
    if (type === 'service' || type === 'servicio' || type === 'combo') {
        return false;
    }

    // En Odoo versiones anteriores donde type es 'consu' (consumible) sin is_storable
    if (type === 'consu' || type === 'consumable' || type === 'consumible') {
        return false;
    }

    return true;
}

/**
 * Obtiene el stock disponible síncronamente desde posStockCache o qty_available.
 * Para productos tipo servicio, retorna Infinity para permitir ventas ilimitadas.
 */
function getAvailableStock(pos, product) {
    if (!product || !isStorableProduct(product)) return Infinity;
    const pid = product.id;
    if (!pid) return Infinity;

    if (posStockCache[pid] !== undefined && posStockCache[pid] !== null) {
        return posStockCache[pid];
    }
    if (product.qty_available !== undefined && product.qty_available !== null) {
        const val = parseFloat(product.qty_available);
        if (!isNaN(val)) {
            posStockCache[pid] = val;
            return val;
        }
    }
    return 0;
}

/**
 * Consulta el stock real en backend vía ORM pos.session.get_realtime_product_stock y actualiza el cache
 */
async function fetchProductStock(pos, product) {
    if (!product || !isStorableProduct(product)) {
        return Infinity;
    }
    const pid = product.id;
    if (!pid) return Infinity;

    try {
        const configId = pos.config ? pos.config.id : null;
        const stock = await pos.env.services.orm.call(
            "pos.session",
            "get_realtime_product_stock",
            [pid, configId],
            {},
            { silent: true }
        );
        if (typeof stock === 'number' && !isNaN(stock)) {
            product.qty_available = stock;
            posStockCache[pid] = stock;
            return stock;
        }
    } catch (e) {
        console.warn("[pos_restrict_negative_stock] Fallback a qty_available local:", e);
    }
    const fallback = parseFloat(product.qty_available || 0) || 0;
    posStockCache[pid] = fallback;
    return fallback;
}

/**
 * Obtiene la cantidad total del producto en otras líneas de la orden activa.
 */
function getProductQtyInOrder(order, productId, excludeLine = null) {
    if (!order || !productId) return 0;
    const lines = typeof order.get_orderlines === 'function' ? order.get_orderlines() : (order.lines || []);
    let total = 0;
    for (let line of lines) {
        if (excludeLine && line === excludeLine) continue;
        const lineProd = extractProduct(line, order.pos);
        const lineProdId = lineProd ? lineProd.id : null;
        if (lineProdId && parseInt(lineProdId) === parseInt(productId)) {
            let lineQty = line.qty !== undefined ? line.qty : line.quantity;
            if (lineQty === undefined && typeof line.get_quantity === 'function') lineQty = line.get_quantity();
            lineQty = parseFloat(lineQty || 0);
            if (!isNaN(lineQty) && lineQty > 0) {
                total += lineQty;
            }
        }
    }
    return total;
}

let lastPopupTime = 0;

/**
 * Muestra el popup de restricción de stock evitando duplicados en ejecuciones simultáneas o en cascada.
 */
function showStockRestrictionDialog(dialogService, props) {
    const now = Date.now();
    if (now - lastPopupTime < 600) {
        return false;
    }
    lastPopupTime = now;

    if (dialogService && typeof dialogService.add === 'function') {
        try {
            dialogService.add(StockRestrictionPopup, props);
            return true;
        } catch (e) {
            console.warn("[pos_restrict_negative_stock] Error mostrando alerta de stock:", e);
        }
    }
    return false;
}

/**
 * Aplica la cantidad de forma segura en la línea respetando la API del modelo de Odoo
 */
function applyLineQuantity(line, order, maxAllowed) {
    if (!line) return;
    isSettingQuantity = true;
    try {
        if (maxAllowed > 0) {
            if (typeof line.set_quantity === 'function') {
                line.set_quantity(maxAllowed);
            } else if (typeof line.set_qty === 'function') {
                line.set_qty(maxAllowed);
            } else {
                line.qty = maxAllowed;
            }
        } else {
            if (order && typeof order.removeOrderline === 'function') {
                order.removeOrderline(line);
            } else if (typeof line.delete === 'function') {
                line.delete();
            } else {
                if (typeof line.set_quantity === 'function') line.set_quantity(0);
                else line.qty = 0;
            }
        }
    } finally {
        isSettingQuantity = false;
    }
}

let isSettingQuantity = false;

// 1. Patch PosStore (_processData, addLineToCurrentOrder y pay)
patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        if (loadedData && loadedData.pos_product_stock_map) {
            Object.assign(posStockCache, loadedData.pos_product_stock_map);
        }
        if (loadedData && loadedData['product.product']) {
            loadedData['product.product'].forEach(p => {
                if (p.id && p.qty_available !== undefined) {
                    posStockCache[p.id] = parseFloat(p.qty_available) || 0;
                }
            });
        }
    },

    async addLineToCurrentOrder(vals, options = {}, configure = true) {
        const product = extractProduct(vals, this);
        
        if (product && isStorableProduct(product)) {
            const order = typeof this.get_order === 'function' ? this.get_order() : (this.currentOrder || this.selectedOrder || (typeof this.getOrder === 'function' ? this.getOrder() : null));
            const availableStock = await fetchProductStock(this, product);
            const usedQty = getProductQtyInOrder(order, product.id);
            const qtyToAdd = parseFloat(options.quantity || (vals && vals.qty) || 1);

            if (usedQty + qtyToAdd > availableStock) {
                const productName = product.display_name || product.name || 'el producto';
                const dialogService = this.env?.services?.dialog;
                showStockRestrictionDialog(dialogService, {
                    title: _t('Stock Insuficiente'),
                    productName: productName,
                    availableStock: availableStock,
                    usedQty: usedQty,
                });
                return false; // Bloquea agregar más unidades en negativo
            }
        }
        return super.addLineToCurrentOrder(...arguments);
    },

    async pay() {
        const order = typeof this.get_order === 'function' ? this.get_order() : (this.currentOrder || this.selectedOrder || (typeof this.getOrder === 'function' ? this.getOrder() : null));
        if (order) {
            const lines = typeof order.get_orderlines === 'function' ? order.get_orderlines() : (order.lines || []);
            const errors = [];
            const productTotals = {};
            const productObjs = {};

            for (let line of lines) {
                const prod = extractProduct(line, this);
                if (prod && isStorableProduct(prod)) {
                    let qty = line.qty !== undefined ? line.qty : line.quantity;
                    if (qty === undefined && typeof line.get_quantity === 'function') qty = line.get_quantity();
                    qty = parseFloat(qty || 0);

                    if (qty > 0) {
                        productTotals[prod.id] = (productTotals[prod.id] || 0) + qty;
                        productObjs[prod.id] = prod;
                    }
                }
            }

            for (let pid in productTotals) {
                const prod = productObjs[pid];
                const totalQty = productTotals[pid];
                const availableStock = await fetchProductStock(this, prod);

                if (totalQty > availableStock) {
                    errors.push({ prod, totalQty, available: availableStock });
                }
            }

            if (errors.length > 0) {
                const firstErr = errors[0];
                const dialogService = this.env?.services?.dialog;
                showStockRestrictionDialog(dialogService, {
                    title: _t('Stock Insuficiente para Pago'),
                    productName: firstErr.prod.display_name || firstErr.prod.name,
                    availableStock: firstErr.available,
                    requestedQty: firstErr.totalQty,
                    reason: _t(`No se puede procesar el pago porque "${firstErr.prod.display_name}" supera el stock disponible en inventario.`),
                });
                return; // Bloquea el pago
            }
        }
        return super.pay(...arguments);
    }
});

// 2. Patch ProductScreen (onNumpadClick y updateSelectedOrderline)
patch(ProductScreen.prototype, {
    async onNumpadClick(buttonValue) {
        const mode = this.pos ? this.pos.numpadMode : 'quantity';
        if (mode === 'quantity' || !mode || mode === '') {
            if (!["quantity", "discount", "price"].includes(buttonValue)) {
                const order = this.currentOrder || (this.pos ? this.pos.selectedOrder : null);
                const selectedLine = order ? (typeof order.get_selected_orderline === 'function' ? order.get_selected_orderline() : (order.selected_orderline || (typeof order.getSelectedOrderline === 'function' ? order.getSelectedOrderline() : null))) : null;

                if (selectedLine) {
                    const product = extractProduct(selectedLine, this.pos);
                    if (product && isStorableProduct(product)) {
                        const currentBuffer = this.numberBuffer ? (typeof this.numberBuffer.get === 'function' ? this.numberBuffer.get() : (this.numberBuffer.buffer || "")) : "";
                        let newBufferStr = "";
                        if (buttonValue === "Backspace") {
                            newBufferStr = currentBuffer.slice(0, -1);
                        } else if (buttonValue === "+" || buttonValue === "-") {
                            newBufferStr = currentBuffer;
                        } else {
                            newBufferStr = currentBuffer + buttonValue;
                        }

                        let targetQty = parseFloat(newBufferStr);
                        if (!isNaN(targetQty) && targetQty > 0) {
                            const availableStock = getAvailableStock(this.pos, product);
                            const otherLinesQty = getProductQtyInOrder(order, product.id, selectedLine);
                            const maxAllowed = Math.max(0, availableStock - otherLinesQty);

                            if (targetQty > maxAllowed) {
                                const productName = product.display_name || product.name || 'el producto';

                                const dialogService = this.dialog || this.env?.services?.dialog;
                                showStockRestrictionDialog(dialogService, {
                                    title: _t('Stock Insuficiente'),
                                    productName: productName,
                                    availableStock: availableStock,
                                    requestedQty: targetQty,
                                    maxAllowed: maxAllowed,
                                });

                                if (this.numberBuffer) {
                                    this.numberBuffer.reset();
                                }

                                applyLineQuantity(selectedLine, order, maxAllowed);
                                return; // BLOQUEA el Numpad para no permitir ingresar cantidades en exceso
                            }
                        }
                    }
                }
            }
        }
        return super.onNumpadClick(...arguments);
    },

    async updateSelectedOrderline({ buffer, key }) {
        const mode = this.pos ? this.pos.numpadMode : 'quantity';
        if (mode === 'quantity' || !mode || mode === '') {
            const order = this.currentOrder || (this.pos ? this.pos.selectedOrder : null);
            const selectedLine = order ? (typeof order.get_selected_orderline === 'function' ? order.get_selected_orderline() : (order.selected_orderline || (typeof order.getSelectedOrderline === 'function' ? order.getSelectedOrderline() : null))) : null;

            if (selectedLine && buffer !== undefined && buffer !== null && buffer !== "") {
                const product = extractProduct(selectedLine, this.pos);
                if (product && isStorableProduct(product)) {
                    let requestedQty = parseFloat(buffer);
                    if (!isNaN(requestedQty) && requestedQty > 0) {
                        const availableStock = getAvailableStock(this.pos, product);
                        const otherLinesQty = getProductQtyInOrder(order, product.id, selectedLine);
                        const maxAllowed = Math.max(0, availableStock - otherLinesQty);

                        if (requestedQty > maxAllowed) {
                            const productName = product.display_name || product.name || 'el producto';

                            const dialogService = this.dialog || this.env?.services?.dialog;
                            showStockRestrictionDialog(dialogService, {
                                title: _t('Stock Insuficiente'),
                                productName: productName,
                                availableStock: availableStock,
                                requestedQty: requestedQty,
                                maxAllowed: maxAllowed,
                            });

                            if (this.numberBuffer) {
                                this.numberBuffer.reset();
                            }

                            applyLineQuantity(selectedLine, order, maxAllowed);
                            return; // BLOQUEA la adición de buffer excesivo
                        }
                    }
                }
            }
        }
        return super.updateSelectedOrderline(...arguments);
    }
});

// 3. Patch PosOrderline (set_quantity) - Protección defensiva contra super.set_quantity inexsitente
patch(PosOrderline.prototype, {
    set_quantity(quantity, keep_price) {
        if (isSettingQuantity) {
            if (typeof super.set_quantity === 'function') {
                return super.set_quantity(...arguments);
            } else if (typeof this.set_qty === 'function') {
                return this.set_qty(quantity);
            } else {
                this.qty = quantity;
                return true;
            }
        }

        if (quantity !== 'remove' && quantity !== '' && quantity !== undefined) {
            let requestedQty = parseFloat(quantity);
            const pos = this.pos || this.store || this.env?.services?.pos || window.pos || {};
            const product = extractProduct(this, pos);

            if (product && isStorableProduct(product) && !isNaN(requestedQty) && requestedQty > 0) {
                const order = this.order || (typeof pos.get_order === 'function' ? pos.get_order() : null) || this.order_id || pos.selectedOrder;

                const availableStock = getAvailableStock(pos, product);
                const otherLinesQty = getProductQtyInOrder(order, product.id, this);
                const maxAllowed = Math.max(0, availableStock - otherLinesQty);

                if (requestedQty > maxAllowed) {
                    const productName = product.display_name || product.name || 'el producto';

                    isSettingQuantity = true;
                    try {
                        const dialogService = this.env?.services?.dialog || pos.env?.services?.dialog;
                        showStockRestrictionDialog(dialogService, {
                            title: _t('Stock Insuficiente'),
                            productName: productName,
                            availableStock: availableStock,
                            requestedQty: requestedQty,
                            maxAllowed: maxAllowed,
                        });
                    } catch (e) {
                        console.warn("[pos_restrict_negative_stock] Error mostrando alerta de stock:", e);
                    } finally {
                        isSettingQuantity = false;
                    }

                    if (maxAllowed <= 0) {
                        let current_order = order || (pos.get_order ? pos.get_order() : null);
                        if (current_order && typeof current_order.removeOrderline === 'function') {
                            current_order.removeOrderline(this);
                        } else if (typeof this.delete === 'function') {
                            this.delete();
                        }
                        return true;
                    } else {
                        quantity = maxAllowed;
                    }
                }
            }
        }

        if (typeof super.set_quantity === 'function') {
            return super.set_quantity(quantity, keep_price);
        } else if (typeof this.set_qty === 'function') {
            return this.set_qty(quantity);
        } else {
            this.qty = quantity;
            return true;
        }
    }
});

// 4. Observer de DOM para ocultar dinámicamente el botón "Editar" en los modales de información de producto
if (typeof window !== "undefined" && typeof document !== "undefined") {
    const hideEditButtonInPopups = () => {
        const footers = document.querySelectorAll("footer, .modal-footer, .dialog-footer, .o_dialog_footer");
        footers.forEach(footer => {
            const buttons = Array.from(footer.querySelectorAll("button"));
            buttons.forEach(btn => {
                const txt = (btn.innerText || btn.textContent || "").trim().toLowerCase();
                if (txt === "editar" || txt === "edit") {
                    btn.style.setProperty("display", "none", "important");
                }
            });
            const visibleButtons = buttons.filter(b => b.style.display !== "none" && getComputedStyle(b).display !== "none");
            if (visibleButtons.length === 1) {
                visibleButtons[0].style.setProperty("flex-grow", "1", "important");
                visibleButtons[0].style.setProperty("width", "100%", "important");
            }
        });
    };

    const posPopupObserver = new MutationObserver(() => {
        hideEditButtonInPopups();
    });

    const startObserver = () => {
        if (document.body) {
            posPopupObserver.observe(document.body, { childList: true, subtree: true });
            hideEditButtonInPopups();
        }
    };

    if (document.readyState === "complete" || document.readyState === "interactive") {
        startObserver();
    } else {
        document.addEventListener("DOMContentLoaded", startObserver);
    }
}

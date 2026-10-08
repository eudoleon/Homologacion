/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(PosStore.prototype, {
    async pay() {
        const order = typeof this.get_order === 'function' ? this.get_order() : this.selectedOrder;
        if (order) {
            const orderLines = typeof order.get_orderlines === 'function' ? order.get_orderlines() : order.lines;
            for (let i = 0; i < orderLines.length; i++) {
                const line = orderLines[i];

                // Las líneas hijas de un combo, recompensas o propinas tienen precio 0 legítimo
                // porque su valor ya está contemplado en el producto padre del combo.
                const isComboChild = Boolean(
                    line.combo_parent_id ||
                    line.combo_item_id ||
                    line.combo_parent_uuid ||
                    (line.order_id && line.order_id.lines && line.order_id.lines.some(l => l.combo_line_ids && l.combo_line_ids.includes(line)))
                );

                if (isComboChild || line.is_reward_line || line.reward_id || (line.isTipLine && line.isTipLine())) {
                    continue;
                }
                
                // Obtener cantidad
                let qty = undefined;
                if (typeof line.get_quantity === 'function') qty = line.get_quantity();
                if (qty === undefined && typeof line.getQuantity === 'function') qty = line.getQuantity();
                if (qty === undefined) qty = line.qty;
                if (qty === undefined) qty = line.quantity;
                qty = parseFloat(qty);
                if (isNaN(qty)) qty = 0;

                // Obtener precio original
                let original_price = undefined;
                if (line.combo_line_ids && line.combo_line_ids.length > 0) {
                    // Es un producto combo padre: en Odoo 19 su price_unit base es 0 y el precio real/total
                    // está en su displayPrice (suma de items del combo)
                    original_price = qty > 0 ? (line.displayPrice / qty) : line.displayPrice;
                } else {
                    if (line.price_unit !== undefined && line.price_unit !== null) {
                        original_price = line.price_unit;
                    } else if (typeof line.get_unit_price === 'function') {
                        original_price = line.get_unit_price();
                    } else if (typeof line.getUnitPrice === 'function') {
                        original_price = line.getUnitPrice();
                    } else if (line.price !== undefined) {
                        original_price = line.price;
                    } else if (line.displayPriceUnit !== undefined) {
                        original_price = line.displayPriceUnit;
                    } else if (line.displayPrice !== undefined) {
                        original_price = line.displayPrice;
                    }
                }
                original_price = parseFloat(original_price);
                if (isNaN(original_price)) original_price = 0;

                // Obtener descuento
                let discount = undefined;
                if (typeof line.get_discount === 'function') discount = line.get_discount();
                if (discount === undefined && typeof line.getDiscount === 'function') discount = line.getDiscount();
                if (discount === undefined) discount = line.discount;
                discount = parseFloat(discount);
                if (isNaN(discount)) discount = 0;

                // Calcular precio final efectivo
                const final_unit_price = original_price * (1 - (discount / 100.0));
                
                // Obtener producto (compatible con Odoo 19)
                let product = line.product_id;
                if (!product && typeof line.getProduct === 'function') product = line.getProduct();
                if (!product && typeof line.get_product === 'function') product = line.get_product();
                if (!product) product = line.product;
                
                // Fallback a modelo product.product de Odoo 19
                if (!product && line.product_id) {
                    try {
                        const pid = Array.isArray(line.product_id) ? line.product_id[0] : (line.product_id.id || line.product_id);
                        if (this.models && this.models["product.product"]) {
                            product = this.models["product.product"].get(pid);
                        }
                    } catch (e) {}
                }
                
                const productName = product ? (product.display_name || product.name || 'el producto seleccionado') : 'el producto seleccionado';

                // Validacion 1: Cantidad <= 0 o Precio <= 0
                if (qty <= 0 || final_unit_price <= 0.001) {
                    this.env.services.dialog.add(AlertDialog, {
                        title: _t('Cantidad o precio no permitido'),
                        body: _t(`No se permite confirmar el pedido con cantidades o precios cero o negativos en ${productName}.`),
                    });
                    return;
                }

                // Validacion 2: Precio final por debajo del costo
                // Los productos combo padre no poseen costo propio en la cabecera (sus costos corresponden a los componentes individuales)
                if (line.combo_line_ids && line.combo_line_ids.length > 0) {
                    continue;
                }

                let cost = product ? parseFloat(product.standard_price || product.standard_price_usd || 0) : 0;
                
                // Extraer el ID del producto por cualquier medio posible
                let productId = null;
                if (product && typeof product === 'object' && typeof product.id === 'number') {
                    productId = product.id;
                } else if (typeof line.getProduct === 'function' && line.getProduct() && typeof line.getProduct().id === 'number') {
                    productId = line.getProduct().id;
                } else if (typeof line.get_product === 'function' && line.get_product() && typeof line.get_product().id === 'number') {
                    productId = line.get_product().id;
                } else if (line.product_id) {
                    if (typeof line.product_id === 'object' && line.product_id.id) {
                        productId = line.product_id.id;
                    } else if (Array.isArray(line.product_id)) {
                        productId = line.product_id[0];
                    } else {
                        productId = line.product_id;
                    }
                }
                productId = parseInt(productId);

                if (cost === 0 && productId && !isNaN(productId)) {
                    try {
                        const result = await this.env.services.orm.call(
                            "pos.session", 
                            "get_product_cost", 
                            [productId],
                            {},
                            { silent: true }
                        );
                        if (result) {
                            cost = parseFloat(result.standard_price || result.standard_price_usd || 0);
                        }
                    } catch (error) {
                        console.warn("[pos_zero_quantity_restrict] No se pudo usar get_product_cost. Intentando fallback read directo...", error);
                        if (error && error.data) {
                            console.error("=== DETALLE ERROR PYTHON (get_product_cost) ===", "\nMensaje:", error.data.message, "\nTraceback:", error.data.debug);
                        }
                        try {
                            const fallbackResult = await this.env.services.orm.call(
                                "product.product",
                                "read",
                                [[productId], ["standard_price", "standard_price_usd"]],
                                {},
                                { silent: true }
                            );
                            if (fallbackResult && fallbackResult.length > 0) {
                                cost = parseFloat(fallbackResult[0].standard_price || fallbackResult[0].standard_price_usd || 0);
                            }
                        } catch (err2) {
                            console.warn("[pos_zero_quantity_restrict] El fallback también falló.", err2);
                            if (err2 && err2.data) {
                                console.error("=== DETALLE ERROR PYTHON (fallback read) ===", "\nMensaje:", err2.data.message, "\nTraceback:", err2.data.debug);
                            }
                        }
                    }
                }

                if (cost > 0 && final_unit_price < (cost - 0.01)) {
                    this.env.services.dialog.add(AlertDialog, {
                        title: _t('Precio por debajo del costo'),
                        body: _t(`El precio final de "${productName}" (${final_unit_price.toFixed(2)}) no puede ser menor a su costo (${cost.toFixed(2)}).`),
                    });
                    return;
                }
            }
        }
        return super.pay(...arguments);
    }
});

/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { ProductTemplate } from "@point_of_sale/app/models/product_template";

/**
 * Esquema de montos para métodos de pago en dólares (pago_usd):
 *  - `amount`  : siempre en Bs (moneda de la compañía). Es el monto contable que Odoo usa
 *                para totales, restantes, cambio, IGTF, etc.
 *  - `usd_amt` : equivalente en USD (lo que el cajero digita y lo que se muestra como REF).
 *
 * El teclado numérico, para una línea USD, se interpreta en USD y se convierte a Bs.
 */
patch(PosPayment.prototype, {
    get isUsdPayment() {
        return Boolean(this.payment_method_id && this.payment_method_id.pago_usd);
    },

    _getDualRates() {
        const order = this.pos_order_id;
        const config = (order && (order.config || (order.pos && order.pos.config))) || {};
        return {
            rateCompany: config.rate_company || 1,
            rateShow: config.show_currency_rate || 1,
        };
    },

    /** Bs -> USD */
    bsToUsd(bs) {
        const { rateCompany, rateShow } = this._getDualRates();
        const value = parseFloat(bs) || 0;
        let usd = value;
        if (rateCompany > rateShow) {
            usd = value * rateShow;
        } else if (rateCompany < rateShow) {
            usd = value / rateCompany;
        }
        return roundDecimals(usd, 2);
    },

    /** USD -> Bs */
    usdToBs(usd) {
        const { rateCompany, rateShow } = this._getDualRates();
        const value = parseFloat(usd) || 0;
        let bs = value;
        if (rateCompany > rateShow && rateShow > 0) {
            bs = value / rateShow;
        } else if (rateCompany < rateShow && rateCompany > 0) {
            bs = value * rateCompany;
        }
        return bs;
    },

    /** Monto en USD de la línea (para mostrar en pantalla). */
    get usdAmount() {
        return this.usd_amt || this.bsToUsd(this.getAmount());
    },

    // Cada vez que cambia el monto en Bs (incluye la carga inicial del importe completo al
    // seleccionar el método), se refresca el equivalente en USD.
    setAmount(value) {
        super.setAmount(...arguments);
        if (this.isUsdPayment) {
            this.usd_amt = this.bsToUsd(this.getAmount());
        }
    },
});

patch(PaymentScreen.prototype, {
    // Al agregar un método en USD, el buffer del teclado arranca con el importe completo en USD.
    async addNewPaymentLine(paymentMethod) {
        const added = await super.addNewPaymentLine(...arguments);
        if (added && paymentMethod && paymentMethod.pago_usd) {
            const line = this.selectedPaymentLine;
            if (line && line.isUsdPayment) {
                this.numberBuffer.set(String(line.usdAmount));
            }
        }
        return added;
    },

    // Lo digitado en el teclado para una línea USD son dólares: se convierte a Bs para Odoo
    // y se guarda el valor exacto en USD.
    updateSelectedPaymentline(amount = false) {
        const line = this.selectedPaymentLine;
        if (line && line.isUsdPayment) {
            let usdValue = amount;
            if (usdValue === false) {
                const buffer = this.numberBuffer.get();
                if (buffer === null) {
                    // Buffer vacío con borrado: dejamos que Odoo elimine la línea.
                    return super.updateSelectedPaymentline(...arguments);
                }
                usdValue = buffer === "" ? 0 : this.numberBuffer.getFloat();
            }
            if (usdValue !== null) {
                const usd = parseFloat(usdValue) || 0;
                const result = super.updateSelectedPaymentline(line.usdToBs(usd));
                // Si Odoo no eliminó la línea, se conserva el monto USD exacto digitado.
                if (this.selectedPaymentLine === line) {
                    line.usd_amt = roundDecimals(usd, 2);
                }
                return result;
            }
        }
        return super.updateSelectedPaymentline(...arguments);
    },
});

// 4. Mejorar resolución de imágenes
if (ProductProduct && ProductProduct.prototype) {
    patch(ProductProduct.prototype, {
        getImageUrl() {
            return `/web/image?model=product.product&field=image_512&id=${this.id}&unique=${this.write_date}`;
        },
    });
}

if (ProductTemplate && ProductTemplate.prototype) {
    patch(ProductTemplate.prototype, {
        getImageUrl() {
            return `/web/image?model=product.template&field=image_512&id=${this.id}&unique=${this.write_date}`;
        },
    });
}
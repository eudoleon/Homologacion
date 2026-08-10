odoo.define('limit_credit_pos.pos_credit_limit', function (require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');

    console.warn('✅✅✅ [pos_credit_limit] MODULE LOADED');

    const CreditLimitPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            async _showCreditRestrictionPopup(result) {
                const title = '¡CLIENTE RESTRINGIDO!';
                const body = result && result.name
                    ? `El cliente ${result.name} actualmente no posee crédito disponible.`
                    : 'El monto facturado supera el límite o el crédito está bloqueado, Contacte a Administración';

                await this.showPopup('ErrorPopup', { title, body });
            }

            _isCreditAccountPaymentMethod() {
                const order = this.currentOrder;
                const paymentLines = order && order.get_paymentlines ? order.get_paymentlines() : [];
                
                // Verificar si algún método de pago es "CUENTA DE CLIENTE"
                for (const line of paymentLines) {
                    const paymentMethod = line.payment_method;
                    if (paymentMethod && paymentMethod.name && paymentMethod.name.toUpperCase() === 'CUENTA DE CLIENTE') {
                        return true;
                    }
                }
                
                return false;
            }

            async _checkCreditRestriction(skipPaymentMethodCheck = false) {
                const order = this.currentOrder;
                const partner = order && order.get_partner ? order.get_partner() : null;

                if (!partner) {
                    return { restricted: false };
                }

                // Solo validar restricción de crédito si el método de pago es "CUENTA DE CLIENTE"
                // skipPaymentMethodCheck es true cuando ya se verificó el método de pago antes de llamar este método
                if (!skipPaymentMethodCheck && !this._isCreditAccountPaymentMethod()) {
                    console.warn('🔴 [pos_credit_limit] Método de pago no es CUENTA DE CLIENTE, omitiendo validación');
                    return { restricted: false };
                }

                try {
                    const result = await this.env.services.rpc({
                        model: 'res.partner',
                        method: 'check_credit_restriction',
                        args: [partner.id],
                        context: this.env.session.user_context,
                    });

                    console.warn('🔴 [pos_credit_limit] resultado', result);

                    if (result && result.restricted) {
                        await this._showCreditRestrictionPopup(result);
                        return { restricted: true };
                    }

                    return result || { restricted: false };
                } catch (error) {
                    console.error('❌ [pos_credit_limit] error validando crédito', error);
                    return { restricted: false };
                }
            }

            async addNewPaymentLine(event) {
                console.warn('🔴 [pos_credit_limit] addNewPaymentLine interceptado');

                // Verificar si el método de pago seleccionado es "CUENTA DE CLIENTE"
                // event.detail es directamente el objeto del método de pago
                const paymentMethod = event && event.detail;

                if (paymentMethod && paymentMethod.name && paymentMethod.name.toUpperCase() === 'CUENTA DE CLIENTE') {
                    console.warn('🔴 [pos_credit_limit] MÉTODO DE PAGO ES CUENTA DE CLIENTE, validando crédito');
                    // Pasamos true para saltar la verificación del método de pago ya que ya la hicimos aquí
                    const restriction = await this._checkCreditRestriction(true);
                    if (restriction.restricted) {
                        return false;
                    }
                }

                return await super.addNewPaymentLine(event);
            }

            async validateOrder(isForceValidate) {
                console.warn('🔴 [pos_credit_limit] validateOrder interceptado');

                // Solo validar si el método de pago es "CUENTA DE CLIENTE"
                if (this._isCreditAccountPaymentMethod()) {
                    const restriction = await this._checkCreditRestriction();
                    if (restriction.restricted) {
                        return;
                    }
                } else {
                    console.warn('🔴 [pos_credit_limit] Método de pago no es CUENTA DE CLIENTE, omitiendo validación en validateOrder');
                }

                return await super.validateOrder(isForceValidate);
            }

            async _finalizeValidation() {
                console.warn('🔴 [pos_credit_limit] _finalizeValidation interceptado');

                // Solo validar si el método de pago es "CUENTA DE CLIENTE"
                if (this._isCreditAccountPaymentMethod()) {
                    const restriction = await this._checkCreditRestriction();
                    if (restriction.restricted) {
                        return;
                    }
                } else {
                    console.warn('🔴 [pos_credit_limit] Método de pago no es CUENTA DE CLIENTE, omitiendo validación en _finalizeValidation');
                }

                return await super._finalizeValidation();
            }
        };

    Registries.Component.extend(PaymentScreen, CreditLimitPaymentScreen);

    return PaymentScreen;
});

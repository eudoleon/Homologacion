odoo.define('payment_reference_on_pos.PaymentScreen', function (require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const { useListener } = require("@web/core/utils/hooks");

    const PaymentReferenceScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            setup() {
                super.setup();
                useListener('update-payment-reference', this.updatePaymentReference);
            }

            async updatePaymentReference(event) {
                const res = super.selectPaymentLine(...arguments);
                const { cid } = event.detail;
                const line = this.paymentLines.find((line) => line.cid === cid);
                
                if (!line) return;

                const { confirmed, payload: code } = await this.showPopup('PaymentReferencePopup', {
                    startingValue: line.payment_reference,
                    title: this.env._t('Add / Update Payment Reference'),
                });
                if (confirmed && code !== '') {
                    const val = code;
                    line.payment_reference = code;        
                }
            }

        };

    Registries.Component.extend(PaymentScreen, PaymentReferenceScreen);

    return PaymentScreen;
});

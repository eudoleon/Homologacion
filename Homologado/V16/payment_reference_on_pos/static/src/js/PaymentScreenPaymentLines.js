odoo.define('payment_reference_on_pos.PaymentScreenPaymentLines', function (require) {
    'use strict';

    const PaymentScreenPaymentLines = require('point_of_sale.PaymentScreenPaymentLines');
    const Registries = require('point_of_sale.Registries');

    const PaymentReferenceScreenLines = (PaymentScreenPaymentLines) =>
        class extends PaymentScreenPaymentLines {
            /**
             * @override
             */
            selectedLineClass(line) {
                return Object.assign({}, super.selectedLineClass(line), {
                    payment_reference: line.payment_reference,
                });
            }
            /**
             * @override
             */
            unselectedLineClass(line) {
                return Object.assign({}, super.unselectedLineClass(line), {
                    payment_reference: line.payment_reference,
                });
            }
        };

    Registries.Component.extend(PaymentScreenPaymentLines, PaymentReferenceScreenLines);

    return PaymentScreenPaymentLines;
});

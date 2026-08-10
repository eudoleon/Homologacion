odoo.define('payment_reference_on_pos.models', function (require) {
    "use strict";
  
    const { Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

    const PosReferencePayment = (Payment) => class PosReferencePayment extends Payment {
        constructor(obj, options) {
            super(...arguments);
            this.payment_reference = this.payment_reference || null;
        }

        //@override
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.payment_reference = this.payment_reference;
            return json;
        }

        //@override
        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
            this.payment_reference = json.payment_reference;
        }
    }

    Registries.Model.extend(Payment, PosReferencePayment);
});
  
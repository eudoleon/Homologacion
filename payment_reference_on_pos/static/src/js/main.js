/** @odoo-module **/

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { Dialog } from "@web/core/dialog/dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { patch } from "@web/core/utils/patch";
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// 1. Patch the PosPayment model to support serialization of the payment_reference
patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.payment_reference = this.payment_reference || null;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.payment_reference = json.payment_reference || null;
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.payment_reference = this.payment_reference;
        return json;
    }
});

// 2. Define the OWL Dialog Component for the PaymentReferencePopup
export class PaymentReferencePopup extends Component {
    static template = "payment_reference_on_pos.PaymentReferencePopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        startingValue: { optional: true },
        getPayload: { type: Function, optional: true },
        close: { type: Function, optional: true },
        "*": true,
    };
    setup() {
        this.state = useState({ inputValue: this.props.startingValue || '' });
        this.inputRef = useRef('input');
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }
    confirm() {
        if (typeof this.props.getPayload === "function") {
            this.props.getPayload(this.state.inputValue);
        }
        if (typeof this.props.close === "function") {
            this.props.close(this.state.inputValue);
        }
    }
    cancel() {
        if (typeof this.props.getPayload === "function") {
            this.props.getPayload(false);
        }
        if (typeof this.props.close === "function") {
            this.props.close(false);
        }
    }
}

// 3. Patch the PaymentScreenPaymentLines component to add/update the payment reference
patch(PaymentScreenPaymentLines.prototype, {
    async updatePaymentReference(line) {
        const inputVal = await makeAwaitable(this.env.services.dialog, PaymentReferencePopup, {
            title: _t('Add / Update Payment Reference'),
            startingValue: line.payment_reference || '',
        });
        if (typeof inputVal === 'string') {
            line.payment_reference = inputVal;
        }
    }
});


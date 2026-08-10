odoo.define('payment_reference_on_pos.PaymentReferencePopup', function(require) {
    'use strict';

    const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
    const Registries = require('point_of_sale.Registries');
    const { _lt } = require('@web/core/l10n/translation');

    const { onMounted, useRef, useState } = owl;

    class PaymentReferencePopup extends AbstractAwaitablePopup {
        setup() {
            super.setup();
            this.state = useState({ inputValue: this.props.startingValue });
            this.inputRef = useRef('input');
        }
        mounted() {
            this.inputRef.el.focus();
        }
        getPayload() {
            return this.state.inputValue;
        }
    }
    
    PaymentReferencePopup.template = 'PaymentReferencePopup';
    PaymentReferencePopup.defaultProps = {
        confirmText: _lt('Ok'),
        cancelText: _lt('Cancel'),
        title: '',
        body: '',
    };

    Registries.Component.add(PaymentReferencePopup);
    return PaymentReferencePopup;

});
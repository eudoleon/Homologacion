odoo.define('delivery_warning_seniat.form_custom_behavior', function (require) {
    "use strict";

    var FormController = require('web.FormController');

    FormController.include({
        _updateView: function () {
            this._super.apply(this, arguments);
            this._checkDatesAndDisplayWarning();
        },

        _checkDatesAndDisplayWarning: function () {
            var self = this;
            var record = this.model.get(this.handle);
            if (record.data.fiscalyear_lock_date) {
                // Aquí debes reemplazar 'model_name' y 'field_name' con los valores adecuados de tu modelo
                this._rpc({
                    model: 'account.change.lock.date',
                    method: 'check_delivery_orders',
                    args: [record.data.fiscalyear_lock_date],
                }).then(function (result) {
                    if (result.warning) {
                        self.do_warn("Advertencia", result.warning);
                    }
                });
            }
        }
    });
});

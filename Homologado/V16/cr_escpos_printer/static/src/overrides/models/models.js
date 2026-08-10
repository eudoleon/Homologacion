odoo.define('cr_escpos_printer.models', function (require) {
"use strict";

var { PosGlobalState } = require('point_of_sale.models');
var CrPrintNodePrinter = require('cr_escpos_printer.Printer');
const Registries = require('point_of_sale.Registries');

const PosCrPosGlobalState = (PosGlobalState) => class PosCrPosGlobalState extends PosGlobalState {
    after_load_server_data() {
        var self = this;
        return super.after_load_server_data(...arguments).then(function () {
            if (self.config.other_devices  && self.config.printer_id) {
                self.env.proxy.printer = new CrPrintNodePrinter(self.config.printer_id[0], self);
            }
        });
    }
}
Registries.Model.extend(PosGlobalState, PosCrPosGlobalState);

});

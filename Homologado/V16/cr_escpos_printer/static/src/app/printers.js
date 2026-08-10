odoo.define('cr_escpos_printer.Printer', function (require) {
    "use strict";

    var rpc = require('web.rpc');
    var core = require('web.core');
    var { PrinterMixin, PrintResultGenerator } = require('point_of_sale.Printer');

    class CrPrintResultGenerator extends PrintResultGenerator {
        constructor(ip) {
            super();
            this.address = ip;
        }
    }

    var CrPrintNodePrinter = core.Class.extend(PrinterMixin, {
        init(printer_id, pos) {
            PrinterMixin.init.call(this, pos);
            this.printer_id = printer_id;
        },

        async send_printing_job(img) {
            fetch('http://yourserveraddress:5000/proxy_ipify')
            .then(response => response.json())
            .then(data => {
                console.log('Public IP: ' + data.ip);
            })
            .catch(error => console.error('Error:', error));
            if (!this.printer_id) {
                return false
            }
            let receipt = {
                'printer_id': this.printer_id,
                'img': img
            }
            let result;
            await rpc.query({
                route: '/cr_escpos_receipt',
                params: { receipt }
            }).then(function (res) {
                result = res;
            }).catch(function (err) {
                console.error(err);
                result = false;
            });

            return { result };
        },
    });

    return CrPrintNodePrinter;
});

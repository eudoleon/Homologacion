odoo.define('3mit_print_server.connection_error_handling', function (require) {
    "use strict";

    const { Component } = require('web.Component');  // Aquí importas web.Component
    const { Registries } = require('point_of_sale.Registries');
    const { AlertDialog } = require("@web/core/confirmation_dialog/confirmation_dialog");
    const core = require('web.core');
    const _t = core._t;

    const ExtendPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {

            async validate_printer_connection() {
                if (window._debug) return Promise.resolve(true);

                const printer_host = this.env.pos.config.printer_host;
                const testPayload = {
                    razonSocial: "TEST",
                    idFiscal: "00000000",
                    direccion: "TEST ADDRESS",
                    items: [
                        {
                            nombre: "Test Item",
                            cantidad: 1,
                            precio: 1,
                            impuesto: 0,
                            descuento: 0,
                            tipoDescuento: "p",
                            comentario: "",
                        },
                    ],
                    pagos: [
                        {
                            codigo: "01",
                            nombre: "Efectivo",
                            monto: 1,
                        },
                    ],
                    comentarios: ["Prueba de conexión"],
                    emulador: true   // Bandera para activar el modo emulación
                };

                return new Promise((resolve) => {
                    $.ajax({
                        url: `http://${printer_host}/api/imprimir/factura`,
                        method: "POST",
                        data: JSON.stringify(testPayload),
                        contentType: "application/json",
                        dataType: "json",
                        timeout: 5000,
                    })
                    .done((response) => {
                        const status = response?.status?.toLowerCase() || '';
                        const printer_serial = response.data?.serial;

                        if (status !== 'ok') {
                            this.env.services.dialog.add(AlertDialog, {
                                title: "Error de Impresora",
                                body: `Respuesta inválida: ${JSON.stringify(response)}`
                            });
                            return resolve(false);
                        }

                        if (!printer_serial) {
                            this.env.services.dialog.add(AlertDialog, {
                                title: "Serial no detectado",
                                body: "La impresora no devolvió su número de serie"
                            });
                            return resolve(false);
                        }

                        resolve(true);
                    })
                    .fail((jqXHR, textStatus, errorThrown) => {
                        this.env.services.dialog.add(AlertDialog, {
                            title: "Impresora no detectada",
                            body: `No se pudo conectar con la impresora. Revise la conexión y configuración.\n\n${textStatus} - ${errorThrown}`,
                        });
                        resolve(false);
                    });
                });
            }
        };

    Registries.Component.extend(PaymentScreen, ExtendPaymentScreen);
});

odoo.define("3mit_print_server.print_ticket", function (require) {
    "use strict";

    const ReceiptScreen = require("point_of_sale.ReceiptScreen");
    const PaymentScreen = require("point_of_sale.PaymentScreen");
    const Registries = require("point_of_sale.Registries");
    const TicketScreen = require("point_of_sale.TicketScreen"); 

    var { Order, Orderline, PosGlobalState } = require("point_of_sale.models");
    const core = require("web.core");
    const rpc = require("web.rpc");
    const _t = core._t;
	var fixMoney = (window.fixMoney = function fixMoney(n) {
		return Math.round(n * 100) / 100;
		//return round_di(n, 2);
	  });

    const POSOrderMit = (PosGlobalState) =>
        class POSOrderMit extends PosGlobalState {
            async _processData(loadedData) {
                await super._processData(...arguments);
                this.pos_order = loadedData["pos_order"] || [];
            }
        };

    Registries.Model.extend(PosGlobalState, POSOrderMit);

    const ExtendReceiptScreen = (ReceiptScreen) =>
        class extends ReceiptScreen {
            mounted() {
                super.mounted(...arguments);
                // 🔄 Actualizar visibilidad basada en el estado actual
                const isPrinted = this.currentOrder.impresa;
                $(".button.next.validation", this.el).css({
                    "opacity": isPrinted ? "1" : "0",
                    "pointer-events": isPrinted ? "auto" : "none",
                });
            }

			async print_3mit(order) {
				const json = await this._3mit_prepare_json(order);
				const printer_host = this.env.pos.config.printer_host; // <-- ¡Este es el campo correcto!
			
				try {
					const rs = await $.post({
						url: `http://${printer_host}/api/imprimir/factura`,
						data: JSON.stringify(json),
						contentType: "application/json",
						dataType: "json",
						timeout: 10000,
					});
					
					if (rs.status == "OK") {
						return rs.data;
					} else {
						throw new Error(rs.message || "Error en la impresora fiscal");
					}
				} catch (err) {
					await this.showPopup("ErrorPopup", {
						title: "Error Fiscal",
						body: err.message || err.statusText,
					});
					return null;
				}
			}

            async printNewButtonFiscal() {
                console.log("🖨️ Botón de Imprimir Fiscal presionado.");

                const isPrinted = await this._printNewButtonFiscal();

                if (isPrinted) {
                    this.currentOrder.impresa = true;
                    $(".button.next.validation", this.el).css({
                        "opacity": "1",
                        "pointer-events": "auto",
                    });
                    console.log("✅ Impresión finalizada, botón 'New Order' visible.");
                } else {
                    $(".button.next.validation", this.el).css({
                        "opacity": "0",
                        "pointer-events": "none",
                    });
                    console.log("❌ Impresión fallida, botón 'New Order' sigue oculto.");
                }
            }

            async _printNewButtonFiscal() {
                const order = this.currentOrder;

                if (order._printed_fiscal) {
                    await this.showPopup("ErrorPopup", {
                        title: "FACTURA",
                        body: "LA FACTURA SE ESTÁ IMPRIMIENDO",
                    });
                    return true;
                }

                var json = order.export_for_printing();
                var rate_order = await this.rpc({
                    model: "pos.order",
                    method: "get_rate_order",
                    args: [false, json.name],
                });

                order.rate_order = rate_order;
                const dataFiscal = await this.print_3mit(order);

                if (!dataFiscal || !dataFiscal.nroFiscal) {
                    await this.showPopup("ErrorPopup", {
                        title: "ERROR IMPRIMIENDO",
                        body: "APAGUE Y ENCIENDA LA IMPRESORA Y REINTENTE IMPRIMIR\n\n" + dataFiscal,
                    });
                    return false;
                }

                order._printed_fiscal = true;

                try {
                    await this.rpc({
                        model: "pos.order",
                        method: "setTicket",
                        args: [
                            false,
                            {
                                orderUID: order.uid,
                                nroFiscal: dataFiscal.nroFiscal,
                                fecha: dataFiscal.fecha,
                                serial: dataFiscal.serial,
                            },
                        ],
                    });
                } catch (err) {
                    await this.showPopup("ErrorPopup", {
                        title: "ERROR INTERNO",
                        body: "NO SE PUDO OBTENER LA INFORMACIÓN FISCAL DE LA IMPRESORA",
                    });
                } finally {
                    return true;
                }
            }

            orderDone() {
                if (this.currentOrder.impresa) {
                    this.env.pos.removeOrder(this.currentOrder);
                    this._addNewOrder();
                    const { name, props } = this.nextScreen;
                    this.showScreen(name, props);
                    if (this.env.pos.config.iface_customer_facing_display) {
                        this.env.pos.send_current_order_to_customer_facing_display();
                    }
                } else {
                    this.showPopup("ErrorPopup", {
                        title: "Error",
                        body: "Debe imprimir el documento fiscal",
                    });
                }
            }
			async _3mit_prepare_json(order) {
				var json = order.export_for_printing();
				console.log('order', order);
				if (!json.client) json.client = {};
				var receipt = {
					backendRef: json.name || null,
					idFiscal: json.client.vat ||
						json.client.identification_id ||
						null,
					razonSocial: json.client.name || null,
					direccion: json.client.street || null,
					telefono: json.client.phone || null,
				};
				// items-products/
				const discount_product_id = this.env.pos.config.discount_product_id[0]
				var prods = json.orderlines.filter(r=>r.product_id!=discount_product_id);
				receipt.items = prods.map((r) => {
					return {
						nombre: r.product_name,
						cantidad: r.quantity,
						precio: fixMoney(r.product_price),
						impuesto: r.iva_rate,
						descuento: r.discount,
						tipoDescuento: 'p',
						comentario: r.customer_note || "", // Aquí añadimos los comentarios de los productos
					};
				});
				
				if(order.pc_discount){
					receipt.descuento = order.pc_discount;
					receipt.tipoDescuento = 'p';
				}
			
				const bi_igtf = order.bi_igtf || 0;
				receipt.pagos = [];
				async function getPaymentMethodData(paymentMethodName) {
					let paymentMethodId = await rpc.query({
						model: 'pos.payment.method',
						method: 'search',
						args: [[['name', '=', paymentMethodName]]]
					});
					
					let fields = ['dolar_active', 'fiscal_print_code'];
					
					let paymentMethodData = await rpc.query({
						model: 'pos.payment.method',
						method: 'read',
						args: [paymentMethodId, fields]
					});
					
					return paymentMethodData[0];
				}
			
				// Consolida por código en la impresora
				const pagos = await Promise.all(json.paymentlines.map(async (r) => {
					let data_payment = await getPaymentMethodData(r.name);
					console.log(data_payment);
					console.log("dolar_active:",data_payment.dolar_active);
					console.log("Code:",data_payment.fiscal_print_code);
					console.log("Objeto r:", r);
			
					let monto = 0;
					let igtf = 0;
					if(data_payment.dolar_active == true){
						igtf = fixMoney(r.amount * 0.03);
						monto = fixMoney(r.amount);
					} else {
						monto = fixMoney(r.amount);
					}
					console.log('tasa', order.rate_order);
					console.log('igtf', igtf);
					console.log('amount', r.amount);
					console.log('monto', monto);
					return {
						codigo: data_payment.fiscal_print_code,
						nombre: r.name,
						monto: monto,
						//monto: fixMoney(r.amount * order.rate_order),
					};
				}));
			
				pagos.forEach((r) => {
					const p = receipt.pagos.find((f) => f.codigo == r.codigo);
					if (!p) {
						receipt.pagos.push(r);
					} else {
						p.monto += r.monto;
					}
				});
			
				// Añade los comentarios del pedido
				receipt.comentarios = json.note ? [json.note] : [];
			
				return receipt;
			}
        };

    Registries.Component.extend(ReceiptScreen, ExtendReceiptScreen);

    const ExtendPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            async _isOrderValid(isForceValidate) {
                const ret = await super._isOrderValid(isForceValidate);
                const isPrinterDetected = await this.validate_printer_connection();
    
                this.currentOrder.ticket_fiscal = null;
                // para forzar la creación de la factura
                this.to_invoice = true;
    
                return ret && isPrinterDetected;
            }
    
            /**
             * Envía un JSON mínimo con todos los campos que el servicio de impresión requiere,
             * para validar la conexión sin lanzar NullReferenceException.
             * Permite continuar con el pago si la respuesta es:
             * {
             *   "data": null,
             *   "message": "El documento no tiene valor comercial",
             *   "status": "ERROR"
             * }
             */
            validate_printer_connection() {
                if (window._debug) return Promise.resolve(true);
    
                const printer_host = this.env.pos.config.printer_host;
                const configured_serial = this.env.pos.config.printer_serial; // 🔴 Obtener serial configurado
                // JSON mínimo "válido" para la validación de la conexión
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
                    $.post({
                        url: `http://${printer_host}/api/imprimir/factura`,
                        data: JSON.stringify(testPayload),
                        contentType: "application/json",
                        dataType: "json",
                        timeout: 5000,
                    })
                    .done((response) => {
                        const status = response?.status?.toLowerCase() || '';
                        const printer_serial = response.data?.serial; // 🔴 Obtener serial de la respuesta
                        // 1. Validar estado de la respuesta
                        if (status !== 'ok' && !(status === 'error')) {
                            this.showPopup('ErrorPopup', {
                                title: "Error de Impresora",
                                body: `Respuesta inválida: ${JSON.stringify(response)}`
                            });
                            return resolve(false);
                        }
    
                        // 2. Validar serial fiscal
                        if (!printer_serial) {
                            this.showPopup('ErrorPopup', {
                                title: "Serial no detectado",
                                body: "La impresora no devolvió su número de serie"
                            });
                            return resolve(false);
                        }
    
                        if (printer_serial !== configured_serial) {
                            this.showPopup('ErrorPopup', {
                                title: "Serial incorrecto",
                                body: `Serial configurado: ${configured_serial}\nSerial detectado: ${printer_serial}`
                            });
                            return resolve(false);
                        }
    
                        resolve(true);
                    })
                    .fail((jqXHR, textStatus, errorThrown) => {
                        this.showPopup("ErrorPopup", {
                            title: "Impresora no detectada",
                            body: `No se pudo conectar con la impresora. Revise la conexión y configuración.\n\n${textStatus} - ${errorThrown}`,
                        });
                        resolve(false);
                    });
                });
            }
        };
    
    Registries.Component.extend(PaymentScreen, ExtendPaymentScreen);    

    const MitCustomOrder = (Order) =>
        class MitCustomOrder extends Order {
            constructor(obj, options) {
                super(...arguments);
                this.ticket_fiscal = null;
                this.serial_fiscal = null;
                this.fecha_fiscal = null;
                this.pc_discount = 0;
                this.impresa = false; // Se agrega la variable para rastrear la impresión
            }

            init_from_JSON(json) {
                this.ticket_fiscal = json.ticket_fiscal;
                this.serial_fiscal = json.serial_fiscal;
                this.fecha_fiscal = json.fecha_fiscal;
                this.pc_discount = json.pc_discount;
                this.impresa = json.impresa || false;
                super.init_from_JSON(...arguments);
            }

            export_as_JSON() {
                var data = super.export_as_JSON(...arguments);
                data.ticket_fiscal = this.ticket_fiscal;
                data.serial_fiscal = this.serial_fiscal;
                data.fecha_fiscal = this.fecha_fiscal;
                data.pc_discount = this.pc_discount;
                data.impresa = this.impresa;
                return data;
            }

            export_for_printing() {
                var receipt = super.export_for_printing(...arguments);
                receipt.client = this.get_partner();
                return receipt;
            }
        };

    Registries.Model.extend(Order, MitCustomOrder);

	const CustomOrderLine = (Orderline) => class CustomOrderLine extends Orderline{

        export_for_printing() {
        	var line = super.export_for_printing(...arguments);
			var taxes = this.get_taxes();
			if (taxes.length === 0) {
				line.iva_rate = 0;
			} else {
				line.iva_rate = taxes[0].amount;
			}
			  //
			line.product_price = this.price
			line.product_id = this.product.id; //luego se usará para determinar si es una línea de Descuento
			return line;
	    }
	    
	}
	Registries.Model.extend(Orderline, CustomOrderLine);

    // 🔴 1. Extensión de TicketScreen con validación reforzada
    const TicketScreenMit = (TicketScreen) =>
        class extends TicketScreen {
            shouldHideDeleteButton(order) {
                // Bloquear delete si está impreso o facturado
                return super.shouldHideDeleteButton(order) || order.impresa || order.finalized;
            }
    
            async _onDeleteOrder({ detail: order }) {
                if (order.impresa) {
                    await this.showPopup('ErrorPopup', {
                        title: "Acción no permitida",
                        body: "No puede eliminar pedidos con comprobante fiscal impreso",
                    });
                    return;
                }
                await super._onDeleteOrder(...arguments);
            }
        };
        Registries.Component.extend(TicketScreen, TicketScreenMit);
    
});

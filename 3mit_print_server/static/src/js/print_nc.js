/** @odoo-module **/

import { onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

class PrintNotaCreditoController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");

        onMounted(() => {
            if (this.model && this.model.root) {
                // En Odoo 17+, los botones special="save" en dialogos llaman directamente
                // a model.root.save(), ignorando el save() del FormController.
                // Interceptamos la funcion save en el root para ejecutar nuestra logica.
                const originalSave = this.model.root.save.bind(this.model.root);
                this.model.root.save = async (params = {}) => {
                    try {
                        const record = this.model.root;
                        const orderId = record.context?.active_id || this.props.context?.active_id;
                        const payload = {
                            numFactura: record.data.numFactura,
                            fechaFactura: record.data.fechaFactura,
                            serialImpresora: record.data.serialImpresora,
                        };
                        
                        // En Odoo 17+ debemos pasar el contexto en kwargs para que lo lea env.context.get('active_id')
                        const kwargs = { context: { active_id: orderId } };
                        const printerData = await this.orm.call("pos.print.notacredito", "getTicket", [payload], kwargs);
                        
                        const response = await this.print_3mit(printerData.printer_host, printerData.ticket);
                        await this.orm.call("pos.order", "setTicket", [[orderId], response.data]);
                        
                        return await originalSave(params);
                    } catch (error) {
                        this.notification.add(error?.message || error?.statusText || String(error), {
                            title: "TICKET FISCAL",
                            type: "danger",
                        });
                        return false;
                    }
                };
            }
        });
    }

    async print_3mit(printer_host, ticket) {
        const port = printer_host && printer_host.includes(":") ? printer_host.split(":")[1] : "5000";
        const rawHost = printer_host && printer_host.includes(":") ? printer_host.split(":")[0] : (printer_host || "localhost");

        const candidateUrls = [
            `http://${rawHost}:${port}/api/imprimir/nota-credito`,
            `http://localhost:${port}/api/imprimir/nota-credito`,
            `http://127.0.0.1:${port}/api/imprimir/nota-credito`,
        ];

        console.log("[3mit Nota Credito] Intentando imprimir en URLs candidatas:", candidateUrls);

        let lastError = null;
        for (const url of candidateUrls) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 15000);

                const response = await fetch(url, {
                    method: "POST",
                    cache: 'no-store',
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: ticket,
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data?.message || `Error devuelto por la impresora en ${url}`);
                }
                console.log(`[3mit Nota Credito] ✓ Impresión exitosa en ${url}:`, data);
                return data;
            } catch (err) {
                lastError = err;
                console.warn(`[3mit Nota Credito] Falló intento en ${url}:`, err);
            }
        }

        throw lastError || new Error(`No se pudo conectar con el servidor de impresión fiscal en ninguna dirección (${printer_host}, localhost, 127.0.0.1).`);
    }
}

registry.category("views").add("pos_printer_nota_credito", {
    ...formView,
    Controller: PrintNotaCreditoController,
});
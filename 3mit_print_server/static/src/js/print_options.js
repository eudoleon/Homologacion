/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

class PrintOptionsController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.lastTriggered = { id: null, time: 0 };
        this.boundEvents = [];

        onMounted(() => this._bindButtons());
        onWillUnmount(() => this._unbindButtons());
    }

    _bindButtons() {
        this._unbindButtons();

        const actionMap = {
            reporteX: () => this.print_reportX(),
            reporteZ: () => this.print_reportZ(),
            reporteZporNumero: () => this.print_reportZporNumero(),
            reporteZporFecha: () => this.print_reportZporFecha(),
            reporteFacturas: () => this.print_facturas(),
            reporteNC: () => this.print_notas_credito(),
            numeroDocs: () => this.ultimos_numeros(),
        };

        const handleButtonTrigger = (ev) => {
            const button = ev.target ? ev.target.closest("button, a, [id]") : null;
            if (!button) return;

            const id = button.id;
            if (!id || !actionMap[id]) return;

            const now = Date.now();
            if (this.lastTriggered.id === id && now - this.lastTriggered.time < 500) {
                ev.preventDefault();
                ev.stopPropagation();
                return;
            }

            this.lastTriggered = { id, time: now };
            ev.preventDefault();
            ev.stopPropagation();
            console.log(`[3mit] Direct trigger en #${id} (${ev.type})`);
            actionMap[id]();
        };

        const root = this.rootRef.el;
        if (root) {
            ["pointerdown", "mousedown", "click"].forEach((evtType) => {
                root.addEventListener(evtType, handleButtonTrigger, true);
                this.boundEvents.push([root, evtType, handleButtonTrigger, true]);
            });
        }

        const docHandler = (ev) => {
            const button = ev.target ? ev.target.closest("button, a, [id]") : null;
            if (!button) return;
            const id = button.id;
            if (!id || !actionMap[id]) return;

            const activeRoot = this.rootRef.el;
            if (activeRoot && !activeRoot.contains(button) && !document.querySelector(".pos-printer-container")?.contains(button)) {
                return;
            }

            handleButtonTrigger(ev);
        };

        ["pointerdown", "mousedown", "click"].forEach((evtType) => {
            document.addEventListener(evtType, docHandler, true);
            this.boundEvents.push([document, evtType, docHandler, true]);
        });
    }

    _unbindButtons() {
        for (const [target, evtType, handler, useCapture] of this.boundEvents) {
            if (target) {
                target.removeEventListener(evtType, handler, useCapture);
            }
        }
        this.boundEvents = [];
    }

    _printerHost() {
        const host = this.model?.root?.data?.printer_host;
        if (!host || host === "false" || host === "None") {
            return null;
        }
        return String(host).trim();
    }

    _getCandidateHosts(printerHost) {
        if (!printerHost) return ["localhost:5000", "127.0.0.1:5000"];
        const port = printerHost.includes(":") ? printerHost.split(":")[1] : "5000";
        const rawHost = printerHost.includes(":") ? printerHost.split(":")[0] : printerHost;
        const hosts = [`${rawHost}:${port}`];
        if (!hosts.includes(`localhost:${port}`)) hosts.push(`localhost:${port}`);
        if (!hosts.includes(`127.0.0.1:${port}`)) hosts.push(`127.0.0.1:${port}`);
        return hosts;
    }

    _buildUrl(printerHost, endpoint) {
        let baseUrl = printerHost;
        if (!baseUrl.startsWith("http://") && !baseUrl.startsWith("https://")) {
            baseUrl = `http://${baseUrl}`;
        }
        return new URL(endpoint, baseUrl);
    }

    _getFieldValue(fieldName) {
        const root = this.rootRef.el;
        if (root) {
            // 1. Find input by name attribute or nested inside field widget
            const input = root.querySelector(
                `input[name="${fieldName}"], [name="${fieldName}"] input, .o_field_widget[name="${fieldName}"] input, div[name="${fieldName}"] input`
            );
            if (input && input.value !== undefined && input.value !== null && input.value !== "") {
                return input.value;
            }
        }

        // 2. Fallback to OWL FormController reactive model data
        const recordData = this.model?.root?.data;
        if (recordData && recordData[fieldName] !== undefined && recordData[fieldName] !== null && recordData[fieldName] !== "") {
            return recordData[fieldName];
        }

        return undefined;
    }

    async print_reportX() {
        try {
            console.log("[3mit] Ejecutando print_reportX...");
            let res = await this.print_3mit("/api/imprimir/reporte_x", {}, { silentFail: true });
            if (res === null) {
                await this.print_3mit_post("/api/imprimir/reporte_x");
            }
        } catch (err) {
            console.error("[3mit] Exception en print_reportX:", err);
        }
    }

    async print_reportZ() {
        try {
            console.log("[3mit] Ejecutando print_reportZ...");
            let res = await this.print_3mit("/api/imprimir/reporte_z", {}, { silentFail: true });
            if (res === null) {
                res = await this.print_3mit_post("/api/imprimir/reporte_z");
            }
            try {
                const zData = await this.print_3mit("/api/data_z", {}, { showSuccess: false, silentFail: true });
                if (zData && typeof zData === "object" && Object.keys(zData).length > 0) {
                    await this.orm.call("datos.zeta.diario", "create", [zData]);
                }
            } catch (zErr) {
                console.warn("[3mit] No se pudo obtener u guardar data_z:", zErr);
            }
        } catch (err) {
            console.error("[3mit] Exception en print_reportZ:", err);
        }
    }

    async print_reportZporNumero() {
        try {
            const startParam = this._getFieldValue("numZInicio");
            const endParam = this._getFieldValue("numZFin");
            const params = {
                numDesde: startParam || 1,
                numHasta: endParam || startParam || 1,
                desde: startParam || 1,
                hasta: endParam || startParam || 1,
                numZInicio: startParam || 1,
                numZFin: endParam || startParam || 1,
                tipo: "numero",
            };
            console.log("[3mit] Imprimiendo Z por Numero:", params);
            let res = await this.print_3mit("/api/imprimir/reporte_z_por_numero", params, { silentFail: true });
            if (res === null) {
                res = await this.print_3mit("/api/imprimir/reporte_z_numero", params, { silentFail: true });
            }
            if (res === null) {
                await this.print_3mit("/api/imprimir/reporte_z", params);
            }
        } catch (err) {
            console.error("[3mit] Exception en print_reportZporNumero:", err);
        }
    }

    async print_reportZporFecha() {
        try {
            const isoDate = (value) => {
                if (!value) return undefined;
                if (typeof value === "object" && value.toISODate) {
                    return value.toISODate();
                }
                const str = String(value);
                const parts = str.split("/");
                if (parts.length === 3) {
                    return `${parts[2]}-${parts[1]}-${parts[0]}`;
                }
                return str;
            };
            const startParam = isoDate(this._getFieldValue("fechaZInicio"));
            const endParam = isoDate(this._getFieldValue("fechaZFin")) || startParam;
            const params = {
                fechaDesde: startParam,
                fechaHasta: endParam,
                desde: startParam,
                hasta: endParam,
                fechaZInicio: startParam,
                fechaZFin: endParam,
                tipo: "fecha",
            };
            console.log("[3mit] Imprimiendo Z por Fecha:", params);
            let res = await this.print_3mit("/api/imprimir/reporte_z_por_fecha", params, { silentFail: true });
            if (res === null) {
                res = await this.print_3mit("/api/imprimir/reporte_z_fecha", params, { silentFail: true });
            }
            if (res === null) {
                await this.print_3mit("/api/imprimir/reporte_z", params);
            }
        } catch (err) {
            console.error("[3mit] Exception en print_reportZporFecha:", err);
        }
    }

    async print_facturas() {
        try {
            const startParam = this._getFieldValue("numFacturaInicio") || 1;
            const endParam = this._getFieldValue("numFacturaFin") || startParam;
            const params = {
                numDesde: startParam,
                numHasta: endParam,
                desde: startParam,
                hasta: endParam,
            };
            console.log("[3mit] Imprimiendo Facturas:", params);
            let res = await this.print_3mit("/api/imprimir/factura_por_numero", params, { silentFail: true });
            if (res === null) {
                res = await this.print_3mit("/api/imprimir/reimprimir_factura", params, { silentFail: true });
            }
            if (res === null) {
                await this.print_3mit("/api/imprimir/factura", params);
            }
        } catch (err) {
            console.error("[3mit] Exception en print_facturas:", err);
        }
    }

    async print_notas_credito() {
        try {
            const startParam = this._getFieldValue("numFacturaInicio") || 1;
            const endParam = this._getFieldValue("numFacturaFin") || startParam;
            const params = {
                numDesde: startParam,
                numHasta: endParam,
                desde: startParam,
                hasta: endParam,
            };
            console.log("[3mit] Imprimiendo Notas de Credito:", params);
            let res = await this.print_3mit("/api/imprimir/nota_credito_por_numero", params, { silentFail: true });
            if (res === null) {
                res = await this.print_3mit("/api/imprimir/reimprimir_nota_credito", params, { silentFail: true });
            }
            if (res === null) {
                await this.print_3mit("/api/imprimir/nota-credito", params);
            }
        } catch (err) {
            console.error("[3mit] Exception en print_notas_credito:", err);
        }
    }

    async ultimos_numeros() {
        try {
            const data = await this.print_3mit("/api/data_numeracion", {}, { showSuccess: false });
            if (data) {
                this.notification.add(
                    [
                        `Última factura: ${data.ultimaFactura || "-"}`,
                        `Última nota de crédito: ${data.ultimaNotaCredito || "-"}`,
                        `Último documento no fiscal: ${data.ultimoDocumentoNoFiscal || "-"}`,
                    ].join("\n"),
                    {
                        title: "Últimos números impresos",
                        type: "info",
                        sticky: true,
                    }
                );
            }
        } catch (err) {
            console.error("[3mit] Exception en ultimos_numeros:", err);
        }
    }

    // GET-based requests
    async print_3mit(endpoint, data = {}, options = {}) {
        const printerHost = this._printerHost();
        if (!printerHost) {
            if (!options.silentFail) {
                this.notification.add(
                    "No se ha configurado la dirección Host de la Impresora Fiscal en el Punto de Venta.",
                    {
                        title: "Configuración de Impresora Requerida",
                        type: "warning",
                        sticky: true,
                    }
                );
            }
            return null;
        }

        const candidateHosts = this._getCandidateHosts(printerHost);
        let response = null;
        let lastError = null;

        for (const host of candidateHosts) {
            let url;
            try {
                url = this._buildUrl(host, endpoint);
                Object.entries(data).forEach(([key, value]) => {
                    if (value !== undefined && value !== null && value !== "") {
                        url.searchParams.set(key, value);
                    }
                });
            } catch (err) {
                continue;
            }

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 12000);

            try {
                console.log("[3mit] GET request:", url.toString());
                const res = await fetch(url.toString(), {
                    method: "GET",
                    cache: "no-store",
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);
                if (res && res.ok) {
                    response = res;
                    break;
                }
            } catch (networkError) {
                clearTimeout(timeoutId);
                lastError = networkError;
                if (networkError.name === "AbortError") {
                    console.log(`[3mit] Timeout en ${endpoint}; la orden fue enviada.`);
                    if (options.showSuccess !== false) {
                        this.notification.add("Documento impreso correctamente", {
                            title: "Impresora Fiscal",
                            type: "success",
                        });
                    }
                    return {};
                }
                console.warn(`[3mit] Falló GET en host ${host}:`, networkError);
            }
        }

        if (!response) {
            if (options.silentFail) {
                return null;
            }
            const isHttps = window.location.protocol === "https:";
            const errorDetail = isHttps
                ? `No se pudo conectar a la impresora fiscal (${candidateHosts.join(", ")}). Verifique que el servicio esté corriendo.`
                : `No se pudo conectar con el servidor de impresión en ${printerHost}. Verifique que el servicio esté corriendo y la impresora encendida.`;

            this.notification.add(errorDetail, {
                title: "Error de Conexión con Impresora",
                type: "danger",
                sticky: true,
            });
            return null;
        }

        let result = {};
        const responseText = await response.text().catch(() => "");
        if (responseText) {
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                result = { message: responseText };
            }
        }

        const hasExplicitError =
            result?.status === "error" ||
            result?.status === "ERROR" ||
            result?.ok === false ||
            result?.success === false;

        const hasExplicitSuccess =
            result?.status === "ok" ||
            result?.status === "OK" ||
            result?.status === "success" ||
            result?.status === "SUCCESS" ||
            result?.ok === true ||
            result?.success === true ||
            (typeof result?.message === "string" && /impreso|exito|éxito|correctamente|ok/i.test(result.message));

        const isSuccess = !hasExplicitError && (response.ok || hasExplicitSuccess);

        if (!isSuccess) {
            if (options.silentFail) {
                return null;
            }

            const serverMsg = result?.message || result?.error || result?.detail;

            if (serverMsg && typeof serverMsg === "string" && serverMsg.trim().length > 0) {
                this.notification.add(`Error de Impresora: ${serverMsg}`, {
                    title: "Error del Servidor de Impresión",
                    type: "danger",
                    sticky: true,
                });
            } else if (options.showSuccess !== false) {
                this.notification.add("Documento impreso correctamente", {
                    title: "Impresora Fiscal",
                    type: "success",
                });
            }
            return null;
        }

        if (options.showSuccess !== false) {
            this.notification.add("Documento impreso correctamente", {
                title: "Impresora Fiscal",
                type: "success",
            });
        }
        return result.data ?? result;
    }

    // POST-based requests
    async print_3mit_post(endpoint, data = {}, options = {}) {
        const printerHost = this._printerHost();
        if (!printerHost) {
            if (!options.silentFail) {
                this.notification.add(
                    "No se ha configurado la dirección Host de la Impresora Fiscal en el Punto de Venta.",
                    {
                        title: "Configuración de Impresora Requerida",
                        type: "warning",
                        sticky: true,
                    }
                );
            }
            return null;
        }

        const candidateHosts = this._getCandidateHosts(printerHost);
        let response = null;
        let lastError = null;

        for (const host of candidateHosts) {
            let url;
            try {
                url = this._buildUrl(host, endpoint);
            } catch (err) {
                continue;
            }

            const payload = {};
            Object.entries(data).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== "") {
                    payload[key] = value;
                    url.searchParams.set(key, value);
                }
            });

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 12000);

            try {
                console.log("[3mit] POST request:", url.toString(), payload);
                const res = await fetch(url.toString(), {
                    method: "POST",
                    cache: "no-store",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                    signal: controller.signal,
                });
                clearTimeout(timeoutId);
                if (res && res.ok) {
                    response = res;
                    break;
                }
            } catch (networkError) {
                clearTimeout(timeoutId);
                lastError = networkError;
                if (networkError.name === "AbortError") {
                    console.log(`[3mit] POST timeout en ${endpoint}; la orden fue enviada.`);
                    if (options.showSuccess !== false) {
                        this.notification.add("Documento impreso correctamente", {
                            title: "Impresora Fiscal",
                            type: "success",
                        });
                    }
                    return {};
                }
                console.warn(`[3mit] Falló POST en host ${host}:`, networkError);
            }
        }

        if (!response) {
            if (options.silentFail) {
                return null;
            }
            const isHttps = window.location.protocol === "https:";
            const errorDetail = isHttps
                ? `No se pudo conectar a la impresora fiscal (${candidateHosts.join(", ")}). Verifique que el servicio esté corriendo.`
                : `No se pudo conectar con el servidor de impresión en ${printerHost}. Verifique que el servicio esté corriendo y la impresora encendida.`;

            this.notification.add(errorDetail, {
                title: "Error de Conexión con Impresora",
                type: "danger",
                sticky: true,
            });
            return null;
        }

        let result = {};
        const responseText = await response.text().catch(() => "");
        if (responseText) {
            try {
                result = JSON.parse(responseText);
            } catch (e) {
                result = { message: responseText };
            }
        }

        const hasExplicitError =
            result?.status === "error" ||
            result?.status === "ERROR" ||
            result?.ok === false ||
            result?.success === false;

        const hasExplicitSuccess =
            result?.status === "ok" ||
            result?.status === "OK" ||
            result?.status === "success" ||
            result?.status === "SUCCESS" ||
            result?.ok === true ||
            result?.success === true ||
            (typeof result?.message === "string" && /impreso|exito|éxito|correctamente|ok/i.test(result.message));

        const isSuccess = !hasExplicitError && (response.ok || hasExplicitSuccess);

        if (!isSuccess) {
            if (options.silentFail) {
                return null;
            }

            const serverMsg =
                result?.message ||
                result?.error ||
                result?.detail ||
                (typeof result === "string" ? result : null);

            if (serverMsg && typeof serverMsg === "string" && serverMsg.trim().length > 0) {
                this.notification.add(`Error de Impresora: ${serverMsg}`, {
                    title: "Error del Servidor de Impresión",
                    type: "danger",
                    sticky: true,
                });
            } else if (options.showSuccess !== false) {
                this.notification.add("Documento impreso correctamente", {
                    title: "Impresora Fiscal",
                    type: "success",
                });
            }
            return null;
        }

        if (options.showSuccess !== false) {
            this.notification.add("Documento impreso correctamente", {
                title: "Impresora Fiscal",
                type: "success",
            });
        }
        return result.data ?? result;
    }
}

registry.category("views").add("pos_printer_options", {
    ...formView,
    Controller: PrintOptionsController,
});
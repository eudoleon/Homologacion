/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export const accountBannerService = {
    start(env) {
        console.log("🟡 JS del banner cargado (Odoo 19)");

        async function loadBanner() {
            try {
                console.log("📡 Solicitando estado del banner...");
                const result = await rpc('/account/banner/status', {});
                console.log("📥 Respuesta del servidor:", result);

                // Banner condicional por cierre de periodo
                if (result.show_banner) {
                    const banner1 = document.createElement('div');
                    banner1.id = 'account_closure_banner';
                    banner1.style = 'background: #ffc107; padding: 10px; text-align: center; position: relative; z-index: 1000;';
                    banner1.innerHTML = `
                        <strong style="display:block; font-size: 16px; margin-bottom: 5px; color: red;">
                            🚨 ADVERTENCIA: <span style="color: black; font-weight: bold;">PERIODO ANTERIOR SIN CERRAR</span>
                        </strong>
                        <span style="color: #333; font-weight: 600;">
                            Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.
                            <br/>
                            Por favor, revise y complete el cierre correspondiente para evitar inconsistencias en los registros.
                        </span>
                    `;
                    document.body.prepend(banner1);
                }

                // Banner siempre visible: HOMOLOGACIÓN
                const banner2 = document.createElement('div');
                banner2.id = 'homologation_banner';
                banner2.style = 'background: #222; color: #fff; padding: 8px; text-align: center; font-weight: bold; position: relative; z-index: 1000;';
                banner2.innerHTML = '🔧 VERSIÓN: 19.0.2 / Implementador: Boyer León & Asociados';
                document.body.prepend(banner2);
            } catch (error) {
                console.error("Error al cargar el banner de periodo:", error);
            }
        }

        loadBanner();
    }
};

// Registrar el servicio en la categoría 'services' para que se inicie automáticamente
registry.category("services").add("account_banner_service", accountBannerService);

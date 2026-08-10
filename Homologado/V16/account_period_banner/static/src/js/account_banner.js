odoo.define('account_period_banner.banner', function (require) {
    "use strict";

    const session = require('web.session');
    const AbstractService = require('web.AbstractService');

    console.log("🟡 JS del banner cargado");

    const BannerService = AbstractService.extend({
        start: function () {
            this._super.apply(this, arguments);
            this.loadBanner();
        },

        async loadBanner() {
            console.log("📡 Solicitando estado del banner...");
            const result = await session.rpc('/account/banner/status');
            console.log("📥 Respuesta del servidor:", result);

            // Banner condicional por cierre de periodo
            if (result.show_banner) {
                const banner1 = document.createElement('div');
                banner1.id = 'account_closure_banner';
                banner1.style = 'background: #ffc107; padding: 10px; text-align: center;';
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
            banner2.style = 'background: #222; color: #fff; padding: 8px; text-align: center; font-weight: bold;';
            banner2.innerHTML = '🔧 VERSIÓN: 16.0.2 /  Implementador: Boyer León & Asociados';
            document.body.prepend(banner2);
        }
    });

    // Registrar el servicio en el bus de servicios de Odoo
    require('web.core').serviceRegistry.add('account_banner_service', BannerService);
});

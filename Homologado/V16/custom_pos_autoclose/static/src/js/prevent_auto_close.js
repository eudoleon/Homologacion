odoo.define('custom_pos_autoclose.ChromeOverride', function(require) {
    'use strict';

    const Chrome = require('point_of_sale.Chrome');
    const Registries = require('point_of_sale.Registries');

    const CustomChrome = (Chrome) => class extends Chrome {

        __closeTempScreen(event) {
            // Si se intenta cerrar desde la interfaz, permitimos el cierre manual
            if (event && event.detail && event.detail.manualClose) {
                console.log('Cierre manual permitido para:', this.tempScreen.name);
                this.tempScreen.isShown = false;
                this.env.pos.tempScreenIsShown = false;
                this.tempScreen.name = null;
                return;
            }

            // Evitar el cierre automático del popup para 'PartnerDetailsEdit' y 'PartnerListScreen'
            if (this.tempScreen.name === 'PartnerDetailsEdit' || this.tempScreen.name === 'PartnerListScreen') {
                console.log('Intento de cierre prevenido para:', this.tempScreen.name);
                return; // Evitamos el cierre automático
            }

            // Para otros casos, permitimos el cierre normal
            this.tempScreen.isShown = false;
            this.env.pos.tempScreenIsShown = false;
            this.tempScreen.name = null;
        }

        // Sobrescribimos __showTempScreen para aceptar manualClose en los props
        __showTempScreen(event) {
            console.log("Mostrando pantalla temporal: ", event.detail.name);
            const { name, props, resolve } = event.detail;
            this.tempScreen.isShown = true;
            this.tempScreen.name = name;
            this.tempScreen.component = this.constructor.components[name];
            this.tempScreenProps = Object.assign({}, props, { resolve, manualClose: true });
            this.env.pos.tempScreenIsShown = true;
        }
    };

    Registries.Component.extend(Chrome, CustomChrome);

    return CustomChrome;
});

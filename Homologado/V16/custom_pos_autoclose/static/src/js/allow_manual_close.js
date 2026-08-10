odoo.define('custom_pos_autoclose.PartnerListScreenOverride', function(require) {
    'use strict';

    const PartnerListScreen = require('point_of_sale.PartnerListScreen');
    const Registries = require('point_of_sale.Registries');

    const CustomPartnerListScreen = (PartnerListScreen) =>
        class extends PartnerListScreen {
            // Modificamos el método back para permitir el cierre manual
            back() {
                // Si estamos intentando cerrar manualmente, permitimos el cierre
                this.props.resolve({ confirmed: false, payload: false });
                this.trigger('close-temp-screen', { manualClose: true });  // Añadimos manualClose para Chrome
                console.log("Cerrar manualmente PartnerListScreen");
            }

            // Modificamos el método confirm para permitir el cierre manual
            confirm() {
                // Cuando se selecciona un cliente, permitimos el cierre manual
                this.props.resolve({ confirmed: true, payload: this.state.selectedPartner });
                this.trigger('close-temp-screen', { manualClose: true });  // Añadimos manualClose para Chrome
                console.log("Cliente seleccionado, cerrando PartnerListScreen manualmente.");
            }
        };

    Registries.Component.extend(PartnerListScreen, CustomPartnerListScreen);

    return CustomPartnerListScreen;
});

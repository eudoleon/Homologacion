odoo.define('customer_validation_pos.PartnerListScreen', function (require) {
    'use strict';

    const PartnerListScreen = require('point_of_sale.PartnerListScreen');
    const Registries = require('point_of_sale.Registries');

    const PosNewCustomerValidation = (PartnerListScreen) =>
        class extends PartnerListScreen {
            async saveChanges(event) {
                var name_list = [];
                var vat_list = [];
                var phone_list = [];
                var street_list = [];
                var email_list = [];

                var partners = this.env.pos.db.get_partners_sorted()
                var fields = event.detail.processedChanges
                for (var i = 0; i < partners.length; i++) {
                    if (partners[i].phone) {
                        name_list.push(partners[i].name);
                        vat_list.push(partners[i].vat);
                        phone_list.push(partners[i].phone);
                        street_list.push(partners[i].street);
                        email_list.push(partners[i].email);
                    }
                }
                if (this.env.pos.config.required_name && ((fields.id === false && !fields.name) || (fields.id && fields.name === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere el nombre del cliente!'),
                    });
                }
                // Validar que el campo name solo contenga letras y números y que las letras estén en mayúsculas
                if (fields.name && (!/^[\w\sÑÁÉÍÓÚÜ!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+$/.test(fields.name) || fields.name !== fields.name.toUpperCase())) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡El nombre del cliente debe contener solo letras en mayúsculas!'),
                    });
                }
                if (this.env.pos.config.unique_name && fields.name && name_list.indexOf(fields.name) > -1) {
                    return this.showPopup('ErrorPopup', {
                        title: _('El nombre '+fields.name+' ya existe!'),
                    });
                }
                if (this.env.pos.config.required_vat && ((fields.id === false && !fields.identification_id) || (fields.id && fields.identification_id === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere C.I / R.I.F del cliente!'),
                    });
                }
                // Validar que el campo identification_id solo contenga números, letras de prefijos (V, E, J, P, G) y el símbolo "-"
                if (fields.identification_id && /[^VEJPG0-9-]/.test(fields.identification_id)) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡El C.I / R.I.F solo admite números, letras de prefijos (V, E, J, P, G) y el símbolo "-"!'),
                    });
                }
                if (fields.identification_id && !/^[VEJPG]-\d*$/.test(fields.identification_id)) {
                    fields.identification_id = fields.identification_id.replace(/[^VEJPG\d-]/g, '');
                }
                // Validar que siempre que haya cédula debe haber tipo de documento
                if (fields.identification_id && (!fields.id_type || fields.id_type === '')) {
                    if (!/^[VEJPGC]-/.test(fields.identification_id)) {
                        return this.showPopup('ErrorPopup', {
                            title: _('¡Debe seleccionar el tipo de documento antes de ingresar el número de cédula!'),
                        });
                    }
                }
                if (!fields.id && fields.identification_id && (!fields.id_type || fields.id_type === '')) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Debe seleccionar el tipo de documento antes de ingresar el número de cédula!'),
                    });
                }
                if (this.env.pos.config.unique_vat && fields.identification_id && vat_list.indexOf(fields.identification_id) > -1) {
                    const confirmation = await this.showPopup('ConfirmPopup', {
                        title: _('El cliente ya existe. ¿Desea actualizar los datos?'),
                        confirmText: _('Actualizar'),
                        cancelText: _('Cancelar'),
                    });

                    if (!confirmation) {
                        return;
                    }
                }
                
                // Validar duplicados de RIF/C.I considerando el tipo de documento y sin él
                if (!fields.id && fields.identification_id) { // Validar solo al crear nuevos contactos
                    const normalizedId = fields.identification_id.replace(/^[VEJPG]-/, ''); // Eliminar prefijo si existe

                    // Realizar una consulta al servidor para verificar duplicados en vat o identification_id
                    const existingId = await this.rpc({
                        model: 'res.partner',
                        method: 'search_read',
                        args: [[ '|', ['vat', 'ilike', normalizedId], ['identification_id', 'ilike', normalizedId] ], ['vat', 'identification_id']],
                    });

                    if (existingId && existingId.length > 0) {
                        return this.showPopup('ErrorPopup', {
                            title: _('La cédula ingresada ya está registrada en el sistema. Por favor, utilice la barra de búsqueda para seleccionar al cliente.'),
                        });
                    }
                }
                
                // Si llegamos aquí, significa que el usuario confirmó la actualización o no hay duplicados
                // Continúa con la lógica de actualización de datos aquí
                // ...
                if (this.env.pos.config.required_phone && ((fields.id === false && !fields.phone) || (fields.id && fields.phone === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere el número de teléfono del cliente!'),
                    });
                }
                // Validar que el campo phone solo contenga números
                if (fields.phone && /[^0-9]/.test(fields.phone)) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡El número de teléfono solo admite números!'),
                    });
                }
                // Validar que el campo phone solo contenga números y tenga exactamente 11 dígitos
                if (fields.phone && !/^[0-9]{11}$/.test(fields.phone)) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Numero de telefono Incompleto!'),
                    });
                }
                if (this.env.pos.config.unique_phone && fields.phone && phone_list.indexOf(fields.phone) > -1) {
                    return this.showPopup('ErrorPopup', {
                        title: _('El telefono '+fields.phone+' ya existe!'),
                    });
                }
                if (this.env.pos.config.required_street && ((fields.id === false && !fields.street) || (fields.id && fields.street === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere la dirección del cliente!'),
                    });
                }
                if (fields.street && fields.street !== fields.street.toUpperCase()) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡La dirección debe estar en mayúsculas!'),
                    });
                }
                if (this.env.pos.config.unique_street && fields.street && street_list.indexOf(fields.street) > -1) {
                    return this.showPopup('ErrorPopup', {
                        title: _('La direccion '+fields.street+' ya existe!'),
                    });
                }
                if (this.env.pos.config.required_email && ((fields.id === false && !fields.email) || (fields.id && fields.email === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere el correo del cliente!'),
                    });
                }
                if (this.env.pos.config.unique_email && fields.email && email_list.indexOf(fields.email) > -1) {
                    return this.showPopup('ErrorPopup', {
                        title: _('Correo '+fields.email+' ya existe!'),
                    });
                }
                if (this.env.pos.config.required_id_type && ((fields.id === false && !fields.id_type) || (fields.id && fields.id_type === ""))) {
                    return this.showPopup('ErrorPopup', {
                        title: _('¡Se requiere el tipo de documento del cliente!'),
                    });
                }
                
                // Agregar el tipo de documento al campo RIF/C.I
                if (fields.id_type && fields.identification_id) {
                    if (!fields.identification_id.startsWith(fields.id_type + '-')) {
                        fields.identification_id = fields.identification_id.replace(/^[VEJPG]-/, '');
                        fields.identification_id = fields.id_type + '-' + fields.identification_id;
                    }
                }
                // Sincronizar vat con identification_id para el backend
                fields.vat = fields.identification_id;
                super.saveChanges(...arguments);
            }
        };
    Registries.Component.extend(PartnerListScreen, PosNewCustomerValidation);
    return PosNewCustomerValidation;
});
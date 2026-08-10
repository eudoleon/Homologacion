odoo.define('gelartesano_contacto.partner_validation', function (require) {
    "use strict";
    const models = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    const PosModel = models.PosModel;
    var rpc = require('web.rpc');
    var core = require('web.core');
    var _t = core._t;

    const PartnerValidationPosModel = (PosModel) => class extends PosModel {
        async save_new_partner(partner) {
            if (partner && partner.identification_id) {
                const exists = await rpc.query({
                    model: 'res.partner',
                    method: 'search_count',
                    args: [[
                        ['identification_id', '=', partner.identification_id],
                        ['active', '=', true],
                    ]],
                });
                let existing_partner = null;
                if (exists) {
                    // Buscar el nombre del contacto con esa cédula
                    const partners = await rpc.query({
                        model: 'res.partner',
                        method: 'search_read',
                        args: [[
                            ['identification_id', '=', partner.identification_id],
                            ['active', '=', true],
                        ], ['name']],
                        limit: 1,
                    });
                    if (partners.length) {
                        existing_partner = partners[0].name;
                    }
                    this.env.services.popup.add({
                        title: _t('Documento fiscal duplicado'),
                        body: _t('Ya existe un contacto activo con el documento fiscal: ') + partner.identification_id + (existing_partner ? _t(' (Asignado a: ') + existing_partner + ')' : ''),
                        type: 'error',
                    });
                    return false;
                }
            }
            if (typeof super.save_new_partner === 'function') {
                return super.save_new_partner(...arguments);
            } else {
                // Si no existe el método en la superclase, simplemente retorna true (o ajusta según tu lógica)
                return true;
            }
        }
    };
    if (PosModel) {
        Registries.Model.extend(PosModel, PartnerValidationPosModel);
    } else {
        console.error('PosModel is undefined. No se pudo extender el modelo POS.');
    }
});
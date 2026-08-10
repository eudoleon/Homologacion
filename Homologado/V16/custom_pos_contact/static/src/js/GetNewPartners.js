odoo.define('custom_pos_contact.GetNewPartners', function (require) {
    'use strict';
    const env = require('point_of_sale.env');
    const utils = require('point_of_sale.utils');

    // Función para buscar nuevos partners incluyendo identification_id y todos los campos relevantes
    async function getNewPartners(state) {
        let domain = [];
        const limit = 30;
        // Campos relevantes para mostrar toda la información en el POS
        const search_fields = [
            "name",
            "parent_name",
            "phone",
            "mobile",
            "email",
            "vat",
            "identification_id",
            "street",
            "city",
            "state_id",
            "country_id",
            "zip",
            "property_product_pricelist", // <-- Añadido para evitar error en POS
            "category_id",     // <-- traer ids de etiquetas
            "category_names",  // <-- traer nombres (campo compute/store)
        ];
        if (state.query) {
            domain = [
                '|', '|', '|', '|', '|', '|',
                ['name', 'ilike', state.query],
                ['parent_name', 'ilike', state.query],
                ['phone', 'ilike', state.query],
                ['mobile', 'ilike', state.query],
                ['email', 'ilike', state.query],
                ['vat', 'ilike', state.query],
                ['identification_id', 'ilike', state.query],
            ];
        }
        const result = await env.services.rpc({
            model: 'res.partner',
            method: 'search_read',
            args: [domain, search_fields],
            kwargs: { limit },
        });
        console.log('DEBUG getNewPartners RPC result count:', result && result.length);
        if (result && result.length) {
            result.slice(0,5).forEach(r => console.log('DEBUG getNewPartners sample rec:', {
                id: r.id,
                name: r.name,
                category_id: r.category_id,
                category_names: r.category_names,
            }));
        }
        return result;
    }

    return {
        getNewPartners,
    };
});

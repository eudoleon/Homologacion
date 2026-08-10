odoo.define('custom_pos_contact.PartnerDbExtend', function (require) {
    'use strict';
    const PosDB = require('point_of_sale.DB');

    PosDB.include({
        search_partner: function(query){
            query = query.trim();
            if(query === ''){
                return this.get_partners_sorted(1000);
            }
            var partners = this.get_partners_sorted(1000);
            var q = query.toLowerCase();
            var results = partners.filter(partner => {
                return (
                    (partner.name && partner.name.toLowerCase().includes(q)) ||
                    (partner.email && partner.email.toLowerCase().includes(q)) ||
                    (partner.phone && partner.phone.toLowerCase().includes(q)) ||
                    (partner.mobile && partner.mobile.toLowerCase().includes(q)) ||
                    (partner.vat && partner.vat.toLowerCase().includes(q)) ||
                    (partner.identification_id && partner.identification_id.toLowerCase().includes(q)) ||
                    (partner.category_names && partner.category_names.toLowerCase().includes(q))
                );
            });
            return results;
        },

        // Nuevo: debug y normalización al agregar partners desde backend
        add_partners: function(partners){
            console.log('DEBUG add_partners incoming count:', partners && partners.length);
            if (partners && partners.length) {
                for (let i = 0; i < partners.length; i++){
                    let p = partners[i];
                    // Mostrar antes de normalizar
                    console.log('DEBUG add_partners partner raw:', {
                        id: p.id,
                        name: p.name,
                        category_id: p.category_id,
                        category_names: p.category_names,
                    });
                    if (p.hasOwnProperty('category_names')) {
                        if (Array.isArray(p.category_names)) {
                            p.category_names = p.category_names.join(',');
                        } else if (p.category_names === null) {
                            p.category_names = '';
                        } else {
                            p.category_names = String(p.category_names || '');
                        }
                    }
                    // Mostrar después de normalizar
                    console.log('DEBUG add_partners partner normalized:', {
                        id: p.id,
                        name: p.name,
                        category_id: p.category_id,
                        category_names: p.category_names,
                    });
                }
            }
            return this._super(partners);
        },
    });
});

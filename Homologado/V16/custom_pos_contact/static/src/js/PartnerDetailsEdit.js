odoo.define('custom_pos_contact.PartnerDetailsEdit', function (require) {
    "use strict";
    const PartnerDetailsEdit = require('point_of_sale.PartnerDetailsEdit');
    const Registries = require('point_of_sale.Registries');
    const { useState } = owl;



    const CustomPartnerDetailsEdit = (PartnerDetailsEdit) =>
        class extends PartnerDetailsEdit {
            setup() {
                super.setup();
                const partner = this.props.partner;
                console.log('DEBUG PartnerDetailsEdit partner:', partner);
                if (partner) {
                    console.log('DEBUG identification_id:', partner.identification_id);
                    console.log('DEBUG partner.category_id (raw):', partner.category_id);
                    console.log('DEBUG partner.category_names (stored):', partner.category_names);
                } else {
                    console.log('DEBUG partner no definido');
                }
                if (partner && partner.identification_id) {
                    this.changes.identification_id = partner.identification_id;
                }
                // Copiar etiquetas existentes al campo editable para que se muestre
                if (partner && partner.category_names) {
                    this.changes.category_names = partner.category_names;

                    // NUEVO: si existe category_id y el número de ids difiere del número de nombres,
                    // forzamos a leer los nombres reales desde res.partner.category
                    if (partner.category_id && Array.isArray(partner.category_id) && partner.category_id.length) {
                        const cat_ids = partner.category_id.map(item => Array.isArray(item) ? item[0] : item);
                        const current_names = String(partner.category_names || '').split(',').map(s => s.trim()).filter(Boolean);
                        if (cat_ids.length !== current_names.length) {
                            console.log('DEBUG PartnerDetailsEdit: mismatch category_names vs category_id, fetching names for ids:', cat_ids);
                            this.env.services.rpc({
                                model: 'res.partner.category',
                                method: 'read',
                                args: [cat_ids, ['name']],
                            }).then(cat_res => {
                                if (Array.isArray(cat_res)) {
                                    const names = cat_res.map(c => c.name).filter(Boolean);
                                    const joined = names.join(',');
                                    console.log('DEBUG PartnerDetailsEdit fetched category names (mismatch fix):', joined, 'raw cat_res:', cat_res);
                                    this.changes.category_names = joined;
                                }
                            }).catch(err => {
                                console.error('DEBUG PartnerDetailsEdit RPC error reading categories (mismatch fix):', err);
                            });
                        }
                    }
                } else if (partner) {
                    // Si no viene category_names, solicitarlo por RPC (por si proviene de pos.db sin ese campo)
                    this.changes.category_names = this.changes.category_names || '';

                    // Si el partner trae category_id (lista de ids o pares), obtener los nombres de las categorías
                    if ((!partner.category_names || partner.category_names === '') && partner.category_id && Array.isArray(partner.category_id) && partner.category_id.length) {
                        // Normalizar category_id: puede venir como [id, name] o como id
                        const cat_ids = partner.category_id.map(item => Array.isArray(item) ? item[0] : item);
                        console.log('DEBUG PartnerDetailsEdit: fetching category names for ids (normalized):', cat_ids);
                        this.env.services.rpc({
                            model: 'res.partner.category',
                            method: 'read',
                            args: [cat_ids, ['name']],
                        }).then(cat_res => {
                            if (Array.isArray(cat_res)) {
                                const names = cat_res.map(c => c.name).filter(Boolean);
                                const joined = names.join(',');
                                console.log('DEBUG PartnerDetailsEdit fetched category names:', joined, 'raw cat_res:', cat_res);
                                this.changes.category_names = joined;
                            }
                        }).catch(err => {
                            console.error('DEBUG PartnerDetailsEdit RPC error reading categories:', err);
                        });
                    } else if (!partner.category_names && partner.id) {
                        // fallback: leer category_names y category_id del partner en servidor
                        console.log('DEBUG PartnerDetailsEdit: fetching partner fields by RPC for id', partner.id);
                        this.env.services.rpc({
                            model: 'res.partner',
                            method: 'read',
                            args: [[partner.id], ['category_id', 'category_names', 'identification_id']],
                        }).then(res => {
                            if (res && res[0]) {
                                console.log('DEBUG PartnerDetailsEdit RPC read result:', res[0]);
                                this.changes.category_names = res[0].category_names || '';
                                console.log('DEBUG PartnerDetailsEdit RPC category_id (raw):', res[0].category_id);
                                // If category_id present as ids/pairs, normalize and fetch names to ensure completeness
                                if ((!this.changes.category_names || this.changes.category_names === '') && res[0].category_id && Array.isArray(res[0].category_id) && res[0].category_id.length) {
                                    const cat_ids = res[0].category_id.map(item => Array.isArray(item) ? item[0] : item);
                                    console.log('DEBUG PartnerDetailsEdit: fetching category names for ids (fallback, normalized):', cat_ids);
                                    this.env.services.rpc({
                                        model: 'res.partner.category',
                                        method: 'read',
                                        args: [cat_ids, ['name']],
                                    }).then(cat_res => {
                                        if (Array.isArray(cat_res)) {
                                            const names = cat_res.map(c => c.name).filter(Boolean);
                                            const joined = names.join(',');
                                            console.log('DEBUG PartnerDetailsEdit fetched category names (fallback):', joined, 'raw cat_res:', cat_res);
                                            this.changes.category_names = joined;
                                        }
                                    }).catch(err => {
                                        console.error('DEBUG PartnerDetailsEdit RPC error reading categories (fallback):', err);
                                    });
                                }
                            }
                        }).catch(err => {
                            console.error('DEBUG PartnerDetailsEdit RPC error reading partner:', err);
                        });
                    }
                }
            }

            saveChanges() {
                // Mostrar cambios antes de enviar
                console.log('DEBUG PartnerDetailsEdit saveChanges - before:', {
                    changes: this.changes,
                    props_partner_category_id: this.props.partner && this.props.partner.category_id,
                    props_partner_category_names: this.props.partner && this.props.partner.category_names,
                });

                // Asegura que identification_id se envía siempre
                if (this.changes.identification_id === undefined && this.props.partner && this.props.partner.identification_id) {
                    this.changes.identification_id = this.props.partner.identification_id;
                }
                // Copia identification_id a vat para cumplir con el campo obligatorio de Odoo
                if (this.changes.identification_id) {
                    this.changes.vat = this.changes.identification_id;
                }
                // Aseguramos que category_names se envía aunque no sea cambiado
                if (this.changes.category_names === undefined && this.props.partner && this.props.partner.category_names) {
                    this.changes.category_names = this.props.partner.category_names;
                }

                // Mostrar lo que se enviará finalmente
                console.log('DEBUG PartnerDetailsEdit saveChanges - sending:', this.changes);
                super.saveChanges();
            }
        };

    Registries.Component.extend(PartnerDetailsEdit, CustomPartnerDetailsEdit);
});

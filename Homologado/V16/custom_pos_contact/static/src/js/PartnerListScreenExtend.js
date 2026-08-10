odoo.define('custom_pos_contact.PartnerListScreenExtend', function (require) {
    'use strict';
    const PartnerListScreen = require('point_of_sale.PartnerListScreen');
    const Registries = require('point_of_sale.Registries');
    const { getNewPartners } = require('custom_pos_contact.GetNewPartners');

    const PartnerListScreenExtend = (PartnerListScreen) =>
        class extends PartnerListScreen {
            async getNewPartners() {
                // Usar la función personalizada para buscar por identification_id
                return await getNewPartners(this.state);
            }

            async updatePartnerList(event) {
                this.state.query = event.target.value;
                if (this.state.query && this.state.query.trim() !== '') {
                    const result = await this.getNewPartners();
                    console.log('DEBUG getNewPartners result:', result); // Agregado para depuración
                    this.env.pos.addPartners(result);
                    console.log('DEBUG partner_by_id:', this.env.pos.db.partner_by_id);
                    // Buscar en la base local después de agregar
                    const localResults = this.env.pos.db.search_partner(this.state.query.trim());
                    if (localResults.length === 0 && result.length > 0) {
                        // Si no hay resultados locales, mostrar los traídos del backend
                        this.state._forcePartners = result;
                    } else {
                        this.state._forcePartners = null;
                    }
                    this.render(true);
                } else {
                    this.state._forcePartners = null;
                    this.render(true);
                }
            }

            get partners() {
                if (this.state._forcePartners) {
                    let res = [...this.state._forcePartners];
                    res.sort(function (a, b) { return (a.name || '').localeCompare(b.name || '') });
                    if (this.state.selectedPartner) {
                        let indexOfSelectedPartner = res.findIndex(partner => partner.id === this.state.selectedPartner.id);
                        if (indexOfSelectedPartner !== -1) {
                            res.splice(indexOfSelectedPartner, 1);
                        }
                        res.unshift(this.state.selectedPartner);
                    }
                    return res;
                } else {
                    return super.partners;
                }
            }
        };

    Registries.Component.extend(PartnerListScreen, PartnerListScreenExtend);
});

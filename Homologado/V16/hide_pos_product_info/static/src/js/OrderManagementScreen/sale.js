odoo.define('hide_pos_product_info.PatchedSaleOrderManagementScreen', function(require){
    'use strict';
    // Función getId tomada del código original
    function getId(fieldVal) {
        return fieldVal && fieldVal[0];
    }
    const { sprintf } = require('web.utils');
    const { parse } = require('web.field_utils');
    const { _t } = require('@web/core/l10n/translation');
    const { useListener } = require("@web/core/utils/hooks");
    const ControlButtonsMixin = require('point_of_sale.ControlButtonsMixin');
    const NumberBuffer = require('point_of_sale.NumberBuffer');
    const Registries = require('point_of_sale.Registries');
    const SaleOrderFetcher = require('pos_sale.SaleOrderFetcher');
    const IndependentToOrderScreen = require('point_of_sale.IndependentToOrderScreen');
    const contexts = require('point_of_sale.PosContext');
    const utils = require('web.utils');
    const { Orderline } = require('point_of_sale.models');
    
    const PatchedSaleOrderManagementScreen = (SaleOrderManagementScreen) => class extends SaleOrderManagementScreen {
        async _onClickSaleOrder(event) {
            const clickedOrder = event.detail;
            // Solo mostramos la opción de facturar el pedido
            const { confirmed } = await this.showPopup('SelectionPopup', {
                title: this.env._t('¿Qué deseas hacer?'),
                list: [{id:"1", label: this.env._t("Facturar el pedido"), item: true}],
            });

            if (confirmed) {
                let currentPOSOrder = this.env.pos.get_order();
                let sale_order = await this._getSaleOrder(clickedOrder.id);
                const currentSaleOrigin = this._getSaleOrderOrigin(currentPOSOrder);
                const currentSaleOriginId = currentSaleOrigin && currentSaleOrigin.id;

                if (currentSaleOriginId) {
                    const linkedSO = await this._getSaleOrder(currentSaleOriginId);
                    if (
                        getId(linkedSO.partner_id) !== getId(sale_order.partner_id) ||
                        getId(linkedSO.partner_invoice_id) !== getId(sale_order.partner_invoice_id) ||
                        getId(linkedSO.partner_shipping_id) !== getId(sale_order.partner_shipping_id)
                    ) {
                        currentPOSOrder = this.env.pos.add_new_order();
                        this.showNotification(this.env._t("Se ha creado un nuevo pedido."));
                    }
                }

                let order_partner = this.env.pos.db.get_partner_by_id(sale_order.partner_id[0])
                if(order_partner){
                    currentPOSOrder.set_partner(order_partner);
                } else {
                    try {
                        await this.env.pos._loadPartners([sale_order.partner_id[0]]);
                    }
                    catch (_error){
                        const title = this.env._t('Error cargando el cliente');
                        const body = _.str.sprintf(this.env._t('Hubo un problema al cargar el cliente %s.'), sale_order.partner_id[1]);
                        await this.showPopup('ErrorPopup', { title, body });
                    }
                    currentPOSOrder.set_partner(this.env.pos.db.get_partner_by_id(sale_order.partner_id[0]));
                }

                let orderFiscalPos = sale_order.fiscal_position_id ? this.env.pos.fiscal_positions.find(
                    (position) => position.id === sale_order.fiscal_position_id[0]
                ) : false;
                if (orderFiscalPos){
                    currentPOSOrder.fiscal_position = orderFiscalPos;
                }
                let orderPricelist = sale_order.pricelist_id ? this.env.pos.pricelists.find(
                    (pricelist) => pricelist.id === sale_order.pricelist_id[0]
                ) : false;
                if (orderPricelist){
                    currentPOSOrder.set_pricelist(orderPricelist);
                }

                // SOLO facturar el pedido, NO down payment
                let lines = sale_order.order_line;
                let product_to_add_in_pos = lines.filter(line => !this.env.pos.db.get_product_by_id(line.product_id[0])).map(line => line.product_id[0]);
                if (product_to_add_in_pos.length){
                    const { confirmed } = await this.showPopup('ConfirmPopup', {
                        title: this.env._t('Productos no disponibles en el POS'),
                        body:
                            this.env._t(
                                'Algunos productos de la orden de venta no están disponibles en el POS. ¿Deseas importarlos?'
                            ),
                        confirmText: this.env._t('Sí'),
                        cancelText: this.env._t('No'),
                    });
                    if (confirmed){
                        await this.env.pos._addProducts(product_to_add_in_pos);
                    }
                }

                let useLoadedLots;
                for (var i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (!this.env.pos.db.get_product_by_id(line.product_id[0])){
                        continue;
                    }

                    const line_values = {
                        pos: this.env.pos,
                        order: this.env.pos.get_order(),
                        product: this.env.pos.db.get_product_by_id(line.product_id[0]),
                        description: line.product_id[1],
                        price: line.price_unit,
                        tax_ids: orderFiscalPos ? undefined : line.tax_id,
                        price_automatically_set: true,
                        price_manually_set: false,
                        sale_order_origin_id: clickedOrder,
                        sale_order_line_id: line,
                        customer_note: line.customer_note,
                    };
                    let new_line = Orderline.create({}, line_values);

                    if (
                        new_line.get_product().tracking !== 'none' &&
                        (this.env.pos.picking_type.use_create_lots || this.env.pos.picking_type.use_existing_lots) &&
                        line.lot_names.length > 0
                    ) {
                        // Preguntar una sola vez por los lotes/seriales
                        const { confirmed } =
                            useLoadedLots === undefined
                                ? await this.showPopup('ConfirmPopup', {
                                      title: this.env._t('SN/Lots Loading'),
                                      body: this.env._t(
                                          '¿Deseas cargar los SN/Lotes vinculados a la orden de venta?'
                                      ),
                                      confirmText: this.env._t('Sí'),
                                      cancelText: this.env._t('No'),
                                  })
                                : { confirmed: useLoadedLots };
                        useLoadedLots = confirmed;
                        if (useLoadedLots) {
                            new_line.setPackLotLines({
                                modifiedPackLotLines: [],
                                newPackLotLines: (line.lot_names || []).map((name) => ({ lot_name: name })),
                            });
                        }
                    }
                    new_line.setQuantityFromSOL(line);
                    new_line.set_unit_price(line.price_unit);
                    new_line.set_discount(line.discount);
                    const product = this.env.pos.db.get_product_by_id(line.product_id[0]);
                    const product_unit = product.get_unit();
                    if (product_unit && !product.get_unit().is_pos_groupable) {
                        // Agregar líneas partidas por cantidad
                        let remaining_quantity  = new_line.quantity;
                        while (!utils.float_is_zero(remaining_quantity, 6)) {
                            let splitted_line = Orderline.create({}, line_values);
                            splitted_line.set_quantity(Math.min(remaining_quantity, 1.0), true);
                            splitted_line.set_discount(line.discount);
                            remaining_quantity -= splitted_line.quantity;
                            this.env.pos.get_order().add_orderline(splitted_line);
                        }
                    }
                    else {
                        this.env.pos.get_order().add_orderline(new_line);
                    }
                }

                // ¡Listo! Cerramos la pantalla
                this.close();
            }
        }
    };

    // Parchar la pantalla
    Registries.Component.extend(require('pos_sale.SaleOrderManagementScreen'), PatchedSaleOrderManagementScreen);

    return PatchedSaleOrderManagementScreen;
});


odoo.define('bi_pos_warehouse_management.PaymentScreenWidget', function(require){
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');
    var rpc = require('web.rpc');

    const PaymentScreenWidget = (PaymentScreen) =>
        class extends PaymentScreen {

            async validateOrder(isForceValidate) {
                let self = this;
                let order = self.env.pos.get_order();
                let products = order.calculate_prod_qty();
                let pos_config = self.env.pos.config;
                let partner_id = order.get_partner();
                let location = self.env.pos.config.stock_location_id;
                let other_locations = self.env.pos.pos_custom_location;

                let res = {};
                let call_super = true;

                if (pos_config.display_stock_pos) {
                    for (const prod_id in products) {
                        await this.rpc({
                            model: 'stock.quant',
                            method: 'get_product_stock',
                            args: [partner_id, location, other_locations, parseInt(prod_id)],
                        }).then(function(output) {
                            res[prod_id] = output[1];
                        });
                    }

                    let processed_keys = {};

                    $.each(products, function(prod_id, loc_data) {
                        let product = self.env.pos.db.get_product_by_id(prod_id);
                        if (product && product.has_bom) {
                             return;
                        }
                        $.each(loc_data, function(loc_id, line_data) {
                            let key_unique = `${prod_id}_${loc_id}`;
                            if (processed_keys[key_unique]) return;
                            processed_keys[key_unique] = true;

                            let qty = line_data.qty;
                            let prd = line_data.name;
                            let ol = line_data.line;

                            if (self.env.pos.loc_by_id && self.env.pos.loc_by_id[loc_id]) {
                                let loc_name = self.env.pos.loc_by_id[loc_id]['complete_name'];
                                let loc_list = [];
                                let data = {};

                                $.each(res[prod_id] || [], function(_, v) {
                                    let id = v.location.id;
                                    if (v.quantity != 0) {
                                        loc_list.push([
                                            self.env.pos.loc_by_id[id]?.complete_name,
                                            v.quantity,
                                            id
                                        ]);
                                    }
                                    data[id] = v.quantity;
                                });

                                if (qty > (data[loc_id] || 0)) {
                                    let wrning = prd + ': required ' + qty;
                                    let odrln = order.get_orderline(ol);
                                    odrln.set_quantity(data[loc_id] || 0);
                                    call_super = false;
                                    self.showPopup('PosOutOfStock', {
                                        'title': self.env._t('Out of Stock'),
                                        'warning': self.env._t(wrning),
                                    });
                                }
                            }
                        });
                    });
                }

                if (call_super) {
                    super.validateOrder(isForceValidate);
                }
            }
        };

    Registries.Component.extend(PaymentScreen, PaymentScreenWidget);

    return PaymentScreen;
});

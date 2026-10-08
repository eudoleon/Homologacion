/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
    },
    _switchCategory(event) {
        var self = this;
        this.pos.db.sh_show_total_products = [];
        super._switchCategory(...arguments);
    },
    get productsToDisplay() {
        var self = this;
        var products = [];
        var tmpl_ids = [];
        let list = [];
        if (this.searchWord !== '') {
            list = this.pos.db.search_product_in_category(
                this.selectedCategoryId,
                this.searchWord
            );
            if (self.pos.config.sh_pos_enable_product_variants) {
                _.each(list, function (each_product, i) {
                    if (each_product.attribute_line_ids.length > 0) {
                        if (!tmpl_ids.includes(each_product.product_tmpl_id)) {
                            products.push(each_product);
                        }
                        tmpl_ids.push(each_product.product_tmpl_id);
                    } else {
                        products.push(each_product);
                    }
                });
                return products;
            } else {
                return list;
            }
        } else {
            if (self.pos.config.sh_pos_enable_product_variants) {
                let Products = [];
                if (this.pos.db.sh_show_total_products && this.pos.db.sh_show_total_products.length > 0) {
                    Products = this.pos.db.sh_show_total_products;
                } else {
                    Products = this.pos.db.get_sh_product_by_category(this.selectedCategoryId);
                    this.pos.db.sh_show_total_products = Products.slice(0, 100);
                }
                return Products.slice(0, 100).sort(function (a, b) { return a.display_name.localeCompare(b.display_name); });
            } else {
                list = this.pos.db.get_product_by_category(this.selectedCategoryId);
                return list.sort(function (a, b) { return a.display_name.localeCompare(b.display_name); });
            }
        }
    }
});

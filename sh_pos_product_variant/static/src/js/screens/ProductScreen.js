/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    async _clickProduct(event) {
        var self = this;
        this.product_variants = [];
        this.alternative_products = [];
        var alternative_ids = [];
        
        // En Odoo 17+, event ya es el producto directamente en muchos casos.
        // Verificamos si event.detail existe o si es el producto en sí.
        const product_tmpl_id = event.detail ? event.detail.product_tmpl_id : event.product_tmpl_id;
        const attribute_line_ids = event.detail ? event.detail.attribute_line_ids : event.attribute_line_ids;

        var total_var_products = self.env.pos.db.product_tmpl_by_id[product_tmpl_id];
        if (total_var_products){
            _.each(total_var_products, function (product_id) {
                var each_product = self.env.pos.db.get_product_by_id(product_id);
                if (each_product.product_tmpl_id == product_tmpl_id) {
                    self.product_variants.push(each_product);
                    if (each_product.sh_alternative_products && each_product.sh_alternative_products.length > 0) {
                        for (var i = 0; i < each_product.sh_alternative_products.length; i++){
                            var each = each_product.sh_alternative_products[i];
                            var product = self.env.pos.db.get_product_by_id(each);
                            if (!alternative_ids.includes(each)) {
                                if (self.env.pos.config.sh_pos_display_alternative_products) {
                                    self.alternative_products.push(product);
                                }
                            }
                            alternative_ids.push(each);
                        }
                    }
                }
            });
        }
        
        if (this.product_variants.length > 1) {
            if (!self.env.pos.config.sh_pos_variants_group_by_attribute && self.env.pos.config.sh_pos_enable_product_variants) {
                let morevariant_class = '';
                if (this.product_variants.length > 6 && this.product_variants.length < 15) {
                    morevariant_class = 'sh_lessthan_8_variants';
                } else if (this.product_variants.length > 15) {
                    morevariant_class = ' sh_morethan_15_variants';
                }
                
                self.env.services.popup.add("variantPopup", {
                    'title': 'Product Variants',
                    'morevariant_class': morevariant_class,
                    'product_variants': this.product_variants,
                    'alternative_products': this.alternative_products
                });
            }
            else if (self.env.pos.config.sh_pos_variants_group_by_attribute && self.env.pos.config.sh_pos_enable_product_variants) {
                self.Attribute_names = [];
                _.each(attribute_line_ids, function (each_attribute) {
                    self.Attribute_names.push(self.env.pos.db.product_temlate_attribute_line_by_id[each_attribute]);
                });
                if (this.Attribute_names.length > 0) {
                    self.env.services.popup.add("variantPopup", {
                        'title': 'Product Variants',
                        'attributes_name': this.Attribute_names,
                        'alternative_products': this.alternative_products
                    });
                } else {
                    super._clickProduct(...arguments);
                }
            }
            else {
                super._clickProduct(...arguments);
            }
        } else {
            if (this.alternative_products.length > 0 && self.env.pos.config.sh_pos_display_alternative_products && self.env.pos.config.sh_pos_variants_group_by_attribute) {
                self.env.services.popup.add("variantPopup", { 'title': 'Alternative Product', attributes_name: [], alternative_products: this.alternative_products });
            }
            else if (this.alternative_products.length > 0 && self.env.pos.config.sh_pos_display_alternative_products && !self.env.pos.config.sh_pos_variants_group_by_attribute) {
                self.env.services.popup.add("variantPopup", { 'title': 'Alternative Product', product_variants: [], alternative_products: this.alternative_products });
            }
            super._clickProduct(...arguments);
        }
    }
});

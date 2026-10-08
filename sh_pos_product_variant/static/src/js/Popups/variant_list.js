/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

export class VariantProductItem extends Component {
    setup() {
        this.pos = usePos();
    }
    
    spaceClickProduct(event) {
        if (event.which === 32) {
            this.props.onClick(this.props.product);
        }
    }
    get imageUrl() {
        const product = this.props.product;
        return `/web/image?model=product.product&field=image_128&id=${product.id}&write_date=${product.write_date}&unique=1`;
    }
    get pricelist() {
        const current_order = this.pos.get_order();
        if (current_order) {
            return current_order.pricelist;
        }
        return this.pos.default_pricelist;
    }
    get price() {
        const formattedUnitPrice = this.pos.env.utils.formatCurrency(
            this.props.product.get_price(this.pricelist, 1)
        );
        if (this.props.product.to_weight) {
            return `${formattedUnitPrice}/${this.pos.units_by_id[this.props.product.uom_id[0]].name}`;
        } else {
            return formattedUnitPrice;
        }
    }
}
VariantProductItem.template = 'sh_pos_product_variant.VariantProductItem';

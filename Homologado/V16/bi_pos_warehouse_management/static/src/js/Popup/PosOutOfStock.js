odoo.define('bi_pos_warehouse_management.PosOutOfStock', function(require) {
	'use strict';


	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	const Registries = require('point_of_sale.Registries');
	
	class PosOutOfStock extends AbstractAwaitablePopup {
		setup() {
			super.setup();
			
		}

		cancel() {
			this.showScreen('ProductScreen');
			this.env.posbus.trigger('close-popup', {
                popupId: this.props.id });
        
		}

		Ok() {
			this.showScreen('ProductScreen');
			this.env.posbus.trigger('close-popup', {
                popupId: this.props.id });
        
		}

	}

	PosOutOfStock.template = 'PosOutOfStock';
	PosOutOfStock.defaultProps = {
		confirmText: 'Okay',
		cancelText: 'Cancel',
		title: 'Out of Stock',
		body: '',
	};
	Registries.Component.add(PosOutOfStock);

	return PosOutOfStock;
});

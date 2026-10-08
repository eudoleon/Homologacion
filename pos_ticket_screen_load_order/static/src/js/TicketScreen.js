odoo.define('pos_ticket_screen_load_order.TicketScreen', function(require) {
    'use strict';

    const TicketScreen = require('point_of_sale.TicketScreen');
    const Registries = require('point_of_sale.Registries');
    const NumberBuffer = require('point_of_sale.NumberBuffer');
    const core = require('web.core');
    const _t = core._t;

    const LoadOrderTicketScreen = TicketScreen => class extends TicketScreen {
        setup() {
            super.setup();
        }

        get isOrderSynced() {
            return this.getSelectedSyncedOrder()?.locked;
        }

        async _onFilterSelected(event) {
            this._state.ui.filter = event.detail.filter;
            if (this._state.ui.filter == "ACTIVE_ORDERS" || this._state.ui.filter === null) {
                this._state.ui.selectedOrder = this.pos.get_order();
            }
            if (this._state.ui.filter == "SYNCED") {
                await this._fetchSyncedOrders();
            }
        }

        _onClickOrder({ detail: selectedOrder }) {
            if (!selectedOrder || selectedOrder.locked) {
                this._state.ui.selectedSyncedOrderId = selectedOrder.backendId;
                if (!this.getSelectedOrderlineId()) {
                    // Automatically select the first orderline of the selected order.
                    const firstLine = selectedOrder.get_orderlines()[0];
                    if (firstLine) {
                        this._state.ui.selectedOrderlineIds[selectedOrder.backendId] = firstLine.id;
                    }
                }
                NumberBuffer.reset();
            } else {
                this._state.ui.selectedOrder = selectedOrder
            }
        }

        _setOrder(order) {
            if (order){
                this.env.pos.set_order(order);
                this.close();
            }
        }

        getSelectedSyncedOrder() {
            if (this._state.ui.filter == 'SYNCED') {
                return this._state.syncedOrders.cache[this._state.ui.selectedSyncedOrderId];
            } else {
                return this._state.ui.selectedOrder;
            }
        }

        async _onFilterSelected(event) {
            this._state.ui.filter = event.detail.filter;
            if (this._state.ui.filter == "ACTIVE_ORDERS" || this._state.ui.filter === null) {
                this._state.ui.selectedOrder = this.env.pos.get_order();
            }
            if (this._state.ui.filter == "SYNCED") {
                await this._fetchSyncedOrders();
            }
        
        }

        isHighlighted(order) {
            const selectedOrder = this.getSelectedSyncedOrder();

            return selectedOrder
                ? (order.backendId && order.backendId == selectedOrder.backendId) ||
                      order.uid === selectedOrder.uid
                : false;
        }
    };

    Registries.Component.extend(TicketScreen, LoadOrderTicketScreen);
    return TicketScreen;
});
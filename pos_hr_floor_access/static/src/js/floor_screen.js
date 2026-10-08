/** @odoo-module **/

import { FloorScreen } from "@pos_restaurant/app/floor_screen/floor_screen";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(FloorScreen.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            this._checkAndAdjustActiveFloor();
        });
    },

    /**
     * Retorna únicamente los pisos permitidos para el empleado activo actual.
     */
    get floors() {
        if (this.pos && typeof this.pos.getAllowedFloors === "function") {
            return this.pos.getAllowedFloors();
        }
        return super.floors || [];
    },

    /**
     * Retorna el piso activo asegurando que pertenezca a los pisos autorizados.
     */
    get activeFloor() {
        const active = super.activeFloor;
        const allowed = this.floors;
        if (allowed && allowed.length > 0) {
            if (!active || !allowed.some((f) => f.id === active.id)) {
                return allowed[0];
            }
        }
        return active;
    },

    _checkAndAdjustActiveFloor() {
        const allowed = this.floors;
        const current = this.pos.selectedFloor || this.pos.currentFloor || super.activeFloor;
        if (allowed && allowed.length > 0) {
            if (!current || !allowed.some((f) => f.id === current.id)) {
                if (typeof this.selectFloor === "function") {
                    this.selectFloor(allowed[0]);
                } else if (typeof this.pos.set_floor === "function") {
                    this.pos.set_floor(allowed[0]);
                } else {
                    this.pos.selectedFloor = allowed[0];
                }
            }
        }
    },

    selectFloor(floor) {
        const allowed = this.floors;
        if (allowed && allowed.length > 0 && !allowed.some((f) => f.id === floor.id)) {
            console.warn("[pos_hr_floor_access] Intento de seleccionar piso no autorizado:", floor.name);
            return;
        }
        return super.selectFloor(...arguments);
    },
});

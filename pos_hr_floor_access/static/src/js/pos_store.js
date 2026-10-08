/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /**
     * Obtiene los pisos autorizados para el empleado proporcionado o el cajero activo actual.
     * @param {Object|null} employee 
     * @returns {Array} Lista de pisos permitidos (restaurant.floor)
     */
    getAllowedFloors(employee = null) {
        const config = this.config;
        const allFloors = (this.models && this.models["restaurant.floor"])
            ? (typeof this.models["restaurant.floor"].getAll === "function"
                ? this.models["restaurant.floor"].getAll()
                : (Array.isArray(this.models["restaurant.floor"]) ? this.models["restaurant.floor"] : []))
            : (this.floors || (this.config && this.config.floor_ids) || []);

        // Si no está activa la restricción en la configuración del POS, permitir todos los pisos
        if (!config || config.restrict_floors_by_employee === false) {
            return allFloors;
        }

        const emp = employee || (typeof this.get_cashier === "function" ? this.get_cashier() : null) || this.cashier || this.selectedEmployee;
        if (!emp) {
            return allFloors;
        }

        // Si el empleado tiene permiso explícito de todos los pisos o es administrador
        if (emp.pos_all_floors_access || emp.pos_floor_access_type === "all" || emp.role === "manager" || emp.is_manager) {
            return allFloors;
        }

        // Obtener IDs de pisos asignados en la ficha del empleado
        const empFloorIds = Array.isArray(emp.pos_floor_ids)
            ? emp.pos_floor_ids.map((f) => (typeof f === "object" ? f.id : f))
            : [];
        const empId = emp.id;

        // Filtrar los pisos permitidos
        const allowed = allFloors.filter((floor) => {
            if (empFloorIds.includes(floor.id)) {
                return true;
            }
            const floorEmpIds = Array.isArray(floor.employee_ids)
                ? floor.employee_ids.map((e) => (typeof e === "object" ? e.id : e))
                : [];
            if (floorEmpIds.includes(empId)) {
                return true;
            }
            return false;
        });

        return allowed;
    },

    async set_cashier(employee) {
        const res = await super.set_cashier(...arguments);
        this._handleCashierFloorAdjustment();
        return res;
    },

    async setCashier(employee) {
        const res = super.setCashier ? await super.setCashier(...arguments) : null;
        this._handleCashierFloorAdjustment();
        return res;
    },

    _handleCashierFloorAdjustment() {
        try {
            if (!this.config?.module_pos_restaurant) return;
            const allowed = this.getAllowedFloors();
            const currentFloor = this.selectedFloor || this.currentFloor || (this.table ? this.table.floor : null);

            if (currentFloor && allowed.length > 0 && !allowed.some((f) => f.id === currentFloor.id)) {
                if (typeof this.set_floor === "function") {
                    this.set_floor(allowed[0]);
                } else if (typeof this.setFloor === "function") {
                    this.setFloor(allowed[0]);
                } else {
                    this.selectedFloor = allowed[0];
                    this.currentFloor = allowed[0];
                }
            }
        } catch (e) {
            console.warn("[pos_hr_floor_access] Error al ajustar piso al cambiar de cajero:", e);
        }
    },
});

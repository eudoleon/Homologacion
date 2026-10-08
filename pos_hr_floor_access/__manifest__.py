# -*- coding: utf-8 -*-
{
    "name": "POS Floor Access by Employee | Restricción de Pisos por Empleado",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Restringe y asigna el acceso a pisos y mesas del restaurante por empleado en el Punto de Venta (Odoo 19)",
    "description": """
POS Floor Access by Employee (Odoo 19)
======================================
Este módulo permite gestionar y limitar qué pisos (restaurant.floor) puede ver y operar cada empleado (hr.employee) en el Punto de Venta.

Características principales:
----------------------------
* Asignación de pisos permitidos directamente en la ficha del empleado (hr.employee).
* Asignación de empleados autorizados desde la vista de pisos (restaurant.floor).
* Opción de 'Acceso a Todos los Pisos' para gerentes o personal con acceso total.
* Filtro dinámico en tiempo real en la pantalla de pisos del TPV (FloorScreen).
* Reubicación automática al piso autorizado al cambiar de cajero/mesero.
* Opción de activación/desactivación global en los ajustes del TPV.
    """,
    "author": "Custom",
    "depends": [
        "base",
        "point_of_sale",
        "pos_restaurant",
        "pos_hr",
        "hr",
    ],
    "data": [
        "views/hr_employee_views.xml",
        "views/restaurant_floor_views.xml",
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_hr_floor_access/static/src/css/pos_floor_access.css",
            "pos_hr_floor_access/static/src/js/pos_store.js",
            "pos_hr_floor_access/static/src/js/floor_screen.js",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": False,
}

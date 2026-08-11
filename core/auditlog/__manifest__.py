# -*- coding: utf-8 -*-
# Migrado a Odoo 19.0 - Mantener compatibilidad con versiones anteriores
# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Audit Log",
    "version": "19.0.1.0.0",
    "author": "Contables AG",
    "license": "AGPL-3",
    "website": "https://www.contablesag.com",
    "category": "Tools",
    "depends": ["base"],
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/auditlog_view.xml",
        # "views/http_session_view.xml",
        # "views/http_request_view.xml",
        "views/user_audit_menus.xml",
    ],
    "application": True,
    "installable": True,
}

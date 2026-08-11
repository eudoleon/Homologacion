# -*- coding: utf-8 -*-
# Migrado a Odoo 19.0 - Mantener compatibilidad con versiones anteriores
# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2.extensions import AsIs

from odoo import api, fields, models
from odoo.http import request


class AuditlogHTTPRequest(models.Model):
    _name = "auditlog.http.request"
    _description = "Auditlog - HTTP request log"
    _order = "create_date DESC"

    display_name = fields.Char("Name", compute="_compute_display_name", store=True)
    name = fields.Char("Path")
    root_url = fields.Char("Root URL")
    user_id = fields.Many2one("res.users", string="User")
    http_session_id = fields.Many2one(
        "auditlog.http.session", string="Session", index=True
    )
    user_context = fields.Char("Context")
    log_ids = fields.One2many("auditlog.log", "http_request_id", string="Logs")

    @api.depends("create_date", "name")
    def _compute_display_name(self):
        for httprequest in self:
            # Odoo 19: fields.Datetime.from_string() deprecado, usar directamente create_date
            # create_date = fields.Datetime.from_string(httprequest.create_date)
            tz_create_date = fields.Datetime.context_timestamp(httprequest, httprequest.create_date)
            httprequest.display_name = "{} ({})".format(
                httprequest.name or "?", fields.Datetime.to_string(tz_create_date)
            )

    def name_get(self):
        return [(request.id, request.display_name) for request in self]

    @api.model
    def current_http_request(self):
        """Create a log corresponding to the current HTTP request, and returns
        its ID. This method can be called several times during the
        HTTP query/response cycle, it will only log the request on the
        first call.
        If no HTTP request is available, returns `False`.
        """
        if not request:
            return False
        http_session_model = self.env["auditlog.http.session"]
        httprequest = request.httprequest
        if httprequest:
            cache_key = "auditlog_http_request_id"
            cached_id = False
            if hasattr(httprequest, "environ"):
                cached_id = httprequest.environ.get(cache_key)
            if not cached_id:
                cached_id = getattr(httprequest, cache_key, False)
            if cached_id:
                # Verify existence. Could have been rolled back after a
                # concurrency error
                self.env.cr.execute(
                    "SELECT id FROM %s WHERE id = %s",
                    (AsIs(self._table), cached_id),
                )
                if self.env.cr.fetchone():
                    return cached_id
            vals = {
                "name": httprequest.path,
                "root_url": httprequest.url_root,
                "user_id": request.env.uid,
                "http_session_id": http_session_model.current_http_session(),
                "user_context": str(request.env.context),
            }
            new_id = self.create(vals).id
            if hasattr(httprequest, "environ"):
                httprequest.environ[cache_key] = new_id
            else:
                try:
                    setattr(httprequest, cache_key, new_id)
                except Exception:
                    pass
            return new_id
        return False

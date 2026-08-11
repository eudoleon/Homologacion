# -*- coding: utf-8 -*-
# Migrado a Odoo 19.0 - Mantener compatibilidad con versiones anteriores
# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.http import request


class AuditlogtHTTPSession(models.Model):
    _name = "auditlog.http.session"
    _description = "Auditlog - HTTP User session log"
    _order = "create_date DESC"

    display_name = fields.Char("Name", compute="_compute_display_name", store=True)
    name = fields.Char("Session ID", index=True)
    user_id = fields.Many2one("res.users", string="User", index=True)
    http_request_ids = fields.One2many(
        "auditlog.http.request", "http_session_id", string="HTTP Requests"
    )

    @api.depends("create_date", "user_id")
    def _compute_display_name(self):
        for httpsession in self:
            # Odoo 19: fields.Datetime.from_string() deprecado, usar directamente create_date
            # create_date = fields.Datetime.from_string(httpsession.create_date)
            tz_create_date = fields.Datetime.context_timestamp(httpsession, httpsession.create_date)
            httpsession.display_name = "{} ({})".format(
                httpsession.user_id and httpsession.user_id.name or "?",
                fields.Datetime.to_string(tz_create_date),
            )

    def name_get(self):
        return [(session.id, session.display_name) for session in self]

    @api.model
    def current_http_session(self):
        """Create a log corresponding to the current HTTP user session, and
        returns its ID. This method can be called several times during the
        HTTP query/response cycle, it will only log the user session on the
        first call.
        If no HTTP user session is available, returns `False`.
        """
        if not request:
            return False
        httpsession = request.session
        if httpsession:
            cache_key = "auditlog_http_session_id"

            # Odoo 19 may use a Session object that does not allow custom attrs.
            # Read/write cache in the session mapping when possible.
            cached_id = getattr(httpsession, cache_key, False)
            if not cached_id and hasattr(httpsession, "get"):
                cached_id = httpsession.get(cache_key)
            if cached_id:
                return cached_id

            existing_session = self.search(
                [("name", "=", httpsession.sid), ("user_id", "=", request.env.uid)], limit=1
            )
            if existing_session:
                return existing_session.id
            vals = {"name": httpsession.sid, "user_id": request.env.uid}
            new_id = self.create(vals).id
            try:
                setattr(httpsession, cache_key, new_id)
            except Exception:
                if hasattr(httpsession, "__setitem__"):
                    httpsession[cache_key] = new_id
            return new_id
        return False

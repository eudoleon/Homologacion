# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request
from datetime import datetime


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _authenticate(cls, endpoint):
        res = super(IrHttp, cls)._authenticate(endpoint=endpoint)
        # Only track activity if user is logged in and valid session ID exists
        if request.session.uid and getattr(request.session, 'sid', None):
            sid = request.session.sid
            activity = (
                request.env["recent.activity"]
                .sudo()
                .search([("access_session_id", "=", sid)], limit=1)
            )
            if not activity:
                request.env["recent.activity"].sudo().create(
                    {
                        "access_user_id": request.session.uid,
                        "access_login_date": datetime.now(),
                        "access_duration": "Logged in",
                        "access_status": "active",
                        "access_session_id": sid,
                    }
                )
            else:
                closed = (
                    request.env["recent.activity"]
                    .sudo()
                    .search(
                        [
                            ("access_session_id", "=", sid),
                            ("access_status", "=", "close"),
                        ],
                        limit=1,
                    )
                )
                if closed:
                    request.session.logout(keep_db=True)
        return res

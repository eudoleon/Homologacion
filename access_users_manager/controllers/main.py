# -*- coding: utf-8 -*-

import logging
from odoo.exceptions import UserError

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
import odoo
import odoo.modules.registry
from odoo import http
from odoo import _
from odoo.addons.web.controllers.utils import (
    ensure_db,
    _get_login_redirect_url,
    is_user_internal,
)
from odoo.addons.web.controllers.home import Home
from datetime import datetime
from odoo.addons.web.controllers.session import Session
from odoo.http import request
from dateutil.relativedelta import relativedelta
import json, werkzeug

_logger = logging.getLogger(__name__)

SIGN_UP_REQUEST_PARAMS = {
    "db",
    "login",
    "debug",
    "token",
    "message",
    "error",
    "scope",
    "mode",
    "redirect",
    "redirect_hostname",
    "email",
    "name",
    "partner_id",
    "password",
    "confirm_password",
    "city",
    "country_id",
    "lang",
    "signup_email",
}
LOGIN_SUCCESSFUL_PARAMS = set()


class accessSessionWebsite(Session):

    @http.route(
        "/web/session/logout",
        type="http",
        auth="none",
        website=True,
        multilang=False,
        sitemap=False,
    )
    def logout(self, redirect="/web"):
        # Use sudo() to bypass permission checks during logout
        activity = (
            request.env["recent.activity"]
            .sudo()
            .search([("access_session_id", "=", request.session.sid)])
        )
        if activity:
            activity.access_action_logout()
        return super().logout(redirect=redirect)


class Home(Home):
    @http.route(['/odoo', '/odoo/<path:subpath>'], type='http', auth="public")
    def odoo_redirect(self, subpath=None, **kw):
        ensure_db()
        if request.session.uid:
            user_id = request.env['res.users'].sudo().browse(request.session.uid)
            if user_id.access_is_passwd_expired:
                request.session.logout()
            company_id = request.httprequest.cookies.get('cids') if request.httprequest.cookies.get('cids') else False
            if kw.get('debug') and kw.get('debug') != "0":
                if company_id:
                    lst = [int(x) for x in request.httprequest.cookies.get('cids', '').replace('%2C', ',').replace('-', ',').split(',')]
                    profile_management = request.env['user.management'].sudo().search(
                        [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_company_ids', 'in', lst),
                         ('access_user_ids', 'in', user_id.id)], limit=1)
                else:
                    profile_management = request.env['user.management'].sudo().search(
                        [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_user_ids', 'in', user_id.id)], limit=1)
                if profile_management:
                    return request.redirect('/web?debug=0')
        
        return self.web_client(**kw)

    @http.route('/web/login', type='http', auth="public")
    def web_login(self, *args, **kw):
        if request.httprequest.method == "POST" and request.params.get("login"):
            user = (
                request.env["res.users"]
                .sudo()
                .search([("login", "=", request.params["login"])], limit=1)
            )
            if (
                user
                and not user.has_group("base.group_system")
                and user.access_is_passwd_expired
            ):
                response = super(Home, self).web_login(*args, **kw)
                if hasattr(response, "qcontext") and isinstance(response.qcontext, dict):
                    response.qcontext["error"] = _("Password Expired")
                return response

        return super(Home, self).web_login(*args, **kw)


class accessAuthSignupHomeInherit(AuthSignupHome):

    @http.route(
        "/web/reset_password/direct",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        csrf=False,
    )
    def access_auth_reset_password(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()
        response = request.render(
            "access_users_manager.reset_password_direct", qcontext
        )
        return response

    @http.route(
        "/web/reset_password/submit",
        type="http",
        methods=["POST"],
        auth="public",
        website=True,
        csrf=False,
    )
    def access_change_password(self, *args, **kw):
        values = {}
        if kw.get("confirm_new_password") == kw.get("new_password"):
            try:
                db_name = getattr(request, 'db', None) or request.session.db
                uid = request.env["res.users"].sudo()._login(
                    db_name,
                    kw.get("user_name"),
                    kw.get("old_password")
                )
                user = request.env["res.users"].sudo().browse(uid)
                vals = {
                    "access_password_update": datetime.now(),
                    "password": kw["confirm_new_password"],
                    "access_is_passwd_expired": False,
                }
                expiry_month = (
                    request.env["ir.config_parameter"]
                    .sudo()
                    .get_param("access_users_manager.password_expire_in_days")
                )
                if expiry_month:
                    expire_date = user.access_password_update + relativedelta(
                        days=int(expiry_month)
                    )
                    vals["access_password_expire_date"] = expire_date
                user.sudo().write(vals)
                return request.redirect("/web/login")

            except Exception:
                values["error"] = _("Login or Password Is Incorrect")
                return request.render(
                    "access_users_manager.reset_password_direct", values
                )
        else:
            values["error"] = _("Password Not Match")
            return request.render("access_users_manager.reset_password_direct", values)

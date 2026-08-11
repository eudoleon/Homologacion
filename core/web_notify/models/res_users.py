from odoo import _, api, exceptions, fields, models
from odoo.addons.bus.models.bus import channel_with_db, json_dump
from odoo.addons.web.controllers.utils import clean_action

DEFAULT_MESSAGE = "Default message"

SUCCESS = "success"
DANGER = "danger"
WARNING = "warning"
INFO = "info"
DEFAULT = "default"


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.depends("create_date")
    def _compute_channel_names(self):
        for record in self:
            channel_name = json_dump(channel_with_db(self.env.cr.dbname, record.partner_id))
            record.notify_success_channel_name = channel_name
            record.notify_danger_channel_name = channel_name
            record.notify_warning_channel_name = channel_name
            record.notify_info_channel_name = channel_name
            record.notify_default_channel_name = channel_name

    notify_success_channel_name = fields.Char(compute="_compute_channel_names")
    notify_danger_channel_name = fields.Char(compute="_compute_channel_names")
    notify_warning_channel_name = fields.Char(compute="_compute_channel_names")
    notify_info_channel_name = fields.Char(compute="_compute_channel_names")
    notify_default_channel_name = fields.Char(compute="_compute_channel_names")

    def notify_success(
        self,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        action=None,
        html=False,
        params=None,
    ):
        self._notify_channel(
            SUCCESS,
            message,
            title or _("Success"),
            sticky,
            target,
            html,
            action,
            params,
        )

    def notify_danger(
        self,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        html=False,
        action=None,
        params=None,
    ):
        self._notify_channel(
            DANGER,
            message,
            title or _("Danger"),
            sticky,
            target,
            html,
            action,
            params,
        )

    def notify_warning(
        self,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        html=False,
        action=None,
        params=None,
    ):
        self._notify_channel(
            WARNING,
            message,
            title or _("Warning"),
            sticky,
            target,
            html,
            action,
            params,
        )

    def notify_info(
        self,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        html=False,
        action=None,
        params=None,
    ):
        self._notify_channel(
            INFO,
            message,
            title or _("Information"),
            sticky,
            target,
            html,
            action,
            params,
        )

    def notify_default(
        self,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        html=False,
        action=None,
        params=None,
    ):
        self._notify_channel(
            DEFAULT,
            message,
            title or _("Default"),
            sticky,
            target,
            html,
            action,
            params,
        )

    def _notify_channel(
        self,
        type_message=DEFAULT,
        message=DEFAULT_MESSAGE,
        title=None,
        sticky=False,
        target=None,
        html=False,
        action=None,
        params=None,
    ):
        if not (self.env.user._is_admin() or self.env.su) and any(
            user.id != self.env.uid for user in self
        ):
            raise exceptions.UserError(
                _("Sending a notification to another user is forbidden.")
            )

        if not target:
            target = self.partner_id

        if action:
            action = clean_action(action, self.env)

        bus_message = {
            "type": type_message,
            "message": message,
            "title": title,
            "sticky": sticky,
            "html": html,
            "action": action,
            "params": dict(params or []),
        }
        for partner in target:
            partner._bus_send("web_notify", bus_message)
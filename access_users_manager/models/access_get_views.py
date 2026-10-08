# -*- coding: utf-8 -*-

from odoo import api, models
from lxml import etree
import ast
from odoo.http import request


class BaseModel(models.AbstractModel):
    _inherit = "base"

    def _get_company_ids_safe(self):
        """Return active company ids even when there is no bound HTTP request."""
        company_ids = []
        try:
            http_request = request.httprequest
            if http_request:
                cids = http_request.cookies.get("cids", "")
                company_ids = [int(x) for x in cids.replace("%2C", ",").replace("-", ",").split(",") if x.isdigit()]
        except Exception:
            company_ids = []

        if not company_ids:
            company_ids = self.env.companies.ids or [self.env.company.id]
        return company_ids

    # @api.model
    # def get_view(self, view_id=None, view_type="form", **options):
    #     # TEMPORARILY DISABLED: Return without any access restrictions
    #     return super().get_view(view_id, view_type, **options)

    #     # Bypass all access restrictions for system administrators
    #     if self.env.user.has_group("base.group_system"):
    #         return super().get_view(view_id, view_type, **options)

    #     view_ref = super().get_view(view_id, view_type, **options)
    #     doc = etree.XML(view_ref["arch"])
    #     cids = request.httprequest.cookies.get("cids", "")
    #     lst = [int(x) for x in cids.replace("%2C", ",").replace("-", ",").split(",") if x.isdigit()]

    #     if view_type == "form":
    #         # remove external link
    #         hide_field_access = (
    #             self.env["field.access"]
    #             .sudo()
    #             .search(
    #                 [
    #                     (
    #                         "access_user_manager_id.access_user_ids",
    #                         "in",
    #                         self.env.user.id,
    #                     ),
    #                     ("access_user_manager_id.active", "=", True),
    #                     ("access_model_id.model", "=", view_ref["model"]),
    #                     ("access_field_external_link", "=", True),
    #                     ("access_user_manager_id.access_company_ids", "in", lst),
    #                 ]
    #             )
    #         )
    #         if hide_field_access:
    #             for field in hide_field_access.mapped("access_field_id"):
    #                 if field.ttype in ["many2many", "many2one"]:
    #                     for field_ele in doc.xpath(f"//field[@name='{field.name}']"):
    #                         options = field_ele.attrib.get("options", "{}")
    #                         options = ast.literal_eval(options)
    #                         options.update(
    #                             {
    #                                 "no_create": True,
    #                                 "no_create_edit": True,
    #                                 "no_open": True,
    #                             }
    #                         )
    #                         field_ele.attrib["options"] = str(options)
    #             view_ref["arch"] = etree.tostring(doc, encoding="unicode")

    #         # Hide All Chatter
    #         hide_chatter = (
    #             self.env["user.management"]
    #             .sudo()
    #             .search(
    #                 [
    #                     ("active", "=", True),
    #                     ("access_user_ids", "in", self.env.user.id),
    #                     ("access_company_ids", "in", lst),
    #                     ("access_hide_chatter", "=", True),
    #                 ],
    #                 limit=1,
    #             )
    #         )
    #         if hide_chatter:
    #             for div in doc.xpath("//div[@class='oe_chatter']"):
    #                 div.getparent().remove(div)
    #             view_ref["arch"] = etree.tostring(doc, encoding="unicode")

    #     if view_type == "kanban":
    #         hide_button_ids = (
    #             self.env["button.tab.access"]
    #             .sudo()
    #             .search(
    #                 [
    #                     ("access_model_id.model", "=", view_ref["model"]),
    #                     ("access_user_manager_id.active", "=", True),
    #                     ("access_user_manager_id.access_user_ids", "in", self._uid),
    #                     ("access_user_manager_id.access_company_ids", "in", lst),
    #                 ]
    #             )
    #         )
    #         for button in hide_button_ids:
    #             for btn in button.access_hide_button_ids:
    #                 for xpath_expr in [
    #                     f"//a[@name='{btn.access_name}']",
    #                     f"//button[@name='{btn.access_name}']",
    #                     f"//object[@name='{btn.access_name}']",
    #                 ]:
    #                     for ele in doc.xpath(xpath_expr):
    #                         ele.attrib.update({"class": "d-none"})

    #             # ✅ Validar existencia antes de acceder
    #             if hasattr(button, "access_kanban_button_ids"):
    #                 for link in button.access_kanban_button_ids:
    #                     if link.access_button_type == "edit":
    #                         element = doc.xpath("//a[@type='edit']")
    #                     elif link.access_button_type == "set_cover":
    #                         element = doc.xpath("//a[@type='set_cover']")
    #                     else:
    #                         element = doc.xpath(f"//a[@name='{link.access_name}']")
    #                     for ele in element:
    #                         if (
    #                             not ele.text or ele.text.startswith("\n")
    #                         ) or ele.text == link.access_tab_button_string:
    #                             ele.attrib.update({"class": "d-none"})

    #                 for link in button.access_kanban_button_ids:
    #                     for ele in doc.xpath(f"//button[@name='{link.access_name}']"):
    #                         ele.attrib.update({"class": "d-none"})

    #         view_ref["arch"] = etree.tostring(doc, encoding="unicode")

    #     # Make whole system readonly
    #     readonly_access_id = (
    #         self.env["user.management"]
    #         .sudo()
    #         .search(
    #             [
    #                 ("active", "=", True),
    #                 ("access_user_ids", "in", self.env.user.id),
    #                 ("access_readonly", "=", True),
    #                 ("access_company_ids", "in", lst),
    #             ]
    #         )
    #     )
    #     if readonly_access_id:
    #         doc.attrib.update(
    #             {
    #                 "create": "false",
    #                 "delete": "false",
    #                 "edit": "false",
    #                 "duplicate": "false",
    #             }
    #         )
    #         view_ref["arch"] = etree.tostring(doc, encoding="unicode").replace(
    #             "&amp;quot;", "&quot;"
    #         )
    #     else:
    #         change_model_access = (
    #             self.env["model.access"]
    #             .sudo()
    #             .search(
    #                 [
    #                     (
    #                         "access_user_manager_id.access_user_ids",
    #                         "in",
    #                         self.env.user.id,
    #                     ),
    #                     ("access_user_manager_id.active", "=", True),
    #                     ("access_model_id.model", "=", view_ref["model"]),
    #                     ("access_user_manager_id.access_company_ids", "in", lst),
    #                 ]
    #             )
    #         )
    #         if change_model_access:
    #             create, edit, delete, duplicate = "true", "true", "true", "true"
    #             for access in change_model_access:
    #                 if access.access_hide_create:
    #                     create = "false"
    #                 if access.access_hide_edit:
    #                     edit = "false"
    #                 if access.access_hide_delete:
    #                     delete = "false"
    #                 if access.access_hide_duplicate:
    #                     duplicate = "false"
    #                 if access.access_model_readonly:
    #                     create = delete = edit = "false"
    #             doc.attrib.update(
    #                 {
    #                     "create": create,
    #                     "delete": delete,
    #                     "edit": edit,
    #                     "duplicate": duplicate,
    #                 }
    #             )
    #             view_ref["arch"] = etree.tostring(doc, encoding="unicode")

    #     # --- SAFETY: keep Odoo's get_view() payload shape intact ---
    #     # OWL expects: result['models'][model_name] -> dict with key 'fields' (a dict)
    #     # A buggy post-process (or another addon) may accidentally replace
    #     # result['models'][model_name] with a tuple/list of field names, which
    #     # makes `models[...].fields[...]` crash on the client.
    #     models_payload = view_ref.get("models")
    #     if models_payload and not isinstance(models_payload, dict):
    #         # Worst-case fallback: rebuild minimal structure for current model.
    #         try:
    #             view_ref["models"] = {
    #                 view_ref.get("model"): {"fields": self.env[view_ref.get("model")].fields_get()}
    #             }
    #         except Exception:
    #             # If even that fails, don't block the request; returning the
    #             # original payload is better than raising here.
    #             pass
    #     elif isinstance(models_payload, dict):
    #         for model_name, model_info in list(models_payload.items()):
    #             # If model_info is not a dict, treat it as a list/tuple of field names.
    #             if not isinstance(model_info, dict):
    #                 field_names = None
    #                 if isinstance(model_info, (list, tuple, set)):
    #                     field_names = list(model_info)
    #                 try:
    #                     fields_def = self.env[model_name].fields_get(field_names)
    #                 except Exception:
    #                     try:
    #                         fields_def = self.env[model_name].fields_get()
    #                     except Exception:
    #                         fields_def = {}
    #                 models_payload[model_name] = {"fields": fields_def}
    #                 continue

    #             fields_info = model_info.get("fields")
    #             if fields_info is None:
    #                 continue
    #             if isinstance(fields_info, (list, tuple, set)):
    #                 # fields was replaced by an iterable of names.
    #                 try:
    #                     model_info["fields"] = self.env[model_name].fields_get(list(fields_info))
    #                 except Exception:
    #                     try:
    #                         model_info["fields"] = self.env[model_name].fields_get()
    #                     except Exception:
    #                         model_info["fields"] = {}
    #             elif not isinstance(fields_info, dict):
    #                 # Unknown shape; rebuild.
    #                 try:
    #                     model_info["fields"] = self.env[model_name].fields_get()
    #                 except Exception:
    #                     model_info["fields"] = {}

    #     return view_ref

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        # 1. Bypass para administradores: En v19 el super() es más estricto con los argumentos
        if self.env.user.has_group("base.group_system"):
            return super().get_view(view_id=view_id, view_type=view_type, **options)

        # 2. Obtener la vista base
        view_ref = super().get_view(view_id=view_id, view_type=view_type, **options)
        
        # Parsear el XML para modificaciones dinámicas
        doc = etree.XML(view_ref["arch"])
        lst = self._get_company_ids_safe()
        model_name = view_ref.get("model")

        # --- LÓGICA DE FORMULARIO: Ocultar enlaces externos y Chatter ---
        if view_type == "form":
            hide_field_access = self.env["field.access"].sudo().search([
                ("access_user_manager_id.access_user_ids", "in", self.env.user.id),
                ("access_user_manager_id.active", "=", True),
                ("access_model_id.model", "=", model_name),
                ("access_field_external_link", "=", True),
                ("access_user_manager_id.access_company_ids", "in", lst),
            ])
            if hide_field_access:
                for field in hide_field_access.mapped("access_field_id"):
                    if field.ttype in ["many2many", "many2one"]:
                        for field_ele in doc.xpath(f"//field[@name='{field.name}']"):
                            node_options = ast.literal_eval(field_ele.attrib.get("options", "{}"))
                            node_options.update({
                                "no_create": True, 
                                "no_create_edit": True, 
                                "no_open": True
                            })
                            field_ele.attrib["options"] = str(node_options)

            # Ocultar Chatter si aplica
            hide_chatter_rec = self.env["user.management"].sudo().search([
                ("active", "=", True),
                ("access_user_ids", "in", self.env.user.id),
                ("access_company_ids", "in", lst),
                ("access_hide_chatter", "=", True),
            ], limit=1)
            if hide_chatter_rec:
                for node in doc.xpath("//div[@class='oe_chatter'] | //chatter"):
                    node.getparent().remove(node)

        # --- LÓGICA DE KANBAN: Ocultar botones ---
        if view_type == "kanban":
            hide_button_ids = self.env["button.tab.access"].sudo().search([
                ("access_model_id.model", "=", model_name),
                ("access_user_manager_id.active", "=", True),
                ("access_user_manager_id.access_user_ids", "in", self.env.user.id),
                ("access_user_manager_id.access_company_ids", "in", lst),
            ])
            for button in hide_button_ids:
                for btn in button.access_hide_button_ids:
                    # Ocultar por nombre en diferentes etiquetas
                    for tag in ["a", "button", "object"]:
                        for ele in doc.xpath(f"//{tag}[@name='{btn.access_name}']"):
                            ele.attrib["class"] = ele.attrib.get("class", "") + " d-none"

        # --- LÓGICA DE SOLO LECTURA / PERMISOS DE MODELO ---
        readonly_access_id = self.env["user.management"].sudo().search([
            ("active", "=", True),
            ("access_user_ids", "in", self.env.user.id),
            ("access_readonly", "=", True),
            ("access_company_ids", "in", lst),
        ])
        
        if readonly_access_id:
            doc.attrib.update({"create": "false", "delete": "false", "edit": "false", "duplicate": "false"})
        else:
            change_model_access = self.env["model.access"].sudo().search([
                ("access_user_manager_id.access_user_ids", "in", self.env.user.id),
                ("access_user_manager_id.active", "=", True),
                ("access_model_id.model", "=", model_name),
                ("access_user_manager_id.access_company_ids", "in", lst),
            ])
            if change_model_access:
                # Valores por defecto
                res_perms = {"create": "true", "delete": "true", "edit": "true", "duplicate": "true"}
                for rec in change_model_access:
                    if rec.access_hide_create: res_perms["create"] = "false"
                    if rec.access_hide_edit: res_perms["edit"] = "false"
                    if rec.access_hide_delete: res_perms["delete"] = "false"
                    if rec.access_hide_duplicate: res_perms["duplicate"] = "false"
                    if rec.access_model_readonly:
                        res_perms.update({"create": "false", "delete": "false", "edit": "false"})
                doc.attrib.update(res_perms)

        # 3. GUARDAR CAMBIOS EN EL XML
        view_ref["arch"] = etree.tostring(doc, encoding="unicode")

        # 4. SOLUCIÓN ODOO 19: Inyectar metadatos de campos críticos detectados
        # Esto evita el error 'undefined' en el navegador cuando falta metadata de moneda o pedidos.
        if 'models' in view_ref and model_name in view_ref['models']:
            # En v19 'models' es un frozendict, lo convertimos para poder editarlo
            models_metadata = dict(view_ref['models'])
            field_list = list(models_metadata.get(model_name, []))
            
            # Campos que tu sistema reportó como faltantes y rompen el JS
            essential_fields = ['sale_order_id', 'currency_id', 'company_id']
            
            needs_update = False
            for f in essential_fields:
                if f in self.env[model_name]._fields and f not in field_list:
                    field_list.append(f)
                    needs_update = True
            
            if needs_update:
                models_metadata[model_name] = tuple(field_list)
                view_ref['models'] = models_metadata

        return view_ref
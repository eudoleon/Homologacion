from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = "res.partner"

    # Campo auxiliar ahora correctamente computado, almacenado e inverso
    category_names = fields.Char(
        string="Etiquetas (nombres)",
        compute="_compute_category_names",
        inverse="_inverse_category_names",
        store=True,
    )

    def _prepare_category_ids_from_names(self, names_str):
        """Convierte una cadena 'a,b,c' en lista de ids [id1,id2,...] buscando o creando categorías."""
        if not names_str:
            return []
        names = [n.strip() for n in names_str.split(",") if n.strip()]
        if not names:
            return []
        Category = self.env["res.partner.category"]
        ids = []
        for name in names:
            cat = Category.search([("name", "=", name)], limit=1)
            if not cat:
                cat = Category.create({"name": name})
            ids.append(cat.id)
        return ids

    @api.depends('category_id')
    def _compute_category_names(self):
        for rec in self:
            # unir todos los nombres separados por coma
            rec.category_names = ",".join(rec.category_id.mapped("name")) if rec.category_id else False

    def _inverse_category_names(self):
        # actualizar category_id a partir de category_names
        for rec in self:
            names_str = rec.category_names or ""
            ids = self._prepare_category_ids_from_names(names_str)
            # asignar los ids obtenidos (incluso vaciar si names_str está vacío)
            rec.category_id = [(6, 0, ids)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Si vienen nombres en category_names (desde POS), convertirlos y asignar category_id
            names = vals.pop("category_names", None)
            if names:
                ids = self._prepare_category_ids_from_names(names)
                if ids:
                    vals["category_id"] = [(6, 0, ids)]
                else:
                    vals["category_id"] = [(6, 0, [])]
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        # Procesar category_names si se envía en actualización
        names = vals.pop("category_names", None)
        if names is not None:
            ids = self._prepare_category_ids_from_names(names)
            if ids:
                vals["category_id"] = [(6, 0, ids)]
            else:
                vals["category_id"] = [(6, 0, [])]
        return super(ResPartner, self).write(vals)

# coding: utf-8
from odoo import fields, models, api, _
import time
from datetime import datetime, date, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from odoo.tools.translate import _lt

class AccountInventoryBookWizard(models.TransientModel):
    _name = "account.inventory.book.wizard"
    _description = 'Inventory Book Wizard'

    date_start = fields.Date("Fecha de Inicio", required=True, default=time.strftime('%Y-%m-%d'))
    date_end = fields.Date("Fecha Fin", required=True, default=time.strftime('%Y-%m-%d'))
    product_type_filter = fields.Selection([
        ("all", _("Todos los productos")),
        ("category", _("Categoría")),
        ("product", _("Producto")),
    ], string="Filtrar por", required=True, default='all')

    def _domain_product_ids(self):
        Product = self.env['product.product']
        if 'is_storable' in Product._fields:
            return [('is_storable', '=', True)]
        elif 'detailed_type' in Product._fields:
            return [('detailed_type', '=', 'product')]
        return [('type', '=', 'product')]

    category_ids = fields.Many2many(comodel_name='product.category', string='Categoría')
    product_ids = fields.Many2many(comodel_name='product.product', string='Producto', domain=_domain_product_ids)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    @api.onchange('product_type_filter')
    def _onchange_product_type_filter(self):
        for rec in self:
            if rec.product_type_filter == 'all':
                rec.product_ids = False
                rec.category_ids = False
            elif rec.product_type_filter == 'category':
                rec.product_ids = False
            elif rec.product_type_filter == 'product':
                rec.category_ids = False

    def imprimir_pdf(self):
        for rec in self:
            data = {
                'ids': 0,
                'form': {
                    'date_from': self.date_start,
                    'date_to': self.date_end,
                    'category_ids': self.category_ids.ids if self.category_ids else [],
                    'product_ids': self.product_ids.ids if self.product_ids else [],
                    'company': self.company_id.id
                }
            }
            return self.env.ref('l10n_ve_full.report_inventary_book').report_action(self, data=data)  # , config=False


    def imprimir_xlsx(self):
        for rec in self:
            pass

def _get_move_qty(move):
    if hasattr(move, 'quantity') and move.quantity is not None:
        return abs(move.quantity)
    if hasattr(move, 'quantity_done') and move.quantity_done is not None:
        return abs(move.quantity_done)
    return abs(move.product_uom_qty or 0.0)

def _is_move_in(move):
    if hasattr(move, 'is_in'):
        return bool(move.is_in)
    if hasattr(move, '_is_in'):
        try:
            return bool(move._is_in())
        except Exception:
            pass
    return move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal'

def _is_move_out(move):
    if hasattr(move, 'is_out'):
        return bool(move.is_out)
    if hasattr(move, '_is_out'):
        try:
            return bool(move._is_out())
        except Exception:
            pass
    return move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'

def _get_move_value(move, product, company):
    qty = _get_move_qty(move)
    if hasattr(move, 'value') and move.value:
        return abs(move.value)
    if hasattr(move, 'price_unit') and move.price_unit:
        return abs(move.price_unit * qty)
    cost = product.with_company(company).standard_price or 0.0
    return abs(cost * qty)

class AccountInventoryBookReport(models.AbstractModel):
    _name = 'report.l10n_ve_full.report_invantary_book_template'
    _description = 'Inventory Book Report'

    def _get_autoconsumo_data(self, company_id, productos_ids, date_from_val, date_to_val):
        """
        Obtiene para cada producto:
        1. Cantidad correspondiente a los desechos en la ubicación "DESECHO".
        2. Total Bolívares obtenido de la columna 'debit' de account.move.line.
        3. Conjunto de IDs de las ubicaciones de desecho.
        """
        if not productos_ids:
            return {}, {}, set()

        Location = self.env['stock.location']
        company_domain = ['|', ('company_id', '=', company_id.id), ('company_id', '=', False)]
        has_scrap_field = 'scrap_location' in Location._fields

        # 1. Buscar ubicación por nombre o ruta que contenga "DESECHO"
        desecho_domain = [
            '|', ('name', 'ilike', 'DESECHO'), ('complete_name', 'ilike', 'DESECHO'),
        ] + company_domain
        if has_scrap_field:
            desecho_locs = Location.search([('scrap_location', '=', True)] + desecho_domain)
        else:
            desecho_locs = Location.search(desecho_domain)

        # 2. Si no se encontró filtrando por scrap_location, buscar simplemente por nombre
        if not desecho_locs:
            desecho_locs = Location.search(desecho_domain)

        # 3. Como respaldo si no existe por nombre, buscar cualquier ubicación marcada como scrap (si el campo existe)
        if not desecho_locs and has_scrap_field:
            desecho_locs = Location.search([
                ('scrap_location', '=', True),
            ] + company_domain)

        if not desecho_locs:
            return {}, {}, set()

        # Incluir posibles sub-ubicaciones de DESECHO
        all_desecho_locs = Location.search([
            ('id', 'child_of', desecho_locs.ids)
        ])
        all_desecho_locs_set = set(all_desecho_locs.ids)

        # ----------------------------------------------------
        # 1. CANTIDAD: Stock en la ubicación de desecho
        # ----------------------------------------------------
        Quant = self.env['stock.quant']
        quants = Quant.search([
            ('location_id', 'in', all_desecho_locs.ids),
            ('product_id', 'in', productos_ids.ids),
        ] + company_domain)

        autoconsumo_qty_dict = {}
        use_avail = 'available_quantity' in Quant._fields

        for q in quants:
            qty = q.available_quantity if use_avail else q.quantity
            if qty:
                autoconsumo_qty_dict[q.product_id.id] = autoconsumo_qty_dict.get(q.product_id.id, 0.0) + (qty or 0.0)

        # ----------------------------------------------------
        # 2. TOTAL BOLÍVARES: debit de account.move.line
        # ----------------------------------------------------
        autoconsumo_val_dict = {}
        MoveLine = self.env['account.move.line']
        StockMove = self.env['stock.move']

        desecho_moves = StockMove.search([
            ('location_dest_id', 'in', all_desecho_locs.ids),
            ('product_id', 'in', productos_ids.ids),
            ('state', '=', 'done'),
        ] + company_domain)

        target_amls = MoveLine.browse()

        # a) A través de account_move_ids en stock.move
        if 'account_move_ids' in StockMove._fields:
            target_amls |= desecho_moves.mapped('account_move_ids.line_ids')

        # b) A través de stock_move_id en account.move
        if 'stock_move_id' in self.env['account.move']._fields:
            acc_moves = self.env['account.move'].search([
                ('stock_move_id', 'in', desecho_moves.ids),
            ] + company_domain)
            target_amls |= acc_moves.mapped('line_ids')

        # c) A través de stock_move_id en account.move.line
        if 'stock_move_id' in MoveLine._fields:
            target_amls |= MoveLine.search([
                ('stock_move_id', 'in', desecho_moves.ids),
            ] + company_domain)

        # d) A través de stock.valuation.layer si existe
        if 'stock.valuation.layer' in self.env.registry:
            svl_model = self.env['stock.valuation.layer']
            if 'stock_move_id' in svl_model._fields:
                svls = svl_model.search([
                    ('stock_move_id', 'in', desecho_moves.ids),
                ] + company_domain)
                if 'account_move_id' in svl_model._fields:
                    target_amls |= svls.mapped('account_move_id.line_ids')
                if 'account_move_line_id' in svl_model._fields:
                    target_amls |= svls.mapped('account_move_line_id')

        # e) A través de referencias de movimientos de desecho
        move_names = set()
        for fn in ('name', 'reference', 'origin'):
            if fn in StockMove._fields:
                move_names |= set(desecho_moves.mapped(fn))
        if 'picking_id' in StockMove._fields:
            pickings = desecho_moves.mapped('picking_id')
            if 'name' in self.env['stock.picking']._fields:
                move_names |= set(pickings.mapped('name'))
        move_names.discard(False)
        move_names.discard('')
        if move_names:
            ref_or_conditions = []
            if 'ref' in MoveLine._fields:
                ref_or_conditions.append(('ref', 'in', list(move_names)))
            if 'move_id' in MoveLine._fields and 'ref' in self.env['account.move']._fields:
                ref_or_conditions.append(('move_id.ref', 'in', list(move_names)))
            if ref_or_conditions:
                prefix = ['|'] * (len(ref_or_conditions) - 1)
                target_amls |= MoveLine.search([
                    ('product_id', 'in', productos_ids.ids),
                ] + prefix + ref_or_conditions + company_domain)

        # f) Búsqueda directa por descripción/referencia en el período
        desc_conds = []
        for kw in ('DESECHO', 'AUTOCONSUMO'):
            if 'name' in MoveLine._fields:
                desc_conds.append(('name', 'ilike', kw))
            if 'ref' in MoveLine._fields:
                desc_conds.append(('ref', 'ilike', kw))
            if 'move_id' in MoveLine._fields and 'ref' in self.env['account.move']._fields:
                desc_conds.append(('move_id.ref', 'ilike', kw))
        if desc_conds:
            prefix = ['|'] * (len(desc_conds) - 1)
            target_amls |= MoveLine.search([
                ('product_id', 'in', productos_ids.ids),
                ('date', '>=', date_from_val),
                ('date', '<=', date_to_val),
            ] + prefix + desc_conds + company_domain)

        for aml in target_amls:
            if (aml.debit or 0.0) > 0:
                if 'parent_state' in MoveLine._fields and aml.parent_state == 'cancel':
                    continue
                elif 'move_id' in MoveLine._fields and 'state' in self.env['account.move']._fields and aml.move_id.state == 'cancel':
                    continue

                prod_id = aml.product_id.id if aml.product_id else False
                if not prod_id and 'stock_move_id' in MoveLine._fields and aml.stock_move_id:
                    prod_id = aml.stock_move_id.product_id.id
                elif not prod_id and 'move_id' in MoveLine._fields and 'stock_move_id' in self.env['account.move']._fields and aml.move_id.stock_move_id:
                    prod_id = aml.move_id.stock_move_id.product_id.id

                if prod_id and prod_id in productos_ids.ids:
                    autoconsumo_val_dict[prod_id] = autoconsumo_val_dict.get(prod_id, 0.0) + aml.debit

        return autoconsumo_qty_dict, autoconsumo_val_dict, all_desecho_locs_set

    @api.model
    def _get_report_values(self, docids, data=None):
        format_new = "%d/%m/%Y"
        raw_date_from = data['form']['date_from']
        raw_date_to = data['form']['date_to']

        if isinstance(raw_date_from, datetime):
            date_from_val = raw_date_from.date()
        elif isinstance(raw_date_from, date):
            date_from_val = raw_date_from
        else:
            date_from_val = datetime.strptime(str(raw_date_from), DATE_FORMAT).date()

        if isinstance(raw_date_to, datetime):
            date_to_val = raw_date_to.date()
        elif isinstance(raw_date_to, date):
            date_to_val = raw_date_to
        else:
            date_to_val = datetime.strptime(str(raw_date_to), DATE_FORMAT).date()

        company_id = self.env['res.company'].browse(data['form']['company'])
        datos = []

        dominio_productos = ['|', ('company_id', '=', company_id.id), ('company_id', '=', False)]
        Product = self.env['product.product']
        if 'is_storable' in Product._fields:
            dominio_productos.append(('is_storable', '=', True))
        elif 'detailed_type' in Product._fields:
            dominio_productos.append(('detailed_type', '=', 'product'))
        else:
            dominio_productos.append(('type', '=', 'product'))

        if data['form']['category_ids']:
            dominio_productos.append(('categ_id', 'in', data['form']['category_ids']))
        if data['form']['product_ids']:
            dominio_productos.append(('id', 'in', data['form']['product_ids']))

        productos_ids = Product.search(dominio_productos)

        # Ajuste a UTC según la zona horaria del usuario para que no queden fuera movimientos por desfase horario
        try:
            import pytz
            user_tz = pytz.timezone(self.env.user.tz or 'America/Caracas')
            dt_from = user_tz.localize(datetime.combine(date_from_val, datetime.min.time())).astimezone(pytz.utc)
            dt_to = user_tz.localize(datetime.combine(date_to_val, datetime.max.time())).astimezone(pytz.utc)
            date_from_str = dt_from.strftime('%Y-%m-%d %H:%M:%S')
            date_to_str = dt_to.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            date_from_str = date_from_val.strftime('%Y-%m-%d') + ' 00:00:00'
            date_to_str = date_to_val.strftime('%Y-%m-%d') + ' 23:59:59'

        total_existencia_inicial = 0.0
        total_precio_inicial = 0.0
        total_entradas_mes = 0.0
        total_entradas_mes_precio = 0.0
        total_salida_mes = 0.0
        total_salida_mes_precio = 0.0
        total_autoconsumo_qty = 0.0
        total_autoconsumo_total = 0.0
        total_final = 0.0
        total_final_precio = 0.0

        autoconsumo_qty_dict, autoconsumo_val_dict, all_desecho_locs_set = self._get_autoconsumo_data(
            company_id, productos_ids, date_from_val, date_to_val
        )

        has_svl = 'stock.valuation.layer' in self.env.registry

        if has_svl:
            for p in productos_ids:
                # buscar saldos iniciales del producto
                inciales_ids = self.env['stock.valuation.layer'].search([
                    ('product_id', '=', p.id),
                    ('company_id', '=', company_id.id),
                    ('create_date', '<', date_from_str)
                ])
                existencia_inicial = 0.0
                precio_inicial = 0.0
                precio_total_inicial = 0.0
                if inciales_ids:
                    existencia_inicial = sum(inciales_ids.mapped('quantity'))
                    precio_total_inicial = sum(inciales_ids.mapped('value'))
                    precio_inicial = (precio_total_inicial / existencia_inicial) if existencia_inicial else 0.0

                # inventario del mes
                inventario_mes_ids = self.env['stock.valuation.layer'].search([
                    ('product_id', '=', p.id),
                    ('company_id', '=', company_id.id),
                    ('create_date', '>=', date_from_str),
                    ('create_date', '<=', date_to_str)
                ])

                entradas_mes = 0.0
                entradas_mes_precio = 0.0
                entradas_mes_precio_total = 0.0
                salida_mes = 0.0
                salida_mes_precio = 0.0
                salida_mes_precio_total = 0.0
                if inventario_mes_ids:
                    entadas_ids = inventario_mes_ids.filtered(lambda x: x.quantity > 0)
                    salidas_ids = inventario_mes_ids.filtered(
                        lambda x: x.quantity < 0 and (not x.stock_move_id or x.stock_move_id.location_dest_id.id not in all_desecho_locs_set)
                    )
                    if entadas_ids:
                        entradas_mes = sum(entadas_ids.mapped('quantity'))
                        entradas_mes_precio_total = sum(entadas_ids.mapped('value'))
                        entradas_mes_precio = (entradas_mes_precio_total / entradas_mes) if entradas_mes else 0.0
                    if salidas_ids:
                        salida_mes = abs(sum(salidas_ids.mapped('quantity')))
                        salida_mes_precio_total = abs(sum(salidas_ids.mapped('value')))
                        salida_mes_precio = (salida_mes_precio_total / salida_mes) if salida_mes else 0.0

                autoconsumo_qty = autoconsumo_qty_dict.get(p.id, 0.0)
                if autoconsumo_qty < 0:
                    autoconsumo_qty = 0.0

                autoconsumo_total = autoconsumo_val_dict.get(p.id, 0.0)
                if autoconsumo_total < 0:
                    autoconsumo_total = 0.0

                # Stock final: Existencia Inicial + Cantidad Entradas - Cantidad Salidas - Cantidad en Autoconsumo
                final = existencia_inicial + entradas_mes - salida_mes - autoconsumo_qty
                final_precio_total = precio_total_inicial + entradas_mes_precio_total - salida_mes_precio_total - autoconsumo_total
                if final < 0:
                    final = 0.0
                if final_precio_total < 0:
                    final_precio_total = 0.0
                final_precio = (final_precio_total / final) if final > 0 else 0.0

                if not data['form']['product_ids'] and existencia_inicial == 0 and entradas_mes == 0 and salida_mes == 0 and final == 0 and autoconsumo_qty == 0:
                    continue

                total_existencia_inicial += existencia_inicial
                total_precio_inicial += precio_total_inicial
                total_entradas_mes += entradas_mes
                total_entradas_mes_precio += entradas_mes_precio_total
                total_salida_mes += salida_mes
                total_salida_mes_precio += salida_mes_precio_total
                total_autoconsumo_qty += autoconsumo_qty
                total_autoconsumo_total += autoconsumo_total
                total_final += final
                total_final_precio += final_precio_total

                datos.append({
                    'default_code': p.default_code or '',
                    'name': p.name,
                    'existencia_inicial': existencia_inicial,
                    'precio_inicial': precio_inicial,
                    'precio_total_inicial': precio_total_inicial,
                    'entradas_mes': entradas_mes,
                    'entradas_mes_precio': entradas_mes_precio,
                    'entradas_mes_precio_total': entradas_mes_precio_total,
                    'salida_mes': salida_mes,
                    'salida_mes_precio': salida_mes_precio,
                    'salida_mes_precio_total': salida_mes_precio_total,
                    'autoconsumo_qty': autoconsumo_qty,
                    'autoconsumo_total': autoconsumo_total,
                    'final': final,
                    'final_precio': final_precio,
                    'final_precio_total': final_precio_total,
                })
        else:
            # Odoo 19+: La valoración de inventario reside directamente en stock.move
            StockMove = self.env['stock.move']
            for p in productos_ids:
                inciales_moves = StockMove.search([
                    ('product_id', '=', p.id),
                    ('company_id', '=', company_id.id),
                    ('state', '=', 'done'),
                    ('date', '<', date_from_str)
                ])
                existencia_inicial = 0.0
                precio_total_inicial = 0.0
                for m in inciales_moves:
                    m_qty = _get_move_qty(m)
                    m_val = _get_move_value(m, p, company_id)
                    if _is_move_in(m):
                        existencia_inicial += m_qty
                        precio_total_inicial += m_val
                    elif _is_move_out(m):
                        existencia_inicial -= m_qty
                        precio_total_inicial -= m_val

                if existencia_inicial < 0:
                    existencia_inicial = 0.0
                if precio_total_inicial < 0:
                    precio_total_inicial = 0.0

                precio_inicial = (precio_total_inicial / existencia_inicial) if existencia_inicial > 0 else (p.with_company(company_id).standard_price or 0.0)
                if existencia_inicial > 0 and precio_total_inicial == 0.0:
                    precio_total_inicial = existencia_inicial * precio_inicial

                mes_moves = StockMove.search([
                    ('product_id', '=', p.id),
                    ('company_id', '=', company_id.id),
                    ('state', '=', 'done'),
                    ('date', '>=', date_from_str),
                    ('date', '<=', date_to_str)
                ])

                entradas_mes = 0.0
                entradas_mes_precio_total = 0.0
                salida_mes = 0.0
                salida_mes_precio_total = 0.0

                for m in mes_moves:
                    m_qty = _get_move_qty(m)
                    m_val = _get_move_value(m, p, company_id)
                    if m.location_dest_id.id in all_desecho_locs_set:
                        # Movimiento de desecho: se clasifica como Autoconsumo, no como Salidas del Mes
                        continue
                    if _is_move_in(m):
                        entradas_mes += m_qty
                        entradas_mes_precio_total += m_val
                    elif _is_move_out(m):
                        salida_mes += m_qty
                        salida_mes_precio_total += m_val

                entradas_mes_precio = (entradas_mes_precio_total / entradas_mes) if entradas_mes > 0 else 0.0
                salida_mes_precio = (salida_mes_precio_total / salida_mes) if salida_mes > 0 else 0.0

                autoconsumo_qty = autoconsumo_qty_dict.get(p.id, 0.0)
                if autoconsumo_qty < 0:
                    autoconsumo_qty = 0.0

                autoconsumo_total = autoconsumo_val_dict.get(p.id, 0.0)
                if autoconsumo_total < 0:
                    autoconsumo_total = 0.0

                # El valor de Autoconsumo se resta del Inventario Final
                final = existencia_inicial + entradas_mes - salida_mes - autoconsumo_qty
                final_precio_total = precio_total_inicial + entradas_mes_precio_total - salida_mes_precio_total - autoconsumo_total
                if final < 0:
                    final = 0.0
                if final_precio_total < 0:
                    final_precio_total = 0.0
                final_precio = (final_precio_total / final) if final > 0 else 0.0

                if not data['form']['product_ids'] and existencia_inicial == 0 and entradas_mes == 0 and salida_mes == 0 and final == 0 and autoconsumo_qty == 0:
                    continue

                total_existencia_inicial += existencia_inicial
                total_precio_inicial += precio_total_inicial
                total_entradas_mes += entradas_mes
                total_entradas_mes_precio += entradas_mes_precio_total
                total_salida_mes += salida_mes
                total_salida_mes_precio += salida_mes_precio_total
                total_autoconsumo_qty += autoconsumo_qty
                total_autoconsumo_total += autoconsumo_total
                total_final += final
                total_final_precio += final_precio_total

                datos.append({
                    'default_code': p.default_code or '',
                    'name': p.name,
                    'existencia_inicial': existencia_inicial,
                    'precio_inicial': precio_inicial,
                    'precio_total_inicial': precio_total_inicial,
                    'entradas_mes': entradas_mes,
                    'entradas_mes_precio': entradas_mes_precio,
                    'entradas_mes_precio_total': entradas_mes_precio_total,
                    'salida_mes': salida_mes,
                    'salida_mes_precio': salida_mes_precio,
                    'salida_mes_precio_total': salida_mes_precio_total,
                    'autoconsumo_qty': autoconsumo_qty,
                    'autoconsumo_total': autoconsumo_total,
                    'final': final,
                    'final_precio': final_precio,
                    'final_precio_total': final_precio_total,
                })

        company_rif = getattr(company_id, 'rif', False) or (company_id.partner_id and company_id.partner_id.rif) or company_id.vat or ''

        return {
            'company': company_id,
            'company_rif': company_rif,
            'currency': company_id.currency_id,
            'date_start': date_from_val.strftime(format_new),
            'date_end': date_to_val.strftime(format_new),
            'datos': datos,
            'total_existencia_inicial': total_existencia_inicial,
            'total_precio_inicial': total_precio_inicial,
            'total_entradas_mes': total_entradas_mes,
            'total_entradas_mes_precio': total_entradas_mes_precio,
            'total_salida_mes': total_salida_mes,
            'total_salida_mes_precio': total_salida_mes_precio,
            'total_autoconsumo_qty': total_autoconsumo_qty,
            'total_autoconsumo_total': total_autoconsumo_total,
            'total_final': total_final,
            'total_final_precio': total_final_precio,
        }

# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from markupsafe import Markup


class StockMove(models.Model):
    _inherit = "stock.move"
    stock_inventory_id = fields.Many2one('stock.inventory')

class StockInventory(models.Model):
    _name = 'stock.inventory'
    _order = 'product_id desc'

    name = fields.Char('Reference', required=True,)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True, )
    product_id = fields.Many2one(
        'product.product', 'Producto inventariada',
        help="Specify Product to focus your inventory on a particular Product.")
    location_id = fields.Many2one(
        'stock.location', 'Location',
        domain=[('usage', 'in', ('internal', 'transit'))],
        index=True, required=True)
    company_id = fields.Many2one(related='location_id.company_id', string='Company', store=True, readonly=True)
    date = fields.Datetime(
        'Inventory Date',
        readonly=True, required=True,
        default=fields.Datetime.now,
        help="The date that will be used for the stock level check of the products and the validation of the stock move related to this inventory.",)
    lot_id = fields.Many2one(
        'stock.lot', 'Lot Number', index=True, check_company=True)
    package_id = fields.Many2one(
        'stock.quant.package', 'Package',
        domain="[('location_id', '=', location_id)]",
        help='The package containing this quant', ondelete='restrict', check_company=True, index=True)        
    
    state = fields.Selection(string='Status', selection=[
        ('draft', 'Borrador'),
        ('cancel', 'Cancelado'),
        ('confirm', 'En curso'),
        ('wait_for_approval', 'Esperar la aprobación'),
        ('approved', 'Aprobado'),
        ('done', 'Validado')],
        copy=False, index=True, readonly=True,
        default='draft')
    filter = fields.Selection(
        string='Inventory of', selection='_selection_filter',
        required=True,
        default='none',
        help="If you do an entire inventory, you can choose 'All Products' and it will prefill the inventory with the current stock.  If you only do some products  "
             "(e.g. Cycle Counting) you can choose 'Manual Selection of Products' and the system won't propose anything.  You can also let the "
             "system propose for a single product / lot /... ")
    add_onhand_zero = fields.Boolean('Include Onhand Zero Product',)
    move_ids = fields.One2many(
        'stock.move', 'stock_inventory_id', string='Created Moves',
        copy=False,
        readonly=True)
    line_ids = fields.One2many(
        'stock.inventory.line', 'stock_inventory_id', string='Inventories',
        copy=False,
    )
    partner_id = fields.Many2one(
        'res.partner', 'Inventoried Owner',
        help="Specify Owner to focus your inventory on a particular Owner.")
    category_id = fields.Many2one(
        'product.category', 'Categoría inventariada',
        help="Specify Product Category to focus your inventory on a particular Category.")
    accounting_date = fields.Datetime(
        string='Accounting Date',
        help="Date at which the accounting entries will be created"
            " in case of automated inventory valuation."
            " If empty, the inventory date will be used.",
    )
    note = fields.Text(string="Important Note")
    

    def set_product_serial_type_quantity(self):
        for line in self.line_ids.filtered(lambda x: x.product_id.tracking == 'serial'):
            line.inventory_quantity = line.quantity

    @api.constrains('state')
    def _check_reserved_quantity(self):
        for record in self:
            if record and record.state == 'wait_for_approval':
                for line in record.line_ids:
                    if line.inventory_quantity < line.reserved_quantity:
                        raise ValidationError(_('You are not allowed to add counted quantity(%s) less than reserved quantity(%s)  for %s.', line.inventory_quantity,line.reserved_quantity, line.product_id.display_name))

    @api.model
    def _selection_filter(self):
        """ Returns allowed filter options based on 'Settings Warehouse' configurations. """        
        res_filter = [
            ('none', ('Todos los productos')),
            ('category', ('Una categoría de producto')),
            ('product', ('Un solo producto')),
            ('partial', ('Seleccionar productos manualmente')),
        ]

        if self.env.user.has_group('stock.group_tracking_owner'):
            res_filter += [('owner', ('One owner only')), ('product_owner', ('One product for a specific owner'))]
        if self.env.user.has_group('stock.group_production_lot'):
            res_filter.append(('lot', ('Un número de lote')))
        if self.env.user.has_group('stock.group_tracking_lot'):
            res_filter.append(('pack', ('A Pack')))
        return res_filter

    @api.onchange('filter')
    def onchange_filter(self):
        if self.filter not in ('product', 'product_owner'):
            self.product_id = False
        if self.filter != 'lot':
            self.lot_id = False
        if self.filter not in ('owner', 'product_owner'):
            self.partner_id = False
        if self.filter != 'pack':
            self.package_id = False
        if self.filter != 'category':
            self.category_id = False

    @api.constrains('filter', 'product_id', 'lot_id', 'partner_id', 'package_id')
    def _check_filter_product(self):
        if self.filter == 'none' and self.product_id and self.location_id and self.lot_id:
            return
        if self.filter not in ('product', 'product_owner') and self.product_id:
            raise UserError(_('The selected inventory options are not coherent.'))
        if self.filter != 'lot' and self.lot_id:
            raise UserError(_('The selected inventory options are not coherent.'))
        if self.filter not in ('owner', 'product_owner') and self.partner_id:
            raise UserError(_('The selected inventory options are not coherent.'))
        if self.filter != 'pack' and self.package_id:
            raise UserError(_('The selected inventory options are not coherent.'))


    def prepare_inventory_stock_counting(self):
        domain = [
            ('company_id', '=', self.company_id.id),
            ('location_id', '=', self.location_id.id)
        ]
        product = self.env['product.product']
        if self.filter == 'none':
            rec = self.env['stock.quant'].search(domain)
            if self.add_onhand_zero:
                product = product.search([('id', 'not in', rec.mapped('product_id').ids), ('detailed_type', '=', 'product')]) 
            if rec or product:
                self.prepare_stock_counting_lines(rec, product)
            else:
                raise ValidationError(_('Record not available.'))

        if self.filter == 'category':
            rec = self.env['stock.quant'].search(domain + [('product_id.categ_id','=',self.category_id.id)])
            if self.add_onhand_zero:
                product = product.search([('categ_id','=',self.category_id.id), ('id', 'not in', rec.mapped('product_id').ids),  ('detailed_type', '=', 'product')]) 
            if rec or product:
                self.prepare_stock_counting_lines(rec, product)
            else:
                raise ValidationError(_('Record not available.'))

        if self.filter == 'product':
            rec = self.env['stock.quant'].search(domain + [('product_id','=',self.product_id.id)])
            if self.add_onhand_zero:
                product = product.search([('id','=',self.product_id.id), ('id', 'not in', rec.mapped('product_id').ids),  ('detailed_type', '=', 'product')]) 
            if rec or product:
                self.prepare_stock_counting_lines(rec, product)
            else:        
                raise ValidationError(_('Record not available.'))

        if self.filter == 'lot':
            rec = self.env['stock.quant'].search(domain + [('lot_id','=',self.lot_id.id)])
            if rec:
                self.prepare_stock_counting_lines(rec)
            else:
                raise ValidationError(_('Record not available.'))

        if self.filter == 'pack':
            rec = self.env['stock.quant'].search(domain + [('package_id','=',self.package_id.id)])
            if rec:
                self.prepare_stock_counting_lines(rec)
            else:
                raise ValidationError(_('Record not available.'))
        if self.filter == 'partial':
            self.write({'state':'confirm',})


    def prepare_stock_counting_lines(self, rec, product_id=None):
        domain = [('company_id', '=', self.company_id.id),
            ('location_id', '=', self.location_id.id)
        ]

        if rec:
            for x in rec:
                bom_ids = x.product_id and x.product_id.product_tmpl_id and 'bom_ids' in x.product_id.product_tmpl_id and x.product_id.product_tmpl_id.bom_ids
                if not bom_ids or bom_ids.filtered(lambda bom: bom.type != 'phantom'):
                    self.write({
                        'line_ids': [(0,0,{
                        'product_id': x.product_id.id,
                        'product_uom_id': x.product_uom_id.id,
                        'location_id': x.location_id.id,
                        'prod_lot_id': x.lot_id.id,
                        'package_id': x.package_id.id,
                        'available_quantity' : x.available_quantity,
                        'quantity':x.quantity,
                        'inventory_quantity' :x.inventory_quantity })],
                        'state':'confirm',
                        'date': fields.Datetime.now(),
                    })
        if product_id:
            for x in product_id:
                bom_ids = x.product_tmpl_id and 'bom_ids' in x.product_id.product_tmpl_id and x.product_tmpl_id.bom_ids
                if not bom_ids or bom_ids.filtered(lambda bom: bom.type != 'phantom'):
                    self.write({
                        'state':'confirm',
                        'line_ids': [(0,0,{
                        'product_id': x.id,
                        'product_uom_id': x.uom_id.id,
                        'location_id': self.location_id.id,
                        })],
                    })

    def action_send_for_approval(self):
        for on_hand_qty in self.line_ids:
            if not on_hand_qty.inventory_quantity and not on_hand_qty.make_it_zero:
                on_hand_qty.inventory_quantity = on_hand_qty.quantity
        
        has_group = self.env.ref('inventory_stock_adjustments.group_stock_adjustments_manager')

        url = self._get_html_link(title=self.name)

        users = self.env['res.users']
        if has_group:
            users = has_group.users

        message = _(
            "%s Ha solicitado la aprobación para cambios de stock. Revíselo aquí: %s" % (self.env.user.name, url),
        )
        for user in users:
            if self.env.user.partner_id.id != user.partner_id.id:
                channel_id = self.env['mail.channel'].channel_get([self.env.user.partner_id.id, user.partner_id.id])
                channel_id = self.env['mail.channel'].browse(channel_id.get('id'))
                notification_ids = [((0, 0, {
                   'res_partner_id': user.partner_id.id,
                   'notification_type': 'inbox'}))]
                channel_id.message_post(
                    author_id=self.env.user.partner_id.id,
                    body=(message),
                    message_type='notification',
                    subtype_xmlid="mail.mt_comment",
                    notification_ids=notification_ids,
                    # partner_ids=[user.partner_id.id],
                    notify_by_email=False,
                )
        self.write({'state':'wait_for_approval'})

    def action_approved(self):
        url = self._get_html_link(title=self.name)

        message = _(
            "Sus cambios de stock han sido aprobados por %s. Puedes verlos aquí: %s" % (self.env.user.name, url),
        )
        if self.env.user.partner_id.id != self.user_id.partner_id.id:
            channel_id = self.env['mail.channel'].channel_get([self.env.user.partner_id.id, self.user_id.partner_id.id])
            channel_id = self.env['mail.channel'].browse(channel_id.get('id'))
            notification_ids = [((0, 0, {
               'res_partner_id': self.user_id.partner_id.id,
               'notification_type': 'inbox'}))]
            channel_id.message_post(
                author_id=self.env.user.partner_id.id,
                body=(message),
                message_type='notification',
                subtype_xmlid="mail.mt_comment",
                notification_ids=notification_ids,
                # partner_ids=[user.partner_id.id],
                notify_by_email=False,
            )
        self.write({'state':'approved'})

    def action_done(self):
        for line in self.line_ids:
            domain = [
                ('company_id', '=', line.stock_inventory_id.company_id.id),
                ('location_id', '=', line.stock_inventory_id.location_id.id),
                ('owner_id', '=', line.stock_inventory_id.partner_id.id),
            ]
            if line.product_id.tracking in ['lot', 'serial'] and not line.prod_lot_id:
                raise UserError('Please Add serial number for this product %s' % line.product_id.display_name)

            
            quant_rec = self.env['stock.quant'].search(domain + [('product_id','=',line.product_id.id)])
            if line.prod_lot_id:
                quant_rec = self.env['stock.quant'].search(domain + [('product_id','=',line.product_id.id),('lot_id','=',line.prod_lot_id.id)])

            for validate in quant_rec:
                if line.make_it_zero:
                    validate.write({'inventory_quantity':0.0})
                    validate.action_apply_inventory()
                    line.write({'available_quantity':validate.available_quantity, 'reserved_quantity':validate.reserved_quantity, 'inventory_quantity':0.0})
                elif validate.inventory_quantity != line.inventory_quantity:
                    validate.write({'inventory_quantity':line.inventory_quantity})
                    validate.action_apply_inventory()
                    line.write({'available_quantity':validate.available_quantity, 'reserved_quantity':validate.reserved_quantity})

            if not quant_rec:
                stock_quant = self.env['stock.quant'].create({
                    'product_id': line.product_id.id,
                    'location_id': line.location_id.id,
                    'inventory_quantity':line.inventory_quantity,
                    'lot_id': line.prod_lot_id.id,
                })
                stock_quant.action_apply_inventory()
        self.write({'state':'done', 'accounting_date': fields.Datetime.now()})

    def action_cancel_draft(self):
        self.write({
            'line_ids': [(5,)],
            'state': 'draft'
        })

    def action_export_stock_adjustment(self):
        return {
            'name': "Exportar Ajuste de Inventario",
            'view_mode': 'form',
            'view_id': self.env.ref("inventory_stock_adjustments.stock_adjustment_report_export_view_form").id,
            'res_model': 'stock.adjustment.report.export',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
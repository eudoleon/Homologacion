# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _register_hook(self):
        super()._register_hook()
        # Buscar y desactivar los menús específicos solicitados
        try:
            # Lista de IDs XML conocidos para estos menús en diferentes versiones
            xml_ids = [
                'point_of_sale.menu_point_of_sale_products_taxes',
                'point_of_sale.pos_menu_tax_form',
                'pos_restaurant.menu_pos_restaurant_printer',
                'pos_preparation_display.menu_pos_preparation_display',
                'pos_preparation_display.menu_pos_preparation_display_time_report',
            ]
            menus_to_hide = self.env['ir.ui.menu']
            for xml_id in xml_ids:
                menu = self.env.ref(xml_id, raise_if_not_found=False)
                if menu:
                    menus_to_hide |= menu
            
            # Fallback por nombre sin forzar idiomas para evitar el error de Invalid Language Code
            all_menus = self.search([('parent_path', '!=', False)])
            for m in all_menus:
                name = (m.name or '').lower()
                ext_id = m.get_external_id().get(m.id, '')
                # Verificar coincidencias de nombres en el idioma actual (usualmente inglés durante el hook)
                if any(k in name for k in ['impuesto', 'tax', 'preparation', 'preparación']):
                    # Solo ocultar si pertenece al POS
                    if 'pos' in ext_id or 'point_of_sale' in ext_id or 'restaurant' in ext_id:
                        menus_to_hide |= m
                        
            if menus_to_hide:
                menus_to_hide.write({'active': False})
                _logger.info(f"Ocultados los siguientes menús del POS: {menus_to_hide.mapped('name')}")
                
        except Exception as e:
            _logger.error(f"Error al ocultar menús del backend: {e}")

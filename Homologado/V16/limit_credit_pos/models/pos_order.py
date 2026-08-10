# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _is_credit_account_payment_method(self, payment_lines_data):
        """
        Verifica si algún método de pago es 'CUENTA DE CLIENTE'
        payment_lines_data: puede ser lista de diccionarios o recordset de pos.payment
        """
        if not payment_lines_data:
            return False
        
        # Caso 1: Es un recordset de pos.payment (como en write())
        if hasattr(payment_lines_data, 'mapped'):
            for payment in payment_lines_data:
                if payment.payment_method_id and payment.payment_method_id.name:
                    if payment.payment_method_id.name.upper() == 'CUENTA DE CLIENTE':
                        return True
            return False
        
        # Caso 2: Es una lista de diccionarios (como en create_from_ui y _process_order)
        for payment_line in payment_lines_data:
            payment_method_id = payment_line.get('payment_method_id')
            if payment_method_id:
                payment_method = self.env['pos.payment.method'].browse(payment_method_id)
                if payment_method and payment_method.name and payment_method.name.upper() == 'CUENTA DE CLIENTE':
                    return True
        
        return False

    def create(self, vals):
        """
        Override de create() - La validación de crédito se hace en create_from_ui()
        donde tenemos acceso a los métodos de pago
        """
        return super().create(vals)

    def write(self, vals):
        """
        Override del método write para validar restricción de crédito adicional
        SOLO si el método de pago es 'CUENTA DE CLIENTE'
        """
        # Caso 1: Se está asignando partner_id - No validamos aquí porque no tenemos métodos de pago aún
        if 'partner_id' in vals:
            pass  # La validación se hará en create_from_ui o al finalizar
        
        # Caso 2: Se intenta finalizar (state=paid o account_move)
        is_finalizing = vals.get('state') == 'paid' or 'account_move' in vals
        
        if is_finalizing:
            for order in self:
                # Solo validar si el método de pago es "CUENTA DE CLIENTE"
                if not self._is_credit_account_payment_method(order.payment_ids):
                    _logger.warning(f"🔴 Método de pago no es CUENTA DE CLIENTE, omitiendo validación en write")
                    continue
                
                if order.partner_id and order.partner_id.activate_credit and order.partner_id.is_credit_restricted:
                    _logger.error(f"❌ BLOQUEO write(finalización): {order.partner_id.name}")
                    raise UserError(
                        f"❌ CLIENTE CON CRÉDITO RESTRINGIDO\n\n"
                        f"Cliente: {order.partner_id.name}\n"
                        f"Deuda: ${order.partner_id.total_invoiced_amount:.2f}\n"
                        f"Límite: ${order.partner_id.credit_limit_custom:.2f}\n\n"
                        f"No se puede crear factura/completar la orden.\n"
                        f"Comuníquese con Administración."
                    )
        
        return super().write(vals)

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Validación PREVIA: Revisar restricción de crédito ANTES de procesar
        SOLO si el método de pago es 'CUENTA DE CLIENTE'
        """
        _logger.warning("="*80)
        _logger.warning("🔴🔴🔴 [create_from_ui] VALIDANDO ÓRDENES")
        _logger.warning("="*80)
        
        # Validar CADA orden ANTES de hacer nada
        for idx, order_data in enumerate(orders):
            _logger.warning(f"\n🔴 ORDEN #{idx}")
            
            # El partner_id ESTÁ dentro de order_data['data']
            order_dict = order_data.get('data', {})
            partner_id = order_dict.get('partner_id')
            payment_lines = order_dict.get('payment_ids', [])
            _logger.warning(f"🔴 partner_id extraído de 'data': {partner_id}")
            _logger.warning(f"🔴 payment_lines: {payment_lines}")
            
            # Solo validar restricción de crédito si el método de pago es "CUENTA DE CLIENTE"
            if not self._is_credit_account_payment_method(payment_lines):
                _logger.warning(f"🔴 Método de pago no es CUENTA DE CLIENTE, omitiendo validación")
                continue
            
            if partner_id:
                partner = self.env['res.partner'].browse(partner_id)
                _logger.warning(f"🔴 Partner: {partner.name}")
                _logger.warning(f"🔴 activate_credit: {partner.activate_credit}")
                _logger.warning(f"🔴 is_credit_restricted: {partner.is_credit_restricted}")
                
                if partner.activate_credit and partner.is_credit_restricted:
                    _logger.error(f"❌❌❌ BLOQUEANDO ANTES DE PROCESAR: {partner.name}")
                    # Lanzar UserError - Odoo lo serializa correctamente como error JSON
                    raise UserError(
                        f"❌ CLIENTE CON CRÉDITO RESTRINGIDO\n\n"
                        f"Cliente: {partner.name}\n"
                        f"Deuda: ${partner.total_invoiced_amount:.2f}\n"
                        f"Límite: ${partner.credit_limit_custom:.2f}\n\n"
                        f"No se puede crear orden con este cliente.\n"
                        f"Comuníquese con Administración."
                    )
        
        _logger.warning("✅ Todas las órdenes pasaron validación de crédito")
        return super().create_from_ui(orders, draft)

    def _process_order(self, order, draft, existing_order=False):
        """
        Override para validar restricción de crédito AQUÍ donde sí tenemos partner_id
        SOLO si el método de pago es 'CUENTA DE CLIENTE'
        """
        # Buscar partner_id en los datos de la orden (ya debe estar disponible)
        partner_id = order.get('partner_id')
        payment_lines = order.get('payment_ids', [])
        
        # Solo validar restricción de crédito si el método de pago es "CUENTA DE CLIENTE"
        if not self._is_credit_account_payment_method(payment_lines):
            _logger.warning(f"🔴 Método de pago no es CUENTA DE CLIENTE, omitiendo validación en _process_order")
            return super()._process_order(order, draft, existing_order)
        
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            
            if partner.activate_credit and partner.is_credit_restricted:
                _logger.error(f"❌ BLOQUEANDO EN _process_order: {partner.name}")
                # Lanzar UserError para que Odoo lo serialice correctamente
                raise UserError(
                    f"❌ CLIENTE CON CRÉDITO RESTRINGIDO\n\n"
                    f"Cliente: {partner.name}\n"
                    f"Deuda: ${partner.total_invoiced_amount:.2f}\n"
                    f"Límite: ${partner.credit_limit_custom:.2f}\n\n"
                    f"No se puede crear orden con este cliente.\n"
                    f"Comuníquese con Administración."
                )
        
        return super()._process_order(order, draft, existing_order)

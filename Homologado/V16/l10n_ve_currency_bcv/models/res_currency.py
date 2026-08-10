from odoo import models, fields, api, _
import requests
import urllib3
from bs4 import BeautifulSoup
import logging

urllib3.disable_warnings()
_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def scrapper(self, currency):
        url = 'http://www.bcv.org.ve/'
        try:
            page = self._open_url(url)
            soup = BeautifulSoup(page, 'html.parser')
            div_id = {'USD': 'dolar', 'EUR': 'euro'}.get(currency.name)
            
            if not div_id:
                _logger.warning("Moneda no soportada: %s", currency.name)
                return 0
            
            content = soup.find('div', {"id": div_id})
            rate_text = content.find('strong').text.strip().replace('.', '').replace(',', '.')
            rate = float(rate_text)
            
            _logger.info("Tasa obtenida del BCV (%s): %s", currency.name, rate)
            return rate
        except Exception as e:
            _logger.error("Error al obtener tasa desde BCV (scrapper): %s", e)
            return 0

    def _open_url(self, url):
        try:
            return requests.get(url, verify=False).content
        except (ValueError, requests.exceptions.ConnectionError,
                requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            _logger.error("(_open_url) Connection BCV error: %s", e)

    def actualizar_productos2(self):
        # Actualiza únicamente los precios de venta list_price a partir de list_price_usd usando inverse_rate.
        for rec in self:
            _logger.info("Actualizando precios de venta para moneda: %s con tasa: %s", rec.name, rec.inverse_rate)

            # Actualización en product.template
            product_templates = self.env['product.template'].search([
                ('list_price_usd', '>', 0),
            ])
            for p in product_templates:
                if p.list_price_usd > 0:
                    p.list_price = p.list_price_usd * rec.inverse_rate
                    _logger.debug("Template [%s] actualizado: list_price=%s", p.name, p.list_price)

            # Actualización en product.product
            product_products = self.env['product.product'].search([
                ('list_price_usd', '>', 0),
            ])
            for p in product_products:
                if p.list_price_usd > 0:
                    p.list_price = p.list_price_usd * rec.inverse_rate
                    _logger.debug("Variante [%s] actualizada: list_price=%s", p.name, p.list_price)

            # Actualización en product.pricelist.item (manteniendo solo para fixed_price, si lo necesitas)
            pricelist_items = self.env['product.pricelist.item'].search([('currency_id', '=', rec.id)])
            for lp in pricelist_items:
                dominio = [('currency_id', '=', lp.company_id.currency_id.id or self.env.company.currency_id.id)]
                if lp.product_id:
                    dominio.append(('product_id', '=', lp.product_id.id))
                elif lp.product_tmpl_id:
                    dominio.append(('product_tmpl_id', '=', lp.product_tmpl_id.id))
                related_items = self.env['product.pricelist.item'].search(dominio)
                for p in related_items:
                    p.fixed_price = lp.fixed_price * rec.inverse_rate
                    _logger.debug("Pricelist item [%s] actualizado: fixed_price=%s", p.id, p.fixed_price)

            # Notificación en canal
            channel_id = self.env.ref('account_dual_currency.trm_channel')
            channel_id.message_post(
                body="Todos los productos han sido actualizados con la nueva tasa de cambio.",
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            _logger.info("Actualización de list_price finalizada para moneda: %s", rec.name)

    def cron_create_currency_rate(self, round_rate=4):
        companies = self.env['res.company'].search([])
        today = fields.Date.today()

        _logger.info("Inicio actualización tasas BCV (%s compañías encontradas)", len(companies))

        for company in companies:
            _logger.info("Procesando compañía: [%s] %s", company.id, company.name)

            if not company.currency_rate_bcv:
                _logger.info(" - Compañía %s no tiene activada la actualización de tasas BCV, saltando.", company.name)
                continue  # Saltar compañías sin configuración BCV

            company_env = self.env['res.currency.rate'].with_company(company)

            for currency in company.currency_available_ids:
                _logger.info(" -- Procesando moneda: [%s] %s en compañía [%s] %s", currency.id, currency.name, company.id, company.name)
                scrapper_flag = True

                # Bloqueo de días
                if company.block_days_bcv and company.days_bcv_ids:
                    blocked_days = [int(day.code) - 1 for day in company.days_bcv_ids]
                    if today.weekday() in blocked_days:
                        rate_bcv = self._old_rate(currency, company)
                        scrapper_flag = False
                        _logger.info(" --- Día bloqueado para compañía %s. Usando tasa anterior: %s", company.name, rate_bcv)

                # Días feriados
                if scrapper_flag:
                    bank_holidays = self.env['bank.holidays.bcv'].sudo().search([('date', '=', today)])
                    if bank_holidays:
                        rate_bcv = self._old_rate(currency, company)
                        scrapper_flag = False
                        _logger.info(" --- Día feriado para compañía %s. Usando tasa anterior: %s", company.name, rate_bcv)

                # Scrapper
                if scrapper_flag:
                    rate_bcv = self.scrapper(currency)
                    if not rate_bcv:
                        _logger.error(" --- Scrapper no devolvió tasa para %s en compañía %s. Usando tasa anterior.", currency.name, company.name)
                        rate_bcv = self._old_rate(currency, company)
                    else:
                        _logger.info(" --- Tasa obtenida del BCV para %s en compañía %s: %s", currency.name, company.name, rate_bcv)

                # Redondeo numérico correcto
                rate_bcv = round(float(rate_bcv), round_rate)
                _logger.info(" --- Tasa final redondeada para %s en compañía %s: %s", currency.name, company.name, rate_bcv)

                # Crear o actualizar la tasa usando contexto específico de la compañía
                values = {
                    'inverse_company_rate': rate_bcv,
                    'currency_id': currency.id,
                    'company_id': company.id,
                    'name': today,
                }

                rec = company_env.search([
                    ('currency_id', '=', currency.id),
                    ('name', '=', today),
                    ('company_id', '=', company.id)
                ])

                if rec:
                    rec.write(values)
                    _logger.info(" --- Tasa actualizada en registro existente para %s en compañía %s", currency.name, company.name)
                else:
                    company_env.create(values)
                    _logger.info(" --- Nuevo registro de tasa creado para %s en compañía %s", currency.name, company.name)

                # Actualizar productos usando contexto de la compañía
                currency.with_company(company).actualizar_productos2()
                _logger.info(" --- Productos actualizados para %s en compañía %s", currency.name, company.name)

        _logger.info("Finalización del cron de actualización tasas BCV")

    def _old_rate(self, currency, company):
        rec = self.env['res.currency.rate'].with_company(company).search([
            ('currency_id', '=', currency.id)
        ], limit=1, order='name desc')
        if rec:
            return rec.inverse_company_rate
        return 0

from odoo import models, fields, api, _
import requests
import urllib3
from bs4 import BeautifulSoup
import logging
import time
import re
import socket
from decimal import Decimal, getcontext, ROUND_HALF_UP
from datetime import datetime
from urllib.parse import urlparse

urllib3.disable_warnings()
_logger = logging.getLogger(__name__)

# Configuración de precisión (opcional, el ORM suele manejar esto, pero lo mantenemos por consistencia)
getcontext().prec = 50 


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # -------------------------------------------------------------------------
    # Métodos de Soporte (Scrapper)
    # -------------------------------------------------------------------------

    def _open_url_legacy(self, url):
        """Mantiene la lógica original para la acción que usa OdooBot."""
        try:
            return requests.get(url, verify=False, timeout=10).content
        except (
            ValueError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as e:
            _logger.error("(_open_url_legacy) Error de conexión al BCV: %s", e)
            return False

    def _open_url(self, url, timeout=20, retries=2, base_backoff=2, diagnose=False):
        """Método helper para manejar la conexión a la URL del BCV con reintentos."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OdooBCVBot/1.0; +https://www.bcv.org.ve/)"
        }

        if diagnose:
            host = urlparse(url).hostname
            if host:
                try:
                    resolved_ips = sorted({info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
                    _logger.info("(_open_url) Diagnostico DNS host=%s ips=%s", host, resolved_ips)
                except Exception as dns_error:
                    _logger.warning("(_open_url) Diagnostico DNS fallo host=%s error=%s", host, dns_error)

        for attempt in range(1, retries + 1):
            started_at = datetime.now()
            try:
                response = requests.get(url, headers=headers, verify=False, timeout=timeout)
                response.raise_for_status()
                elapsed = (datetime.now() - started_at).total_seconds()
                _logger.info(
                    "(_open_url) BCV respondió en %.2fs (intento %s/%s) URL=%s",
                    elapsed,
                    attempt,
                    retries,
                    url,
                )
                return response.content
            except ValueError as e:
                _logger.error("(_open_url) Error de valor al consultar BCV: %s", e)
                return False
            except requests.exceptions.RequestException as e:
                elapsed = (datetime.now() - started_at).total_seconds()
                retryable = isinstance(
                    e,
                    (
                        requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                    ),
                )

                if retryable and attempt < retries:
                    wait_seconds = base_backoff * (2 ** (attempt - 1))
                    _logger.warning(
                        "(_open_url) Fallo de conexión BCV (intento %s/%s) URL=%s: %s (%s) en %.2fs. Reintentando en %ss",
                        attempt,
                        retries,
                        url,
                        e,
                        type(e).__name__,
                        elapsed,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

                _logger.error(
                    "(_open_url) Error final de conexión al BCV (intento %s/%s) URL=%s: %s (%s) en %.2fs",
                    attempt,
                    retries,
                    url,
                    e,
                    type(e).__name__,
                    elapsed,
                )
                return False

        return False

    def _scrapper_bcv(self, currency_name):
        """
        Obtiene la tasa VEF por unidad de moneda (USD o EUR) del BCV.
        Esta versión conserva la lógica tradicional para el cron existente.
        """
        url = "http://www.bcv.org.ve/"
        try:
            page = self._open_url_legacy(url)
            if not page:
                return 0.0

            soup = BeautifulSoup(page, "html.parser")

            if currency_name == "USD":
                content = soup.find("div", {"id": "dolar"})
            elif currency_name == "EUR":
                content = soup.find("div", {"id": "euro"})
            else:
                return 0.0

            rate = 0.0
            if content and content.find("strong"):
                tasa_str = content.find("strong").text.strip()
                rate = float(tasa_str.replace(" ", "").replace(",", "."))
                _logger.info("::: TIPO DE CAMBIO BCV obtenido para %s ::: %s VEF/Unidad", currency_name, tasa_str)

            return rate
        except Exception as e:
            _logger.error("Error al obtener la tasa desde el BCV para %s: %s", currency_name, e)
            return 0.0

    def _scrapper_bcv_rates(self):
        """
        Obtiene las tasas VEF por unidad desde la página específica del SMC.
        Retorna una tupla: (rates, diag)
        rates: dict, por ejemplo {'USD': 443.25, 'EUR': 510.34}
        diag: datos resumidos de diagnóstico para soporte de red.
        """
        candidate_urls = [
            "https://www.bcv.org.ve/estadisticas/tipo-cambio-de-referencia-smc",
            "https://www.bcv.org.ve/estadisticas/otras-monedas",
        ]
        run_started_at = datetime.now()
        diag = {
            "urls": candidate_urls,
            "dns": {},
            "selected_url": None,
            "source": "bcv",
            "ok": False,
            "elapsed": 0.0,
            "error": None,
        }
        try:
            page = False
            selected_url = False
            for url in candidate_urls:
                host = urlparse(url).hostname
                if host and host not in diag["dns"]:
                    try:
                        ips = sorted({info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
                        diag["dns"][host] = ips
                    except Exception as dns_error:
                        diag["dns"][host] = ["DNS_ERROR:%s" % dns_error]

                page = self._open_url(url, timeout=12, retries=1, base_backoff=1, diagnose=True)
                if page:
                    selected_url = url
                    break

            if not page:
                _logger.error("No se pudo obtener respuesta de BCV en ninguna URL candidata")
                fallback_rates, fallback_error = self._scrapper_dolarapi_rates()
                diag["elapsed"] = (datetime.now() - run_started_at).total_seconds()
                if fallback_rates:
                    diag["ok"] = True
                    diag["source"] = "dolarapi"
                    diag["selected_url"] = "https://ve.dolarapi.com/v1/dolares/oficial + /v1/euros/oficial"
                    diag["error"] = "BCV timeout; fallback DolarAPI aplicado"
                    return fallback_rates, diag

                diag["error"] = "No HTTP response from BCV candidates; fallback failed: %s" % fallback_error
                return {}, diag

            _logger.info("Procesando tasas BCV desde URL=%s", selected_url)
            diag["selected_url"] = selected_url

            soup = BeautifulSoup(page, "html.parser")

            rates = {}

            # Intento 1: estructura HTML tradicional por ids.
            dom_map = {"USD": "dolar", "EUR": "euro"}
            for code, dom_id in dom_map.items():
                content = soup.find("div", {"id": dom_id})
                if content and content.find("strong"):
                    tasa_str = content.find("strong").text.strip()
                    try:
                        rates[code] = float(tasa_str.replace(" ", "").replace(",", "."))
                    except (TypeError, ValueError):
                        pass

            # Intento 2: fallback por texto libre (la página SMC suele incluir "USD 443,25870000").
            if "USD" not in rates or "EUR" not in rates:
                plain = soup.get_text(" ", strip=True)
                for code in ("USD", "EUR"):
                    if code in rates:
                        continue
                    match = re.search(r"\b%s\s+([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]+)" % code, plain)
                    if match:
                        raw = match.group(1).replace(".", "").replace(",", ".")
                        try:
                            rates[code] = float(raw)
                        except (TypeError, ValueError):
                            continue

            for code, value in rates.items():
                _logger.info("::: TIPO DE CAMBIO BCV obtenido para %s ::: %s VEF/Unidad", code, value)

            diag["ok"] = bool(rates)
            diag["elapsed"] = (datetime.now() - run_started_at).total_seconds()
            if not rates:
                fallback_rates, fallback_error = self._scrapper_dolarapi_rates()
                if fallback_rates:
                    diag["ok"] = True
                    diag["source"] = "dolarapi"
                    diag["selected_url"] = "https://ve.dolarapi.com/v1/dolares/oficial + /v1/euros/oficial"
                    diag["error"] = "BCV parse failed; fallback DolarAPI aplicado"
                    return fallback_rates, diag

                diag["error"] = "HTTP OK but could not parse USD/EUR; fallback failed: %s" % fallback_error
            return rates, diag
        except Exception as e:
            _logger.error("Error al obtener tasas desde el BCV: %s", e)
            fallback_rates, fallback_error = self._scrapper_dolarapi_rates()
            diag["elapsed"] = (datetime.now() - run_started_at).total_seconds()
            if fallback_rates:
                diag["ok"] = True
                diag["source"] = "dolarapi"
                diag["selected_url"] = "https://ve.dolarapi.com/v1/dolares/oficial + /v1/euros/oficial"
                diag["error"] = "BCV exception: %s; fallback DolarAPI aplicado" % e
                return fallback_rates, diag

            diag["error"] = "BCV exception: %s; fallback failed: %s" % (e, fallback_error)
            return {}, diag

    def _scrapper_dolarapi_rates(self):
        """
        Fallback de continuidad: obtiene tasa oficial USD/EUR publicada por DolarAPI.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OdooBCVBot/1.0)",
            "Accept": "application/json",
        }
        endpoints = {
            "USD": "https://ve.dolarapi.com/v1/dolares/oficial",
            "EUR": "https://ve.dolarapi.com/v1/euros/oficial",
        }
        rates = {}

        try:
            for code, endpoint in endpoints.items():
                response = requests.get(endpoint, headers=headers, timeout=10)
                response.raise_for_status()
                payload = response.json() or {}
                value = payload.get("promedio")
                if value is None:
                    return {}, "Campo 'promedio' ausente en %s" % endpoint
                rates[code] = float(value)

            _logger.warning(
                "Se aplicó fallback DolarAPI para tasas oficiales: USD=%s EUR=%s",
                rates.get("USD"),
                rates.get("EUR"),
            )
            return rates, None
        except Exception as e:
            return {}, str(e)

    def _old_rate(self, currency):
        """Devuelve el último valor almacenado en inverse_company_rate."""
        rec = self.env["res.currency.rate"].search(
            [("currency_id", "=", currency.id)], limit=1, order="name desc"
        )
        if rec:
            # Importante: Odoo guarda la tasa inversa como float en la DB, 
            # pero el método del ejemplo lo trata como Decimal/float.
            # Aquí asumimos que devuelve un valor convertible.
            return rec.inverse_company_rate
        return 0.0

    # -------------------------------------------------------------------------
    # Lógica de Odoo (Actualización de Tasas y Productos)
    # -------------------------------------------------------------------------

    def actualizar_productos(self):
        """
        Actualiza los precios en product.template, product.product y product.pricelist.item 
        utilizando el nuevo inverse_rate de la moneda.
        Se asume que la moneda base del producto es USD/EUR (por el campo 'list_price_usd').
        """
        # Itera sobre las monedas que invocaron el método (ej. USD, EUR)
        for rec in self:
            # 1. Actualización en Plantillas de Producto
            product_templates = self.env["product.template"].search(
                [("list_price_usd", ">", 0)] # Asume que existe un campo 'list_price_usd'
            )
            for p in product_templates:
                company = p.company_id or self.env.company
                # Obtener la tasa inversa (VEF/USD)
                rate = Decimal(str(rec.inverse_rate)) 
                usd_price = Decimal(str(p.list_price_usd))
                
                # Obtener el redondeo de la moneda de la compañía (VEF)
                quant = Decimal(str(company.currency_id.rounding or 0.01))
                
                # Nuevo Precio VEF = Precio USD * Tasa Inversa (VEF/USD)
                new_price = (usd_price * rate).quantize(quant, rounding=ROUND_HALF_UP)
                p.list_price = float(new_price)

            # 2. Actualización en Variantes de Producto (similar a la plantilla)
            product_products = self.env["product.product"].search(
                [("list_price_usd", ">", 0)] # Asume que existe un campo 'list_price_usd'
            )
            for p in product_products:
                company = p.company_id or self.env.company
                rate = Decimal(str(rec.inverse_rate))
                usd_price = Decimal(str(p.list_price_usd))
                quant = Decimal(str(company.currency_id.rounding or 0.01))
                new_price = (usd_price * rate).quantize(quant, rounding=ROUND_HALF_UP)
                p.list_price = float(new_price)

            # 3. Actualización de Items de Listas de Precio Relacionados
            # Esto busca items de lista de precios en USD/EUR y actualiza sus contrapartes en VEF.
            pricelist_items = self.env["product.pricelist.item"].search(
                [("currency_id", "=", rec.id)] # Items en la moneda actualizada (USD/EUR) (self to rec por ahora)
            )
            for lp in pricelist_items:
                # Buscar items de lista de precio relacionados cuya moneda es la de la compañía (VEF)
                dominio = [
                    (
                        "currency_id",
                        "=",
                        lp.company_id.currency_id.id or self.env.company.currency_id.id, # Moneda VEF
                    )
                ]
                if lp.product_id:
                    dominio.append(("product_id", "=", lp.product_id.id))
                elif lp.product_tmpl_id:
                    dominio.append(("product_tmpl_id", "=", lp.product_tmpl_id.id))
                
                related_items = self.env["product.pricelist.item"].search(dominio)

                for p in related_items:
                    company = lp.company_id or self.env.company
                    # Precio base en moneda extranjera (USD/EUR)
                    fixed = Decimal(str(lp.fixed_price)) 
                    # Tasa inversa
                    rate = Decimal(str(rec.inverse_rate)) 
                    quant = Decimal(str(company.currency_id.rounding or 0.01))
                    
                    # El ítem VEF se actualiza con el cálculo: Precio USD * Tasa Inversa
                    p.fixed_price = float(
                        (fixed * rate).quantize(quant, rounding=ROUND_HALF_UP)
                    )

            # 4. Notificación (asumiendo que existe el canal)
            channel_id = self.env.ref("account_dual_currency.trm_channel", raise_if_not_found=False)
            if channel_id:
                channel_id.message_post(
                    body="Todos los productos han sido actualizados con la nueva tasa de cambio del BCV.",
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
                
    def actualizar_tasa_bcv(self):
        """
        Método unificado para obtener y actualizar la tasa de cambio y los productos.
        """
        
        # 1. Definir las monedas a actualizar (USD y EUR)
        currencies_to_update = self.env['res.currency'].search([('name', 'in', ['USD', 'EUR'])])
        company = self.env.company
        today = fields.Date.today()

        for currency in currencies_to_update:
            # Nota: Aquí deberías incluir tu lógica de bloqueo de días/feriados si es necesaria
            rate_bcv = self._scrapper_bcv(currency.name)

            if rate_bcv > 0:
                # 2. Asignación del Inverse Rate
                # La tasa obtenida (VEF/USD) se guarda en 'inverse_company_rate'
                inverse_company_rate = format(float(rate_bcv), ".16f")

                _logger.info("Creando/Actualizando tasa para %s: Inverse Rate = %s", currency.name, inverse_company_rate)

                values = {
                    "inverse_company_rate": inverse_company_rate,
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": today,
                }

                # 3. Buscar y Crear/Actualizar el registro de la tasa del día
                rec = self.env["res.currency.rate"].search(
                    [
                        ("currency_id", "=", currency.id),
                        ("name", "=", today),
                        ("company_id", "=", company.id),
                    ]
                )

                if rec:
                    rec.write(values)
                else:
                    self.env["res.currency.rate"].create(values)

                # 4. Llamar a la actualización de productos (la parte que faltaba)
                currency.actualizar_productos()

            else:
                _logger.warning("No se pudo obtener una tasa válida del BCV para %s. Usando la tasa anterior.", currency.name)

    def actualizar_tasa_bcv_pruebas_manual(self):
        """
        Variante robusta para pruebas manuales con múltiples URLs y reintentos.
        """
        currencies_to_update = self.env['res.currency'].search([('name', 'in', ['USD', 'EUR'])])
        company = self.env.company
        today = fields.Date.today()

        rates_by_currency, diag = self._scrapper_bcv_rates()

        _logger.info(
            "[BCV DIAG RESUMEN] ok=%s source=%s selected_url=%s elapsed=%.2fs dns=%s urls=%s error=%s",
            diag.get("ok"),
            diag.get("source"),
            diag.get("selected_url"),
            diag.get("elapsed", 0.0),
            diag.get("dns"),
            diag.get("urls"),
            diag.get("error"),
        )

        for currency in currencies_to_update:
            rate_bcv = rates_by_currency.get(currency.name, 0.0)

            if rate_bcv > 0:
                # 2. Asignación del Inverse Rate
                # La tasa obtenida (VEF/USD) se guarda en 'inverse_company_rate'
                inverse_company_rate = format(float(rate_bcv), ".16f")
                
                _logger.info("Creando/Actualizando tasa para %s: Inverse Rate = %s", currency.name, inverse_company_rate)
                
                values = {
                    "inverse_company_rate": inverse_company_rate,
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": today,
                }
                
                # 3. Buscar y Crear/Actualizar el registro de la tasa del día
                rec = self.env["res.currency.rate"].search(
                    [
                        ("currency_id", "=", currency.id),
                        ("name", "=", today),
                        ("company_id", "=", company.id),
                    ]
                )

                if rec:
                    rec.write(values)
                else:
                    self.env["res.currency.rate"].create(values)
                
                # 4. Llamar a la actualización de productos (la parte que faltaba)
                currency.actualizar_productos() 

            else:
                _logger.warning("No se pudo obtener una tasa válida del BCV para %s. Usando la tasa anterior.", currency.name)
                # Opcional: Si el scrapper falla, podrías llamar a _old_rate y luego a actualizar_productos
                # para asegurar que los precios se actualicen si hay cambios en la configuración del producto.
                # old_rate = self._old_rate(currency)
                # if old_rate > 0:
                #     currency.actualizar_productos()
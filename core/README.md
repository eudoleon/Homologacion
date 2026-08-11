# Core — Módulos Odoo 19

Carpeta que contiene todos los módulos de **Odoo 19** para la **localización contable venezolana** y la **homologación ante el SENIAT**.

## Resumen

| Categoría | Módulos | Descripción general |
|-----------|---------|---------------------|
| **Localización contable** | `l10n_ve_invoice`, `l10n_ve_full` | Plan de cuentas, retenciones (ISLR, IVA, municipal), libros fiscales y configuración de facturación venezolana. |
| **Contabilidad dual (Bs/$)** | `account_dual_currency`, `account_report_multi_currency`, `tasa_bcv`, `forma_libre` | Manejo de Bs como moneda principal y $ como secundaria, tasas individuales, reportes multi-moneda y tasa BCV automática. |
| **Facturación electrónica / SENIAT** | `facturacion_digital`, `smart_seniat_homologacion`, `delivery_warning_seniat`, `web_notify` | Envío de factura digital, homologación SENIAT, control de cierre fiscal y notificaciones a usuarios. |
| **Utilidades y restricciones** | `auditlog`, `bi_advance_hide_show_menu`, `coletilla_sin_credito_fiscal`, `conditional_invoice_actions`, `easy_product_referencia`, `flete_descuento_odoo`, `hide_confirm_button`, `my_custom_module`, `my_invoice_module`, `my_version_footer`, `precio_negativo`, `purchase_REF`, `restrict_product_storable_on_invoice_customers`, `custom_expiration_text` | Auditoría, control de menús/botones, restricciones de negocio, formatos de impresión y personalizaciones de la interfaz. |

## Módulos incluidos

- **l10n_ve_invoice** — Base de la localización venezolana (plan de cuentas y facturación).
- **l10n_ve_full** — Localización completa: retenciones ISLR/IVA/municipal y libros fiscales.
- **account_dual_currency** — Contabilidad dual Bs/$ con tasa individual por documento.
- **account_report_multi_currency** — Reportes financieros en moneda seleccionada.
- **tasa_bcv** — Actualización automática de la tasa de cambio desde el BCV.
- **forma_libre** — Formato de impresión para facturas forma libre (doble moneda).
- **facturacion_digital** — Facturación digital con Smart-Factura Digital (migrado a Odoo 19).
- **smart_seniat_homologacion** — Homologación ante el SENIAT.
- **delivery_warning_seniat** — Notificación y control de cierre fiscal (SENIAT).
- **web_notify** — Notificaciones del periodo SENIAT a los usuarios.
- **auditlog** — Bitácora de auditoría de cambios en registros.
- **bi_advance_hide_show_menu** — Ocultar/mostrar menús y botones según permisos.
- **coletilla_sin_credito_fiscal** — Coletilla en documentos sin derecho a crédito fiscal.
- **conditional_invoice_actions** — Botón de acciones en facturas solo para usuarios autorizados.
- **easy_product_referencia** — Campo de referencia y búsqueda mejorada en productos.
- **flete_descuento_odoo** — Cálculo de flete + descuento con impuestos globales.
- **hide_confirm_button** — Oculta el botón de confirmar en pedidos de venta.
- **my_invoice_module** — Campo de impuestos no editable en líneas de factura.
- **precio_negativo** — Restricción de montos/cantidades negativas en facturas y órdenes.
- **purchase_REF** — Campo REF para conversión Bs → $ en líneas de compra.
- **restrict_product_storable_on_invoice_customers** — Restricción de productos en facturas de clientes.
- **my_custom_module** — Banner personalizado en la interfaz.
- **my_version_footer** — Versión de Odoo en el footer de configuración.
- **custom_expiration_text** — Banner de neutralización en el layout web.

> Para instalación, configuración y detalle de cada módulo, consulta el **`addons/README.md`** del repositorio.

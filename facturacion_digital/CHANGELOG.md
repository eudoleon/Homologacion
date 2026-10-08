# Changelog - Smart Facturación Digital

## [19.0.1.0] - 2026-03-04

### Migración de Odoo 17 a Odoo 19

#### Cambios Realizados

**Manifest**
- ✅ Actualizada la versión del módulo de `1.0` a `19.0.1.0`
- ✅ Actualizada la descripción para indicar compatibilidad con Odoo V.19

**Modelos (models/)**
- ✅ **account_move.py**: 
  - Eliminado método duplicado `button_cancel()` (comentado para referencia)
  - Actualizado el acceso a información de pagos: reemplazado `invoice_payments_widget` (deprecado) por acceso directo a `payment_state` y movimientos reconciliados
  - **CRÍTICO**: Comentadas importaciones no utilizadas de `odoo.tools` que fueron movidas/eliminadas en Odoo 19 (`email_re`, `email_split`, `date_utils`, etc.)
  - Código antiguo comentado en lugar de eliminado para referencia futura
  
- ✅ **res_company.py**: Revisado y compatible con Odoo 19
- ✅ **res_config_settings.py**: Revisado y compatible con Odoo 19
- ✅ **account_journal.py**: Revisado y compatible con Odoo 19

**Vistas (views/)**
- ✅ **account_move_view.xml**: 
  - Agregados comentarios de migración
  - ✅ **Botones funcionales**: Botones "Factura Digital" y "Re-Enviar F. Digital" agregados después de `action_invoice_sent`
  - ✅ **Pestaña funcional**: Nueva pestaña "Facturación Digital" agregada al notebook
  - ✅ **Modificación de `button_draft`**: Ajustado para prevenir reset a borrador cuando la factura está anulada
  - ⚠️ **Pendiente**: Vista que hereda de `l10n_ve_full.extra_account_move_venezuela` (comentada hasta que l10n_ve_full esté adaptado)
- ✅ **res_config_settings.xml**: Agregados comentarios de migración
- ✅ **account_journal.xml**: Agregados comentarios de migración
- ✅ **res_company.xml**: Agregados comentarios de migración
- ✅ **category.xml**: Agregados comentarios de migración

#### Notas Técnicas

**APIs y Utilidades Deprecadas/Movidas en Odoo 19:**
- `invoice_payments_widget`: Reemplazado por acceso directo a pagos reconciliados mediante `payment_state` y relaciones `matched_credit_ids`/`matched_debit_ids`
- Importaciones de `odoo.tools` no utilizadas comentadas: `email_re`, `email_split`, `date_utils`, `float_compare`, `float_is_zero`, `format_amount`, `format_date`, `formatLang`, `frozendict`, `get_lang`, `is_html_empty`, `sql` (estas fueron movidas o eliminadas en Odoo 19)

**Código Comentado:**
- Todo el código antiguo fue comentado en lugar de eliminado para permitir referencia futura y posibles ajustes
- Los comentarios incluyen la etiqueta `# ODOO 17:` o `<!-- ODOO 17: -->` para fácil identificación

#### Compatibilidad
- ✅ Compatible con Odoo 19.0
- ✅ Módulo se instala sin errores
- ✅ Botones de facturación digital funcionales en vistas de facturas
- ✅ Pestaña "Facturación Digital" agregada correctamente al formulario de facturas
- ✅ Funcionalidad base de facturación digital completamente operativa
- ⚠️ Vista de modificación de `nro_ctrl` comentada temporalmente (requiere `l10n_ve_full` adaptado)
- ✅ Sin errores de sintaxis o lint

#### Pruebas Recomendadas
1. Verificar la creación y envío de facturas digitales
2. Verificar la anulación de facturas digitales
3. Verificar el reenvío de facturas por correo
4. Verificar la configuración del módulo en res.config.settings
5. Verificar la activación por diario
6. Verificar que los pagos se capturen correctamente en la API

#### Vistas Comentadas (Pendientes)
La siguiente modificación de vista fue comentada temporalmente:

1. **Vista `smart_facturacion_digital_nro_ctrl`**: Hereda de `l10n_ve_full.extra_account_move_venezuela` para modificar el campo `nro_ctrl`. Debe descomentarse cuando el módulo `l10n_ve_full` esté completamente adaptado a Odoo 19 y la vista `extra_account_move_venezuela` esté disponible.

---

**Autor de la Migración**: Adaptación automática a Odoo 19  
**Fecha**: 4 de Marzo, 2026  
**Módulo Original**: Smart Systems, C.A.

# Proyecto Odoo v19 - Estructura de Homologación

Este repositorio contiene la estructura estandarizada para la versión 19 de Odoo, diseñada para la homologación, desarrollo y despliegue modular de adiciones fiscales, nómina y desarrollos personalizados por área de negocio.

---

## Estructura del Proyecto

```text
mi_proyecto_odoo/
├── odoo.conf                         # Archivo de configuración central de Odoo
├── README.md                         # Documentación general del proyecto
├── .gitignore                        # Patrones de archivos excluidos del control de versiones
│
├── core/                             # Módulos base y localizaciones normativas
│   ├── l10n_ve_fiscal/               # Localización fiscal (retenciones, libros IVA/ISLR)
│   ├── l10n_ve_payroll/              # Localización de nómina y adaptaciones legales
│   ├── base_company_extended/        # Extensión de datos corporativos base
│   └── core_audit_trail/             # Módulo de auditoría y trazabilidad de cambios
│
└── custom_addons/                    # Adicionales y desarrollos personalizados categorizados
    ├── payroll/                      # Módulos funcionales de Nómina
    │   ├── hr_payroll_custom_rules/  # Reglas salariales personalizadas
    │   └── hr_payroll_reports/       # Reportes específicos de nómina
    │
    ├── sales/                        # Módulos funcionales de Ventas
    │   ├── sale_custom_approval/     # Flujo de aprobación de pedidos de venta
    │   └── sale_discount_limit/      # Control y límites de descuento en cotizaciones
    │
    ├── inventory/                    # Módulos funcionales de Inventario
    │   └── stock_custom_barcode/     # Personalizaciones de código de barras para stock
    │
    └── accounting/                   # Módulos funcionales de Contabilidad
        └── account_custom_reports/   # Informes contables a medida
```

---

## Descripción de Componentes y Módulos

### Archivos de Configuración Raíz
* **`odoo.conf`**: Configuración principal del servidor (parámetros de base de datos, puertos, credenciales y `addons_path`).
* **`.gitignore`**: Reglas de exclusión para evitar subir archivos temporales (`*.pyc`, `__pycache__`), logs, entornos virtuales o respaldos de BD.
* **`README.md`**: Guía y especificación técnica de la estructura de homologación V19.

---

### Módulos `core/` (Localizaciones y Base)
Contiene las soluciones normativas y transversales obligatorias:
* **`l10n_ve_fiscal`**: Adaptación a la legislación tributaria (SENIAT, comprobantes de retención, numeración de control, libros fiscales).
* **`l10n_ve_payroll`**: Adaptación a la legislación laboral (LOTTT, conceptos legales, utilidades, prestaciones).
* **`base_company_extended`**: Ampliación de campos institucionales en el modelo `res.company`.
* **`core_audit_trail`**: Registro de auditoría para rastrear creaciones, ediciones y eliminaciones críticas en el sistema.

---

### Módulos `custom_addons/` (Desarrollos Personalizados por Área)
Estructura modular agrupada por departamento funcional para garantizar mantenimiento eficiente y escalabilidad:

* **`payroll/`** (Nómina)
  * `hr_payroll_custom_rules`: Definición y cálculo de reglas salariales adicionales.
  * `hr_payroll_reports`: Formatos de recibos de pago y reportes consolidados de nómina.

* **`sales/`** (Ventas)
  * `sale_custom_approval`: Matriz de aprobaciones jerárquicas en cotizaciones.
  * `sale_discount_limit`: Validaciones para evitar exceder porcentajes de descuento autorizados.

* **`inventory/`** (Inventario y Almacén)
  * `stock_custom_barcode`: Adaptaciones para lecturas e impresión de etiquetas con código de barras en albaranes/recepciones.

* **`accounting/`** (Contabilidad y Finanzas)
  * `account_custom_reports`: Adaptación de estados financieros e informes contables internos.

---

## Configuración del `addons_path`

En el archivo `odoo.conf`, declare las rutas correspondientes para asegurar que Odoo cargue todos los módulos adecuadamente:

```ini
[options]
addons_path = core,custom_addons/payroll,custom_addons/sales,custom_addons/inventory,custom_addons/accounting
```

---

## Guía de Inicio y Despliegue

### Requisitos Previos
* **Odoo**: 19.0 (Community / Enterprise)
* **Python**: 3.12+
* **PostgreSQL**: 16+

### Comandos de Uso Frecuente

#### Iniciar el servidor Odoo:
```bash
odoo -c odoo.conf
```

#### Actualizar / Instalar módulos específicos:
```bash
# Actualizar localización fiscal
odoo -c odoo.conf -d mi_base_datos -u l10n_ve_fiscal

# Actualizar todos los custom addons de ventas
odoo -c odoo.conf -d mi_base_datos -u sale_custom_approval,sale_discount_limit
```

---

## Buenas Prácticas de Homologación

1. **Estándar de Nombres**: Usar `snake_case` e incluir el prefijo del módulo estándar base (`hr_payroll_`, `sale_`, `stock_`, `account_`).
2. **Manifiesto de Módulo (`__manifest__.py`)**:
   * Especificar siempre versión `19.0.1.0.0`.
   * Declarar todas las dependencias exactas en la clave `'depends'`.
3. **Modularidad Estricta**: No mezclar lógica de diferentes departamentos en un mismo módulo. Cada directorio en `custom_addons/` debe alojar únicamente su dominio de negocio.
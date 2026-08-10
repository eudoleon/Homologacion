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
├── core/                             
│   ├── l10n_ve_fiscal/               
│   ├── l10n_ve_payroll/             
│   ├── base_company_extended/       
│   └── core_audit_trail/             
│
└── custom_addons/                    # Adicionales y desarrollos personalizados categorizados
    ├── payroll/                      
    │   ├── hr_payroll_custom_rules/  
    │   └── hr_payroll_reports/       
    │
    ├── sales/                        
    │   ├── sale_custom_approval/     
    │   └── sale_discount_limit/      
    │
    ├── inventory/                    
    │   └── stock_custom_barcode/     
    │
    └── accounting/                   
        └── account_custom_reports/   
```

---

## Descripción de Componentes y Módulos

### Archivos de Configuración Raíz
* **`odoo.conf`**: Configuración principal del servidor (parámetros de base de datos, puertos, credenciales y `addons_path`).
* **`.gitignore`**: Reglas de exclusión para evitar subir archivos temporales (`*.pyc`, `__pycache__`), logs, entornos virtuales o respaldos de BD.
* **`README.md`**: Guía y especificación técnica de la estructura de homologación V19.

---

### Módulos `core/` (Localizaciones y Base)
Contiene las soluciones normativas y transversales obligatorias
---

### Módulos `custom_addons/` (Desarrollos Personalizados por Área)
Estructura modular agrupada por departamento funcional para garantizar mantenimiento eficiente y escalabilidad

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
* **Odoo**: 19.0 (Enterprise)
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

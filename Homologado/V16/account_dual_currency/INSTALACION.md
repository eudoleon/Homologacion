# Instrucciones de Instalación y Actualización

## 📦 Actualización del Módulo

### 1. Actualizar el Módulo en Odoo

#### Opción A: Desde la Interfaz de Odoo
1. Ir a **Apps** (Aplicaciones)
2. Buscar "account_dual_currency"
3. Click en el menú de 3 puntos
4. Seleccionar **"Actualizar"**

#### Opción B: Desde Línea de Comandos
```bash
# Detener el servicio Odoo
sudo systemctl stop odoo

# Actualizar el módulo
odoo-bin -u account_dual_currency -d NOMBRE_BASE_DATOS --stop-after-init

# Reiniciar el servicio
sudo systemctl start odoo
```

### 2. Verificar Instalación

Después de actualizar, verificar que los nuevos campos aparezcan:

1. Ir a **Inventario > Productos > Productos**
2. Abrir cualquier producto
3. En la sección de **Inventario**, verificar que aparezcan:
   - Costo $ (standard_price_usd) - existente, ahora automático
   - Última actualización de Costo (nuevo)
   - Tasa USD del Costo (nuevo, visible después del primer cambio)

## 🔄 Migración de Datos Existentes

### Script de Migración

Para productos que ya tienen costos definidos, ejecutar este script en la consola de Odoo:

```python
# Conectarse a la consola Odoo
# Shell: odoo shell -d NOMBRE_BASE_DATOS

# Copiar y ejecutar:
from odoo import fields

# Obtener productos con costo pero sin datos de tracking
products = env['product.product'].search([
    ('standard_price', '>', 0),
    ('standard_price_last_update', '=', False)
])

print(f"Productos a migrar: {len(products)}")

# Obtener la tasa USD actual
currency_usd = env.company.currency_id_dif

if not currency_usd or currency_usd.inverse_rate <= 0:
    print("ERROR: No se puede obtener la tasa USD")
    print("Verificar configuración de currency_id_dif en la compañía")
else:
    print(f"Tasa USD actual: {currency_usd.inverse_rate}")
    
    migrated = 0
    errors = 0
    
    for product in products:
        try:
            new_standard_price_usd = product.standard_price / currency_usd.inverse_rate
            
            # Usar super() para evitar triggear el write() personalizado
            env['product.product'].browse(product.id).with_context(
                tracking_disable=True
            ).write({
                'standard_price_usd': new_standard_price_usd,
                'standard_price_last_update': fields.Datetime.now(),
                'standard_price_usd_rate': currency_usd.inverse_rate,
            })
            
            migrated += 1
            
            # Commit cada 100 productos
            if migrated % 100 == 0:
                print(f"Progreso: {migrated}/{len(products)}")
                env.cr.commit()
                
        except Exception as e:
            errors += 1
            print(f"Error en producto {product.name} (ID: {product.id}): {str(e)}")
    
    # Commit final
    env.cr.commit()
    
    print(f"\n✓ Migración completada!")
    print(f"  - Productos migrados: {migrated}")
    print(f"  - Errores: {errors}")
```

### Script Alternativo (Más Simple)

Si prefieres un script más simple que use el módulo directamente:

```python
# En consola Odoo
exec(open('/ruta/completa/a/account_dual_currency/tests/test_standard_price_usd.py').read())
migrate_existing_products()
```

## 🧪 Pruebas Post-Instalación

### Test 1: Cambio Manual
```python
# En consola Odoo
product = env['product.product'].search([('type', '=', 'product')], limit=1)

print(f"Producto: {product.name}")
print(f"Costo VEF antes: {product.standard_price}")
print(f"Costo USD antes: {product.standard_price_usd}")

# Cambiar el costo
product.write({'standard_price': product.standard_price + 100})

# Recargar
product.invalidate_cache()

print(f"\nCosto VEF después: {product.standard_price}")
print(f"Costo USD después: {product.standard_price_usd}")
print(f"Fecha actualización: {product.standard_price_last_update}")
print(f"Tasa registrada: {product.standard_price_usd_rate}")

# Validar cálculo
calculated = product.standard_price_usd * product.standard_price_usd_rate
print(f"\nValidación: {product.standard_price} == {calculated}")
print(f"Diferencia: {abs(product.standard_price - calculated)}")
```

### Test 2: Recepción de Compra

1. Crear una orden de compra
2. Confirmarla
3. Recibir los productos
4. Verificar que los campos se actualizaron en el producto

### Test 3: Verificación en Interfaz

1. Abrir un producto
2. Cambiar el campo "Costo"
3. Guardar
4. Verificar que:
   - "Costo $" se actualizó automáticamente
   - "Última actualización de Costo" muestra la fecha/hora actual
   - "Tasa USD del Costo" muestra la tasa actual

## 🔧 Troubleshooting

### Problema: Los campos no se actualizan

**Solución:**
```python
# Verificar que currency_id_dif está configurado
company = env.company
print(f"Currency ID Dif: {company.currency_id_dif}")
print(f"Tasa: {company.currency_id_dif.inverse_rate if company.currency_id_dif else 'N/A'}")
```

### Problema: Error "maximum recursion depth"

**Causa:** El método write() está en recursión infinita
**Solución:** Ya está resuelto en el código usando `super()` directo

### Problema: Los campos no aparecen en la vista

**Solución:**
1. Limpiar cache del navegador
2. Actualizar el módulo: `odoo-bin -u account_dual_currency -d DB_NAME`
3. Verificar que no haya errores en el log de Odoo

### Problema: La tasa USD es 0 o None

**Solución:**
```python
# Verificar y configurar la moneda diferente
company = env.company
usd = env['res.currency'].search([('name', '=', 'USD')], limit=1)

if usd:
    company.write({'currency_id_dif': usd.id})
    print(f"Currency configurada: {usd.name}")
    print(f"Tasa actual: {usd.inverse_rate}")
else:
    print("ERROR: No se encuentra la moneda USD")
    print("Activar USD desde Contabilidad > Configuración > Monedas")
```

## 📋 Checklist Post-Instalación

- [ ] Módulo actualizado sin errores
- [ ] Campos visibles en formulario de producto
- [ ] Migración de datos ejecutada exitosamente
- [ ] Test de cambio manual exitoso
- [ ] Verificación en interfaz OK
- [ ] Logs de Odoo sin errores relacionados
- [ ] Documentación entregada al equipo

## 📞 Soporte

Si encuentras problemas:
1. Revisar logs de Odoo: `/var/log/odoo/odoo-server.log`
2. Verificar la documentación en `CHANGELOG_STANDARD_PRICE_USD.md`
3. Ejecutar tests en `tests/test_standard_price_usd.py`

## 📅 Fecha de Instalación
Registrar aquí: ___________________

## ✅ Instalado por
Nombre: ___________________
Fecha: ___________________

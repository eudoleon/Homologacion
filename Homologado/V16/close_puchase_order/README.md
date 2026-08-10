Close Purchase Order module

Este módulo añade la posibilidad de marcar pedidos de compra (`purchase.order`) como "Totalmente facturados" desde el formulario y mediante una acción de servidor.

Instalación y prueba

1. Copia la carpeta `close_puchase_order` en el directorio de addons de tu instancia de Odoo o añade la ruta a `addons_path`.
2. Reinicia el servidor de Odoo y actualiza la lista de apps.
3. Instala el módulo "Close Purchase Order".
4. Abre un pedido de compra y haz clic en el botón "Cerrar Orden" en el encabezado del pedido. El módulo cambiará el campo interno `invoice_status` de `'to invoice'` a `'invoiced'`.
5. También puedes seleccionar pedidos y usar la acción de servidor llamada "Marcar pedido de compra como facturado" desde el menú Acciones -> Acciones de servidor, o ejecutar la acción desde Ajustes > Técnicos > Acciones automatizadas.

Notas

- El módulo no permite marcar pedidos cancelados como facturados.
- Solo cambia pedidos cuyo `invoice_status` sea `'to invoice'`.
- Añade una nota en el chatter indicando quién realizó la acción.

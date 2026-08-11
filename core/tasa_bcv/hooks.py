from datetime import datetime, timedelta
# Ya no necesitas importar api ni SUPERUSER_ID para esto

def set_bcv_cron_nextcall(env): # Cambiado: ahora recibe 'env' directamente
    # Buscamos el cron usando el env que nos da Odoo
    cron = env.ref('tasa_bcv.ir_cron_actualizar_tasa_bcv', raise_if_not_found=False)
    
    if not cron:
        return

    # Calculamos la fecha para mañana a las 2 AM
    tomorrow_2am = (datetime.now() + timedelta(days=1)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )

    # Escribimos directamente en el objeto
    cron.write({
        'nextcall': tomorrow_2am
    })
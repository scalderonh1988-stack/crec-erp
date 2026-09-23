import sqlite3
import json
from db_local import DB_NAME
from conexion import hay_internet

def sincronizar_ventas_pendientes(supabase_client):
    """Sube las ventas offline guardadas a Supabase."""
    if not hay_internet():
        return 0, "Sin conexión a internet."

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fecha, rut_empresa, monto_total, metodo_pago, items_json FROM ventas_pendientes WHERE estado = 'pendiente'")
    filas = cursor.fetchall()

    if not filas:
        conn.close()
        return 0, "No hay ventas pendientes."

    sincronizadas = 0
    for fila in filas:
        v_id, fecha, rut, monto, metodo, items_str = fila
        items = json.loads(items_str)
        
        try:
            # Insertar en la nube
            data_venta = {
                "fecha": fecha,
                "rut_empresa": rut,
                "monto_total": monto,
                "metodo_pago": metodo,
                "items": items,
                "origen": "offline_sync"
            }
            supabase_client.table("ventas").insert(data_venta).execute()
            
            # Marcar como sincronizada localmente
            cursor.execute("UPDATE ventas_pendientes SET estado = 'sincronizado' WHERE id = ?", (v_id,))
            sincronizadas += 1
        except Exception as e:
            print(f"Error sincronizando venta {v_id}: {e}")

    conn.commit()
    conn.close()
    return sincronizadas, f"Se sincronizaron {sincronizadas} ventas con éxito."
import sqlite3
import json
from datetime import datetime

DB_NAME = "pos_local_cache.db"

def inicializar_db_local():
    """Crea las tablas locales si no existen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Catálogo local de productos (para escanear sin internet)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos_cache (
            codigo_barras TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            stock INTEGER DEFAULT 0
        )
    """)
    
    # 2. Cola de ventas pendientes de subir a la nube
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            rut_empresa TEXT NOT NULL,
            monto_total REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            items_json TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente'
        )
    """)
    
    conn.commit()
    conn.close()

def guardar_catalogo_local(productos):
    """Guarda o actualiza el catálogo descargado desde Supabase."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for p in productos:
        cursor.execute("""
            INSERT OR REPLACE INTO productos_cache (codigo_barras, nombre, precio, stock)
            VALUES (?, ?, ?, ?)
        """, (p.get("codigo_barras"), p.get("nombre"), float(p.get("precio", 0)), int(p.get("stock", 0))))
    conn.commit()
    conn.close()

def buscar_producto_local(codigo):
    """Busca un producto en la memoria local por código de barras."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT codigo_barras, nombre, precio, stock FROM productos_cache WHERE codigo_barras = ?", (codigo,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"codigo_barras": row[0], "nombre": row[1], "precio": row[2], "stock": row[3]}
    return None

def guardar_venta_offline(rut_empresa, monto_total, metodo_pago, items):
    """Registra una venta en la cola local si no hay internet."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ventas_pendientes (fecha, rut_empresa, monto_total, metodo_pago, items_json, estado)
        VALUES (?, ?, ?, ?, ?, 'pendiente')
    """, (datetime.now().isoformat(), rut_empresa, monto_total, metodo_pago, json.dumps(items)))
    conn.commit()
    conn.close()
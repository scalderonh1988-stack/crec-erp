import os
import json
import hmac
import hashlib
import sqlite3
from datetime import datetime

# Clave secreta interna para firmar digitalmente la licencia (No compartir)
SECRET_KEY = b"CREC_ERP_SECRET_LICENSING_KEY_2026_SECURE_HMAC"
DB_LOCAL = "crec_local.db"


def _obtener_conexion():
    """Conecta a la base de datos local SQLite."""
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_tabla_licencia():
    """Crea la tabla de licencia local si no existe."""
    conn = _obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licencia_local (
            rut_empresa TEXT PRIMARY KEY,
            fecha_expiracion TEXT,
            licencia_activa INTEGER,
            ultima_ejecucion TEXT,
            firma_digital TEXT
        )
    """)
    conn.commit()
    conn.close()


def _generar_firma(rut_empresa: str, fecha_expiracion: str, licencia_activa: bool) -> str:
    """Genera una firma HMAC-SHA256 para evitar que el usuario altere los datos en SQLite."""
    payload = f"{rut_empresa.strip().upper()}|{fecha_expiracion}|{1 if licencia_activa else 0}"
    return hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def guardar_licencia_online(rut_empresa: str, fecha_expiracion: str, licencia_activa: bool):
    """
    Se ejecuta cuando el sistema está ONLINE.
    Guarda o actualiza el estado oficial de la licencia en SQLite con su firma digital.
    """
    inicializar_tabla_licencia()
    
    rut_clean = rut_empresa.strip().upper()
    activa_int = 1 if licencia_activa else 0
    firma = _generar_firma(rut_clean, fecha_expiracion, licencia_activa)
    ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = _obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO licencia_local (rut_empresa, fecha_expiracion, licencia_activa, ultima_ejecucion, firma_digital)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(rut_empresa) DO UPDATE SET
            fecha_expiracion = excluded.fecha_expiracion,
            licencia_activa = excluded.licencia_activa,
            ultima_ejecucion = excluded.ultima_ejecucion,
            firma_digital = excluded.firma_digital
    """, (rut_clean, fecha_expiracion, activa_int, ahora_str, firma))
    
    conn.commit()
    conn.close()


def validar_licencia_offline(rut_empresa: str) -> dict:
    """
    Se ejecuta cuando el sistema está OFFLINE.
    Retorna un diccionario con el resultado de la validación:
    {
        "valida": True/False,
        "mensaje": "...",
        "dias_restantes": int,
        "fecha_expiracion": str
    }
    """
    inicializar_tabla_licencia()
    rut_clean = rut_empresa.strip().upper()

    conn = _obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM licencia_local WHERE rut_empresa = ?", (rut_clean,))
    registro = cursor.fetchone()

    if not registro:
        conn.close()
        return {
            "valida": False,
            "mensaje": "No existe un registro local de licencia para esta empresa. Conéctate a internet para inicializarla.",
            "dias_restantes": 0,
            "fecha_expiracion": None
        }

    fecha_exp_str = registro["fecha_expiracion"]
    lic_activa = bool(registro["licencia_activa"])
    ultima_ejec_str = registro["ultima_ejecucion"]
    firma_guardada = registro["firma_digital"]

    # 1. VALIDACIÓN DE INTEGRIDAD (Firma Digital HMAC)
    firma_calculada = _generar_firma(rut_clean, fecha_exp_str, lic_activa)
    if not hmac.compare_digest(firma_guardada, firma_calculada):
        conn.close()
        return {
            "valida": False,
            "mensaje": "🚨 ALERTA DE SEGURIDAD: La licencia local ha sido manipulada ilegalmente.",
            "dias_restantes": 0,
            "fecha_expiracion": fecha_exp_str
        }

    # 2. VALIDACIÓN DE ESTADO ACTIVO
    if not lic_activa:
        conn.close()
        return {
            "valida": False,
            "mensaje": "❌ La licencia de esta empresa se encuentra suspendida o inactiva.",
            "dias_restantes": 0,
            "fecha_expiracion": fecha_exp_str
        }

    # 3. CONTROL ANTI-RELOJ (Anti-Tamper)
    ahora = datetime.now()
    try:
        ultima_ejec = datetime.strptime(ultima_ejec_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        ultima_ejec = ahora

    if ahora < ultima_ejec:
        conn.close()
        return {
            "valida": False,
            "mensaje": "⚠️ DETECTADO CAMBIO DE FECHA EN EL SISTEMA: La hora actual es anterior a la última ejecución registrada. Por favor ajusta la fecha o conéctate a internet.",
            "dias_restantes": 0,
            "fecha_expiracion": fecha_exp_str
        }

    # 4. VALIDACIÓN DE FECHA DE EXPIRACIÓN
    try:
        if "T" in fecha_exp_str:
            fecha_exp = datetime.strptime(fecha_exp_str.split("T")[0], "%Y-%m-%d")
        else:
            fecha_exp = datetime.strptime(fecha_exp_str.split(" ")[0], "%Y-%m-%d")
    except Exception:
        conn.close()
        return {
            "valida": False,
            "mensaje": "Formato de fecha de expiración no válido en el registro de licencia.",
            "dias_restantes": 0,
            "fecha_expiracion": fecha_exp_str
        }

    dias_restantes = (fecha_exp.date() - ahora.date()).days

    if dias_restantes < 0:
        conn.close()
        return {
            "valida": False,
            "mensaje": f"❌ LICENCIA EXPIRADA: Tu licencia venció hace {abs(dias_restantes)} días. Conéctate a internet para renovar.",
            "dias_restantes": dias_restantes,
            "fecha_expiracion": fecha_exp_str
        }

    # 5. ACTUALIZAR 'ultima_ejecucion'
    ahora_actualizado = ahora.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE licencia_local 
        SET ultima_ejecucion = ? 
        WHERE rut_empresa = ?
    """, (ahora_actualizado, rut_clean))
    conn.commit()
    conn.close()

    return {
        "valida": True,
        "mensaje": f"Licencia offline válida. Expira en {dias_restantes} días.",
        "dias_restantes": dias_restantes,
        "fecha_expiracion": fecha_exp_str
    }
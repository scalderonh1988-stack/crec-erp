import os
import json
from datetime import datetime

CACHE_DIR = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'CREC_ERP_POS', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

class RespuestaSimulada:
    """Simula la respuesta de Supabase cuando estamos en modo Offline"""
    def __init__(self, data):
        self.data = data if data is not None else []

class ConsultaTablaCacheada:
    """Intercepta las consultas a Supabase para leer/guardar caché local"""
    def __init__(self, consulta_real, nombre_tabla):
        self.consulta_real = consulta_real
        self.nombre_tabla = nombre_tabla

    def __getattr__(self, item):
        try:
            attr = getattr(self.consulta_real, item)
            if callable(attr):
                def wrapper(*args, **kwargs):
                    res = attr(*args, **kwargs)
                    return ConsultaTablaCacheada(res, self.nombre_tabla)
                return wrapper
            return attr
        except Exception:
            return lambda *args, **kwargs: self

    def execute(self):
        archivo_cache = os.path.join(CACHE_DIR, f"{self.nombre_tabla}.json")
        try:
            # 1. Intentar consulta real en vivo
            resultado = self.consulta_real.execute()
            
            # 2. Si responde con datos, actualizar foto local
            if hasattr(resultado, 'data') and isinstance(resultado.data, list):
                with open(archivo_cache, 'w', encoding='utf-8') as f:
                    json.dump({
                        "ultima_conexion": datetime.now().isoformat(),
                        "datos": resultado.data
                    }, f, ensure_ascii=False, indent=2)
            return resultado
            
        except Exception:
            # 3. Si falla la red (sin Wi-Fi), cargar la copia local guardada
            if os.path.exists(archivo_cache):
                try:
                    with open(archivo_cache, 'r', encoding='utf-8') as f:
                        contenido = json.load(f)
                        return RespuestaSimulada(contenido.get("datos", []))
                except Exception:
                    return RespuestaSimulada([])
            return RespuestaSimulada([])

class ClienteSupabaseConCache:
    """Envoltorio completo que intercepta table() y from_()"""
    def __init__(self, cliente_real):
        self.cliente_real = cliente_real

    def table(self, nombre_tabla):
        return ConsultaTablaCacheada(self.cliente_real.table(nombre_tabla), nombre_tabla)

    def from_(self, nombre_tabla):
        return ConsultaTablaCacheada(self.cliente_real.from_(nombre_tabla), nombre_tabla)

    def __getattr__(self, item):
        return getattr(self.cliente_real, item)

def obtener_tabla_con_cache(supabase_client, nombre_tabla: str):
    res = supabase_client.table(nombre_tabla).select("*").execute()
    return getattr(res, 'data', []), True
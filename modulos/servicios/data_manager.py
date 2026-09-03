import os
import pandas as pd
import streamlit as st
from pathlib import Path
import shutil
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA NUBE (SUPABASE) ---
SUPABASE_URL = "https://dmkjlcjrobszhwasrofc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRta2psY2pyb2Jzemh3YXNyb2ZjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjA1NjY3OCwiZXhwIjoyMTAxNjMyNjc4fQ.PSk-oNFl16Inaidztx3ixOz0ahzQuV1SvF4CBhl44gg"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_TENANTS_DIR = "clientes"

def get_current_tenant() -> str:
    """
    Obtiene el identificador exacto del negocio activo desde cualquier 
    variable de sesión posible en tu sistema.
    """
    for key in ["negocio_actual", "negocio_seleccionado", "tenant_id", "negocio_asignado"]:
        if key in st.session_state and st.session_state[key]:
            val = str(st.session_state[key]).strip()
            if val and val != "admin_general":
                return val
    return ""

def get_tenant_path(filename: str) -> str:
    tenant_id = get_current_tenant() or "negocio_demo"
    tenant_dir = os.path.join(BASE_TENANTS_DIR, tenant_id)
    os.makedirs(tenant_dir, exist_ok=True)
    return os.path.join(tenant_dir, filename)

def load_excel_data(filename: str) -> pd.DataFrame:
    file_path = get_tenant_path(filename)
    if os.path.exists(file_path):
        return pd.read_excel(file_path)
    return pd.DataFrame()

def save_excel_data(df: pd.DataFrame, filename: str):
    file_path = get_tenant_path(filename)
    df.to_excel(file_path, index=False)

def cargar_maestro_clientes():
    """
    Carga los clientes asegurando un aislamiento total entre empresas.
    Bajo ninguna circunstancia descarga la tabla completa sin filtrar.
    """
    try:
        tenant_id = get_current_tenant()
        maestro = {}
        
        # Si no hay tenant en sesión, bloqueamos la salida por seguridad absoluta
        if not tenant_id:
            print("⚠️ Advertencia: No hay un tenant activo en la sesión para cargar clientes.")
            return {}

        respuesta_data = []

        # Intentamos consultar ordenadamente probando las columnas clave en Supabase
        for col in ["rut_empresa", "id_negocio", "rut_negocio", "negocio_id"]:
            try:
                res = supabase.table("clientes").select("*").eq(col, tenant_id).execute()
                if res.data and len(res.data) > 0:
                    respuesta_data = res.data
                    break # Encontramos la columna correcta, salimos del ciclo
            except Exception:
                continue
                
        # Si ninguna columna dio resultado directo, hacemos una última pasada de seguridad estricta
        if not respuesta_data:
            res_general = supabase.table("clientes").select("*").execute()
            if res_general.data:
                # Filtro manual estricto en memoria línea por línea
                for cliente in res_general.data:
                    empresa_cliente = str(
                        cliente.get("rut_empresa") or 
                        cliente.get("id_negocio") or 
                        cliente.get("rut_negocio") or 
                        cliente.get("negocio_id") or ""
                    ).strip()
                    if empresa_cliente == tenant_id:
                        respuesta_data.append(cliente)

        if not respuesta_data:
            return {}
        
        # Transformamos la lista filtrada al formato de diccionario {rut: datos}
        for cliente in respuesta_data:
            rut = cliente.get("rut")
            if rut:
                maestro[str(rut).strip()] = cliente
                
        return maestro
    except Exception as e:
        print(f"❌ Error cargando maestro de clientes desde la nube: {e}")
        return {}

def guardar_nuevo_cliente(id_negocio, datos_cliente):
    try:
        # Inyectamos el ID de forma unificada en todas las variantes de columna posibles
        target_id = id_negocio if id_negocio else get_current_tenant()
        datos_cliente["rut_empresa"] = target_id
        datos_cliente["id_negocio"] = target_id
        
        supabase.table("clientes").upsert(
            datos_cliente, 
            on_conflict="rut"
        ).execute()
        print(f"✅ Cliente guardado/actualizado en la nube con éxito para {target_id}.")
    except Exception as e:
        print(f"❌ Error guardando cliente en Supabase: {e}")

    tenant_dir = Path("clientes") / (id_negocio or "negocio_demo")
    tenant_dir.mkdir(parents=True, exist_ok=True)

    plantilla_dir = Path(__file__).resolve().parent / "plantilla_cliente"
    if plantilla_dir.exists():
        for archivo_plantilla in plantilla_dir.glob("*.xlsx"):
            destino = tenant_dir / archivo_plantilla.name
            shutil.copy(archivo_plantilla, destino)
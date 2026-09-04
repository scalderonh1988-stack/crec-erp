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
    Obtiene el identificador exacto del negocio activo (RUT o Tenant ID)
    desde cualquier variable de sesión posible en Streamlit.
    """
    keys_to_check = [
        "negocio_actual", "negocio_seleccionado", "tenant_id", 
        "negocio_asignado", "rut_empresa", "negocio_actual_datos",
        "datos_empresa", "empresa_activa"
    ]
    
    for key in keys_to_check:
        if key in st.session_state and st.session_state[key]:
            val = st.session_state[key]
            # Si en la sesión se guardó un diccionario completo con datos
            if isinstance(val, dict):
                val = val.get("rut") or val.get("rut_empresa") or val.get("tenant_id") or val.get("id") or ""
            val = str(val).strip()
            if val and val.lower() != "admin_general":
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

def _normalizar_datos_empresa(data: dict, target_tenant: str = "") -> dict:
    """
    Homologa las llaves del diccionario para que caja_ventas.py y dte_manager.py
    puedan acceder a los datos sin importar cómo estén guardados en la BDD o Sesión.
    """
    razon_social = (
        data.get("razon_social") or data.get("nombre_negocio") or 
        data.get("nombre") or data.get("razon_social_empresa") or "MI EMPRESA"
    )
    rut = data.get("rut") or data.get("rut_empresa") or target_tenant or "00.000.000-0"
    giro = data.get("giro") or data.get("giro_negocio") or data.get("giro_comercial") or "GIRO COMERCIAL"
    direccion = data.get("direccion") or data.get("direccion_negocio") or ""
    comuna = data.get("comuna") or data.get("comuna_negocio") or ""
    ciudad = data.get("ciudad") or data.get("ciudad_negocio") or "Santiago"
    logo = data.get("logo") or data.get("logo_url") or data.get("logo_path") or data.get("imagen_logo")

    return {
        "rut": str(rut).strip(),
        "rut_empresa": str(rut).strip(),
        "razon_social": str(razon_social).strip(),
        "nombre_negocio": str(razon_social).strip(),
        "giro": str(giro).strip(),
        "direccion": str(direccion).strip(),
        "comuna": str(comuna).strip(),
        "ciudad": str(ciudad).strip(),
        "telefono": str(data.get("telefono", "")).strip(),
        "email": str(data.get("email", "")).strip(),
        "logo": logo,
        "logo_path": logo,
        "logo_url": logo
    }

def obtener_datos_empresa(tenant_id: str = None) -> dict:
    """
    Consulta en la sesión de Streamlit y en Supabase la configuración del negocio.
    Retorna siempre un diccionario estandarizado.
    """
    target_tenant = tenant_id or get_current_tenant()

    # 1. Búsqueda en la sesión de Streamlit
    for sesion_key in ["datos_empresa", "negocio_actual_datos", "config_empresa", "empresa_activa"]:
        if sesion_key in st.session_state and isinstance(st.session_state[sesion_key], dict):
            data_session = st.session_state[sesion_key]
            if data_session.get("razon_social") or data_session.get("nombre_negocio") or data_session.get("rut"):
                return _normalizar_datos_empresa(data_session, target_tenant)

    # 2. Búsqueda en Supabase
    datos_remotos = {}
    if target_tenant:
        for tabla in ["tenants", "empresas", "configuracion_negocio", "negocios"]:
            for col in ["rut_empresa", "rut", "tenant_id", "id_negocio", "id"]:
                try:
                    res = supabase.table(tabla).select("*").eq(col, target_tenant).execute()
                    if res.data and len(res.data) > 0:
                        datos_remotos = res.data[0]
                        break
                except Exception:
                    continue
            if datos_remotos:
                break

    if datos_remotos:
        return _normalizar_datos_empresa(datos_remotos, target_tenant)

    # 3. Fallback en caso de que no existan registros previos
    fallback_data = {
        "rut": target_tenant or st.session_state.get("rut_negocio") or "00.000.000-0",
        "razon_social": st.session_state.get("nombre_negocio") or st.session_state.get("razon_social") or "MI EMPRESA",
        "giro": st.session_state.get("giro_negocio") or "GIRO COMERCIAL",
        "direccion": st.session_state.get("direccion_negocio") or "",
        "comuna": st.session_state.get("comuna_negocio") or "",
        "ciudad": st.session_state.get("ciudad_negocio") or "Santiago",
        "telefono": st.session_state.get("telefono_negocio") or "",
        "email": st.session_state.get("email_negocio") or "",
        "logo": st.session_state.get("logo_empresa") or st.session_state.get("logo_path") or None
    }
    return _normalizar_datos_empresa(fallback_data, target_tenant)

# Alias para compatibilidad de llamados
obtener_config_empresa = obtener_datos_empresa

def cargar_maestro_clientes():
    """
    Carga los clientes asegurando un aislamiento total entre empresas.
    Bajo ninguna circunstancia descarga la tabla completa sin filtrar.
    """
    try:
        tenant_id = get_current_tenant()
        maestro = {}
        
        if not tenant_id:
            print("⚠️ Advertencia: No hay un tenant activo en la sesión para cargar clientes.")
            return {}

        respuesta_data = []

        for col in ["rut_empresa", "id_negocio", "rut_negocio", "negocio_id"]:
            try:
                res = supabase.table("clientes").select("*").eq(col, tenant_id).execute()
                if res.data and len(res.data) > 0:
                    respuesta_data = res.data
                    break
            except Exception:
                continue
                
        if not respuesta_data:
            res_general = supabase.table("clientes").select("*").execute()
            if res_general.data:
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
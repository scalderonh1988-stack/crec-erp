import io
import os
import sys
import json
from datetime import datetime, timedelta, date

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from fpdf import FPDF
from PIL import Image
from werkzeug.security import generate_password_hash

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y OCULTACIÓN DE ELEMENTOS DE DESARROLLADOR
# (Obligatorio: debe ser la PRIMERA llamada a 'st' en todo el código)
# ==============================================================================
st.set_page_config(
    page_title="CREC-ERP - Gestión Inteligente",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Oculta menú de Streamlit, barra superior con botón Fork/GitHub, footer, estado y estilos CSS generales
st.markdown("""
    <style>
    /* Ocultar menú principal, encabezado y pie de página */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Ocultar barra superior nativa (Fork, GitHub, Botones de desarrollador) */
    .stAppHeader {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    
    /* Bloquear selección accidental de texto en pantallas de caja */
    .stApp { user-select: none; }

    /* Estilos globales */
    .main-title {
        font-size: 1.8rem;
        color: #1E3A8A;
        text-align: center;
        font-weight: bold;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #4B5563;
        text-align: center;
        margin-bottom: 15px;
    }
    .ticket-box {
        background-color: #1F2937;
        padding: 20px;
        border-radius: 10px;
        border: 1px dashed #3B82F6;
        color: #F3F4F6;
        font-family: monospace;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. IMPORTACIÓN DE MÓDULOS DE LA APLICACIÓN
# ==============================================================================
# 💾 Módulo de Caché Offline (Respaldo automático de Supabase)
# from modulos.offline_cache import obtener_tabla_con_cache

from modulos.servicios.data_manager import get_current_tenant

# Servicios y Gestión de Datos
from modulos.servicios.data_manager import guardar_nuevo_cliente, cargar_maestro_clientes
from modulos.servicios import data_manager, dte_manager, integrar_productos

# Ventas e Inventario
from modulos.ventas_inventario.compras_cpp import mostrar_modulo_compras
from modulos.ventas_inventario.notas_credito import mostrar_modulo_notas_credito
from modulos.ventas_inventario import (
    caja_ventas,
    control_mermas,
    alerta_sobrestock
)

# Finanzas y Contabilidad
from modulos.finanzas.calendario_pagos import mostrar_modulo_calendario_pagos
from modulos.finanzas.cuadratura import mostrar_modulo_cuadratura_diaria
from modulos.finanzas.cuentas_por_pagar import mostrar_modulo_cuentas_por_pagar
from modulos.finanzas import (
    calculadora_impuestos,
    estado_resultados,
    comparativa_costos,
    calendario_vencimientos
)

# Módulos de raíz y distribución
from historial_ventas import mostrar_modulo_historial_ventas
from produccion_recetas import mostrar_modulo_produccion
from modulos.distribucion import mostrar_modulo_distribucion

def obtener_datos_emisor(supabase, tenant_id):
    """Obtiene los datos legales de la empresa emisora desde Supabase."""
    try:
        res = supabase.table("empresas").select("*").eq("rut_empresa", str(tenant_id)).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        pass
    
    return {
        "razon_social": st.session_state.get("empresa_razon_social", "MI EMPRESA SPA"),
        "rut_empresa": tenant_id or "12345678-9",
        "giro": st.session_state.get("empresa_giro", "Giro Comercial No Especificado"),
        "direccion": st.session_state.get("empresa_direccion", "Dirección Matriz"),
        "comuna": st.session_state.get("empresa_comuna", "Santiago"),
        "email_dte": st.session_state.get("empresa_email", "dte@miempresa.cl")
    }

def generar_encabezado_documento(tipo_doc, folio, emisor, receptor):
    """Genera el encabezado visual con datos de la Empresa (Emisor) y del Cliente (Receptor)."""
    
    # Recuadro Rojo Tributario (Estilo SII)
    st.markdown(f"""
    <div style="border: 2px solid #D32F2F; padding: 12px; text-align: center; border-radius: 6px; margin-bottom: 20px;">
        <h3 style="color: #D32F2F; margin: 0;">R.U.T.: {emisor.get('rut_empresa', 'N/A')}</h3>
        <h2 style="color: #D32F2F; margin: 5px 0; font-weight: bold;">{tipo_doc.upper()}</h2>
        <h4 style="color: #D32F2F; margin: 0;">N° {folio}</h4>
    </div>
    """, unsafe_allow_html=True)

    # Columnas con datos del Emisor y Receptor
    col_emisor, col_receptor = st.columns(2)

    with col_emisor:
        st.markdown("### 🏢 **DATOS EMISOR**")
        st.markdown(f"""
        * **Razón Social:** {emisor.get('razon_social', 'N/A')}
        * **RUT:** {emisor.get('rut_empresa', 'N/A')}
        * **Giro Comercial:** {emisor.get('giro', 'N/A')}
        * **Dirección:** {emisor.get('direccion', 'N/A')}
        * **Comuna:** {emisor.get('comuna', 'N/A')}
        """)

    with col_receptor:
        st.markdown("### 👤 **DATOS RECEPTOR**")
        st.markdown(f"""
        * **Nombre / Razón Social:** {receptor.get('nombre', 'CLIENTE CONTADO / ANÓNIMO')}
        * **RUT:** {receptor.get('rut', '66666666-6')}
        * **Giro Comercial:** {receptor.get('giro', 'Particular / Consumidor Final')}
        * **Dirección:** {receptor.get('direccion', 'N/A')}
        * **Comuna:** {receptor.get('comuna', 'N/A')}
        """)

    st.markdown("---")

def cargar_maestro_proveedores(ruta_negocio):
    archivo_prov = os.path.join(ruta_negocio, "Maestro_Proveedores.xlsx")
    if not os.path.exists(archivo_prov):
        df_ini = pd.DataFrame(columns=['Nombre_Proveedor', 'Rut', 'Contacto', 'Telefono', 'Email'])
        df_ini.to_excel(archivo_prov, index=False)
    return pd.read_excel(archivo_prov)

def guardar_nuevo_proveedor(ruta_negocio, nombre, rut="", contacto="", telefono="", email=""):
    archivo_prov = os.path.join(ruta_negocio, "Maestro_Proveedores.xlsx")
    df_prov = cargar_maestro_proveedores(ruta_negocio)
    
    nombre_limpio = str(nombre).strip().upper()
    if not df_prov.empty and nombre_limpio in df_prov['Nombre_Proveedor'].str.upper().values:
        return 
        
    nuevo = pd.DataFrame([{
        'Nombre_Proveedor': nombre.strip(),
        'Rut': rut,
        'Contacto': contacto,
        'Telefono': telefono,
        'Email': email
    }])
    
    df_actualizado = pd.concat([df_prov, nuevo], ignore_index=True)
    df_actualizado.to_excel(archivo_prov, index=False)

# --- 2. RUTAS Y CARPETAS GLOBALES ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CLIENTES_DIR = os.path.join(BASE_DIR, "clientes")
CARPETA_CLIENTES = CLIENTES_DIR
PERMISOS_FILE = os.path.join(BASE_DIR, "permisos_negocios.json")

if not os.path.exists(CLIENTES_DIR):
    os.makedirs(CLIENTES_DIR)

negocios_disponibles = [d for d in os.listdir(CLIENTES_DIR) if os.path.isdir(os.path.join(CLIENTES_DIR, d))]
if not negocios_disponibles:
    negocio_default = "negocio_1"
    os.makedirs(os.path.join(CLIENTES_DIR, negocio_default), exist_ok=True)
    negocios_disponibles = [negocio_default]

# 🔌 Conexión a Supabase usando st.secrets
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase: Client = create_client(url, key)

try:
    resultado = supabase.table("empresas").select("*").execute()
    empresas_data = resultado.data
except:
    empresas_data = []

PROVEEDORES_FILE = os.path.join(CLIENTES_DIR, "maestro_proveedores.xlsx")


# --- 3. FUNCIONES DE MÓDULOS ---
def generar_guia_pdf(
    cliente_nombre,
    cliente_rut,
    carrito,
    tipo_documento="GUÍA DE DESPACHO",
    fecha_emision=None,
    datos_empresa=None,
):
  import io
  from datetime import datetime
  from fpdf import FPDF
  import requests

  # 1. Formateo de la fecha
  if fecha_emision is None:
    fecha_str = datetime.now().strftime("%d/%m/%Y")
  elif hasattr(fecha_emision, "strftime"):
    fecha_str = fecha_emision.strftime("%d/%m/%Y")
  else:
    fecha_str = str(fecha_emision)

  pdf = FPDF(orientation="P", unit="mm", format="Letter")
  pdf.add_page()

  # 2. Rescate de Datos de la Empresa (Desde parámetro o Session State de Supabase)
  datos_emp = datos_empresa or st.session_state.get("empresa_actual", {})
  cfg = st.session_state.get("config_ticket", {})

  nombre_empresa = (
      datos_emp.get("razon_social")
      or datos_emp.get("nombre_empresa")
      or cfg.get("nombre_empresa")
      or st.session_state.get("nombre_empresa")
      or "MI EMPRESA SPA"
  )

  rut_empresa = (
      datos_emp.get("rut")
      or datos_emp.get("rut_empresa")
      or cfg.get("rut_empresa")
      or st.session_state.get("rut_empresa")
      or "Sin RUT"
  )

  direccion_empresa = (
      datos_emp.get("direccion")
      or cfg.get("direccion")
      or st.session_state.get("direccion_empresa")
      or "Sin Dirección"
  )

  # 3. Descarga del Logo desde Supabase Storage
  url_logo = (
      datos_emp.get("url_logo")
      or cfg.get("url_logo")
      or st.session_state.get("url_logo")
  )
  if url_logo:
    try:
      resp = requests.get(url_logo, timeout=5)
      if resp.status_code == 200:
        img_bytes = io.BytesIO(resp.content)
        pdf.image(img_bytes, x=10, y=8, w=25)
    except Exception:
      pass

  # 4. Impresión de Cabecera
  pdf.set_font("Arial", "B", 14)
  pdf.cell(0, 6, str(nombre_empresa).upper(), ln=True, align="C")
  pdf.set_font("Arial", "", 9)
  pdf.cell(0, 5, f"Dirección: {str(direccion_empresa)}", ln=True, align="C")
  pdf.cell(0, 5, f"RUT: {str(rut_empresa)}", ln=True, align="C")
  pdf.ln(5)

  titulo_doc = str(tipo_documento).upper()
  pdf.set_font("Arial", "B", 12)
  pdf.cell(0, 8, titulo_doc, ln=True, align="C")
  pdf.set_font("Arial", "", 10)
  pdf.cell(0, 5, f"Fecha de Emisión: {fecha_str}", ln=True, align="C")
  pdf.ln(5)

  c_nombre = (
      cliente_nombre
      if cliente_nombre and cliente_nombre.strip()
      else "Consumidor Final"
  )
  c_rut = cliente_rut if cliente_rut and cliente_rut.strip() else "Sin RUT"

  pdf.set_font("Arial", "B", 10)
  pdf.cell(0, 6, "DATOS DEL CLIENTE", ln=True)
  pdf.set_font("Arial", "", 10)
  pdf.cell(115, 6, f"Razón Social / Nombre: {c_nombre}", border=1)
  pdf.cell(60, 6, f"RUT: {c_rut}", border=1, ln=True)
  pdf.ln(5)

  # 5. Encabezados de Tabla
  pdf.set_font("Arial", "B", 9)
  es_factura = "FACTURA" in titulo_doc

  if es_factura:
    pdf.cell(70, 8, "Descripción", border=1, align="C")
    pdf.cell(15, 8, "Cant", border=1, align="C")
    pdf.cell(35, 8, "P. Unit. Neto", border=1, align="C")
    pdf.cell(35, 8, "P. Unit. Bruto", border=1, align="C")
    pdf.cell(35, 8, "Total Bruto", border=1, align="C", ln=True)
  else:
    pdf.cell(90, 8, "Descripción", border=1, align="C")
    pdf.cell(20, 8, "Cant.", border=1, align="C")
    pdf.cell(40, 8, "P. Unitario", border=1, align="C")
    pdf.cell(40, 8, "Total", border=1, align="C", ln=True)

  # 6. Detalle y Motor Contable
  tasa_defecto = (
      22.0
      if "URUGUAY" in str(nombre_empresa).upper()
      else 19.0
  )
  tasa_iva_global = float(cfg.get("iva_tasa", tasa_defecto))

  pdf.set_font("Arial", "", 9)
  total_general = 0.0
  total_neto = 0.0
  total_iva = 0.0
  total_ila = 0.0

  for item in carrito:
    producto = str(item.get("Descripción") or item.get("Producto") or "Ítem")
    cantidad = float(item.get("Cantidad", 0))
    precio_unitario_bruto = float(
        item.get("Precio Unitario") or item.get("Precio_Unitario") or 0
    )
    subtotal_bruto = float(item.get("Subtotal", 0))

    tasa_iva_item = (
        0.0 if item.get("Es Exento", False) else (tasa_iva_global / 100.0)
    )
    tasa_ila_item = float(item.get("Tasa ILA", 0.0))

    precio_unitario_neto = precio_unitario_bruto / (
        1.0 + tasa_iva_item + tasa_ila_item
    )

    if es_factura:
      pdf.cell(70, 7, producto[:35], border=1)
      pdf.cell(15, 7, f"{cantidad:g}", border=1, align="C")
      pdf.cell(35, 7, f"${precio_unitario_neto:,.0f}", border=1, align="R")
      pdf.cell(35, 7, f"${precio_unitario_bruto:,.0f}", border=1, align="R")
      pdf.cell(35, 7, f"${subtotal_bruto:,.0f}", border=1, align="R", ln=True)
    else:
      pdf.cell(90, 7, producto, border=1)
      pdf.cell(20, 7, f"{cantidad:g}", border=1, align="C")
      pdf.cell(40, 7, f"${precio_unitario_bruto:,.0f}", border=1, align="R")
      pdf.cell(40, 7, f"${subtotal_bruto:,.0f}", border=1, align="R", ln=True)

    neto_calc = subtotal_bruto / (1.0 + tasa_iva_item + tasa_ila_item)
    iva_calc = neto_calc * tasa_iva_item
    ila_calc = neto_calc * tasa_ila_item

    total_neto += neto_calc
    total_iva += iva_calc
    total_ila += ila_calc
    total_general += subtotal_bruto

  # 7. Totales
  pdf.set_font("Arial", "B", 10)
  if es_factura:
    pdf.cell(155, 7, "SUBTOTAL NETO:", border=1, align="R")
    pdf.cell(35, 7, f"${total_neto:,.0f}", border=1, align="R", ln=True)

    pdf.cell(155, 7, f"IVA ({tasa_iva_global:g}%):", border=1, align="R")
    pdf.cell(35, 7, f"${total_iva:,.0f}", border=1, align="R", ln=True)

    if total_ila > 0:
      pdf.cell(155, 7, "IMP. ESPECÍFICO:", border=1, align="R")
      pdf.cell(35, 7, f"${total_ila:,.0f}", border=1, align="R", ln=True)

    pdf.cell(155, 8, "TOTAL GENERAL:", border=1, align="R")
    pdf.cell(35, 8, f"${total_general:,.0f}", border=1, align="R", ln=True)
  else:
    pdf.cell(150, 8, "TOTAL GENERAL:", border=1, align="R")
    pdf.cell(40, 8, f"${total_general:,.0f}", border=1, align="R", ln=True)

  return pdf.output(dest="S").encode("latin1")

import requests
import streamlit as st
import pandas as pd
from datetime import date

# --- FUNCIÓN AUXILIAR: CONSULTA AUTOMÁTICA DEL DÓLAR ---
@st.cache_data(ttl=14400) # Se actualiza cada 4 horas automáticamente
def obtener_dolar_hoy():
    try:
        url = "https://mindicador.cl/api/dolar"
        respuesta = requests.get(url, timeout=4)
        if respuesta.status_code == 200:
            return float(respuesta.json()["serie"][0]["valor"])
    except Exception:
        pass
    return 950.0  # Valor por defecto si la API externa no responde


# ----------------- SECCIÓN CUENTAS POR COBRAR (NUBE) -----------------
def mostrar_modulo_cuentas_por_cobrar(ruta_negocio):
    mostrar_encabezado_con_home("📑 Gestión de Cuentas por Cobrar")
    rut_actual = str(st.session_state.get("negocio_seleccionado", "")).strip()

    if not rut_actual:
        st.error("⚠️ No hay un negocio seleccionado en la sesión.")
        st.stop()

    st.markdown("### 📊 Estado de Deudas Pendientes y Abonos")
    st.info("💡 Este módulo está conectado en tiempo real a la caja registradora. Las ventas a crédito y consignaciones de cualquier documento aparecen aquí automáticamente.")

    # 1. Leer ventas activas y cuentas por cobrar desde Supabase
    df_cxp = pd.DataFrame()
    folios_existentes = set()

    try:
        # Traer folios reales que existen actualmente en la tabla 'ventas' (evita registros huérfanos)
        res_ventas = supabase.table("ventas").select("folio").eq("rut_empresa", rut_actual).execute()
        if not res_ventas.data:
            res_ventas = supabase.table("ventas").select("folio").eq("rut_empresa", rut_actual.replace(".", "")).execute()
            
        if res_ventas.data:
            folios_existentes = {str(v["folio"]).strip() for v in res_ventas.data if v.get("folio")}

        # Consultar la tabla de cuentas por cobrar
        res_cxc = supabase.table("cuentas_por_cobrar").select("*").eq("rut_empresa", rut_actual).execute()
        if res_cxc.data:
            df_cxp = pd.DataFrame(res_cxc.data)
        else:
            # Reintento de respaldo sin puntos por inconsistencias de formato de RUT
            res_cxc_alt = supabase.table("cuentas_por_cobrar").select("*").eq("rut_empresa", rut_actual.replace(".", "")).execute()
            if res_cxc_alt.data:
                df_cxp = pd.DataFrame(res_cxc_alt.data)
    except Exception as e:
        st.error(f"⚠️ Error cargando Cuentas por Cobrar desde la nube: {e}")

    # 2. Filtrar exclusiones: estado pagado/anulado, saldo <= 0 y folios borrados de 'ventas'
    if not df_cxp.empty:
        df_cxp["saldo_pendiente"] = pd.to_numeric(df_cxp["saldo_pendiente"], errors="coerce").fillna(0)
        df_cxp["monto_total"] = pd.to_numeric(df_cxp["monto_total"], errors="coerce").fillna(0)
        
        # Filtro insensibles a mayúsculas y género ("pagado", "pagada", "anulado", "anulada")
        estados_invalidos = ["pagada", "pagado", "anulada", "anulado"]
        condicion_estado = ~df_cxp["estado"].astype(str).str.strip().str.lower().isin(estados_invalidos)
        condicion_saldo = df_cxp["saldo_pendiente"] > 0
        
        # Filtro estricto: el folio de la venta DEBE existir en la tabla 'ventas'
        if folios_existentes:
            condicion_folio_real = df_cxp["folio_venta"].astype(str).str.strip().isin(folios_existentes)
            df_cxp = df_cxp[condicion_estado & condicion_saldo & condicion_folio_real].copy()
        else:
            df_cxp = df_cxp[condicion_estado & condicion_saldo].copy()

    if df_cxp.empty:
        st.info("ℹ️ ¡Excelente! No hay registros de cuentas por cobrar pendientes para este negocio.")
    else:
        # 3. Calcular días de atraso en tiempo real
        if "fecha_vencimiento" in df_cxp.columns:
            hoy = pd.to_datetime(date.today())
            fechas_venc = pd.to_datetime(df_cxp["fecha_vencimiento"], errors='coerce')
            dias_atraso = (hoy - fechas_venc).dt.days
            df_cxp["DiasAtraso"] = dias_atraso.apply(lambda x: int(x) if pd.notnull(x) and x > 0 else 0)
        else:
            df_cxp["DiasAtraso"] = 0
        
        # 4. Buscador inteligente por Cliente o Folio
        cliente_filtro = st.text_input("🔍 Buscar por Cliente o Folio de Venta:")
        df_filtrado = df_cxp.copy()
        if cliente_filtro:
            filtro_c = df_filtrado["cliente"].astype(str).str.contains(cliente_filtro, case=False, na=False)
            filtro_f = df_filtrado["folio_venta"].astype(str).str.contains(cliente_filtro, case=False, na=False)
            df_filtrado = df_filtrado[filtro_c | filtro_f]
        
        # 5. Formatear la tabla visualmente
        columnas_mostrar = ["folio_venta", "cliente", "rut_cliente", "monto_total", "saldo_pendiente", "fecha_emision", "fecha_vencimiento", "DiasAtraso", "estado"]
        columnas_existentes = [col for col in columnas_mostrar if col in df_filtrado.columns]
        
        df_display = df_filtrado[columnas_existentes].rename(columns={
            "folio_venta": "Folio Venta",
            "cliente": "Cliente",
            "rut_cliente": "RUT Cliente",
            "monto_total": "Monto Original",
            "saldo_pendiente": "Saldo Pendiente",
            "fecha_emision": "Emisión",
            "fecha_vencimiento": "Vencimiento",
            "DiasAtraso": "Días Atraso",
            "estado": "Estado"
        })
        
        st.dataframe(df_display, use_container_width=True)
        
        # Métricas principales
        total_pendiente = df_filtrado["saldo_pendiente"].sum()
        st.metric(label="💰 Total Dinero en la Calle (Por Cobrar)", value=f"${total_pendiente:,.2f}")
        
        st.divider()
        st.markdown("### 💳 Registrar Abono o Pago")
        
        # 6. Lógica de abonos y reingresos
        deudas_opciones = df_filtrado.copy() if not df_filtrado.empty else df_cxp.copy()
        
        if not deudas_opciones.empty:
            deudas_opciones["etiqueta"] = (
                "Folio: " + deudas_opciones["folio_venta"].astype(str) + 
                " | " + deudas_opciones["cliente"].astype(str) + 
                " | Saldo: $" + deudas_opciones["saldo_pendiente"].astype(str)
            )
            opciones_deuda = deudas_opciones["etiqueta"].tolist()
            
            deuda_seleccionada = st.selectbox("📌 Selecciona el documento/venta a abonar:", options=opciones_deuda)
            
            folio_seleccionado = deuda_seleccionada.split(" | ")[0].replace("Folio: ", "").strip()
            fila_deuda = deudas_opciones[deudas_opciones["folio_venta"].astype(str) == str(folio_seleccionado)].iloc[0]
            
            saldo_actual = float(fila_deuda["saldo_pendiente"])
            id_deuda = fila_deuda["id"]
            
            # --- CONSULTAR DETALLE DE VENTA PARA DETECTAR CONSIGNACIONES ---
            items_venta = []
            es_consignacion = False
            try:
                res_ventas = (
                    supabase.table("ventas")
                    .select("*")
                    .eq("rut_empresa", rut_actual)
                    .eq("folio", str(folio_seleccionado))
                    .execute()
                )
                items_venta = res_ventas.data or []
                es_consignacion = any(
                    "consigna" in str(item.get("forma_pago", item.get("metodo_pago", ""))).lower() 
                    for item in items_venta
                )
            except Exception as e:
                st.warning(f"⚠️ No se pudo obtener el detalle de la venta: {e}")

            # --- REGISTRO DE ABONO EN DINERO (BASE USD / ALTERNATIVA CLP) ---
            texto_sesion_completo = " ".join([f"{k} {v}" for k, v in st.session_state.items()]).upper()
            texto_ruta = str(ruta_negocio).upper()
            
            es_multimoneda = (
                "URUGUAY" in texto_sesion_completo or 
                "ENVIROTECH" in texto_sesion_completo or 
                "URUGUAY" in texto_ruta
            )

            if es_multimoneda:
                dolar_hoy = obtener_dolar_hoy()
                
                # Por defecto selecciona USD ($)
                moneda_pago = st.radio(
                    "Seleccione la moneda del pago:",
                    ["Dólares (USD $)", "Pesos Chilenos (CLP $)"],
                    horizontal=True,
                    key=f"radio_moneda_{folio_seleccionado}"
                )

                if moneda_pago == "Pesos Chilenos (CLP $)":
                    st.info(f"🇨🇱 **Valor Dólar Observado (Chile):** ${dolar_hoy:,.2f} CLP")
                    
                    col_clp, col_tc = st.columns(2)
                    with col_clp:
                        monto_clp = st.number_input(
                            "Monto recibido en CLP ($):",
                            min_value=0.0,
                            max_value=float(saldo_actual * dolar_hoy),
                            step=1000.0,
                            format="%.2f",
                            key=f"clp_{folio_seleccionado}"
                        )
                    with col_tc:
                        tipo_cambio = st.number_input(
                            "Tipo de Cambio (T/C CLP/USD):",
                            min_value=1.0,
                            value=float(dolar_hoy),
                            step=1.0,
                            format="%.2f",
                            key=f"tc_{folio_seleccionado}"
                        )

                    # Convierte CLP a USD dividiendo por el tipo de cambio
                    monto_abono = monto_clp / tipo_cambio if tipo_cambio > 0 else 0.0
                    st.success(f"💰 Equivalente a abonar a la deuda: **${monto_abono:,.2f} USD**")

                else:
                    # Pago directo en USD (Default)
                    monto_abono = st.number_input(
                        f"💵 Monto a abonar en USD (Máximo ${saldo_actual:,.2f} USD):",
                        min_value=0.0,
                        max_value=saldo_actual,
                        step=10.0,
                        format="%.2f",
                        key=f"usd_{folio_seleccionado}"
                    )
            else:
                monto_abono = st.number_input(
                    f"💵 Monto a abonar en dinero (Máximo ${saldo_actual:,.2f}):",
                    min_value=0.0,
                    max_value=saldo_actual,
                    step=100.0,
                    key=f"clp_{folio_seleccionado}"
                )

            # --- REGISTRO DE REINGRESO / DEVOLUCIÓN (SÓLO SI ES CONSIGNACIÓN) ---
            if es_consignacion and items_venta:
                st.divider()
                st.markdown("### 🔄 Reingreso / Devolución de Mercadería (Consignación)")
                st.info("💡 Este documento corresponde a una **Consignación**. Ingresa las unidades devueltas por cada producto para reingresar el stock a la bodega y rebajar la deuda.")

                with st.form(key=f"form_dev_consignacion_{folio_seleccionado}"):
                    devoluciones = {}
                    total_rebaja_calculada = 0.0

                    for idx, item in enumerate(items_venta):
                        cod_prod = item.get("codigo_producto", "")
                        detalle_prod = item.get("descripcion", item.get("detalle", "Producto"))
                        cant_original = float(item.get("cantidad", 1))
                        monto_linea = float(item.get("subtotal", item.get("monto", 0)))
                        precio_unitario = monto_linea / cant_original if cant_original > 0 else 0.0

                        st.write(f"📦 **{detalle_prod}** (`{cod_prod}`) — Enviados: **{cant_original:g}** uds | P.U: **${precio_unitario:,.2f}**")
                        
                        cant_devuelta = st.number_input(
                            f"Devolver unidades:",
                            min_value=0.0,
                            max_value=cant_original,
                            value=0.0,
                            step=1.0,
                            key=f"dev_{folio_seleccionado}_{idx}"
                        )
                        
                        monto_rebaja_linea = cant_devuelta * precio_unitario
                        total_rebaja_calculada += monto_rebaja_linea
                        
                        devoluciones[cod_prod] = {
                            "cant_devuelta": cant_devuelta,
                            "detalle": detalle_prod
                        }

                    st.write(f"#### 📉 Total a rebajar del saldo: **${total_rebaja_calculada:,.2f}**")
                    btn_confirmar_dev = st.form_submit_button("📦 Confirmar Reingreso e Inventario", type="secondary", use_container_width=True)

                    if btn_confirmar_dev:
                        if total_rebaja_calculada <= 0:
                            st.warning("⚠️ Ingresa al menos 1 unidad para devolver.")
                        else:
                            try:
                                bodega_actual = st.session_state.get("bodega_pos_seleccionada", "Bodega Principal")
                                
                                # 1. Devuelve las unidades al inventario mediante RPC
                                for cod_prod, datos in devoluciones.items():
                                    cant = datos["cant_devuelta"]
                                    if cant > 0:
                                        supabase.rpc(
                                            'actualizar_stock_atomico',
                                            {
                                                'p_rut_empresa': str(rut_actual),
                                                'p_codigo': str(cod_prod),
                                                'p_bodega': str(bodega_actual),
                                                'p_cantidad': cant,
                                                'p_operacion': 'ENTRADA'
                                            }
                                        ).execute()

                                # 2. Rebaja el saldo pendiente en Cuentas por Cobrar
                                nuevo_saldo = saldo_actual - total_rebaja_calculada

                                if nuevo_saldo <= 0:
                                    supabase.table("cuentas_por_cobrar").delete().eq("id", id_deuda).execute()
                                    supabase.table("ventas").update({"estado": "Pagado"}).eq("rut_empresa", rut_actual).eq("folio", str(folio_seleccionado)).execute()
                                    st.success(f"🎉 ¡Mercadería devuelta y deuda saldada por completo para el folio {folio_seleccionado}!")
                                else:
                                    supabase.table("cuentas_por_cobrar").update({
                                        "saldo_pendiente": nuevo_saldo,
                                        "estado": "Pendiente"
                                    }).eq("id", id_deuda).execute()
                                    st.success(f"✅ Reingreso exitoso. Stock devuelto a bodega y saldo rebajado en ${total_rebaja_calculada:,.2f}. Nuevo saldo:${nuevo_saldo:,.2f}")

                                st.rerun()

                            except Exception as e:
                                st.error(f"❌ Error al procesar el reingreso de consignación: {e}")

def mostrar_modulo_registro_gastos(supabase):
    st.markdown("### 📋 Registro y Control de Gastos")
    
    rut_actual = st.session_state.get("negocio_seleccionado")
    
    with st.form("form_nuevo_gasto"):
        st.markdown("#### ➕ Registrar Nuevo Gasto o Egreso")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fecha_gasto = st.date_input("Fecha del Gasto")
            proveedor_g = st.text_input("Proveedor / Establecimiento")
            factura_g = st.text_input("Número de Factura o Boleta (Opcional)")
            categoria_g = st.selectbox("Categoría", ["Mercadería", "Gastos Operativos", "Servicios Básicos", "Logística", "Otros"])
        with col_g2:
            monto_g = st.number_input("Monto Total ($)", min_value=0.0, step=100.0, value=0.0)
            tipo_pago_g = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta de Débito", "Tarjeta de Crédito", "Transferencia", "Cheque"])
            descripcion_g = st.text_input("Descripción / Detalle (ej: Paltas, Tablillas)")
            
        btn_guardar_gasto = st.form_submit_button("💾 Guardar Gasto", type="primary")
        
        if btn_guardar_gasto:
            if monto_g <= 0:
                st.warning("⚠️ Debes ingresar un monto mayor a cero.")
            else:
                texto_detalle = f"{proveedor_g} - {descripcion_g}" if proveedor_g else descripcion_g
                
                nuevo_gasto = {
                    "rut_empresa": rut_actual,
                    "fecha": str(fecha_gasto),
                    "detalle": texto_detalle,
                    "categoria": categoria_g,
                    "metodo_pago": tipo_pago_g,
                    "documento": factura_g or "S/N",
                    "monto": monto_g
                }
                try:
                    supabase.table("gastos").insert(nuevo_gasto).execute()
                    st.success("✅ ¡Gasto registrado con éxito en la nube!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar en la nube: {e}")

    st.divider()
    st.markdown("### 📂 Historial de Gastos Registrados")
    
    try:
        res = supabase.table("gastos").select("*").eq("rut_empresa", rut_actual).order("fecha", desc=True).execute()
        df_gastos = pd.DataFrame(res.data)
    except Exception as e:
        df_gastos = pd.DataFrame()
        st.error("Error al conectar con la base de datos.")

    if df_gastos.empty:
        st.info("ℹ️ No hay registros de gastos todavía.")
    else:
        total_gastos = df_gastos['monto'].sum()
        st.metric(label="💰 Total Histórico de Gastos", value=f"${total_gastos:,.2f}")
        
        st.divider()
        st.markdown("Revisa el detalle de cada gasto y utiliza el botón de la derecha para **eliminar** el registro en caso de error.")

        for idx, row in df_gastos.iterrows():
            c_info, c_btn = st.columns([10, 1])
            with c_info:
                st.info(f"📅 **{row.get('fecha', '')}** | 📝 **{row.get('detalle', '')}** | 🏷️ {row.get('categoria', '')} | 💳 {row.get('metodo_pago', '')} | 📄 Fac/Bol: {row.get('documento', 'S/N')} | **Monto: ${float(row.get('monto', 0)):,.2f}**")
            with c_btn:
                if st.button("🗑️", key=f"del_gasto_{row.get('id')}", help="Eliminar este registro"):
                    try:
                        supabase.table("gastos").delete().eq("id", row.get('id')).execute()
                        st.success("✅ Gasto eliminado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error("Error al eliminar el registro.")

def mostrar_modulo_costos_fijos(rut_empresa, supabase):
    st.subheader("🏢 Gestión de Costos Fijos y Créditos Mensuales")
    
    # 1. Formulario para agregar nuevo costo fijo o crédito
    with st.expander("➕ Registrar Nuevo Costo Fijo o Crédito"):
        # El checkbox va FUERA del form para que sea interactivo al instante
        es_credito = st.checkbox("¿Es un Crédito con cuotas definidas?")
        
        cuotas_totales = 1
        cuota_actual = 1
        if es_credito:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                cuotas_totales = st.number_input("Cuotas Totales", min_value=1, step=1, value=12)
            with col_c2:
                cuota_actual = st.number_input("¿En qué cuota vamos?", min_value=1, step=1, value=1)

        with st.form("form_costo_fijo"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre del Gasto (Ej: Arriendo Local, Banco Estado)")
                categoria = st.selectbox("Categoría", ["Arriendo", "Sueldos", "Crédito / Financiamiento", "Servicios Básicos", "Suscripciones", "Otros"])
                monto = st.number_input("Monto Mensual ($)", min_value=0.0, step=1000.0)
            
            submitted = st.form_submit_button("Guardar Costo Fijo")
            if submitted:
                if nombre and monto > 0:
                    nuevo_costo = {
                        "rut_empresa": rut_empresa,
                        "nombre": nombre,
                        "categoria": categoria,
                        "monto": monto,
                        "es_credito": es_credito,
                        "cuotas_totales": int(cuotas_totales) if es_credito else 0,
                        "cuota_actual": int(cuota_actual) if es_credito else 0,
                        "activo": True
                    }
                    supabase.table("costos_fijos").insert(nuevo_costo).execute()
                    st.success("¡Costo fijo registrado con éxito!")
                    st.rerun()
                else:
                    st.warning("Completa el nombre y un monto válido.")

    # 2. Cargar y mostrar los costos fijos actuales
    response = supabase.table("costos_fijos").select("*").eq("rut_empresa", rut_empresa).eq("activo", True).execute()
    data = response.data

    if data:
        df_costos = pd.DataFrame(data)
        
        # Métrica resumen del total mensual
        total_fijo = df_costos["monto"].sum()
        st.metric(label="Total Costos Fijos Mensuales", value=f"${total_fijo:,.0f}")
        
        st.markdown("---")
        st.markdown("### 📋 Listado de Compromisos Mensuales")
        
        # Formatear visualización para créditos
        for index, row in df_costos.iterrows():
            with st.container():
                col_a, col_b, col_c, col_d = st.columns([3, 2, 2, 1])
                with col_a:
                    st.markdown(f"**{row['nombre']}**")
                    st.caption(f"Categoría: {row['categoria']}")
                with col_b:
                    st.markdown(f"**Monto:** ${row['monto']:,.0f}")
                with col_c:
                    if row['es_credito']:
                        st.markdown(f"💳 **Crédito:** Cuota {row['cuota_actual']} de {row['cuotas_totales']}")
                        # Barra de progreso visual para el crédito
                        progreso = float(row['cuota_actual']) / float(row['cuotas_totales']) if row['cuotas_totales'] > 0 else 0
                        st.progress(min(progreso, 1.0))
                    else:
                        st.markdown("🔄 *Gasto Fijo Recurrente*")
                with col_d:
                    if st.button("🗑️", key=f"del_cf_{row['id']}"):
                        supabase.table("costos_fijos").update({"activo": False}).eq("id", row['id']).execute()
                        st.rerun()
                st.divider()
    else:
        st.info("No hay costos fijos registrados todavía. Agrega el primero usando el formulario de arriba.")


def mostrar_modulo_conciliacion_retiros(ruta_negocio):
    if "mostrar_encabezado_con_home" in globals():
        mostrar_encabezado_con_home("🏦 Conciliación Bancaria y Retiros Protegidos por Markup")
    else:
        st.markdown("### 🏦 Conciliación Bancaria y Retiros Protegidos por Markup")
    
    # 1. Obtener el RUT de la empresa activa
    rut_actual = str(st.session_state.get("negocio_seleccionado", "")).strip()
    rut_limpio = rut_actual.replace(".", "").replace("-", "").strip()

    if not rut_actual:
        st.error("⚠️ No hay un negocio seleccionado en la sesión.")
        st.stop()

    # 2. Consultar cuentas bancarias de la empresa desde Supabase
    lista_cuentas = []
    try:
        res_cuentas = supabase.table("cuentas_bancarias").select("*").eq("rut_empresa", rut_actual).execute()
        if res_cuentas.data:
            lista_cuentas = res_cuentas.data
        else:
            res_cuentas_alt = supabase.table("cuentas_bancarias").select("*").eq("rut_empresa", rut_limpio).execute()
            if res_cuentas_alt.data:
                lista_cuentas = res_cuentas_alt.data
    except Exception as e:
        st.warning(f"⚠️ Nota al cargar cuentas: {e}")

    # 3. Construir lista dinámica para el selector
    opciones_cuentas = []
    dict_cuentas = {}

    if lista_cuentas:
        for c in lista_cuentas:
            nombre = c.get('nombre_cuenta', '').strip()
            banco = f" ({c.get('banco')})" if c.get('banco') else ""
            num_cta = f" N°{c.get('numero_cuenta')}" if c.get('numero_cuenta') else ""
            moneda = c.get('moneda', 'USD')
            
            # Formato visible: "Itaú USD (Banco Itaú) N°123456 [USD]"
            etiqueta = f"🏦 {nombre}{banco}{num_cta} [{moneda}]"
            opciones_cuentas.append(etiqueta)
            dict_cuentas[etiqueta] = c
    else:
        opciones_cuentas = ["⚠️ Sin cuentas registradas (Crea una en la pestaña '⚙️ Cuentas Bancarias')"]

    tab_cr1, tab_cr2, tab_cr3, tab_cr4 = st.tabs([
        "💰 Cálculo de Retiro Seguro (Markup)", 
        "🏦 Conciliación de Cartolas (USD / CLP)", 
        "📂 Historial de Retiros",
        "⚙️ Cuentas Bancarias"
    ])

    # ---------------- TAB 1: CÁLCULO DE RETIRO SEGURO ----------------
    with tab_cr1:
        st.markdown("### 🎯 Asistente de Retiro Diario sin Desfinanciar el Negocio")
        
        with st.form("form_calculo_retiro_nube"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fecha_calculo = st.date_input("Fecha de la Cuadratura", value=date.today())
                moneda_retiro = st.selectbox("Moneda de la Operación", ["USD ($)", "CLP ($)"])
                val_defecto = 1500.0 if "USD" in moneda_retiro else 150000.0
                venta_dia_input = st.number_input(
                    "💵 Venta Total del Día", 
                    min_value=0.0, 
                    step=100.0, 
                    value=val_defecto,
                    format="%.2f" if "USD" in moneda_retiro else "%.0f"
                )
            with col_c2:
                markup_porcentaje = st.number_input("📈 Markup / Margen Promedio (%)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)
                observacion_retiro = st.text_input("📝 Notas u Observaciones del Día", value="Cierre diario normal")

            markup_decimal = markup_porcentaje / 100.0
            costo_reposicion = venta_dia_input / (1.0 + markup_decimal)
            utilidad_neta_retirable = venta_dia_input - costo_reposicion

            st.divider()
            simbolo = "USD $" if "USD" in moneda_retiro else "CLP $"
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric(label="🛒 Venta Total Ingresada", value=f"{simbolo} {venta_dia_input:,.2f}")
            with col_m2:
                st.metric(label="🔒 Fondo Intocable (Reposición)", value=f"{simbolo} {costo_reposicion:,.2f}", delta="Guardar en Cuenta")
            with col_m3:
                st.metric(label="💵 Utilidad Real Retirable", value=f"{simbolo} {utilidad_neta_retirable:,.2f}", delta="Disponible para Retiro")

            btn_guardar_retiro = st.form_submit_button("☁️ Guardar Registro en la Nube", type="primary", use_container_width=True)

            if btn_guardar_retiro:
                if venta_dia_input <= 0:
                    st.warning("⚠️ Ingresa una venta válida mayor a 0.")
                else:
                    try:
                        data_retiro = {
                            "rut_empresa": rut_actual,
                            "fecha": str(fecha_calculo),
                            "moneda": "USD" if "USD" in moneda_retiro else "CLP",
                            "venta_total": float(venta_dia_input),
                            "markup_aplicado": float(markup_porcentaje),
                            "costo_mercaderia": float(costo_reposicion),
                            "utilidad_real_retirable": float(utilidad_neta_retirable),
                            "retiro_efectuado": float(utilidad_neta_retirable),
                            "observaciones": observacion_retiro
                        }
                        supabase.table("registro_retiros_seguros").insert(data_retiro).execute()
                        st.success("✅ ¡Registro guardado en Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Supabase: {e}")

    # ---------------- TAB 2: CONCILIACIÓN DE CARTOLAS ----------------
    with tab_cr2:
        st.markdown("### 🏦 Conciliación de Cartolas por Cuenta Bancaria")
        
        # Historial de conciliaciones
        df_conci = pd.DataFrame()
        try:
            res_c = supabase.table("conciliacion_bancaria").select("*").eq("rut_empresa", rut_actual).execute()
            if res_c.data:
                df_conci = pd.DataFrame(res_c.data)
            else:
                res_c_alt = supabase.table("conciliacion_bancaria").select("*").eq("rut_empresa", rut_limpio).execute()
                if res_c_alt.data:
                    df_conci = pd.DataFrame(res_c_alt.data)
        except Exception:
            pass

        if not df_conci.empty:
            st.markdown("#### 📜 Registros de Conciliación en la Nube")
            columnas_mostrar = ["fecha", "cuenta_destino", "moneda", "origen_pago", "monto_pos", "monto_banco", "diferencia", "estado"]
            cols_ex = [c for c in columnas_mostrar if c in df_conci.columns]
            
            st.dataframe(
                df_conci[cols_ex].rename(columns={
                    "fecha": "Fecha",
                    "cuenta_destino": "Cuenta Bancaria",
                    "moneda": "Moneda",
                    "origen_pago": "Origen",
                    "monto_pos": "Monto POS",
                    "monto_banco": "Monto Banco",
                    "diferencia": "Diferencia",
                    "estado": "Estado"
                }),
                use_container_width=True
            )
        else:
            st.info("ℹ️ No hay conciliaciones registradas en la nube para esta empresa.")

        st.divider()
        with st.form("form_nueva_conciliacion_nube"):
            st.markdown("#### ➕ Registrar Nueva Validación de Cartola")
            
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                f_conci = st.date_input("Fecha de Cartola", value=date.today(), key="f_con_nube")
                
                # SELECCIONADOR DE CUENTAS REGISTRADAS
                cuenta_destino_sel = st.selectbox(
                    "🏦 Cuenta Corriente Destino", 
                    opciones_cuentas,
                    key="sel_cuenta_destino"
                )

            # Auto-detección de moneda según la cuenta elegida
            moneda_sugerida = "USD"
            if cuenta_destino_sel in dict_cuentas:
                moneda_sugerida = dict_cuentas[cuenta_destino_sel].get("moneda", "USD")
            elif "[CLP]" in cuenta_destino_sel or "CLP" in cuenta_destino_sel:
                moneda_sugerida = "CLP"

            with col_b2:
                moneda_conci = st.selectbox(
                    "Moneda de Cartola", 
                    ["USD", "CLP"], 
                    index=0 if moneda_sugerida == "USD" else 1,
                    key="sel_moneda_cartola"
                )
                origen_pago = st.selectbox("Origen del Abono / Transacción", [
                    "Transferencia Bancaria Directa", 
                    "POS / Transbank / Débito", 
                    "POS / Transbank / Crédito", 
                    "Depósito en Ventanilla / Efectivo",
                    "Cheque / Otro"
                ])
            with col_b3:
                simb_m = "USD $" if moneda_conci == "USD" else "CLP $"
                monto_pos = st.number_input(f"Monto Registrado POS/Sistema ({simb_m})", min_value=0.0, step=10.0 if moneda_conci == "USD" else 1000.0, value=0.0, key="m_pos_nube")
                monto_banco = st.number_input(f"Monto Abonado en Banco ({simb_m})", min_value=0.0, step=10.0 if moneda_conci == "USD" else 1000.0, value=0.0, key="m_ban_nube")

            diferencia_banco = monto_banco - monto_pos
            if diferencia_banco == 0:
                estado_conci = "Conciliado OK"
            elif diferencia_banco < 0:
                estado_conci = "Diferencia en contra (Comisión o Faltante)"
            else:
                estado_conci = "Abono Mayor"

            btn_guardar_conci = st.form_submit_button("☁️ Guardar Conciliación en Nube", type="primary", use_container_width=True)

            if btn_guardar_conci:
                if "Sin cuentas registradas" in cuenta_destino_sel:
                    st.warning("⚠️ Debes registrar al menos una cuenta bancaria en la pestaña '⚙️ Cuentas Bancarias'.")
                else:
                    try:
                        data_conci = {
                            "rut_empresa": rut_actual,
                            "fecha": str(f_conci),
                            "cuenta_destino": cuenta_destino_sel,
                            "moneda": moneda_conci,
                            "origen_pago": origen_pago,
                            "monto_pos": float(monto_pos),
                            "monto_banco": float(monto_banco),
                            "diferencia": float(diferencia_banco),
                            "estado": estado_conci
                        }
                        supabase.table("conciliacion_bancaria").insert(data_conci).execute()
                        st.success("✅ ¡Conciliación bancaria guardada en Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar conciliación: {e}")

    # ---------------- TAB 3: HISTORIAL DE RETIROS ----------------
    with tab_cr3:
        st.markdown("### 📂 Historial de Retiros Seguros Realizados (Nube)")
        
        df_hist_ret = pd.DataFrame()
        try:
            res_r = supabase.table("registro_retiros_seguros").select("*").eq("rut_empresa", rut_actual).execute()
            if res_r.data:
                df_hist_ret = pd.DataFrame(res_r.data)
            else:
                res_r_alt = supabase.table("registro_retiros_seguros").select("*").eq("rut_empresa", rut_limpio).execute()
                if res_r_alt.data:
                    df_hist_ret = pd.DataFrame(res_r_alt.data)
        except Exception:
            pass

        if not df_hist_ret.empty:
            cols_r = ["fecha", "moneda", "venta_total", "markup_aplicado", "costo_mercaderia", "utilidad_real_retirable", "observaciones"]
            cols_r_ex = [c for c in cols_r if c in df_hist_ret.columns]
            
            df_disp_ret = df_hist_ret[cols_r_ex].rename(columns={
                "fecha": "Fecha",
                "moneda": "Moneda",
                "venta_total": "Venta Total",
                "markup_aplicado": "Markup (%)",
                "costo_mercaderia": "Costo Reposición",
                "utilidad_real_retirable": "Utilidad Retirada",
                "observaciones": "Observaciones"
            })
            
            st.dataframe(df_disp_ret, use_container_width=True)
            
            col_tot1, col_tot2 = st.columns(2)
            with col_tot1:
                df_usd = df_hist_ret[df_hist_ret["moneda"] == "USD"] if "moneda" in df_hist_ret.columns else pd.DataFrame()
                tot_usd = df_usd["utilidad_real_retirable"].sum() if not df_usd.empty else 0.0
                st.metric(label="💵 Total Utilidad Retirada (USD)", value=f"USD ${tot_usd:,.2f}")
            with col_tot2:
                df_clp = df_hist_ret[df_hist_ret["moneda"] == "CLP"] if "moneda" in df_hist_ret.columns else pd.DataFrame()
                tot_clp = df_clp["utilidad_real_retirable"].sum() if not df_clp.empty else 0.0
                st.metric(label="🇨🇱 Total Utilidad Retirada (CLP)", value=f"CLP ${tot_clp:,.2f}")
        else:
            st.info("ℹ️ No hay registros de retiros guardados en la nube todavía.")

    # ---------------- TAB 4: GESTIÓN DE CUENTAS BANCARIAS ----------------
    with tab_cr4:
        st.markdown("### ⚙️ Configuración y Creación de Cuentas Bancarias")
        st.info("💡 Crea aquí las cuentas corrientes, vistas o cajas de la empresa. Aparecerán automáticamente en el selector de Conciliación.")

        with st.form("form_crear_cuenta_bancaria"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                nombre_cuenta = st.text_input("Nombre / Alias de la Cuenta *", placeholder="Ej: Itaú Corriente USD")
                banco = st.text_input("Banco / Institución Financial", placeholder="Ej: Banco Itaú")
                tipo_cuenta = st.selectbox("Tipo de Cuenta", ["Cuenta Corriente", "Cuenta Vista / RUT", "Caja Chica / Efectivo", "Otra"])
            with col_c2:
                numero_cuenta = st.text_input("N° de Cuenta (Opcional)", placeholder="Ej: 021-98765-4")
                moneda_cuenta = st.selectbox("Moneda Principal de la Cuenta", ["USD", "CLP"])

            btn_crear = st.form_submit_button("➕ Registrar Cuenta Bancaria en la Nube", type="primary", use_container_width=True)

            if btn_crear:
                if not nombre_cuenta.strip():
                    st.warning("⚠️ Debes ingresar un nombre o alias para la cuenta.")
                else:
                    try:
                        nueva_cuenta = {
                            "rut_empresa": rut_actual,
                            "nombre_cuenta": nombre_cuenta.strip(),
                            "banco": banco.strip(),
                            "numero_cuenta": numero_cuenta.strip(),
                            "moneda": moneda_cuenta,
                            "tipo_cuenta": tipo_cuenta,
                            "activa": True
                        }
                        supabase.table("cuentas_bancarias").insert(nueva_cuenta).execute()
                        st.success(f"🎉 ¡Cuenta '{nombre_cuenta}' guardada exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear la cuenta en Supabase: {e}")

        st.divider()
        st.markdown("#### 📜 Cuentas Registradas para esta Empresa")
        if lista_cuentas:
            df_cuentas = pd.DataFrame(lista_cuentas)
            cols_c = ["nombre_cuenta", "banco", "numero_cuenta", "moneda", "tipo_cuenta"]
            cols_exist = [col for col in cols_c if col in df_cuentas.columns]
            
            st.dataframe(
                df_cuentas[cols_exist].rename(columns={
                    "nombre_cuenta": "Nombre Cuenta",
                    "banco": "Banco",
                    "numero_cuenta": "N° Cuenta",
                    "moneda": "Moneda",
                    "tipo_cuenta": "Tipo"
                }),
                use_container_width=True
            )
        else:
            st.info("ℹ️ No hay cuentas bancarias personalizadas creadas aún.")

# --- CONEXIÓN DE REPORTES A SUPABASE ---
def mostrar_modulo_reportes_avanzados(ruta_negocio):
    if st.button("⬅️ Volver al Home", use_container_width=True):
        st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
        st.rerun()

    st.markdown("### 📊 Módulo de Reportes e Inteligencia de Negocio")
    st.info("📈 Analiza el rendimiento financiero en tiempo real conectado a Supabase.")

    rut_actual = st.session_state.get("negocio_seleccionado")
    fecha_hoy = date.today().strftime('%Y-%m-%d')
    
    # Lectura de Ventas y Gastos en la Nube
    try:
        res_ventas = supabase.table("ventas").select("monto").eq("rut_empresa", rut_actual).like("fecha", f"{fecha_hoy}%").execute()
        total_ingresos_dia = sum([float(v['monto'] or 0) for v in res_ventas.data])
    except:
        total_ingresos_dia = 0.0

    try:
        res_gastos = supabase.table("gastos").select("monto, categoria").eq("rut_empresa", rut_actual).execute()
        df_g = pd.DataFrame(res_gastos.data)
        
        # Filtramos solo los gastos de hoy para el balance
        res_gastos_hoy = supabase.table("gastos").select("monto").eq("rut_empresa", rut_actual).like("fecha", f"{fecha_hoy}%").execute()
        total_egresos_hoy = sum([float(g['monto'] or 0) for g in res_gastos_hoy.data])
    except:
        total_egresos_hoy = 0.0
        df_g = pd.DataFrame()

    archivo_cxp = os.path.join(ruta_negocio, "Cuentas_por_Cobrar.xlsx")
    archivo_cpp = os.path.join(ruta_negocio, "Cuentas_Por_Pagar.xlsx")

    tab_r1, tab_r2, tab_r3, tab_r4 = st.tabs(["💰 Balance de Hoy (Nube)", "📈 Análisis de Gastos (Nube)", "📑 Estado de Cartera", "📄 Exportar Informes PDF"])

    with tab_r1:
        st.markdown("#### 💵 Resumen General de Ingresos vs. Gastos (Día Actual)")
        utilidad_estimada = total_ingresos_dia - total_egresos_hoy

        col_rep1, col_rep2, col_rep3 = st.columns(3)
        with col_rep1:
            st.metric(label="🪙 Ingresos Totales de Hoy", value=f"${total_ingresos_dia:,.2f}")
        with col_rep2:
            st.metric(label="📉 Gastos Operativos Hoy", value=f"${total_egresos_hoy:,.2f}")
        with col_rep3:
            st.metric(label="💼 Margen Neto Operativo", value=f"${utilidad_estimada:,.2f}", delta="Estimado")

    with tab_r2:
        st.markdown("#### 📂 Desglose Histórico de Gastos por Categoría")
        if not df_g.empty and 'categoria' in df_g.columns and 'monto' in df_g.columns:
            df_g['monto'] = pd.to_numeric(df_g['monto'], errors='coerce')
            gasto_por_cat = df_g.groupby('categoria')['monto'].sum().reset_index()
            st.dataframe(gasto_por_cat, use_container_width=True)
            st.bar_chart(gasto_por_cat.set_index('categoria')['monto'])
        else:
            st.info("ℹ️ No hay registros suficientes de gastos en la nube.")

    with tab_r3:
        st.markdown("#### ⏳ Reporte de Cuentas por Cobrar y Atrasos (Excel temporal)")
        if os.path.exists(archivo_cxp):
            df_cobrar = pd.read_excel(archivo_cxp)
            if not df_cobrar.empty:
                st.dataframe(df_cobrar, use_container_width=True)
            else:
                st.info("ℹ️ No hay registros activos en Cuentas por Cobrar.")
        else:
            st.info("ℹ️ No existe archivo de Cuentas por Cobrar.")

        st.markdown("#### 💳 Estado de Cuentas por Pagar (Proveedores)")
        if os.path.exists(archivo_cpp):
            df_pagar = pd.read_excel(archivo_cpp)
            if not df_pagar.empty:
                st.dataframe(df_pagar, use_container_width=True)
            else:
                st.info("ℹ️ No hay registros en Cuentas por Pagar.")
        else:
            st.info("ℹ️ No existe archivo de Cuentas por Pagar.")

    with tab_r4:
        st.markdown("#### 📄 Generación y Descarga de Informe Ejecutivo en PDF")
        if st.button("🖨️ Generar Reporte Ejecutivo PDF", type="primary"):
            try:
                pdf = FPDF(orientation='P', unit='mm', format='Letter')
                pdf.add_page()
                
                nombre_empresa_act = st.session_state.get('nombre_empresa', 'MI EMPRESA')
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 8, str(nombre_empresa_act), ln=True, align='C')
                pdf.set_font("Arial", '', 10)
                pdf.cell(0, 6, "INFORME EJECUTIVO DE GESTIÓN Y FINANZAS", ln=True, align='C')
                pdf.cell(0, 6, f"Fecha de Emisión: {date.today().strftime('%d/%m/%Y')}", ln=True, align='C')
                pdf.ln(10)

                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 8, "RESUMEN FINANCIERO DEL DIA", ln=True)
                pdf.set_font("Arial", '', 10)
                
                pdf.cell(100, 7, "Ingresos Totales Registrados:", border=1)
                pdf.cell(90, 7, f"${total_ingresos_dia:,.2f}", border=1, ln=True, align='R')
                pdf.cell(100, 7, "Gastos Operativos Totales:", border=1)
                pdf.cell(90, 7, f"${total_egresos_hoy:,.2f}", border=1, ln=True, align='R')
                pdf.cell(100, 7, "Margen Neto Operativo Estimado:", border=1)
                pdf.cell(90, 7, f"${utilidad_estimada:,.2f}", border=1, ln=True, align='R')
                pdf.ln(10)

                pdf.set_font("Arial", 'I', 9)
                pdf.cell(0, 6, "Reporte generado automáticamente desde la Nube.", ln=True, align='C')

                pdf_output_bytes = pdf.output(dest='S').encode('latin1')

                st.success("✅ ¡Informe PDF generado con éxito!")
                st.download_button(
                    label="⬇️ Descargar Informe PDF",
                    data=bytes(pdf_output_bytes),
                    file_name=f"Informe_Financiero_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Error al generar el PDF: {e}")

# ==============================================================================
# --- LISTA OFICIAL DE MÓDULOS Y FUNCIONES DE ASIGNACIÓN ---
# ==============================================================================
modulos_totales = [
    "🏠 Home / Bienvenida",
    "📊 Dashboard Ejecutivo",
    "📦 Inventario y Productos",
    "🍔 Producción y Recetas",
    "💰 Módulo de Ventas (POS)",
    "🛒 Registrar Compra (CPP)",
    "📉 Mermas y Ajustes",
    "📈 Informes y Movimientos (Kardex)",
    "⚠️ Control y Gestión de Inventario",
    "📊 Módulo de Finanzas",
    "📒 Cuadratura Diaria",
    "📑 Cuentas por Cobrar",
    "📈 Reportes y Analítica",
    "📚 Historial de Ventas",
    "🔄 Notas de Crédito",
    "🏦 Conciliación y Retiros Seguros",
    "🚚 Logística y Distribución (Preventa)",
    "⚙️ Configuración General"
]

def normalizar_lista_modulos(raw_modulos):
    """Convierte texto o lista proveniente de Supabase en una lista con nombres exactos."""
    if not raw_modulos:
        return ["🏠 Home / Bienvenida"]
        
    if isinstance(raw_modulos, str):
        items = [m.strip() for m in raw_modulos.split(",") if m.strip()]
    elif isinstance(raw_modulos, list):
        items = [str(m).strip() for m in raw_modulos if str(m).strip()]
    else:
        items = []

    resultado = []
    for item in items:
        coincidencia = next((mod for mod in modulos_totales if item.lower() in mod.lower() or mod.lower() in item.lower()), item)
        if coincidencia not in resultado:
            resultado.append(coincidencia)

    if "🏠 Home / Bienvenida" not in resultado:
        resultado.insert(0, "🏠 Home / Bienvenida")

    return resultado

# ==============================================================================
# --- 4. SISTEMA DE AUTENTICACIÓN Y BLINDAJE DE SEGURIDAD ---
# ==============================================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "negocio_actual" not in st.session_state:
    st.session_state.negocio_actual = None
if "usuario_logueado" not in st.session_state:
    st.session_state.usuario_logueado = None
if "es_admin_dev" not in st.session_state:
    st.session_state.es_admin_dev = False
if "intentos_fallidos" not in st.session_state:
    st.session_state.intentos_fallidos = 0
if "modulos_permitidos" not in st.session_state:
    st.session_state.modulos_permitidos = ["🏠 Home / Bienvenida"]
if "tipo_usuario" not in st.session_state:
    st.session_state.tipo_usuario = "Propietario"
if "nombre_empresa" not in st.session_state:
    st.session_state.nombre_empresa = ""

# Lectura segura de credenciales maestras desde secretos / variables de entorno
def _obtener_secret_admin():
    user = ""
    pwd = ""
    try:
        if "ADMIN_USER" in st.secrets:
            user = str(st.secrets["ADMIN_USER"]).strip().lower()
        if "ADMIN_PASS" in st.secrets:
            pwd = str(st.secrets["ADMIN_PASS"]).strip()
    except Exception:
        pass
    if not user:
        user = os.getenv("ADMIN_USER", "").strip().lower()
    if not pwd:
        pwd = os.getenv("ADMIN_PASS", "").strip()
    return user, pwd

ADMIN_MASTER_USER, ADMIN_MASTER_PASS = _obtener_secret_admin()

# 🔴 VISTA DE LOGIN: Si no está autenticado, dibuja el formulario y DETIENE la ejecución
if not st.session_state.autenticado:
    st.markdown('<p class="main-title">🔐 CREC-ERP - Acceso Blindado</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Sistema protegido de gestión empresarial</p>', unsafe_allow_html=True)
 
    if st.session_state.intentos_fallidos >= 3:
        st.error("🚨 **Demasiados intentos fallidos.** El acceso está temporalmente restringido por seguridad.")
        st.stop()

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("form_login_blindado"):
            usuario_input = st.text_input("👤 Usuario / RUT / Operador:")
            password_input = st.text_input("🔑 Contraseña:", type="password")
            btn_ingresar = st.form_submit_button("🚀 Entrar al Sistema", use_container_width=True)
         
        if btn_ingresar:
            usuario_limpio = str(usuario_input).strip()
            password_limpio = str(password_input).strip()
          
            if not usuario_limpio or not password_limpio:
                st.error("❌ Debes ingresar tanto el usuario como la contraseña.")
            else:
                supabase_client = globals().get('supabase', None) or st.session_state.get("supabase", None)

                # 1. Validación Admin Master desde secretos (sin valores quemados en código)
                if (
                    ADMIN_MASTER_USER 
                    and ADMIN_MASTER_PASS 
                    and usuario_limpio.lower() == ADMIN_MASTER_USER 
                    and password_limpio == ADMIN_MASTER_PASS
                ):
                    st.session_state.autenticado = True
                    st.session_state.es_admin_dev = True
                    st.session_state.usuario_logueado = "Administrador Master"
                    st.session_state.negocio_actual = "admin_general"
                    st.session_state.nombre_empresa = "CREC-ERP Master"
                    st.session_state.rol_usuario = "Administrador"
                    st.session_state.tipo_usuario = "Propietario"
                    st.session_state.modulos_permitidos = "ALL"
                    st.session_state.intentos_fallidos = 0
                    st.success("🛠️ ¡Acceso Maestro Autorizado!")
                    st.rerun()
                else:
                    acceso_exitoso = False
                    
                    # 1.5 Validación Propietario en Supabase (Dueño del Negocio)
                    if supabase_client:
                        try:
                            res_dueño = supabase_client.table("empresas").select("*").eq("rut_empresa", usuario_limpio).execute()
                            if res_dueño and res_dueño.data:
                                datos_empresa = res_dueño.data[0]
                                pass_db = str(datos_empresa.get("password", ""))
                                if pass_db == password_limpio:
                                    lic_activa = datos_empresa.get("licencia_activa", True)
                                    fecha_exp_str = datos_empresa.get("fecha_expiracion")
                                    expirada_por_fecha = False
                                    
                                    if fecha_exp_str and str(fecha_exp_str).strip() not in ["None", "NaT", "nan", ""]:
                                        try:
                                            expirada_por_fecha = pd.to_datetime(str(fecha_exp_str)).date() < date.today()
                                        except Exception:
                                            pass

                                    if lic_activa and not expirada_por_fecha:
                                        st.session_state.autenticado = True
                                        st.session_state.es_admin_dev = False
                                        st.session_state.negocio_actual = usuario_limpio
                                        st.session_state.usuario_logueado = "Propietario / Administrador"
                                        st.session_state.rol_usuario = "Propietario"
                                        st.session_state.tipo_usuario = "Propietario"
                                        st.session_state.modulos_permitidos = "ALL"
                                        st.session_state.intentos_fallidos = 0
                                        st.session_state.nombre_empresa = datos_empresa.get("empresa_nombre", usuario_limpio)
                                        acceso_exitoso = True
                                        st.rerun()
                                    else:
                                        st.error("❌ La licencia de esta empresa se encuentra expirada o inactiva.")
                                        st.link_button("💳 Renovar Licencia Ahora", "https://mpago.la/1XfbC1E", type="primary", use_container_width=True)
                                        acceso_exitoso = True
                        except Exception:
                            pass
                    
                    # 2. Validación Usuarios Operativos (Vendedores, Cajeros, Bodegueros, etc.)
                    if not acceso_exitoso and supabase_client:
                        try:
                            res_usr = supabase_client.table("usuarios").select("*").eq("rut_usuario", usuario_limpio).execute()
                            if res_usr and res_usr.data:
                                datos_usr = res_usr.data[0]
                                if str(datos_usr.get("password_hash")) == password_limpio:
                                    id_empresa = datos_usr.get("empresa_id")
                                    res_emp = supabase_client.table("empresas").select("rut_empresa", "empresa_nombre", "licencia_activa", "fecha_expiracion").eq("id", id_empresa).execute()
                                    if res_emp and res_emp.data:
                                        datos_empresa = res_emp.data[0]
                                        lic_activa = datos_empresa.get("licencia_activa", True)
                                        fecha_exp_str = datos_empresa.get("fecha_expiracion")
                                        expirada_por_fecha = False
                                        
                                        if fecha_exp_str and str(fecha_exp_str).strip() not in ["None", "NaT", "nan", ""]:
                                            try:
                                                expirada_por_fecha = pd.to_datetime(str(fecha_exp_str)).date() < date.today()
                                            except Exception:
                                                pass

                                        if lic_activa and not expirada_por_fecha:
                                            rut_negocio = datos_empresa.get("rut_empresa")
                                            nombre_negocio = datos_empresa.get("empresa_nombre")
                                            rol_encontrado = str(datos_usr.get("rol", "Operador")).strip()
                                            
                                            # REGLA POR DEFECTO: Vendedor en Ruta (Sólo Preventa)
                                            if "vendedor en ruta" in rol_encontrado.lower() or rol_encontrado.lower() == "vendedor":
                                                st.session_state.autenticado = True
                                                st.session_state.es_admin_dev = False
                                                st.session_state.negocio_actual = rut_negocio
                                                st.session_state.usuario_logueado = datos_usr.get("nombre", usuario_limpio)
                                                st.session_state.rol_usuario = rol_encontrado
                                                st.session_state.tipo_usuario = "Vendedor"
                                                st.session_state.modulos_permitidos = ["🏠 Home / Bienvenida", "🚚 Logística y Distribución (Preventa)"]
                                                st.session_state.menu_seleccionado = "🚚 Logística y Distribución (Preventa)"
                                                st.session_state.intentos_fallidos = 0
                                                st.session_state.nombre_empresa = nombre_negocio
                                                acceso_exitoso = True
                                                st.rerun()
                                            else:
                                                # OTROS ROLES: Módulos configurados individualmente por el Propietario en la BD
                                                raw_modulos = datos_usr.get("modulos", "")
                                                
                                                if str(raw_modulos).upper().strip() == "ALL":
                                                    modulos_operador = list(modulos_totales)
                                                else:
                                                    modulos_operador = normalizar_lista_modulos(raw_modulos)
                                                
                                                if not raw_modulos and len(modulos_operador) <= 1:
                                                    st.error("❌ El Propietario aún no ha asignado módulos a esta cuenta.")
                                                    acceso_exitoso = True 
                                                else:
                                                    st.session_state.autenticado = True
                                                    st.session_state.es_admin_dev = False
                                                    st.session_state.negocio_actual = rut_negocio
                                                    st.session_state.usuario_logueado = datos_usr.get("nombre", usuario_limpio)
                                                    st.session_state.rol_usuario = rol_encontrado
                                                    st.session_state.tipo_usuario = "Operador"
                                                    st.session_state.modulos_permitidos = modulos_operador
                                                    st.session_state.intentos_fallidos = 0
                                                    st.session_state.nombre_empresa = nombre_negocio
                                                    acceso_exitoso = True
                                                    st.rerun()
                                        else:
                                            st.error("❌ La licencia de la empresa se encuentra expirada.")
                                            st.link_button("💳 Renovar Licencia Ahora", "https://mpago.la/1XfbC1E", type="primary", use_container_width=True)
                                            acceso_exitoso = True
                        except Exception:
                            pass
                        
                    if not acceso_exitoso:
                        st.session_state.intentos_fallidos += 1
                        intentos_restantes = 3 - st.session_state.intentos_fallidos
                        st.error(f"❌ Usuario no encontrado o contraseña incorrecta. Te quedan {intentos_restantes} intento(s).")

    st.stop()


# ==============================================================================
# TODO LO SIGUIENTE SOLO SE EJECUTA SI EL USUARIO YA ESTÁ AUTENTICADO
# ==============================================================================

# --- 5. CONFIGURACIÓN DE RUTAS Y ARCHIVOS DEL NEGOCIO ACTIVO ---
CLIENTES_DIR = globals().get('CLIENTES_DIR', 'clientes')
PERMISOS_FILE = globals().get('PERMISOS_FILE', 'permisos.json')

negocio_seleccionado = st.session_state.get("negocio_actual", None)
if negocio_seleccionado and negocio_seleccionado != "admin_general":
    ruta_negocio = os.path.join(CLIENTES_DIR, str(negocio_seleccionado))
    os.makedirs(ruta_negocio, exist_ok=True)
    archivos_en_carpeta = os.listdir(ruta_negocio) if os.path.exists(ruta_negocio) else []
    archivo_base = next((os.path.join(ruta_negocio, f) for f in archivos_en_carpeta if f.startswith("BASE DE DATOS")), os.path.join(ruta_negocio, "BASE DE DATOS.xlsx"))
    archivo_compras = next((os.path.join(ruta_negocio, f) for f in archivos_en_carpeta if f.startswith("Libro_Compras")), os.path.join(ruta_negocio, "Libro_Compras.xlsx"))
else:
    ruta_negocio = CLIENTES_DIR
    archivo_base = None
    archivo_compras = None

st.session_state.negocio_seleccionado = negocio_seleccionado


# --- 6. BARRA LATERAL, PERMISOS Y PANEL DESARROLLADOR ---
if not st.session_state.get("es_admin_dev", False):
    rut_actual = st.session_state.get("negocio_seleccionado")
    supabase_client = globals().get('supabase', None) or st.session_state.get("supabase", None)
    
    if rut_actual and supabase_client:
        try:
            res_lic = supabase_client.table("empresas").select("licencia_activa", "fecha_expiracion").eq("rut_empresa", rut_actual).execute()
            if res_lic and res_lic.data:
                datos_lic = res_lic.data[0]
                estado_lic = str(datos_lic.get("licencia_activa", "")).lower()
                fecha_exp_str = datos_lic.get("fecha_expiracion")
                
                expirada_por_fecha = False
                if fecha_exp_str and str(fecha_exp_str).strip() not in ["None", "NaT", "nan", ""]:
                    try:
                        expirada_por_fecha = pd.to_datetime(str(fecha_exp_str)).date() < date.today()
                    except Exception:
                        pass

                lic_valida = (estado_lic in ["true", "1", "t"]) and not expirada_por_fecha

                if not lic_valida:
                    st.error("🚨 **LICENCIA EXPIRADA O INACTIVA**")
                    st.info("Tu suscripción no se encuentra activa. Para seguir utilizando el sistema, realiza la renovación.")
                    st.link_button("💳 Renovar Licencia Ahora", "https://mpago.la/2PrU39R", type="primary", use_container_width=True)
                    
                    if st.button("🚪 Cerrar Sesión", use_container_width=True):
                        st.session_state.clear()
                        st.rerun()
                    
                    st.stop()
        except Exception:
            pass

st.sidebar.markdown(f"👤 Usuario: **{st.session_state.get('usuario_logueado', 'Ninguno')}**")
st.sidebar.markdown(f"🏢 Negocio: *{st.session_state.get('nombre_empresa', 'NINGUNO')}*")

if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.clear()
    st.rerun()

if not st.session_state.get("es_admin_dev", False):
    st.sidebar.write("") 
    st.sidebar.link_button("💳 Renovar Licencia Mensual", "https://mpago.la/2PrU39R", type="primary", use_container_width=True)

    try:
        rut_actual = st.session_state.get("negocio_seleccionado") 
        supabase_client = globals().get('supabase', None) or st.session_state.get("supabase", None)
        if rut_actual and supabase_client:
            res_licencia = supabase_client.table("empresas").select("fecha_expiracion").eq("rut_empresa", rut_actual).execute()
            
            if res_licencia and res_licencia.data:
                fecha_exp_str = res_licencia.data[0].get("fecha_expiracion")
                if fecha_exp_str and str(fecha_exp_str).strip() not in ["None", "NaT", "nan", ""]:
                    hoy = date.today()
                    fecha_exp_date = pd.to_datetime(str(fecha_exp_str)).date()
                    dias_restantes = (fecha_exp_date - hoy).days
                    
                    if 0 < dias_restantes <= 5:
                        st.sidebar.warning(f"⚠️ **Atención:** Tu licencia expira en **{dias_restantes} días**.")
                    elif dias_restantes == 0:
                        st.sidebar.error("🚨 **Último día:** Tu licencia expira **HOY**.")
                    elif dias_restantes < 0:
                        st.sidebar.error(f"🚫 **Licencia Expirada** hace {abs(dias_restantes)} días.")
    except Exception:
        pass

st.sidebar.divider()

def cargar_permisos():
    if os.path.exists(PERMISOS_FILE):
        try:
            with open(PERMISOS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def guardar_permisos(datos):
    try:
        with open(PERMISOS_FILE, "w") as f:
            json.dump(datos, f, indent=4)
    except Exception:
        pass

if st.session_state.get("es_admin_dev", False) and "🔑 Control Maestro de Licencias" not in modulos_totales:
    modulos_totales.append("🔑 Control Maestro de Licencias")

if st.session_state.get("es_admin_dev", False):
    with st.sidebar.expander("🛠️ Panel de Desarrollador (Licencias y Mantenimiento)"):
        st.success("✔️ Modo Desarrollador Activo")
        
        negocios_disponibles = []
        try:
            supabase_cli = globals().get('supabase', None) or st.session_state.get("supabase", None)
            if supabase_cli:
                res_empresas = supabase_cli.table("empresas").select("rut_empresa").execute()
                if res_empresas and res_empresas.data:
                    negocios_disponibles = [str(emp["rut_empresa"]) for emp in res_empresas.data if emp.get("rut_empresa")]
        except Exception:
            pass
            
        if not negocios_disponibles:
            negocios_disponibles = ["15382273-5"]

        tab_lic, tab_crear, tab_mant = st.tabs(["⚙️ Licencias", "➕ Crear Negocio", "🧹 Mantenimiento"])
        
        with tab_lic:
            negocio_a_modificar = st.selectbox("Selecciona Negocio:", negocios_disponibles, key="sel_dev_negocio_nico")
            db_permisos = cargar_permisos()
            if negocio_a_modificar not in db_permisos:
                db_permisos[negocio_a_modificar] = {mod: True for mod in modulos_totales}
           
            with st.form(f"form_licencia_dev_{negocio_a_modificar}"):
                permisos_temporales = {}
                for mod in modulos_totales:
                    estado_actual = db_permisos[negocio_a_modificar].get(mod, True)
                    permisos_temporales[mod] = st.checkbox(mod, value=estado_actual, key=f"chk_dev_{negocio_a_modificar}_{mod}")
               
                if st.form_submit_button("💾 Guardar Licencia"):
                    db_permisos[negocio_a_modificar] = permisos_temporales
                    guardar_permisos(db_permisos)
                    st.success("✅ ¡Licencia actualizada!")
                    st.rerun()

        with tab_crear:
            with st.form("form_crear_cliente_dev_unico"):
                id_negocio = st.text_input("ID Carpeta / RUT (ej: 77297004-8)", key="input_id_neg")
                nombre_comercial = st.text_input("Nombre Comercial / Razón Social", key="input_nom_neg")
                password_cliente = st.text_input("Contraseña / RUT", type="password", key="input_pass_neg")
                fecha_exp = st.date_input("Fecha de Expiración Inicial", value=date(2026, 12, 31), key="input_fech_neg")
               
                guardar_nuevo = st.form_submit_button("💾 Crear y Guardar Negocio")
               
                if guardar_nuevo:
                    if not id_negocio or not nombre_comercial:
                        st.warning("⚠️ Debes completar el ID y el Nombre.")
                    else:
                        db_permisos = cargar_permisos()
                        db_permisos[id_negocio] = {mod: True for mod in modulos_totales}
                        guardar_permisos(db_permisos)
                        
                        try:
                            supabase_cli = globals().get('supabase', None) or st.session_state.get("supabase", None)
                            if supabase_cli:
                                supabase_cli.table("empresas").insert({
                                    "rut_empresa": id_negocio,
                                    "empresa_nombre": nombre_comercial,
                                    "password": password_cliente,
                                    "fecha_expiracion": str(fecha_exp),
                                    "licencia_activa": True
                                }).execute()
                        except Exception:
                            pass 
                        
                        st.success(f"✨ ¡Negocio '{nombre_comercial}' creado con éxito!")
                        st.rerun()

        with tab_mant:
            st.markdown("#### 🧹 Reseteo y Limpieza Remota")
            negocio_a_limpiar = st.selectbox("Selecciona Negocio a Gestionar:", negocios_disponibles, key="limpiar_negocio_sel_nico")
            dir_cliente_objetivo = os.path.join(CLIENTES_DIR, negocio_a_limpiar)
            confirmar_borrado = st.checkbox("Confirmo que deseo restablecer este negocio", key="chk_confirmar_fabrica")

            if st.button("🚨 Restablecer a Versión de Fábrica", type="primary", key="btn_version_fabrica"):
                if not confirmar_borrado:
                    st.error("❌ Debes marcar la casilla de confirmación.")
                else:
                    try:
                        import shutil
                        if os.path.exists(dir_cliente_objetivo):
                            for archivo in os.listdir(dir_cliente_objetivo):
                                ruta_archivo = os.path.join(dir_cliente_objetivo, archivo)
                                if os.path.isfile(ruta_archivo) and archivo != "logo_empresa.png":
                                    os.remove(ruta_archivo)
                            for carpeta_sub in ["archivador_ventas", "archivador_compras"]:
                                dir_sub = os.path.join(dir_cliente_objetivo, carpeta_sub)
                                if os.path.exists(dir_sub):
                                    shutil.rmtree(dir_sub)
                        st.success(f"✨ ¡Negocio '{negocio_a_limpiar}' restablecido!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al restablecer: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("© 2026 CREC-ERP")
st.sidebar.markdown("Desarrollado por **Sebastián Calderón**")


# --- 7. INICIALIZACIÓN Y APLICACIÓN DE JERARQUÍA DE MÓDULOS ---
if "menu_seleccionado" not in st.session_state:
    st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []
if "ejecutar_cobro" not in st.session_state:
    st.session_state.ejecutar_cobro = False
if "estado_pago" not in st.session_state:
    st.session_state.estado_pago = False
if "ultimo_recibo" not in st.session_state:
    st.session_state.ultimo_recibo = None
if "formas_pago_erp" not in st.session_state:
    st.session_state.formas_pago_erp = [
        "Efectivo", "Tarjeta de Débito", "Tarjeta de Crédito", 
        "Transferencia Electrónica", "Cheque", "Cuenta Corriente / Crédito Directo"
    ]

# Determinación de módulos según el rol/asignación del Propietario
db_permisos_actuales = cargar_permisos()
negocio_actual_sesion = st.session_state.get('negocio_seleccionado', '')

if st.session_state.get("modulos_permitidos") == "ALL":
    if negocio_actual_sesion in db_permisos_actuales:
        permisos_negocio = db_permisos_actuales[negocio_actual_sesion]
        lista_modulos_permitidos = [mod for mod in modulos_totales if permisos_negocio.get(mod, True)]
    else:
        lista_modulos_permitidos = list(modulos_totales)
elif isinstance(st.session_state.get("modulos_permitidos"), list):
    lista_modulos_permitidos = list(st.session_state.get("modulos_permitidos"))
else:
    lista_modulos_permitidos = ["🏠 Home / Bienvenida"]

if "🏠 Home / Bienvenida" not in lista_modulos_permitidos:
    lista_modulos_permitidos.insert(0, "🏠 Home / Bienvenida")

# RENDERIZADO DEL MENÚ LATERAL (SOLO POST-LOGIN)
menu = st.sidebar.selectbox(
    "🧭 Selecciona un Módulo:",
    lista_modulos_permitidos,
    index=lista_modulos_permitidos.index(st.session_state.menu_seleccionado) if st.session_state.menu_seleccionado in lista_modulos_permitidos else 0
)
st.session_state.menu_seleccionado = menu

query_params = st.query_params
param_caja = query_params.get("caja", None)

if param_caja:
    menu = "💰 Módulo de Ventas (POS)"
    st.sidebar.info(f"🖥️ Modo Terminal Activo: **{param_caja}**")

def cargar_datos(path_db):
    if path_db and os.path.exists(path_db):
        df = pd.read_excel(path_db, dtype={'Código': str})
        if 'Activo' in df.columns:
            df = df[df['Activo'].astype(str).str.strip().str.capitalize() == 'Si']
        return df
    return None

df_base = cargar_datos(archivo_base)

def mostrar_encabezado_con_home(titulo_modulo):
    col_titulo, col_btn = st.columns([4, 1])
    with col_titulo:
        nombre_mostrar = st.session_state.get('nombre_empresa', st.session_state.get('negocio_seleccionado', 'Empresa no seleccionada'))
        st.subheader(f"{titulo_modulo} (Negocio: {nombre_mostrar})")
    with col_btn:
        st.write("")
        if st.button("🏠 Volver al Home", use_container_width=True, key=f"btn_home_{titulo_modulo}"):
            st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
            st.rerun()


# --- 8. RENDERIZADO DEL HOME Y NAVEGACIÓN DE MÓDULOS ---
if menu == "🏠 Home / Bienvenida":
    st.markdown(f"<p class='main-title'>🪙 CREC-ERP: {st.session_state.nombre_empresa if st.session_state.nombre_empresa else 'GENERAL'}</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>Selecciona un módulo para comenzar:</p>", unsafe_allow_html=True)
   
    if st.session_state.get("es_admin_dev", False):
        st.error("🛠️ **PANEL DE CONTROL MAESTRO**")
        if st.button("🔑 ABRIR CONTROL DE LICENCIAS Y CLIENTES", type="primary", use_container_width=True):
            st.session_state.menu_seleccionado = "🔑 Control Maestro de Licencias"
            st.rerun()
        st.divider()

    modulos_disponibles_home = [
        {"id": "dash", "nombre_ref": "Dashboard Ejecutivo", "label": "📊 Dashboard Ejecutivo"},
        {"id": "inv", "nombre_ref": "Inventario y Productos", "label": "📦 Inventario y Productos"},
        {"id": "prod", "nombre_ref": "Producción y Recetas", "label": "🍔 Producción y Recetas"},
        {"id": "pos", "nombre_ref": "Módulo de Ventas (POS)", "label": "💰 Módulo de Ventas (POS)"},
        {"id": "nc", "nombre_ref": "Notas de Crédito", "label": "🔄 Notas de Crédito"},
        {"id": "comp", "nombre_ref": "Registrar Compra (CPP)", "label": "🛒 Registrar Compra (CPP)"},
        {"id": "mermas", "nombre_ref": "Mermas y Ajustes", "label": "📉 Mermas y Ajustes"},
        {"id": "inf", "nombre_ref": "Informes y Movimientos (Kardex)", "label": "📋 Informes y Movimientos"},
        {"id": "ctrl", "nombre_ref": "Control y Gestión de Inventario", "label": "⚠️ Control y Gestión de Inventario"},
        {"id": "fin", "nombre_ref": "Módulo de Finanzas", "label": "📊 Módulo de Finanzas"},
        {"id": "cuadratura", "nombre_ref": "Cuadratura Diaria", "label": "📒 Cuadratura Diaria"},
        {"id": "cobrar", "nombre_ref": "Cuentas por Cobrar", "label": "📑 Cuentas por Cobrar"},
        {"id": "conci", "nombre_ref": "Conciliación y Retiros Seguros", "label": "🏦 Conciliación y Retiros Seguros"},
        {"id": "historial", "nombre_ref": "Historial de Ventas", "label": "📚 Historial de Ventas"},
        {"id": "report", "nombre_ref": "Reportes y Analítica", "label": "📈 Reportes y Analítica"},
        {"id": "distribucion", "nombre_ref": "Logística y Distribución (Preventa)", "label": "🚚 Logística y Distribución (Preventa)"},
        {"id": "conf", "nombre_ref": "Configuración General", "label": "⚙️ Configuración General"}
    ]

    botones_activos = [mod for mod in modulos_disponibles_home if any(mod["nombre_ref"].lower() in str(p).lower() for p in lista_modulos_permitidos)]

    if botones_activos:
        num_columnas = 2
        for i in range(0, len(botones_activos), num_columnas):
            fila_mods = botones_activos[i:i + num_columnas]
            cols = st.columns(num_columnas)
            for idx_col, mod in enumerate(fila_mods):
                with cols[idx_col]:
                    if st.button(mod["label"], use_container_width=True, key=f"btn_home_{mod['id']}"):
                        nombre_destino = next((p for p in lista_modulos_permitidos if mod["nombre_ref"].lower() in str(p).lower()), mod["nombre_ref"])
                        st.session_state.menu_seleccionado = nombre_destino
                        st.rerun()
    else:
        st.info("ℹ️ Tu usuario no tiene módulos activos asignados. Contacta al Administrador.")

# --- 9. RENDERIZADO DE MÓDULOS DE INVENTARIO Y REGISTROS ---
elif menu == "📦 Inventario y Productos":
    mostrar_encabezado_con_home("📦 Administración de Inventario")
    
    tab_inv1, tab_inv2, tab_inv3, tab_inv4 = st.tabs(["📦 Productos", "👥 Clientes", "🚚 Proveedores", "🏢 Bodegas y Sucursales"])
    
    with tab_inv1:
        st.markdown("#### ➕ Registrar o Gestionar Productos")
        rut_actual = st.session_state.get("negocio_seleccionado")
        
        try:
            res_inv = supabase.table("productos").select("*").eq("rut_empresa", rut_actual).execute()
            df_inv = pd.DataFrame(res_inv.data)
            st.success(f"Base de datos conectada con éxito desde la Nube. ({len(df_inv)} productos)")
            if not df_inv.empty:
                st.dataframe(df_inv, use_container_width=True)
            
            st.markdown("### 🆕 Ingresar Nuevo Producto a la Base de Datos")
            
            bodegas_existentes = ["Bodega Principal"]
            
            try:
                res_bodegas = supabase.table("bodegas").select("nombre").eq("rut_empresa", rut_actual).execute()
                if res_bodegas.data:
                    for row in res_bodegas.data:
                        nombre_b = str(row.get("nombre", "")).strip(' "\'') 
                        if nombre_b and nombre_b not in bodegas_existentes:
                            bodegas_existentes.append(nombre_b)
            except Exception:
                pass 
                
            if not df_inv.empty and "bodega" in df_inv.columns:
                bodegas_extra = df_inv["bodega"].dropna().unique().tolist()
                for b in bodegas_extra:
                    b_clean = str(b).strip(' "\'') 
                    if b_clean and b_clean not in bodegas_existentes:
                        bodegas_existentes.append(b_clean)
                
            bodegas_existentes.append("➕ Crear Nueva Bodega / Sucursal...")

            codigo_scanned_nuevo = st.text_input("📷 Digita o ingresa el código del producto nuevo:", key="scan_nuevo_prod")
        
            with st.form("form_crear_producto_multi", clear_on_submit=True):
                st.markdown("##### Datos Básicos y Ubicación")
                col_b1, col_b2 = st.columns(2)
                
                with col_b1:
                    codigo = st.text_input("Código del Producto (EAN o Interno) *", value=codigo_scanned_nuevo if codigo_scanned_nuevo else "")
                    descripcion = st.text_input("Descripción / Nombre del Producto *")
                    categoria = st.selectbox("Categoría", ["Ninguna", "BEBIDAS", "ABARROTES", "SNACKS", "OTROS"])
                    
                with col_b2:
                    bodega_seleccionada = st.selectbox("🏢 Asignar a Bodega / Sucursal:", bodegas_existentes)
                    nueva_bodega = ""
                    if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal...":
                        nueva_bodega = st.text_input("✍️ Escribe el nombre de la nueva Bodega:")
                    
                    stock = st.number_input("Stock Inicial a ingresar en esta bodega", min_value=0.0, step=1.0)
                    costo = st.number_input("Costo de Compra Neto ($)", min_value=0.0, step=100.0)

                st.markdown("##### 💡 Configuración Tributaria (Ingresa el Neto o el Bruto)")
                
                nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
                tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_act or str(rut_actual) == "219449970012" else 19.0
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    precio_neto = st.number_input("Precio Neto ($)", min_value=0.0, step=100.0)
                    porcentaje_iva = st.number_input("% de IVA", min_value=0.0, value=tasa_defecto, step=1.0)
                    impuesto_especifico = st.selectbox("Impuesto Específico", ["Ninguno", "IABA 10", "IABA 18", "ILA", "ILA 31.5"])
                with col_p2:
                    precio_venta = st.number_input("Precio Bruto/Final ($)", min_value=0.0, step=100.0)
                    es_exento = st.selectbox("¿Es Exento de IVA?", ["No", "Si"])
                    activo = st.selectbox("¿Activo en el sistema?", ["Si", "No"])
            
                btn_crear_prod = st.form_submit_button("💾 Guardar Producto en la Bodega")

                if btn_crear_prod:
                    bodega_final = nueva_bodega.strip() if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal..." else bodega_seleccionada
                    
                    if not codigo or not descripcion or (precio_venta <= 0 and precio_neto <= 0):
                        st.warning("⚠️ Por favor, completa Código, Descripción y un Precio (Neto o Bruto).")
                    elif not bodega_final:
                        st.warning("⚠️ Debes asignar un nombre a la bodega.")
                    else:
                        iva_final = 0.0 if es_exento == "Si" else float(porcentaje_iva)
                        p_neto_calc, p_bruto_calc = float(precio_neto), float(precio_venta)
                        
                        if p_bruto_calc > 0 and p_neto_calc == 0:
                            p_neto_calc = p_bruto_calc / (1.0 + (iva_final / 100.0))
                        elif p_neto_calc > 0:
                            p_bruto_calc = p_neto_calc * (1.0 + (iva_final / 100.0))

                        nuevo_producto = {
                            "rut_empresa": rut_actual,
                            "codigo": codigo.strip(),
                            "bodega": bodega_final.strip(' "\''),
                            "descripcion": descripcion.strip(),
                            "categoria": categoria if categoria != "Ninguna" else None,
                            "costo": costo,
                            "precio_neto": round(p_neto_calc, 2),
                            "porcentaje_iva": round(iva_final, 2),
                            "precio_venta": round(p_bruto_calc, 2),
                            "stock": stock,
                            "es_exento": es_exento,
                            "impuesto_especifico": impuesto_especifico if impuesto_especifico != "Ninguno" else None,
                            "activo": activo
                        }
                        
                        try:
                            res_check = supabase.table("productos").select("id").eq("rut_empresa", rut_actual).eq("codigo", codigo.strip()).eq("bodega", bodega_final).execute()
                            
                            if res_check.data:
                                supabase.table("productos").update(nuevo_producto).eq("id", res_check.data[0]["id"]).execute()
                                st.success(f"✅ Producto actualizado en '{bodega_final}'.")
                            else:
                                supabase.table("productos").insert(nuevo_producto).execute()
                                st.success(f"✅ ¡Producto nuevo creado exitosamente en '{bodega_final}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar en la nube: {e}")
        except Exception as e:
            st.error(f"⚠️ Error al conectar con Supabase: {e}")

    with tab_inv2:
        st.markdown("#### 👥 Maestro de Clientes")
        df_clientes = pd.DataFrame()
        try:
            res_cli = supabase.table("clientes").select("*").eq("id_negocio", rut_actual).execute()
            if res_cli.data:
                df_clientes = pd.DataFrame(res_cli.data)
                renames = {}
                if "nombre" in df_clientes.columns and "Nombre_Cliente" not in df_clientes.columns:
                    renames["nombre"] = "Nombre_Cliente"
                if "direccion" in df_clientes.columns and "Direccion" not in df_clientes.columns:
                    renames["direccion"] = "Direccion"
                if renames:
                    df_clientes = df_clientes.rename(columns=renames)
        except Exception as e:
            st.error(f"⚠️ Error cargando clientes desde la nube: {e}")

        st.dataframe(df_clientes, use_container_width=True)
        
        with st.form("form_nuevo_cliente_local", clear_on_submit=True):
            st.markdown("##### Registrar Cliente Nuevo")
            cl_nom = st.text_input("Nombre / Razón Social")
            cl_rut = st.text_input("RUT / Identificación")
            cl_tel = st.text_input("Teléfono")
            cl_mail = st.text_input("Correo Electrónico")
            cl_dir = st.text_input("Dirección")
            
            btn_g_cliente = st.form_submit_button("💾 Guardar Cliente")
            if btn_g_cliente:
                if not cl_nom or not cl_rut:
                    st.warning("⚠️ Debes ingresar al menos el nombre y el RUT del cliente.")
                else:
                    nuevo_cliente_nube = {
                        "rut": str(cl_rut).strip(),
                        "nombre": str(cl_nom).strip(),
                        "telefono": str(cl_tel).strip(),
                        "correo": str(cl_mail).strip(),
                        "direccion": str(cl_dir).strip(),
                        "id_negocio": str(rut_actual).strip()
                    }
                    try:
                        supabase.table("clientes").upsert(nuevo_cliente_nube, on_conflict="rut").execute()
                        st.success("✅ ¡Cliente guardado con éxito en la nube!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Supabase: {e}")

    with tab_inv3:
        st.markdown("#### 🚚 Directorio de Proveedores")
        df_proveedores = pd.DataFrame()
        try:
            res_prov = supabase.table("proveedores").select("*").eq("id_negocio", rut_actual).execute()
            if res_prov.data:
                df_proveedores = pd.DataFrame(res_prov.data)
                renames_prov = {}
                if "nombre" in df_proveedores.columns and "Nombre_Proveedor" not in df_proveedores.columns:
                    renames_prov["nombre"] = "Nombre_Proveedor"
                if "rut" in df_proveedores.columns and "Rut" not in df_proveedores.columns:
                    renames_prov["rut"] = "Rut"
                if "contacto" in df_proveedores.columns and "Contacto" not in df_proveedores.columns:
                    renames_prov["contacto"] = "Contacto"
                if "telefono" in df_proveedores.columns and "Telefono" not in df_proveedores.columns:
                    renames_prov["telefono"] = "Telefono"
                if "email" in df_proveedores.columns and "Email" not in df_proveedores.columns:
                    renames_prov["email"] = "Email"
                if renames_prov:
                    df_proveedores = df_proveedores.rename(columns=renames_prov)
        except Exception as e:
            st.error(f"⚠️ Error cargando proveedores desde la nube: {e}")

        st.dataframe(df_proveedores, use_container_width=True)
        
        with st.form("form_nuevo_proveedor_nube", clear_on_submit=True):
            st.markdown("##### Registrar Proveedor Nuevo")
            pr_nom = st.text_input("Nombre del Proveedor")
            pr_rut = st.text_input("RUT Proveedor")
            pr_cont = st.text_input("Persona de Contacto")
            pr_tel = st.text_input("Teléfono")
            pr_mail = st.text_input("Email")
            
            btn_g_prov = st.form_submit_button("💾 Guardar Proveedor")
            if btn_g_prov:
                if not pr_nom or not pr_rut:
                    st.warning("⚠️ Debes ingresar al menos el nombre y el RUT del proveedor.")
                else:
                    nuevo_proveedor_nube = {
                        "rut": str(pr_rut).strip(),
                        "nombre": str(pr_nom).strip(),
                        "contacto": str(pr_cont).strip(),
                        "telefono": str(pr_tel).strip(),
                        "correo": str(pr_mail).strip(),
                        "id_negocio": str(rut_actual).strip()
                    }
                    try:
                        supabase.table("proveedores").insert(nuevo_proveedor_nube).execute()
                        st.success("✅ ¡Proveedor guardado con éxito en la nube!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Supabase: {e}")

    with tab_inv4:
        st.markdown("### 🏢 Administración de Bodegas y Sucursales")
        st.info("💡 Crea diferentes ubicaciones físicas para controlar el stock separado.")
        
        df_bodegas = pd.DataFrame()
        try:
            res_bodegas = supabase.table("bodegas").select("*").eq("rut_empresa", rut_actual).execute()
            if res_bodegas.data:
                df_bodegas = pd.DataFrame(res_bodegas.data)
                st.dataframe(df_bodegas[["nombre", "direccion"]], use_container_width=True)
            else:
                st.warning("⚠️ No tienes bodegas creadas. El sistema asume una 'Bodega Principal' por defecto.")
        except Exception as e:
            st.error(f"⚠️ Error cargando bodegas desde la nube: {e}")

        with st.form("form_nueva_bodega", clear_on_submit=True):
            st.markdown("##### Registrar Nueva Bodega")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                nombre_bodega = st.text_input("Nombre de la Bodega *", placeholder="Ej: Bodega Central")
            with col_b2:
                direccion_bodega = st.text_input("Ubicación / Dirección", placeholder="Opcional")
            
            btn_g_bodega = st.form_submit_button("💾 Crear Bodega")
            
            if btn_g_bodega:
                if not nombre_bodega:
                    st.warning("⚠️ El nombre de la bodega es obligatorio.")
                else:
                    nueva_bodega = {
                        "rut_empresa": rut_actual,
                        "nombre": nombre_bodega.strip(),
                        "direccion": direccion_bodega.strip()
                    }
                    try:
                        supabase.table("bodegas").insert(nueva_bodega).execute()
                        st.success(f"✅ ¡Bodega '{nombre_bodega}' creada con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Supabase: {e}")       

elif menu == "📚 Historial de Ventas":
    mostrar_modulo_historial_ventas(ruta_negocio)                    

elif menu == "📊 Módulo de Finanzas":
    mostrar_encabezado_con_home("📊 Panel de Control Financiero")
    tab_fin1, tab_fin2, tab_fin3, tab_fin4 = st.tabs([
        "💳 Cuentas por Pagar",
        "📅 Calendario de Pagos",
        "💸 Registro de Gastos",
        "🏢 Costos Fijos y Créditos"
    ])
   
    with tab_fin1:
        mostrar_modulo_cuentas_por_pagar(ruta_negocio)
       
    with tab_fin2:
        mostrar_modulo_calendario_pagos(ruta_negocio)
       
    with tab_fin3:
        mostrar_modulo_registro_gastos(supabase)
        
    with tab_fin4:
        mostrar_modulo_costos_fijos(ruta_negocio, supabase)

elif menu == "📒 Cuadratura Diaria":
    mostrar_encabezado_con_home("📒 Cuadratura Diaria")
    mostrar_modulo_cuadratura_diaria(ruta_negocio)

elif menu == "📑 Cuentas por Cobrar":
    mostrar_modulo_cuentas_por_cobrar(ruta_negocio)

# ----------------- SECCIÓN DASHBOARD EJECUTIVO -----------------
elif menu == "📊 Dashboard Ejecutivo":
    mostrar_encabezado_con_home("⚡ Resumen Ejecutivo en Tiempo Real")
    tenant_id = st.session_state.get("negocio_seleccionado") or get_current_tenant()
   
    # 🕒 Selector de Período Temporal
    st.markdown("### 🎛️ Filtro Temporal de Análisis")
    col_f1, _ = st.columns([2, 2])
    with col_f1:
        periodo_seleccionado = st.selectbox(
            "Selecciona el período a visualizar:",
            options=["Diaria (Hoy)", "Semanal (Últimos 7 días)", "Quincenal (Últimos 15 días)", "Mensual (Últimos 30 días)", "Histórico Completo"],
            index=3
        )

    hoy_dt = pd.to_datetime(date.today())
    if periodo_seleccionado == "Diaria (Hoy)":
        fecha_limite = hoy_dt
    elif periodo_seleccionado == "Semanal (Últimos 7 días)":
        fecha_limite = hoy_dt - pd.Timedelta(days=7)
    elif periodo_seleccionado == "Quincenal (Últimos 15 días)":
        fecha_limite = hoy_dt - pd.Timedelta(days=15)
    elif periodo_seleccionado == "Mensual (Últimos 30 días)":
        fecha_limite = hoy_dt - pd.Timedelta(days=30)
    else:
        fecha_limite = None

    # ==============================================================================
    # 1. VENTAS Y DÉBITO FISCAL DESDE SUPABASE
    # ==============================================================================
    total_ventas_periodo = 0.0
    total_debito_fiscal = 0.0
    df_ventas_filtrado = pd.DataFrame()

    try:
        res_v = supabase.table("ventas").select("*").execute()
        if res_v.data:
            df_v = pd.DataFrame(res_v.data)
            if not df_v.empty:
                if 'rut_empresa' in df_v.columns and tenant_id:
                    df_v = df_v[df_v['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                
                if not df_v.empty and 'fecha' in df_v.columns:
                    df_v['Fecha_Parsed'] = pd.to_datetime(df_v['fecha'], errors='coerce')
                    
                    if fecha_limite is not None:
                        if periodo_seleccionado == "Diaria (Hoy)":
                            df_ventas_filtrado = df_v[df_v['Fecha_Parsed'].dt.date == hoy_dt.date()]
                        else:
                            df_ventas_filtrado = df_v[df_v['Fecha_Parsed'] >= fecha_limite]
                    else:
                        df_ventas_filtrado = df_v.copy()

                    if not df_ventas_filtrado.empty:
                        col_monto = 'monto' if 'monto' in df_ventas_filtrado.columns else 'total'
                        if 'folio' in df_ventas_filtrado.columns:
                            total_ventas_periodo = float(df_ventas_filtrado.drop_duplicates(subset=["folio"])[col_monto].sum())
                        else:
                            total_ventas_periodo = float(df_ventas_filtrado[col_monto].sum())

                        if 'iva' in df_ventas_filtrado.columns:
                            total_debito_fiscal = float(df_ventas_filtrado['iva'].sum())
                        else:
                            total_debito_fiscal = float(total_ventas_periodo * (0.19 / 1.19))
    except Exception as e:
        print(f"Error cargando ventas desde la nube: {e}")

    # ==============================================================================
    # 2. COSTOS FIJOS (TABLA DEDICADA 'costos_fijos')
    # ==============================================================================
    costos_fijos = 0.0
    try:
        res_cf = supabase.table("costos_fijos").select("*").eq("activo", True).execute()
        if res_cf.data:
            df_cf = pd.DataFrame(res_cf.data)
            if not df_cf.empty:
                if 'rut_empresa' in df_cf.columns and tenant_id:
                    df_cf = df_cf[df_cf['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                
                if not df_cf.empty and 'monto' in df_cf.columns:
                    costos_fijos = float(pd.to_numeric(df_cf['monto'], errors='coerce').fillna(0).sum())
    except Exception as e:
        print(f"Error cargando tabla costos_fijos desde la nube: {e}")

    # ==============================================================================
    # 3. GASTOS VARIABLES, MERCADERÍA Y CRÉDITO FISCAL (TABLA 'gastos')
    # ==============================================================================
    costos_variables = 0.0
    inversion_mercaderia_gastos = 0.0
    total_credito_fiscal = 0.0
    df_g_filtrado = pd.DataFrame()

    try:
        res_g = supabase.table("gastos").select("*").execute()
        if res_g.data:
            df_g = pd.DataFrame(res_g.data)
            if not df_g.empty:
                if 'rut_empresa' in df_g.columns and tenant_id:
                    df_g = df_g[df_g['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                
                if not df_g.empty and 'fecha' in df_g.columns:
                    df_g['Fecha_Parsed'] = pd.to_datetime(df_g['fecha'], errors='coerce')
                    
                    if fecha_limite is not None:
                        if periodo_seleccionado == "Diaria (Hoy)":
                            df_g_filtrado = df_g[df_g['Fecha_Parsed'].dt.date == hoy_dt.date()]
                        else:
                            df_g_filtrado = df_g[df_g['Fecha_Parsed'] >= fecha_limite]
                    else:
                        df_g_filtrado = df_g.copy()

                    if not df_g_filtrado.empty:
                        col_monto_g = 'monto' if 'monto' in df_g_filtrado.columns else 'total'
                        
                        if 'iva' in df_g_filtrado.columns:
                            total_credito_fiscal = float(df_g_filtrado['iva'].sum())
                        else:
                            total_credito_fiscal = float(df_g_filtrado[col_monto_g].sum() * (0.19 / 1.19))

                        for _, row in df_g_filtrado.iterrows():
                            monto = float(row.get(col_monto_g, 0))
                            tipo = str(row.get('tipo_costo', row.get('tipo', ''))).lower()
                            cat = str(row.get('categoria', '')).lower()

                            if 'fijo' in tipo or any(k in cat for k in ['arriendo', 'sueldo', 'servicio', 'patente', 'fijo']):
                                costos_fijos += monto
                            elif 'mercadería' in cat or 'mercaderia' in cat or 'compra' in cat or 'inventario' in cat:
                                inversion_mercaderia_gastos += monto
                            else:
                                costos_variables += monto
    except Exception as e:
        print(f"Error cargando gastos desde la nube: {e}")

    # ==============================================================================
    # 4. INVENTARIO Y MARGENES DESDE SUPABASE
    # ==============================================================================
    inversion_inventario_costo = 0.0
    total_productos = 0
    margen_promedio = 0.0

    try:
        res_prod = supabase.table("productos").select("costo, precio_venta, stock, rut_empresa").execute()
        if res_prod.data:
            df_prod = pd.DataFrame(res_prod.data)
            if not df_prod.empty:
                if 'rut_empresa' in df_prod.columns and tenant_id:
                    df_prod = df_prod[df_prod['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                
                df_prod['costo'] = pd.to_numeric(df_prod['costo'], errors='coerce').fillna(0)
                df_prod['precio_venta'] = pd.to_numeric(df_prod['precio_venta'], errors='coerce').fillna(0)
                df_prod['stock'] = pd.to_numeric(df_prod['stock'], errors='coerce').fillna(0)

                inversion_inventario_costo = float((df_prod['costo'] * df_prod['stock']).sum())
                total_productos = len(df_prod)

                df_m = df_prod[(df_prod['costo'] > 0) & (df_prod['precio_venta'] > 0)].copy()
                if not df_m.empty:
                    df_m['margen'] = ((df_m['precio_venta'] - df_m['costo']) / df_m['precio_venta']) * 100
                    margen_promedio = float(df_m['margen'].mean())
    except Exception as e:
        print(f"Error cargando inventario desde la nube: {e}")

    # ==============================================================================
    # 5. CÁLCULOS FINANCIEROS Y PUNTO DE EQUILIBRIO
    # ==============================================================================
    total_egresos_operativos = costos_fijos + costos_variables
    utilidad_neta_estimada = total_ventas_periodo - total_egresos_operativos

    pct_margen_decimal = (margen_promedio / 100.0) if margen_promedio > 0 else 0.40
    punto_equilibrio = costos_fijos / pct_margen_decimal if pct_margen_decimal > 0 else 0.0
    estimado_f29_pagar = total_debito_fiscal - total_credito_fiscal

    st.divider()

    # --- BLOQUE 1: ESTRUCTURA DE COSTOS Y VENTAS ---
    st.markdown("### 💰 Flujo Operacional y Estructura de Costos")
    col_b1_1, col_b1_2, col_b1_3, col_b1_4 = st.columns(4)
    with col_b1_1:
        st.metric(label=f"💵 Ventas Totales ({periodo_seleccionado.split()[0]})", value=f"${total_ventas_periodo:,.0f}")
    with col_b1_2:
        st.metric(label="🏢 Costos Fijos", value=f"${costos_fijos:,.0f}", help="Sueldos, arriendos, servicios básicos y patentes activas.")
    with col_b1_3:
        st.metric(label="🚚 Costos Variables", value=f"${costos_variables:,.0f}", help="Combustible, comisiones, fletes, insumos directos.")
    with col_b1_4:
        st.metric(label="🛍️ Inversión en Mercadería", value=f"${inversion_mercaderia_gastos:,.0f}", help="Egresos destinados a compras de stock en el período.")

    st.divider()

    # --- BLOQUE 2: SALUD DE INVENTARIO Y UTILIDAD REAL ---
    st.markdown("### 📈 Inventario, Punto de Equilibrio y Rentabilidad")
    col_b2_1, col_b2_2, col_b2_3 = st.columns(3)
    with col_b2_1:
        st.metric(label="📦 Inventario Valorizado (al Costo)", value=f"${inversion_inventario_costo:,.0f}", delta=f"{total_productos} productos")
    with col_b2_2:
        st.metric(
            label="⚖️ Punto de Equilibrio Mensual", 
            value=f"${punto_equilibrio:,.0f}", 
            help="Monto de venta mínimo necesario para cubrir los costos fijos según tu margen promedio."
        )
    with col_b2_3:
        color_delta = "normal" if utilidad_neta_estimada >= 0 else "inverse"
        st.metric(
            label="💼 Utilidad Neta Estimada", 
            value=f"${utilidad_neta_estimada:,.0f}", 
            delta=f"Egresos Totales: ${total_egresos_operativos:,.0f}",
            delta_color=color_delta
        )

    st.divider()

    # --- BLOQUE 3: SALUD FISCAL E IMPUESTOS (F29) ---
    st.markdown("### 🏛️ Salud Fiscal e Impuestos Estimados (F29)")
    col_b3_1, col_b3_2, col_b3_3 = st.columns(3)
    with col_b3_1:
        st.metric(label="📈 Débito Fiscal (IVA Ventas)", value=f"${total_debito_fiscal:,.0f}", help="IVA recaudado en tus ventas del período.")
    with col_b3_2:
        st.metric(label="📉 Crédito Fiscal (IVA Compras/Gastos)", value=f"${total_credito_fiscal:,.0f}", help="IVA pagado en tus compras y gastos facturados.")
    with col_b3_3:
        label_f29 = "🏛️ Estimado a Pagar (F29)" if estimado_f29_pagar >= 0 else "🏛️ Remanente a Favor"
        st.metric(
            label=label_f29, 
            value=f"${abs(estimado_f29_pagar):,.0f}", 
            delta="A pagar al Fisco" if estimado_f29_pagar >= 0 else "Favor del Contribuyente",
            delta_color="inverse" if estimado_f29_pagar >= 0 else "normal"
        )

    st.divider()

    # --- GRÁFICOS Y TENDENCIAS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("#### 📈 Evolución de Ingresos (Cuadratura Nube)")
        try:
            res_cuat = supabase.table("cuadratura_diaria").select("*").execute()
            if res_cuat.data:
                df_cuat = pd.DataFrame(res_cuat.data)
                if not df_cuat.empty:
                    if 'rut_empresa' in df_cuat.columns and tenant_id:
                        df_cuat = df_cuat[df_cuat['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                    
                    if not df_cuat.empty and 'fecha' in df_cuat.columns:
                        col_monto_cuat = 'monto_total' if 'monto_total' in df_cuat.columns else 'venta_total'
                        df_cuat['Fecha_Parsed'] = pd.to_datetime(df_cuat['fecha'], errors='coerce')
                        if fecha_limite is not None and periodo_seleccionado != "Histórico Completo":
                            if periodo_seleccionado == "Diaria (Hoy)":
                                df_cuat = df_cuat[df_cuat['Fecha_Parsed'].dt.date == hoy_dt.date()]
                            else:
                                df_cuat = df_cuat[df_cuat['Fecha_Parsed'] >= fecha_limite]
                        
                        if not df_cuat.empty and col_monto_cuat in df_cuat.columns:
                            st.line_chart(df_cuat.set_index('fecha')[col_monto_cuat])
                        else:
                            st.info("ℹ️ No hay registros de cuadratura en este período.")
            else:
                st.info("ℹ️ Sin datos de cuadratura diarios en la nube.")
        except Exception:
            st.info("ℹ️ Módulo de cuadratura no disponible en la nube.")

    with col_g2:
        st.markdown("#### 📊 Distribución de Gastos por Categoría")
        if not df_g_filtrado.empty and 'categoria' in df_g_filtrado.columns:
            col_m_g = 'monto' if 'monto' in df_g_filtrado.columns else 'total'
            df_cat = df_g_filtrado.groupby('categoria')[col_m_g].sum().reset_index()
            
            fig_dona = px.pie(
                df_cat, 
                values=col_m_g, 
                names='categoria', 
                hole=0.65,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            
            fig_dona.update_traces(
                textposition='inside', 
                textinfo='percent', 
                hovertemplate="<b>%{label}</b><br>Gasto: $%{value:,.0f}<br>Porcentaje: %{percent}<extra></extra>"
            )
            
            fig_dona.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                margin=dict(t=10, b=10, l=0, r=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            
            st.plotly_chart(fig_dona, use_container_width=True)
        else:
            st.info("ℹ️ No hay registros de gastos para el período seleccionado.")

    st.divider()
    st.markdown("### 🔔 Alertas y Salud Financiera del Negocio")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if total_egresos_operativos > (total_ventas_periodo * 0.7) and total_ventas_periodo > 0:
            st.error("⚠️ **Alerta Financiera:** Los gastos operativos (fijos + variables) superan el 70% de las ventas en este período.")
        else:
            st.success("✅ **Salud Financiera Estable:** Niveles de gastos controlados para el período analizado.")
            
    with col_a2:
        try:
            res_cpp = supabase.table("cuentas_por_pagar").select("*").eq("estado", "PENDIENTE").execute()
            if res_cpp.data:
                df_cpp = pd.DataFrame(res_cpp.data)
                if 'rut_empresa' in df_cpp.columns and tenant_id:
                    df_cpp = df_cpp[df_cpp['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]
                if not df_cpp.empty:
                    st.warning(f"⚠️ Tienes **{len(df_cpp)} factura(s) pendiente(s)** de pago a proveedores.")
                else:
                    st.info("ℹ️ No hay facturas de proveedores pendientes de pago.")
            else:
                st.info("ℹ️ No hay facturas de proveedores pendientes de pago.")
        except Exception:
            st.info("ℹ️ Módulo de cuentas por pagar sin registros activos en la nube.")

# ----------------- SECCIÓN INVENTARIO GENERAL -----------------
elif menu == "📦 Inventario y Productos":
    mostrar_encabezado_con_home("📦 Administración de Inventario")
    
    rut_actual = st.session_state.get("negocio_seleccionado")
    if not rut_actual:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión.")
        st.stop()
   
    # 🚨 AQUÍ AGREGAMOS LA NUEVA PESTAÑA DE INGREDIENTES SIN BORRAR LAS OTRAS
    tab_prod, tab_ing, tab_cli, tab_prov, tab_bod = st.tabs([
        "📦 Productos (Venta)", 
        "🍅 Ingredientes", 
        "👥 Clientes", 
        "🚚 Proveedores", 
        "🏢 Bodegas y Sucursales"
    ])
   
    # --- MOTOR DE BODEGAS (Global para Productos e Ingredientes) ---
    bodegas_existentes = ["Bodega Principal"]
    try:
        res_bodegas = supabase.table("bodegas").select("nombre").eq("rut_empresa", rut_actual).execute()
        if res_bodegas.data:
            for row in res_bodegas.data:
                nombre_b = str(row.get("nombre", "")).strip(' "\'')
                if nombre_b and nombre_b not in bodegas_existentes:
                    bodegas_existentes.append(nombre_b)
    except Exception:
        pass 
        
    try:
        res_inv = supabase.table("productos").select("*").eq("rut_empresa", rut_actual).execute()
        df_inv = pd.DataFrame(res_inv.data)
        if not df_inv.empty and "bodega" in df_inv.columns:
            for b in df_inv["bodega"].dropna().unique().tolist():
                b_clean = str(b).strip(' "\'')
                if b_clean and b_clean not in bodegas_existentes:
                    bodegas_existentes.append(b_clean)
    except Exception:
        df_inv = pd.DataFrame()
        
    bodegas_existentes.append("➕ Crear Nueva Bodega / Sucursal...")

    # ==========================================
    # PESTAÑA 1: PRODUCTOS PARA LA VENTA
    # ==========================================
    with tab_prod:
        st.markdown("### ➕ Registrar o Gestionar Productos")
        if not df_inv.empty:
            # Mostramos solo los productos que sí se venden (Precio > 0)
            df_venta = df_inv[df_inv['precio_venta'] > 0]
            st.success(f"Base de datos conectada con éxito desde la Nube. ({len(df_venta)} productos de venta)")
            st.dataframe(df_venta, use_container_width=True)
            
        st.markdown("### 🆕 Ingresar Nuevo Producto a la Base de Datos")
        codigo_scanned_nuevo = st.text_input("📷 Digita o ingresa el código del producto nuevo:", key="scan_nuevo_prod")
    
        with st.form("form_crear_producto_multi", clear_on_submit=True):
            st.markdown("#### Datos Básicos y Ubicación")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                codigo = st.text_input("Código del Producto (EAN o Interno) *", value=codigo_scanned_nuevo if codigo_scanned_nuevo else "")
                descripcion = st.text_input("Descripción / Nombre del Producto *")
                categoria = st.selectbox("Categoría", ["Ninguna", "BEBIDAS", "ABARROTES", "SNACKS", "OTROS"])
            with col_b2:
                bodega_seleccionada = st.selectbox("🏢 Asignar a Bodega / Sucursal:", bodegas_existentes, key="bod_prod")
                nueva_bodega = st.text_input("✍️ Escribe el nombre de la nueva Bodega:") if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal..." else ""
                stock = st.number_input("Stock Inicial a ingresar en esta bodega", min_value=0.0, step=1.0)
                costo = st.number_input("Costo de Compra Neto ($)", min_value=0.0, step=100.0)

            st.markdown("#### 💡 Configuración Tributaria (Ingresa el Neto o el Bruto)")
            nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
            tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_act or str(rut_actual) == "219449970012" else 19.0
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                precio_neto = st.number_input("Precio Neto ($)", min_value=0.0, step=100.0)
                porcentaje_iva = st.number_input("% de IVA", min_value=0.0, value=tasa_defecto, step=1.0)
                impuesto_especifico = st.selectbox("Impuesto Específico", ["Ninguno", "IABA 10", "IABA 18", "ILA", "ILA 31.5"])
            with col_p2:
                precio_venta = st.number_input("Precio Bruto/Final ($)", min_value=0.0, step=100.0)
                es_exento = st.selectbox("¿Es Exento de IVA?", ["No", "Si"])
                activo = st.selectbox("¿Activo en el sistema?", ["Si", "No"])
        
            if st.form_submit_button("💾 Guardar Producto en la Bodega"):
                bodega_final = nueva_bodega.strip() if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal..." else bodega_seleccionada
                if not codigo or not descripcion or (precio_venta <= 0 and precio_neto <= 0):
                    st.warning("⚠️ Completa Código, Descripción y un Precio (Neto o Bruto).")
                elif not bodega_final:
                    st.warning("⚠️ Asigna un nombre a la bodega.")
                else:
                    iva_final = 0.0 if es_exento == "Si" else float(porcentaje_iva)
                    p_neto_calc, p_bruto_calc = float(precio_neto), float(precio_venta)
                    
                    if p_bruto_calc > 0 and p_neto_calc == 0: p_neto_calc = p_bruto_calc / (1.0 + (iva_final / 100.0))
                    elif p_neto_calc > 0: p_bruto_calc = p_neto_calc * (1.0 + (iva_final / 100.0))

                    nuevo_producto = {
                        "rut_empresa": rut_actual, "codigo": codigo.strip(), "bodega": bodega_final.strip(' "\''),
                        "descripcion": descripcion.strip(), "categoria": categoria if categoria != "Ninguna" else None,
                        "costo": costo, "precio_neto": round(p_neto_calc, 2), "porcentaje_iva": round(iva_final, 2),
                        "precio_venta": round(p_bruto_calc, 2), "stock": stock, "es_exento": es_exento,
                        "impuesto_especifico": impuesto_especifico if impuesto_especifico != "Ninguno" else None, "activo": activo
                    }
                    try:
                        res_check = supabase.table("productos").select("id").eq("rut_empresa", rut_actual).eq("codigo", codigo.strip()).eq("bodega", bodega_final).execute()
                        if res_check.data:
                            supabase.table("productos").update(nuevo_producto).eq("id", res_check.data[0]["id"]).execute()
                            st.success(f"✅ Producto actualizado.")
                        else:
                            supabase.table("productos").insert(nuevo_producto).execute()
                            st.success(f"✅ Producto creado.")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Error: {e}")

    # ==========================================
    # 🚨 PESTAÑA 2: INGREDIENTES / MATERIA PRIMA (NUEVA)
    # ==========================================
    with tab_ing:
        st.markdown("#### 🍅 Registrar Materia Prima e Ingredientes")
        st.info("💡 Usa este formulario simplificado para ingresar insumos (Pan, Carne, Palta). Se guardarán con Precio de Venta $0 para que no estorben en el Punto de Venta.")
        
        if not df_inv.empty:
            df_insumos = df_inv[df_inv['precio_venta'] == 0]
            if not df_insumos.empty:
                st.markdown("##### Insumos Actuales:")
                st.dataframe(df_insumos[['codigo', 'descripcion', 'categoria', 'bodega', 'stock', 'costo']], use_container_width=True)

        with st.form("form_crear_ingrediente", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                codigo_ing = st.text_input("Código del Insumo (Ej: INS-001) *")
                descripcion_ing = st.text_input("Nombre del Ingrediente (Ej: Palta Hass) *")
                categoria_ing = st.selectbox("Categoría", ["VEGETALES", "CARNES", "PANADERIA", "SALSAS", "LACTEOS", "OTROS"])
            with col_i2:
                bodega_ing_sel = st.selectbox("🏢 Bodega / Sucursal:", bodegas_existentes, key="bod_ing")
                nueva_bodega_ing = st.text_input("✍️ Escribe el nombre de la nueva Bodega:", key="nb_ing") if bodega_ing_sel == "➕ Crear Nueva Bodega / Sucursal..." else ""
                stock_ing = st.number_input("Stock Inicial (En Kilos, Litros o Unidades)", min_value=0.0, step=0.1, format="%.2f")
                costo_bruto_ing = st.number_input("Costo Bruto Total de Compra ($)", min_value=0.0, step=100.0)

            if st.form_submit_button("💾 Guardar Ingrediente"):
                bodega_ing_final = nueva_bodega_ing.strip() if bodega_ing_sel == "➕ Crear Nueva Bodega / Sucursal..." else bodega_ing_sel
                
                if not codigo_ing or not descripcion_ing:
                    st.warning("⚠️ El Código y Nombre del ingrediente son obligatorios.")
                elif not bodega_ing_final:
                    st.warning("⚠️ Asigna un nombre a la bodega.")
                else:
                    nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
                    tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_act or str(rut_actual) == "219449970012" else 19.0
                    costo_neto_calc = costo_bruto_ing / (1.0 + (tasa_defecto / 100.0)) if costo_bruto_ing > 0 else 0.0

                    nuevo_ingrediente = {
                        "rut_empresa": rut_actual, "codigo": codigo_ing.strip(), "bodega": bodega_ing_final.strip(' "\''),
                        "descripcion": descripcion_ing.strip(), "categoria": categoria_ing, "costo": round(costo_neto_calc, 2),
                        "precio_neto": 0.0, "porcentaje_iva": tasa_defecto, "precio_venta": 0.0, 
                        "stock": stock_ing, "es_exento": "No", "impuesto_especifico": None, "activo": "Si"
                    }
                    try:
                        res_check = supabase.table("productos").select("id").eq("rut_empresa", rut_actual).eq("codigo", codigo_ing.strip()).eq("bodega", bodega_ing_final).execute()
                        if res_check.data:
                            supabase.table("productos").update(nuevo_ingrediente).eq("id", res_check.data[0]["id"]).execute()
                            st.success(f"✅ Ingrediente actualizado.")
                        else:
                            supabase.table("productos").insert(nuevo_ingrediente).execute()
                            st.success(f"✅ Ingrediente creado.")
                        st.rerun()
                    except Exception as e: st.error(f"❌ Error: {e}")

    # ==========================================
    # PESTAÑA 3: CLIENTES
    # ==========================================
    with tab_cli:
        # A partir de aquí, deja TU CÓDIGO ACTUAL EXACTAMENTE COMO ESTÁ
        st.markdown("### 👥 Administración de Clientes (Nube)")
       
        with st.form("form_nuevo_cliente", clear_on_submit=True):
            st.markdown("#### Registrar Nuevo Cliente")
            col1, col2 = st.columns(2)
            with col1:
                rut_cliente = st.text_input("RUT / Identificación *")
                nombre_cliente = st.text_input("Nombre / Razón Social *")
                telefono_cliente = st.text_input("Teléfono")
            with col2:
                correo_cliente = st.text_input("Correo Electrónico")
                direccion_cliente = st.text_input("Dirección")
           
            if st.form_submit_button("💾 Guardar Cliente en Nube"):
                if rut_cliente and nombre_cliente:
                    try:
                        nuevo_cliente = {
                            "id_negocio": str(rut_actual), # En tu BD vi que usas id_negocio para clientes
                            "rut": str(rut_cliente).strip(),
                            "nombre": str(nombre_cliente).strip(),
                            "telefono": telefono_cliente,
                            "correo": correo_cliente,
                            "direccion": direccion_cliente
                        }
                        supabase.table("clientes").insert(nuevo_cliente).execute()
                        st.success(f"✅ Cliente '{nombre_cliente}' guardado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar (¿El RUT ya existe?): {e}")
                else:
                    st.warning("⚠️ RUT y Nombre son obligatorios.")

        st.markdown("#### 📋 Listado de Clientes")
        try:
            res_cli = supabase.table("clientes").select("rut, nombre, telefono, correo, direccion").eq("id_negocio", rut_actual).execute()
            df_clientes = pd.DataFrame(res_cli.data)
            if not df_clientes.empty:
                st.dataframe(df_clientes, use_container_width=True, hide_index=True)
            else:
                st.info("No hay clientes registrados en la nube todavía.")
        except Exception as e:
            st.error(f"Error conectando a clientes: {e}")
       
    # ==========================================
    # PESTAÑA 3: IMPUESTOS (100% NUBE)
    # ==========================================
    with tab_inf3:
        st.markdown("### 🏛️ Proyección de Impuestos (Acumulado Mensual)")
        st.info("💡 Este panel cruza tus Ventas (IVA Débito) con tus Compras (IVA Crédito) para calcular tu carga fiscal.")

        # --- 🧠 LECTURA DINÁMICA DE IVA DESDE LA CONFIGURACIÓN ---
        # Leemos el diccionario de configuración de la empresa actual
        cfg_actual = st.session_state.get("config_ticket", {})
        # Extraemos la tasa exacta que el usuario guardó (ej. 22.0)
        iva_configurado = float(cfg_actual.get("iva_tasa", 19.0))
        
        tasa_iva_decimal = iva_configurado / 100.0  # Ej: 22.0 -> 0.22
        factor_iva = 1.0 + tasa_iva_decimal         # Ej: 1.22

        # --- 1. CÁLCULO DE VENTAS (DÉBITO) ---
        tot_neto_ventas, tot_iva_debito, tot_ila_ventas = 0.0, 0.0, 0.0
        if 'df_v' in locals() and not df_v.empty:
            tot_neto_ventas = df_v["neto"].sum() if "neto" in df_v.columns else 0.0
            tot_iva_debito = df_v["iva"].sum() if "iva" in df_v.columns else 0.0
            tot_ila_ventas = df_v["impuesto_especifico"].sum() if "impuesto_especifico" in df_v.columns else 0.0

        st.markdown("#### 🔵 VENTAS (Impuestos Débito)")
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            st.metric(label="📊 Ventas Netas", value=f"${tot_neto_ventas:,.0f}")
        with col_v2:
            # ¡Ahora el título se adapta al porcentaje configurado!
            st.metric(label=f"🏛️ IVA Débito ({iva_configurado:g}%)", value=f"${tot_iva_debito:,.0f}")
        with col_v3:
            st.metric(label="🍷 Imp. Específicos Débito", value=f"${tot_ila_ventas:,.0f}")

        st.divider()

        # --- 2. CÁLCULO DE COMPRAS (CRÉDITO) ---
        tot_neto_compras, tot_iva_credito, tot_ila_compras = 0.0, 0.0, 0.0
        if 'df_c' in locals() and not df_c.empty:
            # Detecta si ya tienes las columnas neto e iva en compras, o las calcula con tu IVA DINÁMICO
            if "neto" in df_c.columns:
                tot_neto_compras = df_c["neto"].sum()
            else:
                tot_neto_compras = (df_c["costo_total"].sum() / factor_iva) if "costo_total" in df_c.columns else 0.0
                
            if "iva" in df_c.columns:
                tot_iva_credito = df_c["iva"].sum()
            else:
                tot_iva_credito = tot_neto_compras * tasa_iva_decimal

            tot_ila_compras = df_c["impuesto_especifico"].sum() if "impuesto_especifico" in df_c.columns else 0.0

        st.markdown("#### 🟢 COMPRAS (Impuestos Crédito)")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.metric(label="🛒 Compras Netas", value=f"${tot_neto_compras:,.0f}")
        with col_c2:
            # Título dinámico
            st.metric(label=f"💳 IVA Crédito ({iva_configurado:g}%)", value=f"${tot_iva_credito:,.0f}")
        with col_c3:
            st.metric(label="🍷 Imp. Específicos Crédito", value=f"${tot_ila_compras:,.0f}")

        st.divider()
        
        # --- 3. RESULTADO FINAL PARA EL FISCO ---
        iva_a_pagar = tot_iva_debito - tot_iva_credito
        iva_efectivo = iva_a_pagar if iva_a_pagar > 0 else 0.0
        
        total_impuestos = iva_efectivo + tot_ila_ventas
        
        st.markdown(f"### 🚨 Total a Pagar Fisco Aprox: **${total_impuestos:,.0f}**")
        
        if iva_a_pagar < 0:
            st.success(f"🎉 Tienes un Remanente de IVA a favor para el próximo mes de: **${abs(iva_a_pagar):,.0f}**")

# ----------------- SECCIÓN MERMAS Y AJUSTES DE INVENTARIO -----------------
elif menu == "📉 Mermas y Ajustes":
    mostrar_encabezado_con_home("📉 Módulo de Control de Mermas y Ajustes de Inventario")
    st.markdown("Registra salidas extraordinarias de mercadería (roturas, vencimientos, consumo interno o mermas) para mantener tu inventario y lotes cuadrados.")

    if df_base is not None:
        col_cod = next((c for c in df_base.columns if 'código' in str(c).lower() or 'codigo' in str(c).lower() or 'ean' in str(c).lower()), df_base.columns[0])
        col_desc = next((c for c in df_base.columns if 'descripción' in str(c).lower() or 'nombre' in str(c).lower() or 'producto' in str(c).lower()), df_base.columns[1])
        col_stock = next((c for c in df_base.columns if 'stock' in str(c).lower() or 'cantidad' in str(c).lower()), None)

        if col_stock:
            st.markdown("### 📋 Registro de Salida por Merma o Ajuste")

            metodo_busqueda_merma = st.radio("Método para buscar producto:", ["⌨️ Escáner / Pistola Láser (Código)", "🔎 Buscar por Nombre / Palabra Clave"], horizontal=True, key="radio_merma")
           
            prod_seleccionado_merma = None
            opciones_productos_merma = ["-- Selecciona un producto --"] + [f"{row[col_cod]} - {row[col_desc]}" for idx, row in df_base.iterrows()]

            if metodo_busqueda_merma == "⌨️ Escáner / Pistola Láser (Código)":
                codigo_buscado_m = st.text_input("Pistola láser / Digitar Código EAN:", key="input_pistola_merma")
                if codigo_buscado_m:
                    match_pm = df_base[df_base[col_cod].astype(str) == str(codigo_buscado_m)]
                    if not match_pm.empty:
                        prod_seleccionado_merma = f"{match_pm.iloc[0][col_cod]} - {match_pm.iloc[0][col_desc]}"
                        st.success(f"✔️ Producto encontrado: {prod_seleccionado_merma}")
                    else:
                        st.warning("⚠️ No se encontró ningún producto con ese código.")
            else:
                prod_seleccionado_merma = st.selectbox("Selecciona o busca por palabra clave:", options=opciones_productos_merma, key="select_palabra_merma")

            with st.form("form_registrar_merma"):
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    cant_merma = st.number_input("Cantidad a dar de baja / Ajustar", min_value=1.0, step=1.0, value=1.0)
                with col_m2:
                    motivo_merma = st.selectbox("Motivo de la Baja", ["Merma / Rotura", "Vencimiento / Caducado", "Consumo Interno", "Ajuste por Diferencia de Inventario"])

                observacion_merma = st.text_input("Observación opcional (Ej: Rotura en pasillo, vencido del semáforo)")

                lotes_disponibles_prod = []
                codigo_p_merma = ""
                if prod_seleccionado_merma and prod_seleccionado_merma != "-- Selecciona un producto --":
                    codigo_p_merma = str(prod_seleccionado_merma.split(" - ")[0]).strip()
               
                archivo_lotes = os.path.join(ruta_negocio, "base_lotes.xlsx") if 'ruta_negocio' in globals() else "base_lotes.xlsx"
                if os.path.exists(archivo_lotes) and codigo_p_merma:
                    df_lotes_check = pd.read_excel(archivo_lotes, dtype={'Código': str})
                    df_lotes_prod = df_lotes_check[(df_lotes_check['Código'].astype(str) == str(codigo_p_merma)) & (df_lotes_check['CantidadDisponible'] > 0)]
                    if not df_lotes_prod.empty:
                        lotes_disponibles_prod = [f"Lote: {row['Lote']} (Disponibles: {row['CantidadDisponible']} - Vence: {row['FechaVencimiento']})" for idx, row in df_lotes_prod.iterrows()]

                lote_seleccionado_str = "N/A"
                if lotes_disponibles_prod:
                    st.markdown("📌 **Este producto tiene lotes activos. Selecciona a qué lote descontar:**")
                    lote_seleccionado_str = st.selectbox("Lote afectado", options=lotes_disponibles_prod)

                btn_ejecutar_merma = st.form_submit_button("📉 Registrar Merma y Descontar de Inventario", type="primary")

                if btn_ejecutar_merma:
                    if not prod_seleccionado_merma or prod_seleccionado_merma == "-- Selecciona un producto --":
                        st.warning("⚠️ Debes seleccionar un producto válido.")
                    elif cant_merma <= 0:
                        st.warning("⚠️ La cantidad debe ser mayor a 0.")
                    else:
                        codigo_p_merma = str(prod_seleccionado_merma.split(" - ")[0]).strip()
                        desc_p_merma = str(prod_seleccionado_merma.split(" - ")[1]).strip()

                        try:
                            # 1. Consultar el producto en Supabase usando rut_empresa y el código limpio
                            res_prod = supabase.table("productos").select("*").eq("rut_empresa", rut_actual).eq("codigo", codigo_p_merma).execute()
                            
                            if res_prod.data:
                                prod_data = res_prod.data[0]
                                stock_actual_nube = float(prod_data.get("stock", 0) or 0.0)
                                
                                if stock_actual_nube < cant_merma:
                                    st.warning(f"⚠️ Stock insuficiente. Stock actual en nube: {stock_actual_nube}")
                                else:
                                    nuevo_stock_nube = max(0.0, stock_actual_nube - float(cant_merma))
                                    
                                    # 2. Actualizar el stock en Supabase usando rut_empresa
                                    supabase.table("productos").update({"stock": nuevo_stock_nube}).eq("rut_empresa", rut_actual).eq("codigo", codigo_p_merma).execute()

                                    # 3. Registrar la merma en la tabla de Supabase
                                    lote_limpio = "N/A"
                                    if lotes_disponibles_prod and lote_seleccionado_str:
                                        import re
                                        match_lote_ext = re.search(r'Lote:\s*(.*?)\s*\(Disponibles', lote_seleccionado_str)
                                        if match_lote_ext:
                                            lote_limpio = match_lote_ext.group(1).strip()

                                    nuevo_reg_merma_nube = {
                                        "fecha_hora": datetime.now().isoformat(),
                                        "codigo": codigo_p_merma,
                                        "descripcion": desc_p_merma,
                                        "cantidad": float(cant_merma),
                                        "motivo": motivo_merma,
                                        "lote": lote_limpio,
                                        "observacion": observacion_merma if observacion_merma else "Sin observaciones",
                                        "id_negocio": str(rut_actual).strip()
                                    }
                                    
                                    supabase.table("mermas").insert(nuevo_reg_merma_nube).execute()

                                    st.success(f"✅ ¡Merma registrada y stock descontado en la nube con éxito! (Nuevo stock: {nuevo_stock_nube})")
                                    st.rerun()
                            else:
                                st.error(f"❌ No se encontró el producto con código '{codigo_p_merma}' para la empresa '{rut_actual}'.")
                        except Exception as e:
                            st.error(f"❌ Error al procesar la merma en Supabase: {e}")

            archivo_mermas_ver = os.path.join(ruta_negocio, "base_mermas.xlsx") if 'ruta_negocio' in globals() else "base_mermas.xlsx"
            if os.path.exists(archivo_mermas_ver):
                st.divider()
                st.markdown("### 📊 Historial de Mermas y Ajustes Registrados")
                df_ver_mermas = pd.read_excel(archivo_mermas_ver, dtype={'Código': str})
                if not df_ver_mermas.empty:
                    st.dataframe(df_ver_mermas.tail(15), use_container_width=True)
                else:
                    st.info("ℹ️ Aún no hay registros en el historial de mermas.")
        else:
            st.warning("⚠️ No se encontró la columna de stock en la base de datos de productos.")
    else:
        st.error(f"⚠️ No se encontró la base de datos para '{negocio_seleccionado}'.")
# ---------------- SECCIÓN FINANZAS ----------------
elif menu == "📊 Módulo de Finanzas":
    mostrar_encabezado_con_home("📊 Panel de Control Financiero y Gastos")
   
    tab_fin1, tab_fin2, tab_fin3, tab_fin4 = st.tabs([
        "💳 Cuentas por Pagar",
        "📅 Calendario de Pagos",
        "💸 Registro de Gastos",
        "🏢 Costos Fijos y Créditos"
    ])
   
    with tab_fin1:
        mostrar_modulo_cuentas_por_pagar(ruta_negocio)
       
    with tab_fin2:
        mostrar_modulo_calendario_pagos(ruta_negocio)
       
    with tab_fin3:
        mostrar_modulo_registro_gastos(supabase)
    # Actualizacion final de costos fijos   
    with tab_fin4:
        mostrar_modulo_costos_fijos(ruta_negocio, supabase)
   
# ----------------- SECCIÓN INFORMES Y MOVIMIENTOS -----------------
elif menu == "📈 Informes y Movimientos (Kardex)":
    mostrar_encabezado_con_home("📈 Módulo Unificado de Informes y Movimientos")
    st.markdown("Consulta y filtra el historial completo de entradas (compras), salidas (ventas) y movimientos de inventario:")

    # ¡NUEVO! Agregamos la tercera pestaña para Impuestos
    tab_inf1, tab_inf2, tab_inf3 = st.tabs(["📑 Libro de Ventas (Salidas)", "📋 Historial de Compras (Entradas)", "🏛️ Impuestos Mensuales"])

    # ==========================================
    # PESTAÑA 1: VENTAS (100% NUBE)
    # ==========================================
    with tab_inf1:
        st.markdown("### 💰 Registro de Salidas y Ventas (Nube)")
        try:
            res_ventas_nube = supabase.table("ventas").select("*").eq("rut_empresa", rut_actual).execute()
            
            if res_ventas_nube.data:
                df_v = pd.DataFrame(res_ventas_nube.data)
                
                col_fecha = "fecha_hora" if "fecha_hora" in df_v.columns else ("FechaHora" if "FechaHora" in df_v.columns else None)
                if col_fecha:
                    df_v[col_fecha] = pd.to_datetime(df_v[col_fecha])
                    df_v["Fecha_Corta"] = df_v[col_fecha].dt.date
                
                st.dataframe(df_v, use_container_width=True)
               
                # Suma del Monto Bruto (Lo que entró a la caja)
                tot_bruto = df_v["monto"].sum() if "monto" in df_v.columns else 0.0
                st.metric(label="💰 Ingresos Brutos (Caja + Impuestos)", value=f"${tot_bruto:,.0f}")
            else:
                st.info("ℹ️ Aún no hay registros de ventas en la nube para este negocio.")
        except Exception as e:
            st.error(f"⚠️ Error al cargar el historial de ventas desde Supabase: {e}")

    # ==========================================
    # PESTAÑA 2: COMPRAS (100% NUBE)
    # ==========================================
    with tab_inf2:
        st.markdown("### 🛒 Registro de Entradas y Compras (Nube)")
        try:
            res_compras_nube = supabase.table("compras").select("*").eq("id_negocio", rut_actual).execute()
            if res_compras_nube.data:
                df_c = pd.DataFrame(res_compras_nube.data)
                st.dataframe(df_c, use_container_width=True)
                
                tot_c = df_c["costo_total"].sum() if "costo_total" in df_c.columns else (df_c["CostoTotal"].sum() if "CostoTotal" in df_c.columns else 0.0)
                st.metric(label="💵 Total Invertido en Compras Brutas", value=f"${tot_c:,.0f}")
            else:
                st.info("ℹ️ Aún no hay registros de compras en la nube para este negocio.")
        except Exception as e:
            st.error(f"⚠️ Error al cargar el historial de compras desde Supabase: {e}")

    # ==========================================
    # PESTAÑA 3: IMPUESTOS (100% NUBE)
    # ==========================================
    with tab_inf3:
        st.markdown("### 🏛️ Proyección de Impuestos (Acumulado Mensual)")
        st.info("💡 Este panel cruza tus Ventas (IVA Débito) con tus Compras (IVA Crédito) para calcular tu carga fiscal.")

        # --- 1. CÁLCULO DE VENTAS (DÉBITO) ---
        tot_neto_ventas, tot_iva_debito, tot_ila_ventas = 0.0, 0.0, 0.0
        if 'df_v' in locals() and not df_v.empty:
            tot_neto_ventas = df_v["neto"].sum() if "neto" in df_v.columns else 0.0
            tot_iva_debito = df_v["iva"].sum() if "iva" in df_v.columns else 0.0
            tot_ila_ventas = df_v["impuesto_especifico"].sum() if "impuesto_especifico" in df_v.columns else 0.0

        st.markdown("#### 🔵 VENTAS (Impuestos Débito)")
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            st.metric(label="📊 Ventas Netas", value=f"${tot_neto_ventas:,.0f}")
        with col_v2:
            st.metric(label="🏛️ IVA Débito (Ventas)", value=f"${tot_iva_debito:,.0f}")
        with col_v3:
            st.metric(label="🍷 Imp. Específicos Débito", value=f"${tot_ila_ventas:,.0f}")

        st.divider()

        # --- 2. CÁLCULO DE COMPRAS (CRÉDITO) ---
        tot_neto_compras, tot_iva_credito, tot_ila_compras = 0.0, 0.0, 0.0
        if 'df_c' in locals() and not df_c.empty:
            # Detecta si ya tienes las columnas neto e iva en compras, o las calcula aproximadas desde el costo total
            if "neto" in df_c.columns:
                tot_neto_compras = df_c["neto"].sum()
            else:
                tot_neto_compras = (df_c["costo_total"].sum() / 1.19) if "costo_total" in df_c.columns else 0.0
                
            if "iva" in df_c.columns:
                tot_iva_credito = df_c["iva"].sum()
            else:
                tot_iva_credito = tot_neto_compras * 0.19

            tot_ila_compras = df_c["impuesto_especifico"].sum() if "impuesto_especifico" in df_c.columns else 0.0

        st.markdown("#### 🟢 COMPRAS (Impuestos Crédito)")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.metric(label="🛒 Compras Netas", value=f"${tot_neto_compras:,.0f}")
        with col_c2:
            st.metric(label="💳 IVA Crédito (Compras)", value=f"${tot_iva_credito:,.0f}")
        with col_c3:
            st.metric(label="🍷 Imp. Específicos Crédito", value=f"${tot_ila_compras:,.0f}")

        st.divider()
        
        # --- 3. RESULTADO FINAL PARA EL FISCO ---
        iva_a_pagar = tot_iva_debito - tot_iva_credito
        iva_efectivo = iva_a_pagar if iva_a_pagar > 0 else 0.0
        
        total_impuestos = iva_efectivo + tot_ila_ventas
        
        st.markdown(f"### 🚨 Total a Pagar Fisco Aprox: **${total_impuestos:,.0f}**")
        
        if iva_a_pagar < 0:
            st.success(f"🎉 Tienes un Remanente de IVA a favor para el próximo mes de: **${abs(iva_a_pagar):,.0f}**")

# ----------------- SECCIÓN CONTROL Y GESTIÓN DE INVENTARIO -----------------
elif menu == "⚠️ Control y Gestión de Inventario":
    mostrar_encabezado_con_home("⚠️ Panel de Control Operativo y Alertas de Inventario")
  
    with st.expander("⚙️ Configurar Parámetros de Operación e Inventario", expanded=False):
        st.markdown("Ajusta los valores operativos según la logística y tiempos de tu negocio:")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        with col_p1:
            lead_time_dias = st.number_input("🚚 Lead Time Proveedor (Días)", min_value=1, max_value=90, value=3, step=1, help="Tiempo que demora el proveedor en entregar mercadería.")
        with col_p2:
            consumo_diario_estimado = st.number_input("📈 Consumo Promedio Diario (Unid)", min_value=0.1, max_value=10000.0, value=1.5, step=0.1, help="Venta o consumo diario estimado por producto si no hay histórico detallado.")
        with col_p3:
            limite_sobrestock_semanas = st.number_input("🛑 Límite de Sobrestock (Semanas)", min_value=1, max_value=52, value=4, step=1, help="Semanas máximas de stock permitidas antes de marcar exceso de capital.")
        with col_p4:
            dias_alerta_roja = st.number_input("🔴 Alerta Crítica Vencimiento (Días)", min_value=1, max_value=30, value=7, step=1, help="Días restantes para considerar un lote en zona roja.")

    sub_tab1, sub_tab2, sub_tab3 = st.tabs(["🚦 Semáforo de Vencimientos", "📦 Sugerencia de Reabastecimiento", "🛑 Control de Sobrestock"])

    with sub_tab1:
        st.markdown(f"### 🚦 Clasificación Automática de Vencimientos (Lotes Activos)")
      
        # --- ASEGURAR VARIABLE DE NEGOCIO ---
        empresa_id = rut_actual if 'rut_actual' in globals() and rut_actual else locals().get('negocio_seleccionado', '77297004-8')

        # --- CARGA DE LOTES DESDE SUPABASE ---
        df_lotes_venc = pd.DataFrame()
        try:
            res_lotes_nube = supabase.table("lotes").select("*").eq("rut_empresa", empresa_id).execute()
            if res_lotes_nube.data:
                df_lotes_venc = pd.DataFrame(res_lotes_nube.data)
        except Exception as e:
            st.error(f"⚠️ Error cargando lotes desde Supabase: {e}")

        col_f_venc = next((c for c in df_lotes_venc.columns if c.lower() in ['fechavencimiento', 'fecha_vencimiento']), None)
        
        if not df_lotes_venc.empty and col_f_venc:
            roja, amarilla, verde = [], [], []
            hoy = datetime.now().date()
          
            for idx, row in df_lotes_venc.iterrows():
                fecha_val = row.get(col_f_venc)
                lote_val = str(row.get('lote', row.get('Lote', 'N/A')))
               
                if pd.notna(fecha_val) and lote_val != "N/A" and str(fecha_val) != "N/A":
                    try:
                        f_venc = pd.to_datetime(fecha_val).date()
                        dias = (f_venc - hoy).days
                       
                        item = {
                            "Código": str(row.get("codigo", row.get("Código", ""))),
                            "Descripción": str(row.get("descripcion", row.get("Descripción", ""))),
                            "Lote": lote_val,
                            "Cantidad Disponible": float(row.get("cantidad_disponible", row.get("CantidadDisponible", 0))),
                            "Fecha Vencimiento": str(f_venc),
                            "Días Restantes": dias
                        }
                       
                        if dias <= dias_alerta_roja:
                            roja.append(item)
                        elif dias_alerta_roja < dias <= (dias_alerta_roja + 8):
                            amarilla.append(item)
                        elif (dias_alerta_roja + 9) <= dias <= (dias_alerta_roja + 23):
                            verde.append(item)
                    except Exception:
                        pass

            c1, c2, c3 = st.columns(3)
            with c1:
                st.error(f"🔴 Zona Roja <= {dias_alerta_roja} días ({len(roja)})")
                if roja:
                    st.dataframe(pd.DataFrame(roja), use_container_width=True)
                else:
                    st.caption("Sin productos en riesgo crítico.")
            with c2:
                st.warning(f"🟡 Zona Amarilla ({len(amarilla)})")
                if amarilla:
                    st.dataframe(pd.DataFrame(amarilla), use_container_width=True)
                else:
                    st.caption("Sin productos en alerta media.")
            with c3:
                st.success(f"🟢 Zona Verde ({len(verde)})")
                if verde:
                    st.dataframe(pd.DataFrame(verde), use_container_width=True)
                else:
                    st.caption("Sin productos próximos a vencer.")
        else:
            st.info("ℹ️ Aún no hay registros de lotes con fecha de vencimiento guardados en la nube para este negocio.")

    with sub_tab2:
        st.markdown(f"### 📦 Asistente de Reabastecimiento Automático (Lead Time configurado: {lead_time_dias} días)")
        if df_base is not None:
            col_stock = next((c for c in df_base.columns if 'stock' in str(c).lower() or 'cantidad' in str(c).lower() or 'existencia' in str(c).lower()), None)
            col_desc = next((c for c in df_base.columns if 'descripción' in str(c).lower() or 'nombre' in str(c).lower()), 'Descripción')
            col_cod = next((c for c in df_base.columns if 'código' in str(c).lower() or 'codigo' in str(c).lower()), df_base.columns[0])

            if col_stock:
                sugerencias = []
                consumo_periodo_lt = consumo_diario_estimado * lead_time_dias
                demanda_semanal = consumo_diario_estimado * 7.0

                for idx, row in df_base.iterrows():
                    stock = float(row.get(col_stock, 0)) if pd.notna(row.get(col_stock)) else 0.0
                    if stock <= consumo_periodo_lt:
                        sugerencias.append({
                            'Código': str(row.get(col_cod, '')),
                            'Descripción': str(row.get(col_desc, '')),
                            'Stock Actual': stock,
                            'Sugerido a Comprar': round(demanda_semanal - stock + consumo_periodo_lt, 2)
                        })
                if sugerencias:
                    st.warning(f"⚠️ {len(sugerencias)} productos en riesgo de quiebre según el lead time actual.")
                    st.dataframe(pd.DataFrame(sugerencias), use_container_width=True)
                else:
                    st.success(f"✔️ Todo el inventario soporta holgadamente los {lead_time_dias} días de entrega.")
            else:
                st.warning("⚠️ Falta la columna de stock.")
        else:
            st.error("⚠️ Falta la base de datos.")

    with sub_tab3:
        st.markdown("### 🖨️ Datos del Comprobante e Impresión")

        st.markdown("---")
        st.markdown("### 🖼️ Logotipo de la Empresa")
        
        if negocio_seleccionado and negocio_seleccionado != "admin_general":
            tenant_dir_logo = os.path.join(CARPETA_CLIENTES, str(negocio_seleccionado))
            ruta_logo_final = os.path.join(tenant_dir_logo, "logo_empresa.png")
            
            if os.path.exists(ruta_logo_final):
                st.image(ruta_logo_final, width=120, caption="Logotipo actual guardado")
       
            logo_cargado = st.file_uploader("Sube una imagen para tu logo (PNG o JPG)", type=["png", "jpg", "jpeg"], key="uploader_logo_empresa")
            
            if logo_cargado is not None:
                try:
                    os.makedirs(tenant_dir_logo, exist_ok=True)
                    
                    img = Image.open(logo_cargado)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    img.save(ruta_logo_final, "PNG")
                    st.success("✅ ¡Logotipo procesado y actualizado con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ocurrió un error al guardar el logotipo: {e}")
        else:
            st.warning("⚠️ Selecciona un negocio específico desde el panel para poder cambiar su logotipo.")

# ----------------- SECCIÓN COMPRAS Y RECEPCIONES (GRC / GRI) -----------------
elif menu == "🛒 Registrar Compra (CPP)":
    mostrar_encabezado_con_home("🛒 Gestión de Compras y Recepciones (GRC / GRI)")

    # --- CARGA DE PRODUCTOS DIRECTO DESDE LA NUBE (SUPABASE) PARA GRC/GRI ---
    df_base = pd.DataFrame()
    try:
        res_prod_nube = supabase.table("productos").select("codigo, descripcion, stock, precio_venta").eq("rut_empresa", rut_actual).limit(10000).execute()
        if res_prod_nube.data:
            df_base = pd.DataFrame(res_prod_nube.data)
    except Exception as e:
        st.error(f"⚠️ Error conectando al inventario de la nube para compras: {e}")

    if not df_base.empty:
        # Definimos las columnas estándar que usarán los selectbox y campos de la GRC
        col_cod = 'codigo'
        col_desc = 'descripcion'
        col_stock = 'stock'
        col_precio = 'precio_venta'
        accion_producto = st.radio("Selecciona una opción:", ["📥 Registrar Compra / GRC (Factura con Lotes)", "🔄 Recepción Interna / GRI (Ajustes / Producción)", "➕ Crear Producto Nuevo", "✏️ Editar Producto Existente"], horizontal=True)
        st.divider()

        # --- 1. REGISTRO GRC (Guía de Recepción de Compra - Proveedor Externo) ---
        if accion_producto == "📥 Registrar Compra / GRC (Factura con Lotes)":
            st.markdown("### 📋 Cabecera de la Recepción de Compra (GRC)")

            # --- CARGA DE PROVEEDORES DIRECTO DESDE LA NUBE (SUPABASE) ---
            lista_proveedores = ["Proveedor General"]
            try:
                # 1. Cargar todos los proveedores sin filtro rígido de columna
                res_prov_nube = supabase.table("proveedores").select("*").execute()
                
                if res_prov_nube.data:
                    tenant_clean = str(rut_actual).strip().lower() if 'rut_actual' in locals() and rut_actual else ""
                    
                    for p in res_prov_nube.data:
                        # Obtener negocio asociado
                        emp_p = str(p.get("id_negocio") or p.get("rut_empresa") or p.get("rut") or "").strip().lower()
                        
                        # Incluir si coincide con la empresa actual o si el proveedor no tiene empresa fija
                        if not emp_p or not tenant_clean or emp_p == tenant_clean:
                            nom_p = (
                                p.get("nombre") or 
                                p.get("razon_social") or 
                                p.get("nombre_proveedor") or 
                                p.get("Nombre_Proveedor") or 
                                p.get("proveedor")
                            )
                            if nom_p and str(nom_p).strip():
                                lista_proveedores.append(str(nom_p).strip())
                                
                    lista_proveedores = list(dict.fromkeys(lista_proveedores))
            except Exception as e:
                print(f"Error cargando proveedores desde Supabase en GRC: {e}")

            # 🚨 CARGAR BODEGAS DESDE SUPABASE PARA LA GRC
            bodegas_grc_opc = ["Bodega Principal"]
            try:
                res_bod_grc = supabase.table("bodegas").select("nombre").eq("rut_empresa", rut_actual).execute()
                if res_bod_grc.data:
                    for rb in res_bod_grc.data:
                        nb_g = str(rb.get("nombre", "")).strip(' "\'')
                        if nb_g and nb_g not in bodegas_grc_opc:
                            bodegas_grc_opc.append(nb_g)
            except Exception:
                pass

            # 🚨 CARGAR INGREDIENTES ADEMÁS DE PRODUCTOS PARA EL BUSCADOR DE GRC
            opciones_items_grc = []
            try:
                res_ing_grc = supabase.table("ingredientes").select("codigo, descripcion").eq("rut_empresa", rut_actual).execute()
                if res_ing_grc.data:
                    for ri in res_ing_grc.data:
                        opciones_items_grc.append(f"🍅 [Insumo] {ri['codigo']} - {ri['descripcion']}")
            except Exception:
                pass

            if not df_base.empty:
                for _, row_p in df_base.iterrows():
                    opciones_items_grc.append(f"📦 [Producto] {row_p[col_cod]} - {row_p[col_desc]}")

            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                proveedor_factura = st.selectbox("Nombre del Proveedor", options=lista_proveedores)
                num_factura = st.text_input("Número de Factura / Folio GRC")
            with col_f2:
                fecha_compra = st.date_input("Fecha de Recepción GRC", value=date.today())
                condicion_pago = st.selectbox("Condición de Pago", ["Contado", "Crédito", "Cheque"])
            with col_f3:
                bodega_destino_grc = st.selectbox("🏢 Bodega de Destino:", options=bodegas_grc_opc)
            with col_f4:
                col_imp_esp = next((c for c in df_base.columns if 'impuesto' in str(c).lower() or 'específico' in str(c).lower() or ' ila ' in str(c).lower() or 'iaba' in str(c).lower()), None)
                st.write("")
                st.write(f"🔍 Columna de Impuestos: **{'Detectada' if col_imp_esp else 'No detectada'}**")

            fecha_vencimiento_pago = fecha_compra
            num_serie_cheque = ""
            banco_cheque = ""
            estado_inicial = "Pagado" if condicion_pago == "Contado" else "Pendiente"

            if condicion_pago == "Crédito":
                fecha_vencimiento_pago = st.date_input("Fecha de Vencimiento del Crédito", value=date.today())
            elif condicion_pago == "Cheque":
                col_ch1, col_ch2 = st.columns(2)
                with col_ch1:
                    fecha_vencimiento_pago = st.date_input("Fecha de Cobro del Cheque", value=date.today())
                    num_serie_cheque = st.text_input("Número de Serie del Cheque")
                with col_ch2:
                    banco_cheque = st.text_input("Banco Emisor")

            st.divider()
            st.markdown("#### 🔍 Agregar Productos o Insumos de la GRC")

            if 'carrito_factura_compras' not in st.session_state:
                st.session_state.carrito_factura_compras = []

            prod_seleccionado_item = None
            if not opciones_items_grc:
                opciones_items_grc = ["-- No hay productos ni insumos registrados --"]

            prod_seleccionado_item = st.selectbox("Selecciona Producto o Insumo para la GRC:", options=["-- Selecciona un ítem --"] + opciones_items_grc, key="select_item_grc_unificado")

            col_item1, col_item2, col_item3 = st.columns(3)
            with col_item1:
                cant_item = st.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0, key="cant_grc")
            with col_item2:
                neto_unit_item = st.number_input("Valor Neto Unitario ($)", min_value=0.0, step=1.0, value=0.0, key="neto_grc")
            with col_item3:
                maneja_lote = st.selectbox("¿Maneja Lote y Vencimiento?", ["No", "Sí"], key="lote_grc")

            lote_item = "SIN-LOTE"
            venc_item = str(date.today())

            if maneja_lote == "Sí":
                st.markdown("📌 **Ingrese los datos reales del lote:**")
                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    lote_item = st.text_input("N° Lote", value="LOTE-001", key="num_lote_grc")
                with col_l2:
                    venc_item_date = st.date_input("Fecha de Vencimiento Lote", value=date.today(), key="venc_lote_grc")
                    venc_item = str(venc_item_date)

            if st.button("➕ Agregar Línea a la GRC", type="primary", key="btn_add_grc"):
                if not prod_seleccionado_item or prod_seleccionado_item == "-- Selecciona un ítem --":
                    st.warning("⚠️ Debes seleccionar un producto o insumo válido.")
                elif neto_unit_item <= 0:
                    st.warning("⚠️ El valor neto unitario debe ser mayor a 0.")
                elif maneja_lote == "Sí" and not lote_item:
                    st.warning("⚠️ Debes ingresar el número de lote.")
                else:
                    # Detectar si es insumo o producto
                    es_insumo_linea = "[Insumo]" in prod_seleccionado_item
                    limpio_str = prod_seleccionado_item.replace("📦 [Producto] ", "").replace("🍅 [Insumo] ", "")
                    codigo_p = limpio_str.split(" - ")[0]
                    descripcion_p = limpio_str.split(" - ")[1]

                    match_m = df_base[df_base[col_cod].astype(str) == str(codigo_p)] if not df_base.empty else pd.DataFrame()
                    porcentaje_ila = 0.0
                
                    if col_imp_esp and not match_m.empty:
                        val_imp = str(match_m.iloc[0][col_imp_esp]).strip()
                        import re
                        numeros = re.findall(r'\d+[\,,\.]?\d*', val_imp.replace(',', '.'))
                        if numeros:
                            porcentaje_ila = float(numeros[0])

                    subtotal_neto = cant_item * neto_unit_item
                    monto_iva = subtotal_neto * 0.19
                    monto_ila = subtotal_neto * (porcentaje_ila / 100.0)
                    costo_total_linea = subtotal_neto + monto_iva + monto_ila
                    costo_unitario_final = costo_total_linea / cant_item

                    st.session_state.carrito_factura_compras.append({
                        "TipoDoc": "GRC",
                        "EsInsumo": es_insumo_linea,
                        "Código": codigo_p,
                        "Descripción": descripcion_p,
                        "Cantidad": cant_item,
                        "NetoUnitario": neto_unit_item,
                        "SubtotalNeto": subtotal_neto,
                        "IVA": monto_iva,
                        "ImpuestoEspecifico": monto_ila,
                        "CostoTotal": costo_total_linea,
                        "CostoUnitarioFinal": costo_unitario_final,
                        "ManejaLote": maneja_lote,
                        "Lote": lote_item if maneja_lote == "Sí" else "N/A",
                        "FechaVencimiento": venc_item if maneja_lote == "Sí" else "N/A",
                        "BodegaDestino": bodega_destino_grc
                    })
                    st.success(f"✅ ¡Línea agregada a la GRC!")
                    st.rerun()

            if st.session_state.carrito_factura_compras:
                st.markdown("#### 📦 Ítems Agregados en esta GRC")
            
                for idx_c, item in enumerate(st.session_state.carrito_factura_compras):
                    if item.get("TipoDoc", "GRC") == "GRC":
                        etiqueta_tipo = "🍅 [Insumo]" if item.get("EsInsumo") else "📦 [Producto]"
                        c_col1, c_col2 = st.columns([8, 1])
                        with c_col1:
                            st.info(f"{etiqueta_tipo} **{item['Cantidad']}x** {item['Descripción']} | Bodega: {item.get('BodegaDestino', 'Bodega Principal')} | Neto: ${item['NetoUnitario']:,.0f} | **Costo Unit. c/Imp: ${item['CostoUnitarioFinal']:,.0f}** | Total: ${item['CostoTotal']:,.0f}")
                        with c_col2:
                            if st.button("❌", key=f"del_linea_grc_{idx_c}", help="Eliminar esta línea"):
                                st.session_state.carrito_factura_compras.pop(idx_c)
                                st.rerun()

                monto_total_factura_general = sum(item["CostoTotal"] for item in st.session_state.carrito_factura_compras if item.get("TipoDoc", "GRC") == "GRC")
                st.markdown(f"### 💰 **Monto Total GRC (con Impuestos): ${monto_total_factura_general:,.2f}**")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("🗑️ Limpiar / Vaciar GRC", type="secondary", key="btn_limpiar_grc"):
                        st.session_state.carrito_factura_compras = [i for i in st.session_state.carrito_factura_compras if i.get("TipoDoc") != "GRC"]
                        st.rerun()
                with col_b2:
                    if st.button("💾 Procesar GRC Completa y Actualizar Stock/Finanzas", type="primary", key="btn_procesar_grc"):
                        if not num_factura:
                            st.warning("⚠️ Ingresa el Número de Factura o Folio GRC antes de procesar.")
                        else:
                            prov_final = proveedor_factura if proveedor_factura else "Proveedor General"
                            try:
                                archivo_prov_reg = os.path.join(ruta_negocio, "Maestro_Proveedores.xlsx") if 'ruta_negocio' in globals() else "Maestro_Proveedores.xlsx"
                                if os.path.exists(archivo_prov_reg):
                                    df_pr_g = pd.read_excel(archivo_prov_reg)
                                    if prov_final not in df_pr_g['Nombre_Proveedor'].values:
                                        nuevo_p_df = pd.DataFrame([{'Nombre_Proveedor': prov_final, 'Rut': '', 'Contacto': '', 'Telefono': '', 'Email': ''}])
                                        pd.concat([df_pr_g, nuevo_p_df], ignore_index=True).to_excel(archivo_prov_reg, index=False)
                                else:
                                    pd.DataFrame([{'Nombre_Proveedor': prov_final, 'Rut': '', 'Contacto': '', 'Telefono': '', 'Email': ''}]).to_excel(archivo_prov_reg, index=False)
                            except Exception:
                                pass

                            procesados = 0
                            lineas_detalle_grc = ""
                            for item in st.session_state.carrito_factura_compras:
                                if item.get("TipoDoc", "GRC") == "GRC":
                                    tipo_etiqueta = "Insumo" if item.get("EsInsumo") else "Producto"
                                    lineas_detalle_grc += f"- [{tipo_etiqueta}] {item['Descripción']} (x{item['Cantidad']}) | Costo Unit: ${item['CostoUnitarioFinal']:,.2f} | Subtotal: ${item['CostoTotal']:,.2f} | Bodega: {item.get('BodegaDestino', 'Bodega Principal')}\n"
                                    
                                    # 1. Registro directo en la tabla 'compras' de Supabase con aislamiento por negocio
                                    nuevo_reg_compra_nube = {
                                        "fecha_hora": datetime.now().isoformat(),
                                        "tipo_recepcion": "GRC",
                                        "proveedor": str(prov_final),
                                        "factura": str(num_factura),
                                        "codigo": str(item["Código"]),
                                        "descripcion": f"[{tipo_etiqueta}] {str(item['Descripción'])}",
                                        "cantidad": float(item["Cantidad"]),
                                        "neto_unitario": float(item["NetoUnitario"]),
                                        "costo_total": float(item["CostoTotal"]),
                                        "lote": str(item["Lote"]),
                                        "fecha_vencimiento_lote": str(item["FechaVencimiento"]),
                                        "condicion_pago": str(condicion_pago),
                                        "id_negocio": str(rut_actual).strip()
                                    }
                                    
                                    try:
                                        supabase.table("compras").insert(nuevo_reg_compra_nube).execute()
                                    except Exception as e:
                                        print(f"⚠️ Error guardando compra en Supabase: {e}")

                                    # 2. Actualizar Stock según sea Producto o Insumo en la bodega destino elegida
                                    bodega_linea = item.get("BodegaDestino", "Bodega Principal")
                                    if item.get("EsInsumo"):
                                        try:
                                            res_stk_ing = supabase.table("ingredientes").select("stock").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).eq("bodega", bodega_linea).execute()
                                            if res_stk_ing.data:
                                                stk_actual_ing = float(res_stk_ing.data[0]["stock"] or 0.0)
                                                nuevo_stk_ing = stk_actual_ing + float(item["Cantidad"])
                                                supabase.table("ingredientes").update({"stock": nuevo_stk_ing}).eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).eq("bodega", bodega_linea).execute()
                                            else:
                                                # Si no existe en esa bodega, buscamos el maestro base para copiarlo
                                                res_ing_gen = supabase.table("ingredientes").select("*").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).limit(1).execute()
                                                if res_ing_gen.data:
                                                    ing_nuevo = res_ing_gen.data[0].copy()
                                                    if 'id' in ing_nuevo: del ing_nuevo['id']
                                                    ing_nuevo['bodega'] = bodega_linea
                                                    ing_nuevo['stock'] = float(item["Cantidad"])
                                                    supabase.table("ingredientes").insert(ing_nuevo).execute()
                                        except Exception as e:
                                            print(f"⚠️ Error actualizando stock de ingrediente en Supabase: {e}")
                                    else:
                                        try:
                                            res_stk = supabase.table("productos").select("stock").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).eq("bodega", bodega_linea).execute()
                                            if res_stk.data:
                                                stk_actual = float(res_stk.data[0]["stock"] or 0.0)
                                                nuevo_stk = stk_actual + float(item["Cantidad"])
                                                supabase.table("productos").update({"stock": nuevo_stk}).eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).eq("bodega", bodega_linea).execute()
                                            else:
                                                res_general = supabase.table("productos").select("*").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).limit(1).execute()
                                                if res_general.data:
                                                    prod_nuevo = res_general.data[0].copy()
                                                    if 'id' in prod_nuevo: del prod_nuevo['id']
                                                    prod_nuevo['bodega'] = bodega_linea
                                                    prod_nuevo['stock'] = float(item["Cantidad"])
                                                    supabase.table("productos").insert(prod_nuevo).execute()
                                        except Exception as e:
                                            print(f"⚠️ Error actualizando stock en Supabase: {e}")

                                    # 3. Registrar el lote directamente en la tabla 'lotes' de Supabase (si aplica)
                                    if item.get("ManejaLote") == "Sí" and item.get("Lote") and item.get("Lote") != "N/A":
                                        nuevo_reg_lote_nube = {
                                            "codigo": str(item["Código"]),
                                            "descripcion": str(item["Descripción"]),
                                            "lote": str(item["Lote"]),
                                            "cantidad_disponible": float(item["Cantidad"]),
                                            "fecha_vencimiento": str(item["FechaVencimiento"]),
                                            "costo_unitario_final": float(item["CostoUnitarioFinal"]),
                                            "rut_empresa": str(rut_actual).strip()
                                        }
                                        try:
                                            supabase.table("lotes").insert(nuevo_reg_lote_nube).execute()
                                        except Exception as e:
                                            print(f"⚠️ Error guardando lote en Supabase: {e}")

                                    procesados += 1

                            archivo_gastos = os.path.join(ruta_negocio, "Registro_Gastos.xlsx") if 'ruta_negocio' in globals() else "Registro_Gastos.xlsx"
                            nuevo_gasto = pd.DataFrame([{
                                'Fecha_Hora': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'Descripcion_Gasto': f"GRC Factura/Folio #{num_factura} - {prov_final}",
                                'Categoria': 'Mercadería',
                                'Metodo_Pago': condicion_pago,
                                'Documento': f"GRC {num_factura}",
                                'Monto': monto_total_factura_general
                            }])
                            if os.path.exists(archivo_gastos):
                                df_gastos_ant = pd.read_excel(archivo_gastos)
                                pd.concat([df_gastos_ant, nuevo_gasto], ignore_index=True).to_excel(archivo_gastos, index=False)
                            else:
                                nuevo_gasto.to_excel(archivo_gastos, index=False)

                            if condicion_pago in ["Crédito", "Cheque"]:
                                archivo_cuentas = os.path.join(ruta_negocio, "Cuentas_Por_Pagar.xlsx") if 'ruta_negocio' in globals() else "Cuentas_Por_Pagar.xlsx"
                                nueva_cuenta = pd.DataFrame([{
                                    'Proveedor': prov_final,
                                    'Numero_Factura': num_factura,
                                    'Fecha_Emision': str(fecha_compra),
                                    'Fecha_Vencimiento': str(fecha_vencimiento_pago),
                                    'Monto_Total': monto_total_factura_general,
                                    'Estado': 'PENDIENTE'
                                }])
                                if os.path.exists(archivo_cuentas):
                                    df_cuentas_ant = pd.read_excel(archivo_cuentas)
                                    pd.concat([df_cuentas_ant, nueva_cuenta], ignore_index=True).to_excel(archivo_cuentas, index=False)
                                else:
                                    nueva_cuenta.to_excel(archivo_cuentas, index=False)

                            # 🗂️ ARCHIVADOR AUTOMÁTICO GRC (Subdirectorio)
                            try:
                                dir_arch_grc = os.path.join(ruta_negocio, "archivador_compras", "grc")
                                os.makedirs(dir_arch_grc, exist_ok=True)
                                doc_grc_txt = f"""========================================
 GUÍA DE RECEPCIÓN DE COMPRA (GRC)
========================================
FOLIO / FACTURA: {num_factura}
PROVEEDOR: {prov_final}
FECHA: {fecha_compra}
CONDICIÓN PAGO: {condicion_pago}
----------------------------------------
DETALLE:
{lineas_detalle_grc}----------------------------------------
TOTAL GRC: ${monto_total_factura_general:,.2f}
========================================"""
                                ruta_doc_grc = os.path.join(dir_arch_grc, f"GRC_{num_factura}.txt")
                                with open(ruta_doc_grc, "w", encoding="utf-8") as f_grc:
                                    f_grc.write(doc_grc_txt)
                            except Exception as e:
                                print(f"Error archivando GRC: {e}")

                            st.session_state.carrito_factura_compras = [i for i in st.session_state.carrito_factura_compras if i.get("TipoDoc") != "GRC"]
                            st.success(f"✅ ¡GRC #{num_factura} procesada con éxito! Inventario (productos/insumos), lotes y finanzas actualizados.")
                            st.rerun()

        # --- 2. REGISTRO GRI (Guía de Recepción Interna - Ajustes / Producción / Hallazgos) ---
        elif accion_producto == "🔄 Recepción Interna / GRI (Ajustes / Producción)":
            st.markdown("### 🔄 Generar Guía de Recepción Interna (GRI)")
            st.info("ℹ️ Use este módulo para ingresos de inventario generados internamente (devoluciones, producción propia, hallazgos o ajustes positivos de bodega).")

            # Identificador único de la empresa en Supabase
            func_tenant = globals().get("get_current_tenant")
            if callable(func_tenant):
                tenant_id = func_tenant()
            else:
                tenant_id = st.session_state.get("rut_empresa") or st.session_state.get("empresa_activa") or st.session_state.get("negocio")
            
            rut_actual = str(tenant_id) if tenant_id else ""

            # Cargar lista de bodegas desde Supabase
            opciones_bodegas = ["Bodega Principal"]
            try:
                res_bodegas = supabase.table("bodegas").select("nombre").eq("id_negocio", rut_actual).execute()
                if res_bodegas.data:
                    bodegas_db = [b.get("nombre") for b in res_bodegas.data if b.get("nombre")]
                    if bodegas_db:
                        opciones_bodegas = bodegas_db
            except Exception:
                pass

            with st.form("form_gri_interno"):
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    folio_gri = st.text_input("N° Folio GRI interno (ej. GRI-2026-001)")
                    motivo_gri = st.selectbox("Motivo del Ingreso Interno", ["Producción Propia", "Hallazgo de Inventario / Conteo", "Devolución de Cliente", "Ajuste Positivo de Bodega", "Otro"])
                    bodega_destino = st.selectbox("Bodega de Destino / Recepción", options=opciones_bodegas)
                with col_g2:
                    fecha_gri = st.date_input("Fecha de Recepción Interna", value=date.today())
                    responsable_gri = st.text_input("Responsable / Autorizado por")

                st.markdown("#### 📦 Seleccionar Producto y Cantidad")
                opciones_prod_gri = ["-- Selecciona un producto --"] + [f"{row[col_cod]} - {row[col_desc]}" for idx, row in df_base.iterrows()]
                prod_gri_sel = st.selectbox("Producto a Ingresar Internamente", options=opciones_prod_gri)
                
                col_q1, col_q2 = st.columns(2)
                with col_q1:
                    cant_gri = st.number_input("Cantidad a Ingresar", min_value=1.0, step=1.0, value=1.0)
                with col_q2:
                    costo_estimado_gri = st.number_input("Costo Unitario de Referencia ($)", min_value=0.0, step=1.0, value=0.0)

                maneja_lote_gri = st.selectbox("¿Asignar Lote a este ingreso interno?", ["No", "Sí"])
                lote_gri = "GRI-LOTE"
                venc_gri = str(date.today())

                if maneja_lote_gri == "Sí":
                    col_lg1, col_lg2 = st.columns(2)
                    with col_lg1:
                        lote_gri = st.text_input("N° Lote Interno", value="LOTE-INT-01")
                    with col_lg2:
                        venc_gri_date = st.date_input("Fecha de Vencimiento Lote Interno", value=date.today())
                        venc_gri = str(venc_gri_date)

                btn_procesar_gri = st.form_submit_button("💾 Emitir GRI y Actualizar Inventario", type="primary")

                if btn_procesar_gri:
                    if not folio_gri:
                        st.warning("⚠️ Debes ingresar un número de folio para la GRI.")
                    elif prod_gri_sel == "-- Selecciona un producto --":
                        st.warning("⚠️ Selecciona un producto válido.")
                    elif cant_gri <= 0:
                        st.warning("⚠️ La cantidad debe ser mayor a 0.")
                    else:
                        codigo_gri = prod_gri_sel.split(" - ")[0].strip()
                        desc_gri = prod_gri_sel.split(" - ")[1].strip()
                        
                        try:
                            # 1. ACTUALIZAR STOCK EN TABLA 'productos'
                            res_prod = supabase.table("productos").select("stock").eq("codigo", str(codigo_gri)).execute()
                            
                            if res_prod.data:
                                stock_actual_sb = float(res_prod.data[0].get("stock") or 0.0)
                                nuevo_stock_sb = stock_actual_sb + float(cant_gri)
                                supabase.table("productos").update({"stock": nuevo_stock_sb}).eq("codigo", str(codigo_gri)).execute()

                            # 2. REGISTRAR LOTE EN TABLA 'lotes' CON LA BODEGA CORRESPONDIENTE
                            if maneja_lote_gri == "Sí":
                                try:
                                    datos_lote = {
                                        "id_negocio": rut_actual,
                                        "codigo": str(codigo_gri),
                                        "descripcion": desc_gri,
                                        "lote": lote_gri,
                                        "cantidad_disponible": float(cant_gri),
                                        "fecha_vencimiento": str(venc_gri),
                                        "costo_unitario": float(costo_estimado_gri)
                                    }
                                    try:
                                        datos_lote["bodega"] = bodega_destino
                                        supabase.table("lotes").insert([datos_lote]).execute()
                                    except Exception:
                                        datos_lote.pop("bodega", None)
                                        supabase.table("lotes").insert([datos_lote]).execute()
                                except Exception as e_lote:
                                    print(f"Advertencia al registrar lote: {e_lote}")

                            # 3. REGISTRAR HISTORIAL EN TABLA 'compras'
                            datos_compra = {
                                "fecha_hora": datetime.now().isoformat(),
                                "tipo_recepcion": "GRI",
                                "proveedor": f"INTERNO ({motivo_gri})",
                                "factura": str(folio_gri),
                                "codigo": str(codigo_gri),
                                "descripcion": desc_gri,
                                "cantidad": float(cant_gri),
                                "neto_unitario": float(costo_estimado_gri),
                                "costo_total": float(cant_gri * costo_estimado_gri),
                                "lote": lote_gri if maneja_lote_gri == "Sí" else "",
                                "fecha_vencimiento_lote": str(venc_gri) if maneja_lote_gri == "Sí" else "",
                                "condicion_pago": "Interno",
                                "id_negocio": rut_actual,
                                "usuario": responsable_gri
                            }
                            
                            try:
                                datos_compra["bodega"] = bodega_destino
                                supabase.table("compras").insert([datos_compra]).execute()
                            except Exception:
                                datos_compra.pop("bodega", None)
                                supabase.table("compras").insert([datos_compra]).execute()

                            st.success(f"✅ ¡GRI #{folio_gri} guardada en la bodega '{bodega_destino}' y stock actualizado!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al comunicar la GRI con Supabase: {e}")
                            
        # --- 3. CREAR PRODUCTO NUEVO (MÓDULO DE COMPRAS) ---
        elif accion_producto == "➕ Crear Producto Nuevo":
            st.markdown("### 🆕 Ingresar Nuevo Producto a la Base de Datos")
            
            # 1. Rescatar bodegas existentes para Compras
            bodegas_existentes = ["Bodega Principal"]
            try:
                res_bod = supabase.table("productos").select("bodega").eq("rut_empresa", rut_actual).execute()
                if res_bod.data:
                    for row in res_bod.data:
                        b = row.get("bodega")
                        if b and b not in bodegas_existentes:
                            bodegas_existentes.append(b)
            except Exception:
                pass
            bodegas_existentes.append("➕ Crear Nueva Bodega / Sucursal...")

            codigo_scanned_nuevo = st.text_input("📷 Digita o ingresa el código del producto nuevo:", key="scan_nuevo_prod")
        
            with st.form("form_crear_producto_compras", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    codigo = st.text_input("Código del Producto (EAN o Interno) *", value=codigo_scanned_nuevo if codigo_scanned_nuevo else "")
                    dun14 = st.text_input("DUN14 (Opcional)", placeholder="Código de caja")
                    descripcion = st.text_input("Descripción / Nombre del Producto *", placeholder="Ej: BEBIDA ORANGE CRUSH PET300")
                    categoria = st.selectbox("Categoría", ["Ninguna", "BEBIDAS", "ABARROTES", "SNACKS", "OTROS"])
                    
                with col2:
                    # 🚨 SELECTOR DE BODEGA EN COMPRAS
                    bodega_seleccionada = st.selectbox("🏢 Asignar a Bodega / Sucursal:", bodegas_existentes)
                    nueva_bodega = ""
                    if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal...":
                        nueva_bodega = st.text_input("✍️ Escribe el nombre de la nueva Bodega:")
                        
                    costo = st.number_input("Costo de Compra Neto ($)", min_value=0.0, step=100.0)
                    stock = st.number_input("Stock Inicial", min_value=0.0, step=1.0)
                    impuesto_especifico = st.selectbox("Impuesto Específico", ["Ninguno", "IABA 10", "IABA 18", "ILA", "ILA 31.5"])
                    
                st.markdown("##### 💡 Configuración Tributaria (Ingresa el Neto o el Bruto)")
                nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
                tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_act or str(rut_actual) == "219449970012" else 19.0
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    precio_neto = st.number_input("Precio Neto ($)", min_value=0.0, step=100.0)
                    porcentaje_iva = st.number_input("% de IVA", min_value=0.0, value=tasa_defecto, step=1.0)
                with col_p2:
                    precio_venta = st.number_input("Precio Bruto/Final ($) *", min_value=0.0, step=100.0)
                    es_exento = st.selectbox("¿Es Exento de IVA?", ["No", "Si"])
                    
                st.markdown("---")
                col_disp, col_act = st.columns(2)
                with col_disp:
                    disponible_venta = st.selectbox("¿Disponible para Venta?", ["Si", "No"])
                with col_act:
                    activo = st.selectbox("¿Activo en el sistema?", ["Si", "No"])
            
                btn_crear_prod = st.form_submit_button("💾 Agregar Producto a la Base de Datos")

                if btn_crear_prod:
                    bodega_final = nueva_bodega.strip() if bodega_seleccionada == "➕ Crear Nueva Bodega / Sucursal..." else bodega_seleccionada
                    
                    if codigo == "" or descripcion == "" or (precio_venta <= 0 and precio_neto <= 0):
                        st.warning("⚠️ Por favor, completa Código, Descripción y un Precio (Neto o Bruto mayor a 0).")
                    elif not bodega_final:
                        st.warning("⚠️ Debes asignar un nombre a la bodega.")
                    else:
                        iva_final = float(porcentaje_iva)
                        if es_exento == "Si":
                            iva_final = 0.0
                            
                        p_neto_calc = float(precio_neto)
                        p_bruto_calc = float(precio_venta)
                        
                        if p_bruto_calc > 0 and p_neto_calc == 0:
                            p_neto_calc = p_bruto_calc / (1.0 + (iva_final / 100.0))
                        elif p_neto_calc > 0:
                            p_bruto_calc = p_neto_calc * (1.0 + (iva_final / 100.0))

                        nuevo_producto = {
                            "rut_empresa": rut_actual,
                            "codigo": codigo.strip(),
                            "bodega": bodega_final,
                            "dun14": dun14 if dun14 else None,
                            "descripcion": descripcion.strip(),
                            "categoria": categoria if categoria != "Ninguna" else None,
                            "costo": costo,
                            "precio_neto": round(p_neto_calc, 2),
                            "porcentaje_iva": round(iva_final, 2),
                            "precio_venta": round(p_bruto_calc, 2),
                            "stock": stock,
                            "es_exento": es_exento,
                            "impuesto_especifico": impuesto_especifico if impuesto_especifico != "Ninguno" else None,
                            "disponible_venta": disponible_venta,
                            "activo": activo
                        }
                        
                        try:
                            # 🚨 CHECK MULTI-BODEGA (Actualiza o Crea)
                            res_check = supabase.table("productos").select("id").eq("rut_empresa", rut_actual).eq("codigo", codigo.strip()).eq("bodega", bodega_final).execute()
                            if res_check.data:
                                supabase.table("productos").update(nuevo_producto).eq("id", res_check.data[0]["id"]).execute()
                                st.success(f"✅ Producto actualizado en '{bodega_final}'.")
                            else:
                                supabase.table("productos").insert(nuevo_producto).execute()
                                st.success(f"✅ ¡Producto '{descripcion}' guardado con éxito en '{bodega_final}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar en la nube: {e}")

        # --- 4. EDITAR PRODUCTO EXISTENTE ---
        elif accion_producto == "✏️ Editar Producto Existente":
            st.markdown("### ✏️ Modificar datos de un Producto Existente")
            # Cargamos las opciones directamente desde el DataFrame que ya bajamos de la nube
            opciones_editar = ["-- Selecciona producto a editar --"] + [f"{row[col_cod]} - {row[col_desc]}" for idx, row in df_base.iterrows()]
        
            with st.form("form_editar_producto_compras"):
                st.info("💡 Deja en 0 o en blanco los campos que NO deseas modificar.")
                prod_a_editar = st.selectbox("Selecciona Producto", options=opciones_editar)
                nuevo_nombre = st.text_input("Nueva Descripción / Nombre")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    nuevo_precio_neto = st.number_input("Modificar Precio Neto ($)", min_value=0.0, step=100.0, value=0.0)
                    nuevo_iva = st.number_input("Modificar % IVA (Ingresa -1 para omitir)", min_value=-1.0, step=1.0, value=-1.0)
                    nuevo_costo = st.number_input("Modificar Costo Neto ($)", min_value=0.0, step=100.0, value=0.0)
                with col_e2:
                    nuevo_precio_bruto = st.number_input("Modificar Precio Bruto ($)", min_value=0.0, step=100.0, value=0.0)
                    nuevo_stock = st.number_input("Reemplazar Stock Actual", min_value=0.0, step=1.0, value=0.0)
                
                btn_editar_prod = st.form_submit_button("💾 Guardar Cambios en la Nube")

                if btn_editar_prod:
                    if prod_a_editar != "-- Selecciona producto a editar --":
                        cod_editar = prod_a_editar.split(" - ")[0]
                        
                        datos_a_actualizar = {}
                        if nuevo_nombre.strip() != "":
                            datos_a_actualizar["descripcion"] = nuevo_nombre.strip()
                        if nuevo_precio_neto > 0:
                            datos_a_actualizar["precio_neto"] = nuevo_precio_neto
                        if nuevo_precio_bruto > 0:
                            datos_a_actualizar["precio_venta"] = nuevo_precio_bruto
                        if nuevo_iva != -1.0:
                            datos_a_actualizar["porcentaje_iva"] = nuevo_iva
                        if nuevo_costo > 0:
                            datos_a_actualizar["costo"] = nuevo_costo
                        if nuevo_stock > 0:
                            datos_a_actualizar["stock"] = nuevo_stock
                            
                        if datos_a_actualizar:
                            try:
                                supabase.table("productos").update(datos_a_actualizar).eq("rut_empresa", rut_actual).eq("codigo", str(cod_editar)).execute()
                                st.success("✅ ¡Producto actualizado correctamente en todos los módulos!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al actualizar en Supabase: {e}")
                        else:
                            st.warning("⚠️ No ingresaste ningún valor nuevo para actualizar.")
                    else:
                        st.warning("⚠️ Selecciona un producto válido para editar.")

# ----------------- SECCIÓN CONFIGURACIÓN GENERAL -----------------
elif menu == "⚙️ Configuración General":
    mostrar_encabezado_con_home("⚙️ Panel de Configuración General del Sistema")
  
    # 📁 Definición de rutas y directorios específicos del negocio actual
    tenant_dir = os.path.join(CARPETA_CLIENTES, negocio_seleccionado)
    os.makedirs(tenant_dir, exist_ok=True)
    ruta_bd_actual = os.path.join(tenant_dir, "BASE DE DATOS.xlsx")
    ruta_plantilla_base = os.path.join("plantilla_cliente", "BASE DE DATOS.xlsx")
    ruta_logo = os.path.join(tenant_dir, "logo_empresa.png")
    ruta_config_json = os.path.join(tenant_dir, "config_ticket.json")
    ruta_usuarios_local = os.path.join(tenant_dir, "usuarios_negocio.json")

    def cargar_usuarios_local(path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def guardar_usuarios_local(path, datos):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)

    rut_actual = st.session_state.get("negocio_seleccionado")

    # --- OBTENER ID Y DATOS ACTUALES DE LA EMPRESA DESDE SUPABASE ---
    empresa_id_actual = None
    datos_empresa_db = {}
    try:
        res_empresa = supabase.table("empresas").select("*").eq("rut_empresa", rut_actual).execute()
        if res_empresa.data:
            datos_empresa_db = res_empresa.data[0]
            empresa_id_actual = datos_empresa_db.get("id")
    except Exception as e:
        st.error(f"⚠️ Error conectando con la tabla empresas: {e}")

    if "ultimo_negocio_config" not in st.session_state or st.session_state.ultimo_negocio_config != negocio_seleccionado:
        st.session_state.ultimo_negocio_config = negocio_seleccionado
        if os.path.exists(ruta_config_json):
            try:
                with open(ruta_config_json, "r", encoding="utf-8") as f:
                    st.session_state.config_ticket = json.load(f)
            except Exception:
                st.session_state.config_ticket = {
                    "nombre_empresa": negocio_seleccionado, 
                    "rut_empresa": "", 
                    "direccion": "", 
                    "iva_tasa": 19.0, 
                    "pie_pagina": "", 
                    "formato_impresion": "80mm (Térmica Estándar)"
                }
        else:
            st.session_state.config_ticket = {
                "nombre_empresa": negocio_seleccionado, 
                "rut_empresa": "", 
                "direccion": "", 
                "iva_tasa": 19.0, 
                "pie_pagina": "", 
                "formato_impresion": "80mm (Térmica Estándar)"
            }

    # 📜 Pestañas Principales de Configuración General
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏢 Datos de la Empresa",
        "👥 Usuarios y Cajas", 
        "💳 Formas de Pago", 
        "🖨️ Formato de Tickets", 
        "📜 Certificado Digital (DTE)"
    ])

    # ==========================================
    # PESTAÑA 1: DATOS DE LA EMPRESA (PROTEGIDA CONTRA VALORES NULL)
    # ==========================================
    with tab1:
        # Carga/Sincronización inicial en la memoria de sesión
        if datos_empresa_db:
            if "datos_empresa" not in st.session_state:
                st.session_state.datos_empresa = dict(datos_empresa_db)
            else:
                st.session_state.datos_empresa.update(datos_empresa_db)

        st.markdown("### 🏢 Configuración de Identidad de la Empresa")
        st.info("ℹ️ Separa la Razón Social exigida legalmente por el SII del Nombre de Fantasía que verán tus clientes en los tickets impresos.")

        # Sanitización de valores None provenientes de Supabase
        val_razon_def = datos_empresa_db.get("razon_social") or datos_empresa_db.get("empresa_nombre") or negocio_seleccionado or ""
        val_rut_def = datos_empresa_db.get("rut_empresa") or rut_actual or ""
        val_giro_def = datos_empresa_db.get("giro") or ""
        val_dir_trib_def = datos_empresa_db.get("direccion_tributaria") or datos_empresa_db.get("direccion") or ""
        val_comuna_def = datos_empresa_db.get("comuna") or "Santiago"
        val_email_def = datos_empresa_db.get("email_contacto") or ""

        val_fantasia_def = datos_empresa_db.get("nombre_fantasia") or datos_empresa_db.get("empresa_nombre") or negocio_seleccionado or ""
        val_slogan_def = datos_empresa_db.get("slogan") or ""
        val_dir_local_def = datos_empresa_db.get("direccion_local") or datos_empresa_db.get("direccion") or ""
        val_telefono_def = datos_empresa_db.get("telefono") or ""
        val_ticket_def = datos_empresa_db.get("usar_nombre_fantasia_ticket") if datos_empresa_db.get("usar_nombre_fantasia_ticket") is not None else True

        # Sub-pestañas para Razón Social y Nombre de Fantasía
        subtab_razon, subtab_fantasia = st.tabs([
            "🏛️ Razón Social (Datos Legales SII)", 
            "🏪 Nombre de Fantasía (Marca / POS)"
        ])

        # --- SUB-PESTAÑA 1: RAZÓN SOCIAL (LEGAL / DTE) ---
        with subtab_razon:
            st.markdown("#### 🏛️ Datos Legales para Impuestos Internos (SII / DTE)")
            with st.form("form_razon_social_sii"):
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    razon_social_val = st.text_input(
                        "Razón Social Legítima (SII) *", 
                        value=str(val_razon_def),
                        placeholder="Ej: SOCIEDAD COMERCIAL E INVERSIONES LIMITADA"
                    )
                    rut_empresa_input = st.text_input(
                        "RUT Empresa *", 
                        value=str(val_rut_def),
                        placeholder="Ej: 77.654.321-K"
                    )
                    giro_comercial = st.text_input(
                        "Giro Comercial (SII) *", 
                        value=str(val_giro_def),
                        placeholder="Ej: Venta al por menor de bebidas y licores"
                    )
                with col_r2:
                    direccion_tributaria = st.text_input(
                        "Dirección Casa Matriz / Tributaria *", 
                        value=str(val_dir_trib_def),
                        placeholder="Ej: Av. Providencia 1234, Of. 501"
                    )
                    comuna_ciudad = st.text_input(
                        "Comuna / Ciudad *", 
                        value=str(val_comuna_def),
                        placeholder="Ej: Santiago"
                    )
                    email_tributario = st.text_input(
                        "Correo Electrónico Tributario (DTE) *", 
                        value=str(val_email_def),
                        placeholder="dte@miempresa.cl"
                    )

                btn_guardar_razon = st.form_submit_button("💾 Guardar Razón Social y Datos Legales", type="primary", use_container_width=True)

                if btn_guardar_razon:
                    str_razon = (razon_social_val or "").strip()
                    str_rut = (rut_empresa_input or "").strip()

                    if not str_razon or not str_rut:
                        st.warning("⚠️ La Razón Social y el RUT son obligatorios.")
                    else:
                        payload_razon = {
                            "razon_social": str_razon,
                            "empresa_nombre": str_razon,
                            "rut_empresa": str_rut,
                            "giro": (giro_comercial or "").strip(),
                            "direccion_tributaria": (direccion_tributaria or "").strip(),
                            "direccion": (direccion_tributaria or "").strip(),
                            "comuna": (comuna_ciudad or "").strip(),
                            "email_contacto": (email_tributario or "").strip()
                        }
                        try:
                            if empresa_id_actual:
                                supabase.table("empresas").update(payload_razon).eq("id", empresa_id_actual).execute()
                            else:
                                supabase.table("empresas").insert(payload_razon).execute()

                            # 🔄 ACTUALIZACIÓN DIRECTA EN LA MEMORIA DE LA SESIÓN
                            if "datos_empresa" not in st.session_state:
                                st.session_state.datos_empresa = {}
                            st.session_state.datos_empresa.update(payload_razon)

                            if "config_ticket" not in st.session_state:
                                st.session_state.config_ticket = {}
                            st.session_state.config_ticket.update({
                                "razon_social": str_razon,
                                "rut_empresa": str_rut,
                                "direccion": (direccion_tributaria or "").strip(),
                                "direccion_tributaria": (direccion_tributaria or "").strip(),
                                "giro": (giro_comercial or "").strip(),
                                "comuna": (comuna_ciudad or "").strip(),
                                "email_contacto": (email_tributario or "").strip()
                            })

                            st.toast("✅ ¡Razón Social y datos legales guardados correctamente!", icon="🏛️")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar Razón Social: {e}")

        # --- SUB-PESTAÑA 2: NOMBRE DE FANTASÍA (MARCA / TICKETS) ---
        with subtab_fantasia:
            st.markdown("#### 🏪 Identidad Comercial para Punto de Venta (POS)")
            with st.form("form_nombre_fantasia"):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    nombre_fantasia_val = st.text_input(
                        "Nombre de Fantasía (Marca Comercial) *", 
                        value=str(val_fantasia_def),
                        placeholder="Ej: BOTILLERIA SAPIRON"
                    )
                    slogan_o_leyenda = st.text_input(
                        "Slogan / Leyenda de Marca", 
                        value=str(val_slogan_def),
                        placeholder="Ej: Vinos, Cervezas y Licores Premium"
                    )
                with col_f2:
                    direccion_local = st.text_input(
                        "Dirección Visible en Ticket", 
                        value=str(val_dir_local_def),
                        placeholder="Ej: AVENIDA MAIPU 1512"
                    )
                    telefono_local = st.text_input(
                        "Teléfono de Atención al Cliente", 
                        value=str(val_telefono_def),
                        placeholder="Ej: +56 9 1234 5678"
                    )

                mostrar_fantasia_en_ticket = st.checkbox(
                    "Imprimir Nombre de Fantasía en el encabezado de los tickets de venta", 
                    value=bool(val_ticket_def)
                )

                btn_guardar_fantasia = st.form_submit_button("💾 Guardar Nombre de Fantasía", type="primary", use_container_width=True)

                if btn_guardar_fantasia:
                    str_fantasia = (nombre_fantasia_val or "").strip()

                    if not str_fantasia:
                        st.warning("⚠️ El Nombre de Fantasía no puede estar vacío.")
                    else:
                        payload_fantasia = {
                            "nombre_fantasia": str_fantasia,
                            "slogan": (slogan_o_leyenda or "").strip(),
                            "direccion_local": (direccion_local or "").strip(),
                            "telefono": (telefono_local or "").strip(),
                            "usar_nombre_fantasia_ticket": mostrar_fantasia_en_ticket
                        }
                        try:
                            if empresa_id_actual:
                                supabase.table("empresas").update(payload_fantasia).eq("id", empresa_id_actual).execute()
                            else:
                                supabase.table("empresas").insert(payload_fantasia).execute()

                            # 🔄 ACTUALIZACIÓN DIRECTA EN LA MEMORIA DE LA SESIÓN
                            if "datos_empresa" not in st.session_state:
                                st.session_state.datos_empresa = {}
                            st.session_state.datos_empresa.update(payload_fantasia)

                            if "config_ticket" not in st.session_state:
                                st.session_state.config_ticket = {}
                            st.session_state.config_ticket["nombre_fantasia"] = str_fantasia
                            if mostrar_fantasia_en_ticket:
                                st.session_state.config_ticket["nombre_empresa"] = str_fantasia

                            st.toast("✅ ¡Nombre de Fantasía guardado correctamente!", icon="🏪")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar Nombre de Fantasía: {e}")

    # ==========================================
    # PESTAÑA 2: USUARIOS Y CAJAS (RESTRINGIDA A PROPIETARIO / ADMINISTRADOR)
    # ==========================================
    with tab2:
        st.markdown("### 👥 Administración de Operadores y Permisos")

        # Verificación ultra robusta de Rol / Permiso en session_state
        texto_sesion_usuario = ""
        
        # 1. Inspeccionar claves habituales de usuario y rol
        for key in ["rol", "usuario_rol", "rol_usuario", "user_role", "role", "perfil", "usuario", "usuario_actual", "user"]:
            val = st.session_state.get(key)
            if isinstance(val, dict):
                texto_sesion_usuario += f" {val.get('rol', '')} {val.get('role', '')} {val.get('nombre', '')} {val.get('usuario', '')}"
            elif isinstance(val, str):
                texto_sesion_usuario += f" {val}"

        # 2. Escaneo de respaldo sobre todas las variables de session_state
        for k, v in st.session_state.items():
            if isinstance(v, str) and any(t in v.lower() for t in ["propietario", "administrador", "admin"]):
                texto_sesion_usuario += f" {v}"

        texto_sesion_usuario = texto_sesion_usuario.lower()
        es_propietario = any(term in texto_sesion_usuario for term in ["propietario", "administrador", "admin"])

        if not es_propietario:
            st.error("🔒 **Acceso Restringido:** La creación, edición y administración de usuarios es de uso exclusivo para el Propietario o Administrador del sistema.")
        else:
            st.info("ℹ️ Crea usuarios, edita sus datos y define a qué módulos pueden acceder. Estos datos se guardan directamente en la tabla 'usuarios' de Supabase.")

            todos_los_modulos_sistema = [
                "🏠 Home / Bienvenida", "📊 Dashboard Ejecutivo", "📦 Inventario y Productos", 
                "💰 Módulo de Ventas (POS)", "🛒 Registrar Compra (CPP)", "📉 Mermas y Ajustes", 
                "📈 Informes y Movimientos (Kardex)", "⚠️ Control y Gestión de Inventario", 
                "📊 Módulo de Finanzas", "📒 Cuadratura Diaria", "📑 Cuentas por Cobrar", 
                "📈 Reportes y Analítica", "📚 Historial de Ventas", "🔄 Notas de Crédito", 
                "🏦 Conciliación y Retiros Seguros", "⚙️ Configuración General", "🔑 Control Maestro de Licencias"
            ]

            db_permisos_dev = cargar_permisos() if 'cargar_permisos' in globals() else {}
            if rut_actual in db_permisos_dev:
                modulos_permitidos_desarrollador = [mod for mod, activo in db_permisos_dev[rut_actual].items() if activo]
            else:
                modulos_permitidos_desarrollador = todos_los_modulos_sistema

            if not empresa_id_actual:
                st.warning("⚠️ No se encontró el ID de la empresa. Completa primero la pestaña 'Datos de la Empresa'.")
            else:
                db_usuarios = {}
                try:
                    res_users = supabase.table("usuarios").select("*").eq("empresa_id", empresa_id_actual).execute()
                    if res_users.data:
                        for row in res_users.data:
                            db_usuarios[row["rut_usuario"]] = row
                except Exception as e:
                    st.error(f"⚠️ Error cargando usuarios: {e}")

                st.markdown("#### 📋 Usuarios Actuales")
                if db_usuarios:
                    lista_tabla = []
                    for uid, info in db_usuarios.items():
                        modulos_permitidos = info.get("modulos", "")
                        lista_tabla.append({
                            "RUT Usuario": uid,
                            "Nombre": info.get("nombre", "Sin Nombre"),
                            "Rol Asignado": info.get("rol", "No definido"),
                            "Módulos Habilitados": modulos_permitidos if modulos_permitidos else "Ninguno"
                        })
                    st.dataframe(pd.DataFrame(lista_tabla), use_container_width=True)
                else:
                    st.info("ℹ️ No hay operadores registrados para esta empresa todavía.")

                st.divider()

                st.markdown("#### ⚙️ Crear o Editar Permisos de Usuario")
                opciones_usuarios = ["-- ✨ Crear Nuevo Usuario --"] + list(db_usuarios.keys())
                usuario_seleccionado = st.selectbox(
                    "🔍 Buscar Usuario a Editar (o Crear Nuevo):", 
                    opciones_usuarios, 
                    key="select_user_cfg_tab2"
                )
                
                es_nuevo = (usuario_seleccionado == "-- ✨ Crear Nuevo Usuario --")
                def_uid = "" if es_nuevo else usuario_seleccionado
                def_nombre = "" if es_nuevo else db_usuarios[usuario_seleccionado].get("nombre", "")
                def_pass = ""
                def_rol = "Cajero / Vendedor" if es_nuevo else db_usuarios[usuario_seleccionado].get("rol", "Cajero / Vendedor")
                
                modulos_str = "" if es_nuevo else db_usuarios[usuario_seleccionado].get("modulos", "")
                def_modulos = [m.strip() for m in modulos_str.split(",") if m.strip()] if modulos_str else []

                todos_los_modulos = [m for m in todos_los_modulos_sistema if m in modulos_permitidos_desarrollador or m == "🏠 Home / Bienvenida"]
                if not todos_los_modulos:
                    todos_los_modulos = todos_los_modulos_sistema

                key_suffix = "nuevo" if es_nuevo else usuario_seleccionado.replace(" ", "_").replace("-", "_").replace(".", "_")

                with st.form(f"form_crear_editar_operador_{key_suffix}", clear_on_submit=False):
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        nuevo_user_id = st.text_input("RUT del Usuario *", value=def_uid, disabled=not es_nuevo, key=f"rut_{key_suffix}")
                        nuevo_nombre_usr = st.text_input("Nombre Completo *", value=def_nombre, key=f"nombre_{key_suffix}")
                    with col_u2:
                        nuevo_pass_usr = st.text_input("Contraseña de Acceso *", type="password", value=def_pass, key=f"pass_{key_suffix}")
                        roles_opciones = ["Cajero / Vendedor", "Bodeguero", "Administrador"]
                        idx_rol = roles_opciones.index(def_rol) if def_rol in roles_opciones else 0
                        nuevo_rol_usr = st.selectbox("Rol Principal", options=roles_opciones, index=idx_rol, key=f"rol_{key_suffix}")

                    st.markdown("**🔐 Asignación de Permisos (Limitado por Licencia del Desarrollador)**")
                    modulos_seleccionados = st.multiselect(
                        "Selecciona a qué módulos podrá entrar este usuario:",
                        options=todos_los_modulos,
                        default=[m for m in def_modulos if m in todos_los_modulos],
                        key=f"mods_{key_suffix}"
                    )

                    texto_boton = "💾 Registrar Nuevo Operador" if es_nuevo else "🔄 Guardar Cambios"
                    btn_guardar_usr = st.form_submit_button(texto_boton, type="primary")

                    if btn_guardar_usr:
                        user_limpio = nuevo_user_id.strip().upper()
                        pass_limpia = nuevo_pass_usr.strip()
                        
                        if not user_limpio or not nuevo_nombre_usr.strip():
                            st.warning("⚠️ Debes ingresar el RUT y el Nombre.")
                        elif es_nuevo and not pass_limpia:
                            st.warning("⚠️ Para crear un nuevo usuario, la contraseña es obligatoria.")
                        else:
                            registro_usuario = {
                                "empresa_id": empresa_id_actual,
                                "rut_usuario": user_limpio,
                                "nombre": nuevo_nombre_usr.strip(),
                                "rol": nuevo_rol_usr,
                                "modulos": ", ".join(modulos_seleccionados) if modulos_seleccionados else "🏠 Home / Bienvenida"
                            }
                            
                            if pass_limpia:
                                registro_usuario["password_hash"] = pass_limpia
                            
                            try:
                                if es_nuevo:
                                    supabase.table("usuarios").insert(registro_usuario).execute()
                                    st.toast(f"✨ ¡Usuario '{nuevo_nombre_usr}' creado con éxito!", icon="✅")
                                else:
                                    id_db = db_usuarios[usuario_seleccionado]["id"]
                                    supabase.table("usuarios").update(registro_usuario).eq("id", id_db).execute()
                                    st.toast(f"✅ ¡Permisos actualizados para '{nuevo_nombre_usr}'!", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al guardar en base de datos: {e}")

                if not es_nuevo:
                    with st.expander("🗑️ Eliminar Usuario"):
                        st.warning(f"¿Estás seguro de eliminar a **{def_nombre}** ({def_uid})?")
                        if st.button("🚨 Confirmar Eliminación", key=f"del_user_{key_suffix}"):
                            try:
                                id_db = db_usuarios[usuario_seleccionado]["id"]
                                supabase.table("usuarios").delete().eq("id", id_db).execute()
                                st.toast("🗑️ Usuario eliminado correctamente.", icon="🗑️")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al eliminar usuario: {e}")

    # ==========================================
    # PESTAÑA 3: FORMAS DE PAGO
    # ==========================================
    with tab3:
        st.markdown("### 💳 Configuración de Formas de Pago Aceptadas")
        with st.form("form_nueva_forma_pago"):
            nueva_forma = st.text_input("Nueva Forma de Pago")
            btn_add_pago = st.form_submit_button("➕ Agregar Forma de Pago")
            if btn_add_pago and nueva_forma and nueva_forma not in st.session_state.formas_pago_erp:
                st.session_state.formas_pago_erp.append(nueva_forma)
                st.success(f"✅ Forma de pago '{nueva_forma}' agregada.")
        for fp in st.session_state.formas_pago_erp:
            st.markdown(f"- 💳 {fp}")

    # ==========================================
    # PESTAÑA 4: FORMATO DE TICKETS
    # ==========================================
    with tab4:
        st.markdown("### 🖨️ Datos del Comprobante e Impresión")
        with st.form("form_config_ticket"):
            pie = st.text_input("Pie de Página", value=st.session_state.config_ticket.get("pie_pagina", ""))
          
            formatos_disponibles = ["80mm (Térmica Estándar)", "58mm (Térmica Pequeña)", "Carta / A4"]
            formato_actual = st.session_state.config_ticket.get("formato_impresion", "80mm (Térmica Estándar)")
            idx_formato = formatos_disponibles.index(formato_actual) if formato_actual in formatos_disponibles else 0
          
            formato = st.selectbox("Formato", formatos_disponibles, index=idx_formato)
            btn_guardar_config = st.form_submit_button("💾 Guardar Configuración")
          
            if btn_guardar_config:
                st.session_state.config_ticket["pie_pagina"] = pie
                st.session_state.config_ticket["formato_impresion"] = formato
                
                try:
                    if empresa_id_actual:
                        supabase.table("empresas").update(
                            {"config_ticket": st.session_state.config_ticket}
                        ).eq("id", empresa_id_actual).execute()
                        st.success("✅ Configuración de ticket guardada permanentemente en la nube.")
                    else:
                        st.error("No se pudo identificar la empresa para guardar la configuración.")
                except Exception as e:
                    st.error(f"❌ Error al guardar en base de datos: {e}")

        st.markdown("---")
        st.markdown("### 🖼️ Logotipo de la Empresa")
        
        ruta_storage_logo = f"{rut_actual}/logo_empresa.png"
        try:
            url_logo = supabase.storage.from_("archivos_clientes").get_public_url(ruta_storage_logo)
            st.image(url_logo, width=120, caption="Logotipo actual en la nube")
        except Exception:
            st.info("No hay un logotipo cargado en la nube aún.")
   
        logo_cargado = st.file_uploader("Sube una imagen para tu logo (PNG o JPG)", type=["png", "jpg", "jpeg"], key="uploader_logo_empresa")
        
        if logo_cargado is not None:
            try:
                file_bytes = logo_cargado.getvalue()
                supabase.storage.from_("archivos_clientes").upload(
                    path=ruta_storage_logo, 
                    file=file_bytes, 
                    file_options={"content-type": logo_cargado.type, "upsert": "true"}
                )
                
                st.success("✅ ¡Logotipo subido y actualizado en la nube con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al subir el logo a Storage: {e}")

    # ==========================================
    # PESTAÑA 5: CERTIFICADO DIGITAL
    # ==========================================
    with tab5:
        st.markdown("### 📜 Certificado Digital (Firma Electrónica)")
        st.write("Carga tu firma digital para vincular tu negocio ante el SII a través de OpenFactura y habilitar la emisión oficial de DTEs.")

        with st.expander("🛒 ¿Aún no tienes Certificado Digital? Cómpralo aquí", expanded=False):
            st.info("Adquiere tu firma digital autorizada por el SII:")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.link_button("🌐 Comprar en Firma.cl", "https://www.firma.cl", use_container_width=True)
            with col_c2:
                st.link_button("🌐 Comprar en E-CertChile", "https://www.e-certchile.cl", use_container_width=True)

        st.divider()

        st.markdown("#### 📤 Cargar y Vincular Certificado Digital")
        
        archivo_pfx = st.file_uploader(
            "Selecciona el archivo de tu certificado (.pfx o .p12):", 
            type=["pfx", "p12"],
            key="uploader_cert_pfx"
        )
        
        password_pfx = st.text_input(
            "Contraseña del Certificado Digital:", 
            type="password", 
            placeholder="••••••••",
            key="pass_cert_pfx"
        )

        if st.button("🔐 Cargar y Activar Firma en OpenFactura", type="primary", use_container_width=True, key="btn_subir_cert_openfactura"):
            if not archivo_pfx or not password_pfx:
                st.warning("⚠️ Debes adjuntar el archivo e ingresar la contraseña.")
            else:
                with st.spinner("Registrando y validando firma digital con el proveedor DTE..."):
                    import requests
                    endpoint_cert = "https://api.haulmer.com/v2/dte/organization/certificate"
                    
                    headers = {
                        "apikey": "9245922d05404d71b84f0f03227d8e87"
                    }
                    
                    files = {
                        "file": (archivo_pfx.name, archivo_pfx.getvalue(), "application/x-pkcs12")
                    }
                    data = {
                        "password": password_pfx,
                        "rut": str(rut_actual)
                    }
                    
                    try:
                        response = requests.post(endpoint_cert, headers=headers, files=files, data=data, timeout=15)
                        if response.status_code in [200, 201]:
                            st.success("🎉 ¡Certificado Digital cargado y vinculado con éxito!")
                        else:
                            st.error(f"❌ Error al validar certificado con OpenFactura: {response.text}")
                    except Exception as e:
                        st.error(f"⚠️ Error de conexión con la API de OpenFactura: {e}")

    # ==========================================
    # SECCIÓN INFERIOR: ADMINISTRACIÓN DE ARCHIVOS
    # ==========================================
    st.markdown("---")
    st.markdown("### 🗂️ Administración de archivos")
    st.write("Gestiona la base de datos de tu negocio: descarga plantillas en blanco con todas las columnas de Supabase, exporta tu información o realiza cargas masivas.")

    accion = st.radio(
        "¿Qué acción deseas realizar?",
        ("Selecciona una opción...", "Descargar plantilla en blanco", "Exportar base de datos actual", "Importar base de datos"),
        index=0,
        key="radio_adm_archivos_config"
    )

    tenant_id = st.session_state.get("negocio_seleccionado") or get_current_tenant()

    # Columnas por defecto por si la tabla en Supabase está completamente vacía
    columnas_default = {
        "productos": ["id", "created_at", "rut_empresa", "codigo_barra", "nombre", "categoria", "costo", "precio_venta", "stock", "descripcion", "unidad_medida", "activo"],
        "clientes": ["id", "created_at", "rut_empresa", "rut", "nombre", "email", "telefono", "direccion", "comuna", "giro"],
        "proveedores": ["id", "created_at", "rut_empresa", "rut", "razon_social", "giro", "contacto", "telefono", "email", "direccion"],
        "gastos": ["id", "created_at", "rut_empresa", "fecha", "categoria", "descripcion", "monto", "tipo_costo", "iva", "comprobante", "proveedor"],
        "costos_fijos": ["id", "created_at", "rut_empresa", "nombre", "monto", "categoria", "frecuencia", "activo"]
    }

    # 1. DESCARGAR PLANTILLA EN BLANCO (DINÁMICA DESDE SUPABASE)
    if accion == "Descargar plantilla en blanco":
        st.info("💡 La plantilla se genera en tiempo real leyendo la estructura exacta de tu tabla en Supabase.")
        
        tabla_destino = st.selectbox(
            "Selecciona la tabla para generar la plantilla:",
            ["productos", "clientes", "proveedores", "gastos", "costos_fijos"],
            key="select_tipo_plantilla_config"
        )

        try:
            # Consultamos 1 registro en Supabase para obtener el listado exacto de columnas
            res = supabase.table(tabla_destino).select("*").limit(1).execute()
            if res.data and len(res.data) > 0:
                columnas = list(res.data[0].keys())
            else:
                columnas = columnas_default.get(tabla_destino, [])

            df_plantilla = pd.DataFrame(columns=columnas)
            nombre_archivo = f"plantilla_{tabla_destino}.xlsx"

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_plantilla.to_excel(writer, index=False, sheet_name=tabla_destino)
            data_excel = buffer.getvalue()

            st.download_button(
                label=f"⬇️ Descargar plantilla_{tabla_destino}.xlsx ({len(columnas)} columnas)",
                data=data_excel,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_plantilla_config"
            )
            st.success(f"✅ Plantilla lista con las {len(columnas)} columnas detectadas de Supabase: `{', '.join(columnas)}`")
        except Exception as e:
            st.error(f"❌ Error al obtener columnas de Supabase: {e}")

    # 2. EXPORTAR BASE DE DATOS ACTUAL (TODAS LAS COLUMNAS DESDE SUPABASE)
    elif accion == "Exportar base de datos actual":
        st.info("📦 Obtén una copia de seguridad en Excel con todas las columnas y registros almacenados en la nube.")
        
        tabla_exportar = st.selectbox(
            "Selecciona la información a exportar:",
            ["productos", "clientes", "proveedores", "gastos", "ventas", "costos_fijos"],
            key="select_export_tabla_config"
        )

        if st.button("🚀 Generar Exportación Completa", key="btn_exportar_config"):
            try:
                res = supabase.table(tabla_exportar).select("*").execute()
                if res.data:
                    df_exp = pd.DataFrame(res.data)
                    if 'rut_empresa' in df_exp.columns and tenant_id:
                        df_exp = df_exp[df_exp['rut_empresa'].astype(str).str.contains(str(tenant_id), case=False, na=False)]

                    if not df_exp.empty:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_exp.to_excel(writer, index=False, sheet_name=tabla_exportar)
                        
                        st.download_button(
                            label=f"⬇️ Descargar {tabla_exportar}_actual.xlsx ({len(df_exp.columns)} columnas)",
                            data=buffer.getvalue(),
                            file_name=f"{tabla_exportar}_export.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="btn_download_export_config"
                        )
                        st.success(f"✅ Exportados {len(df_exp)} registros con sus {len(df_exp.columns)} columnas.")
                    else:
                        st.warning("⚠️ No hay registros pertenecientes a este negocio.")
                else:
                    st.warning("⚠️ No se encontraron datos registrados en esta tabla.")
            except Exception as e:
                st.error(f"❌ Ocurrió un error al exportar los datos: {e}")

    # 3. IMPORTAR BASE DE DATOS (A SUPABASE)
    elif accion == "Importar base de datos":
        st.warning("⚠️ Carga un archivo Excel para ingresar registros masivos directamente a Supabase.")

        tabla_destino = st.selectbox(
            "Selecciona la tabla destino para la carga masiva:",
            ["productos", "clientes", "proveedores", "gastos", "costos_fijos"],
            key="select_tabla_destino_import_config"
        )

        archivo_cargado = st.file_uploader(
            "Selecciona tu archivo Excel (.xlsx) o CSV desde tu equipo", 
            type=["xlsx", "csv"], 
            key="uploader_importar_bd_config"
        )

        if archivo_cargado is not None:
            try:
                if archivo_cargado.name.endswith(".csv"):
                    df_nuevo = pd.read_csv(archivo_cargado)
                else:
                    df_nuevo = pd.read_excel(archivo_cargado)

                st.write(f"📋 **Previsualización de datos a cargar ({len(df_nuevo.columns)} columnas):**")
                st.dataframe(df_nuevo.head())

                if st.button("🚀 Confirmar y Cargar a Supabase", key="btn_confirmar_import_config"):
                    if tenant_id and 'rut_empresa' not in df_nuevo.columns:
                        df_nuevo['rut_empresa'] = str(tenant_id)

                    registros = df_nuevo.where(pd.notnull(df_nuevo), None).to_dict(orient="records")

                    supabase.table(tabla_destino).upsert(registros).execute()
                    st.success(f"✅ ¡Base de datos cargada con éxito! Se procesaron {len(registros)} registros en '{tabla_destino}'.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Ocurrió un error al procesar la importación: {e}")


# ----------------- SECCIÓN VENTAS / POS RÁPIDO (CONECTADO A LA NUBE Y AISLADO / HÍBRIDO OFFLINE) -----------------
elif menu == "💰 Módulo de Ventas (POS)":

    import sqlite3
    import json
    import socket

    DB_LOCAL_NAME = "pos_local_cache.db"

    # --- 🛠️ FUNCIONES AUXILIARES PARA MODO OFFLINE (SQLITE + FALLBACK) ---
    def init_db_local_pos():
        """Inicializa las tablas locales en SQLite si no existen."""
        try:
            conn = sqlite3.connect(DB_LOCAL_NAME)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS productos_cache (
                    codigo TEXT PRIMARY KEY,
                    descripcion TEXT,
                    precio_venta REAL,
                    stock REAL,
                    es_exento TEXT,
                    impuesto_especifico TEXT,
                    bodega TEXT,
                    rut_empresa TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS ventas_pendientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT,
                    rut_empresa TEXT,
                    caja TEXT,
                    documento TEXT,
                    cliente TEXT,
                    monto_total REAL,
                    metodo_pago TEXT,
                    modo_emision TEXT,
                    items_json TEXT,
                    estado TEXT DEFAULT 'pendiente'
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error inicializando SQLite local: {e}")

    def hay_conexion_activa(host="8.8.8.8", port=53, timeout=1.0):
        """Verifica si hay conexión a internet disponible."""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except OSError:
            return False

    def respaldar_catalogo_local(df_prod, rut, bodega):
        """Guarda una copia del catálogo de productos en SQLite."""
        try:
            if df_prod is None or df_prod.empty: return
            conn = sqlite3.connect(DB_LOCAL_NAME)
            c = conn.cursor()
            for _, row in df_prod.iterrows():
                c.execute("""
                    INSERT OR REPLACE INTO productos_cache 
                    (codigo, descripcion, precio_venta, stock, es_exento, impuesto_especifico, bodega, rut_empresa)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get('codigo', '')),
                    str(row.get('descripcion', '')),
                    float(row.get('precio_venta', 0) or 0),
                    float(row.get('stock', 0) or 0),
                    str(row.get('es_exento', False)),
                    str(row.get('impuesto_especifico', '')),
                    str(bodega),
                    str(rut)
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error guardando catálogo en caché local: {e}")

    def cargar_catalogo_local(rut, bodega):
        """Carga los productos desde la base de datos SQLite local."""
        try:
            conn = sqlite3.connect(DB_LOCAL_NAME)
            df = pd.read_sql_query(
                "SELECT codigo, descripcion, precio_venta, stock, es_exento, impuesto_especifico FROM productos_cache WHERE rut_empresa = ? AND bodega = ?",
                conn, params=(str(rut), str(bodega))
            )
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    def guardar_venta_offline_db(rut, caja, documento, cliente, monto_total, metodo_pago, modo_emision, items):
        """Registra la venta en la cola de SQLite si no hay red."""
        try:
            conn = sqlite3.connect(DB_LOCAL_NAME)
            c = conn.cursor()
            c.execute("""
                INSERT INTO ventas_pendientes (fecha, rut_empresa, caja, documento, cliente, monto_total, metodo_pago, modo_emision, items_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(rut), str(caja), str(documento), str(cliente),
                float(monto_total), str(metodo_pago), str(modo_emision),
                json.dumps(items)
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error guardando venta offline: {e}")
            return False

    def sincronizar_ventas_pendientes_pos(supabase_client):
        """Sube a Supabase las ventas que se registraron estando sin internet."""
        try:
            if not hay_conexion_activa(): return 0
            conn = sqlite3.connect(DB_LOCAL_NAME)
            c = conn.cursor()
            c.execute("SELECT id, fecha, rut_empresa, caja, documento, cliente, monto_total, metodo_pago, modo_emision, items_json FROM ventas_pendientes WHERE estado = 'pendiente'")
            filas = c.fetchall()
            if not filas:
                conn.close()
                return 0
            
            sincronizadas = 0
            for f in filas:
                v_id, fecha, rut, caja, doc, cliente, monto, metodo, modo, items_str = f
                items = json.loads(items_str)
                
                batch = []
                folio_off = f"OFF-{v_id}"
                for item in items:
                    batch.append({
                        "folio": str(folio_off),
                        "rut_empresa": str(rut),
                        "fecha": fecha,
                        "caja": caja,
                        "documento": doc,
                        "cliente": cliente,
                        "codigo_producto": str(item.get("Código", "")),
                        "detalle": str(item.get("Descripción", "")),
                        "cantidad": float(item.get("Cantidad", 1)),
                        "monto": float(item.get("Subtotal", 0)),
                        "metodo_pago": metodo,
                        "neto": round(float(item.get("Subtotal", 0)) / 1.19, 2),
                        "iva": round(float(item.get("Subtotal", 0)) - (float(item.get("Subtotal", 0)) / 1.19), 2),
                        "impuesto_especifico": 0.0,
                        "modo_emision": modo
                    })
                
                try:
                    res = supabase_client.table("ventas").insert(batch).execute()
                    if res.data:
                        c.execute("UPDATE ventas_pendientes SET estado = 'sincronizado' WHERE id = ?", (v_id,))
                        sincronizadas += 1
                except Exception as ex:
                    print(f"Error subiendo venta {v_id}: {ex}")
            
            conn.commit()
            conn.close()
            return sincronizadas
        except Exception as e:
            print(f"Error en sincronización offline: {e}")
            return 0

    # --- 🟢 INICIALIZACIÓN DE LA CAJA LOCAL ---
    init_db_local_pos()
    modo_online = hay_conexion_activa()

    # Intento de auto-sincronización en segundo plano si hay red
    if modo_online:
        cant_sinc, _ = sincronizar_ventas_pendientes_pos(supabase), ""
        if cant_sinc > 0:
            st.toast(f"🔄 ¡Se sincronizaron {cant_sinc} ventas pendientes acumuladas offline!", icon="🎉")

    # --- 🛡️ 1. GUARDIA DE SESIÓN Y ATRIBUTOS BÁSICOS ---
    rut_actual = get_current_tenant()

    if not rut_actual:
        permisos = st.session_state.get("permisos_usuario", {})
        negocios = permisos.get("negocios", []) if isinstance(permisos, dict) else []
        
        if negocios:
            rut_actual = str(negocios[0]).replace(".", "").strip()
            st.session_state["negocio_seleccionado"] = rut_actual
        else:
            st.error("⚠️ No se ha detectado ningún negocio seleccionado en la sesión. Selecciona una empresa en el menú principal.")
            st.stop()

    caja_actual = param_caja if ('param_caja' in locals() and param_caja) else "Caja Principal"
    mostrar_encabezado_con_home(f"Terminal de Ventas - {caja_actual}")

    # Indicador visual del estado de la conexión
    if modo_online:
        st.caption("🟢 **Estado:** Sistema En Línea (Sincronizado con Supabase)")
    else:
        st.warning("🟠 **Estado:** Modo Offline / Contingencia (Operando con copia local SQLite)")

    # --- 🛡️ 2. INICIALIZACIÓN DEFENSIVA DE ESTADOS DE SESIÓN ---
    if "carrito_ventas" not in st.session_state: st.session_state.carrito_ventas = []
    if "ultimo_recibo" not in st.session_state: st.session_state.ultimo_recibo = None
    if "estado_pago" not in st.session_state: st.session_state.estado_pago = False
    if "input_scanner" not in st.session_state: st.session_state.input_scanner = ""
    if "df_nube_pos" not in st.session_state: st.session_state.df_nube_pos = pd.DataFrame()
    if "ultimo_prod_sel" not in st.session_state: st.session_state.ultimo_prod_sel = ""
    if "precio_actual_input" not in st.session_state: st.session_state.precio_actual_input = 0.0

    # --- 3. SELECTOR MULTI-BODEGA PARA EL POS ---
    rut_limpio = str(rut_actual).replace(".", "").strip()
    bodegas_pos = []

    if modo_online and rut_limpio:
        try:
            res_bod = supabase.table("bodegas").select("nombre").eq("rut_empresa", rut_limpio).execute()
            if res_bod.data:
                for r in res_bod.data:
                    nb = str(r.get("nombre", "")).strip(' "\'')
                    if nb and nb not in bodegas_pos:
                        bodegas_pos.append(nb)
        except Exception:
            pass

    if not bodegas_pos:
        bodegas_pos = ["Bodega Principal"]

    bodega_actual = st.selectbox(
        "🏢 Selecciona la Bodega / Sucursal de origen:",
        options=bodegas_pos,
        key="bodega_pos_seleccionada"
    )

    st.markdown("---")

    # --- 4. CARGA PREVIA DEL INVENTARIO (CON FALLBACK AUTOMÁTICO A SQLITE) ---
    df_nube = pd.DataFrame()
    if modo_online:
        try:
            res_pos = supabase.table("productos").select("codigo, descripcion, precio_venta, stock, es_exento, impuesto_especifico").eq("rut_empresa", str(rut_actual)).eq("bodega", bodega_actual).limit(10000).execute()
            if res_pos.data:
                df_nube = pd.DataFrame(res_pos.data)
                st.session_state.df_nube_pos = df_nube
                # Respaldar en memoria local por si se corta el internet más adelante
                respaldar_catalogo_local(df_nube, rut_actual, bodega_actual)
        except Exception as e:
            st.warning(f"⚠️ Red inestable. Cambiando a memoria local: {e}")
            df_nube = cargar_catalogo_local(rut_actual, bodega_actual)
            st.session_state.df_nube_pos = df_nube
    else:
        df_nube = cargar_catalogo_local(rut_actual, bodega_actual)
        st.session_state.df_nube_pos = df_nube

    # --- 5. MÓDULO OPTIMIZADO PARA LECTOR DE CÓDIGO DE BARRAS ---
    def procesar_escaneo_pos():
        codigo_leido = st.session_state.get("input_scanner", "").strip()
        if codigo_leido:
            df_a_buscar = df_nube if not df_nube.empty else st.session_state.get("df_nube_pos", pd.DataFrame())
            if df_a_buscar is not None and not df_a_buscar.empty:
                col_c = 'codigo' if 'codigo' in df_a_buscar.columns else 'Código'
                col_d = 'descripcion' if 'descripcion' in df_a_buscar.columns else ('Descripción' if 'Descripción' in df_a_buscar.columns else 'Nombre')
                col_p = 'precio_venta' if 'precio_venta' in df_a_buscar.columns else ('Precio Venta' if 'Precio Venta' in df_a_buscar.columns else 'Precio')
                
                df_match = df_a_buscar[df_a_buscar[col_c].astype(str).str.strip() == codigo_leido]
                if not df_match.empty:
                    prod = df_match.iloc[0]
                    codigo_prod = str(prod[col_c])
                    nombre_prod = str(prod.get(col_d, 'Sin Nombre'))
                    precio_prod = float(prod.get(col_p, 0))
                    
                    encontrado_en_carrito = False
                    for item in st.session_state.carrito_ventas:
                        if str(item["Código"]) == codigo_prod:
                            item["Cantidad"] += 1.0
                            item["Subtotal"] = item["Cantidad"] * item["Precio Unitario"]
                            encontrado_en_carrito = True
                            break
                    
                    if not encontrado_en_carrito:
                        st.session_state.carrito_ventas.append({
                            "Código": codigo_prod,
                            "Descripción": nombre_prod,
                            "Cantidad": 1.0,
                            "Precio Unitario": precio_prod,
                            "Subtotal": precio_prod,
                            "Es Exento": str(prod.get("es_exento", False)).lower() in ["true", "si", "sí", "1"],
                            "Tasa ILA": 0.0,
                            "es_guia_previa": False
                        })
                    st.success(f"✔️ Agregado: {nombre_prod}")
                else:
                    st.warning(f"⚠️ No se encontró ningún producto con el código: {codigo_leido}")
            else:
                st.error("⚠️ La base de datos de productos no está cargada en la memoria local.")
        st.session_state.input_scanner = ""

    # --- 6. CABECERA Y SELECCIÓN DE DOCUMENTO ---
    col_doc1, col_doc2, col_doc3 = st.columns(3)
    with col_doc1:
        tipo_documento = st.selectbox("📄 Selecciona el documento:", ["Boleta Electrónica", "Factura Electrónica", "Guía de Despacho", "Nota de Venta Interna"])
    with col_doc2:
        fecha_emision_venta = st.date_input("📅 Fecha de Emisión del Documento")
    with col_doc3:
        modo_operacion = st.radio(
            "⚙️ Tipo de Emisión:",
            ["Control Interno (Libre)", "Oficial (SII)"],
            horizontal=True,
            key="radio_modo_emision"
        )
    
    modo_str = "INTERNO" if "Interno" in modo_operacion else "OFICIAL"

    # --- 7. LÓGICA: FACTURAR DESDE UNA GUÍA PREVIA ---
    if tipo_documento == "Factura Electrónica":
        viene_de_guia = st.checkbox("🔗 Facturar desde una Guía de Despacho previa")
        if viene_de_guia:
            col_g1, col_g2 = st.columns([3, 1])
            with col_g1:
                folio_guia_a_facturar = st.text_input("🔎 Ingresa el Folio de la Guía (Ej: 1 o FOLIO_1):")
            with col_g2:
                st.write("")
                if st.button("📥 Cargar Guía", use_container_width=True):
                    if folio_guia_a_facturar and modo_online:
                        try:
                            res_guia = supabase.table("ventas").select("*").eq("rut_empresa", str(rut_actual)).eq("folio", folio_guia_a_facturar.strip()).execute()
                            if res_guia.data:
                                st.session_state.carrito_ventas = []
                                st.session_state.folio_guia_origen = folio_guia_a_facturar.strip()
                                cliente_de_guia = res_guia.data[0].get("cliente", "")
                                if cliente_de_guia and cliente_de_guia != "Cliente General":
                                    st.session_state.cliente_preseleccionado = cliente_de_guia

                                for item in res_guia.data:
                                    cant = float(item.get("cantidad", 1))
                                    monto_total = float(item.get("monto", 0))
                                    precio_unitario = monto_total / cant if cant > 0 else 0
                                    
                                    st.session_state.carrito_ventas.append({
                                        "Código": item.get("codigo_producto", ""),
                                        "Descripción": item.get("detalle", "Producto"),
                                        "Cantidad": cant,
                                        "Precio Unitario": precio_unitario,
                                        "Subtotal": monto_total,
                                        "es_guia_previa": True 
                                    })
                                st.success(f"✅ Guía {folio_guia_a_facturar} cargada exitosamente.")
                            else:
                                st.warning("⚠️ No se encontró ninguna guía con ese folio.")
                        except Exception as e:
                            st.error(f"❌ Error al buscar la guía: {e}")
                    elif not modo_online:
                        st.warning("⚠️ La búsqueda de guías previas requiere conexión activa a la nube.")
                    else:
                        st.warning("⚠️ Ingresa un folio válido.")
    st.markdown("---")

    modo_inventario = st.radio(
        "📦 Modo de trabajo del POS:",
        ["Control Estricto de Stock (Alerta si no hay inventario)", "Venta Libre / Solo Base de Datos"],
        horizontal=True,
        key="radio_modo_inventario"
    )
    controlar_stock = "Estricto" in modo_inventario

    # --- 8. SELECCIÓN DE CLIENTES ---
    cliente_nombre, cliente_rut = "", ""
    df_clientes_pos = pd.DataFrame()
    if modo_online:
        try:
            res_clientes = supabase.table("clientes").select("rut, nombre").eq("id_negocio", str(rut_actual)).execute()
            df_clientes_pos = pd.DataFrame(res_clientes.data) if res_clientes.data else pd.DataFrame()
        except Exception:
            pass

    c_nombre_def = st.session_state.get("cliente_preseleccionado", "")
    c_rut_def = ""
    
    if c_nombre_def and not df_clientes_pos.empty and "nombre" in df_clientes_pos.columns:
        match_rut = df_clientes_pos[df_clientes_pos["nombre"] == c_nombre_def]
        if not match_rut.empty:
            c_rut_def = str(match_rut.iloc[0]["rut"])

    lista_clientes = []
    if not df_clientes_pos.empty and "nombre" in df_clientes_pos.columns:
        df_clientes_pos["etiqueta"] = df_clientes_pos["nombre"].astype(str) + " (" + df_clientes_pos["rut"].astype(str) + ")"
        lista_clientes = df_clientes_pos["etiqueta"].tolist()
        
    lista_clientes.insert(0, "-- Selecciona un cliente (Opcional / Requerido para Crédito) --")
    
    idx_cliente = 0
    if c_nombre_def:
        for i, etiqueta in enumerate(lista_clientes):
            if etiqueta.startswith(c_nombre_def + " ("):
                idx_cliente = i
                break

    cliente_elegido = st.selectbox("👤 Selecciona o asigna un cliente:", lista_clientes, index=idx_cliente)
  
    if cliente_elegido and cliente_elegido != "-- Selecciona un cliente (Opcional / Requerido para Crédito) --" and " (" in cliente_elegido:
        cliente_nombre = cliente_elegido.split(" (")[0]
        cliente_rut = cliente_elegido.split(" (")[1].replace(")", "")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1: cliente_nombre = st.text_input("Razón Social / Nombre del Cliente", value=c_nombre_def, placeholder="Ej: Juan Pérez")
        with col_f2: cliente_rut = st.text_input("RUT / Identificación Tributaria", value=c_rut_def, placeholder="Ej: 12.345.678-9")

    # =========================================================================
    # --- VISTA 1: PANTALLA DE ÉXITO ---
    # =========================================================================
    if st.session_state.ultimo_recibo is not None:
        st.success("🎉 ¡Transacción completada y procesada con éxito!")

        # 🟢 NUEVO: Encabezado visual (Emisor + Receptor)
        datos_emisor = obtener_datos_emisor(supabase, rut_actual)
        datos_receptor = {
            "nombre": cliente_nombre if cliente_nombre else "CLIENTE CONTADO",
            "rut": cliente_rut if cliente_rut else "66666666-6",
            "giro": "Particular / Consumidor Final",
            "direccion": "N/A",
            "comuna": "Santiago"
        }
        generar_encabezado_documento(tipo_documento, st.session_state.get("ultimo_folio", "N/A"), datos_emisor, datos_receptor)

        st.markdown(f'<div class="ticket-box">{st.session_state.ultimo_recibo}</div>', unsafe_allow_html=True)
      
        if 'items_recibo_actual' not in st.session_state or st.session_state.items_recibo_actual is None:
            st.session_state.items_recibo_actual = st.session_state.carrito_ventas.copy()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if tipo_documento in ["Guía de Despacho", "Factura Electrónica"]:
                items_a_imprimir = st.session_state.get('items_recibo_actual', st.session_state.carrito_ventas)
                try:
                    pdf_bytes = generar_guia_pdf(cliente_nombre, cliente_rut, items_a_imprimir, tipo_documento, fecha_emision_venta)
                    st.download_button(f"📥 Descargar {tipo_documento} (PDF)", data=bytes(pdf_bytes), file_name=f"{tipo_documento.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"⚠️ Error al generar el PDF: {e}")
            else:
                st.download_button("📥 Descargar Recibo Térmico", data=st.session_state.ultimo_recibo, file_name="Comprobante.txt", mime="text/plain", use_container_width=True)
      
        with col_r2:
            if st.button("➕ Nueva Venta", use_container_width=True, type="primary"):
                st.session_state.ultimo_recibo = None
                st.session_state.estado_pago = False
                st.session_state.items_recibo_actual = None
                st.session_state.carrito_ventas = []
                st.session_state.pop("cliente_preseleccionado", None)
                st.session_state.pop("folio_guia_origen", None) 
                st.rerun()
    # =========================================================================
    # --- VISTA 2: PANTALLA DE PAGO Y CONFIRMACIÓN ---
    # =========================================================================
    elif st.session_state.estado_pago:
        st.markdown("### 💳 2. Formas de Pago")
        if len(st.session_state.carrito_ventas) > 0:
            df_temp = pd.DataFrame(st.session_state.carrito_ventas)
            total_venta = df_temp["Subtotal"].sum()
            st.info(f"💰 **Total a Pagar: ${total_venta:,.2f}**")
            
            opciones_pago = list(st.session_state.get("formas_pago_erp", ["Efectivo"]))
            for extra in ["Crédito", "Consignación", "Transferencia"]:
                if extra not in opciones_pago:
                    opciones_pago.append(extra)
            forma_pago = st.selectbox("Selecciona la Forma de Pago:", options=opciones_pago)
       
            efectivo_recibido, cambio = total_venta, 0.0
            dias_credito = 0  
            
            if forma_pago == "Efectivo":
                efectivo_recibido = st.number_input("💵 Dinero Recibido ($):", min_value=0.0, value=float(total_venta), step=100.0)
                if efectivo_recibido >= total_venta:
                    cambio = efectivo_recibido - total_venta
                    st.success(f"🟢 **Vuelto: ${cambio:,.2f}**")
                else:
                    st.error("🔴 Monto insuficiente.")
            elif forma_pago in ["Crédito", "Consignación"]:
                st.warning(f"⚖️ Esta venta en {forma_pago} se enviará al módulo de Cuentas por Cobrar.")
                dias_credito = st.number_input(f"⏳ Días de Plazo para pagar ({forma_pago}):", min_value=1, value=30, step=1)
                fecha_estimada = datetime.now() + timedelta(days=dias_credito)
                st.info(f"📅 Fecha de vencimiento calculada: **{fecha_estimada.strftime('%d/%m/%Y')}**")

            st.divider()
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                if st.button("⬅️ Volver al Carrito", use_container_width=True):
                    st.session_state.estado_pago = False
                    st.rerun()
            with col_p2:
                if st.button("✅ Confirmar Pago y Generar", use_container_width=True, type="primary"):
                    if forma_pago == "Efectivo" and efectivo_recibido < total_venta:
                        st.warning("⚠️ Monto insuficiente para procesar la venta.")
                    else:
                        fecha_hora_actual = datetime.now()
                        es_offline_para_cobro = not hay_conexion_activa()
                        
                        # --- OBTENER FOLIO ---
                        if not es_offline_para_cobro:
                            try:
                                res_f = supabase.table("folios_empresa").select("ultimo_folio_usado").eq("rut_empresa", str(rut_actual)).eq("tipo_documento", tipo_documento).eq("modo", modo_str).execute()
                                if res_f.data and len(res_f.data) > 0:
                                    numero_folio_actual = int(res_f.data[0]["ultimo_folio_usado"]) + 1
                                    supabase.table("folios_empresa").update({"ultimo_folio_usado": numero_folio_actual}).eq("rut_empresa", str(rut_actual)).eq("tipo_documento", tipo_documento).eq("modo", modo_str).execute()
                                else:
                                    numero_folio_actual = 1
                                    supabase.table("folios_empresa").insert({
                                        "rut_empresa": str(rut_actual),
                                        "tipo_documento": tipo_documento,
                                        "modo": modo_str,
                                        "ultimo_folio_usado": numero_folio_actual
                                    }).execute()
                            except Exception:
                                numero_folio_actual = int(datetime.now().strftime("%H%M%S"))
                        else:
                            numero_folio_actual = int(datetime.now().strftime("%H%M%S"))

                        transaccion_id_actual = str(numero_folio_actual)
                        lineas_productos = ""
                        
                        folio_origen = st.session_state.get("folio_guia_origen")
                        if folio_origen and tipo_documento == "Factura Electrónica" and not es_offline_para_cobro:
                            try:
                                supabase.table("ventas").delete().eq("rut_empresa", str(rut_actual)).eq("folio", folio_origen).execute()
                                supabase.table("cuentas_por_cobrar").delete().eq("rut_empresa", str(rut_actual)).eq("folio_venta", folio_origen).execute()
                            except Exception:
                                pass 
                        
                        cfg_actual = st.session_state.get("config_ticket", {})
                        nombre_empresa_sesion = str(st.session_state.get("nombre_empresa", "")).upper()
                        tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_sesion or str(rut_actual) == "219449970012" else 19.0
                        iva_porcentaje = float(cfg_actual.get("iva_tasa", tasa_defecto))
                        tasa_iva_global = iva_porcentaje / 100.0
                        
                        total_neto_ticket, total_iva_ticket, total_ila_ticket = 0.0, 0.0, 0.0
                        registros_ventas_batch = []

                        for item in st.session_state.carrito_ventas:
                            lineas_productos += f"- {item['Descripción']} (x{int(item['Cantidad'])}) ... ${item['Subtotal']:,.2f}\n"
                            
                            # Intentar descontar stock si estamos online
                            if not es_offline_para_cobro:
                                try:
                                    if not item.get("es_guia_previa", False):
                                        codigo_vendido = str(item["Código"])
                                        cantidad_vendida = float(item["Cantidad"])

                                        res_receta_pos = supabase.table("recetas").select("*").eq("rut_empresa", str(rut_actual)).eq("codigo_producto_final", codigo_vendido).execute()
                                        
                                        if res_receta_pos.data:
                                            for componente in res_receta_pos.data:
                                                cod_componente = str(componente["codigo_ingrediente"])
                                                cant_por_pack = float(componente["cantidad_usada"])
                                                cantidad_total_a_descontar = cant_por_pack * cantidad_vendida

                                                supabase.rpc(
                                                    'actualizar_stock_atomico',
                                                    {
                                                        'p_rut_empresa': str(rut_actual),
                                                        'p_codigo': cod_componente,
                                                        'p_bodega': str(bodega_actual),
                                                        'p_cantidad': cantidad_total_a_descontar,
                                                        'p_operacion': 'VENTA'
                                                    }
                                                ).execute()
                                        else:
                                            supabase.rpc(
                                                'actualizar_stock_atomico',
                                                {
                                                    'p_rut_empresa': str(rut_actual),
                                                    'p_codigo': codigo_vendido,
                                                    'p_bodega': str(bodega_actual),
                                                    'p_cantidad': cantidad_vendida,
                                                    'p_operacion': 'VENTA'
                                                }
                                            ).execute()
                                except Exception as e:
                                    print(f"Error descontando stock en POS: {e}")

                            tasa_iva_item = 0.0 if item.get("Es Exento", False) else tasa_iva_global
                            tasa_ila_item = item.get("Tasa ILA", 0.0)
                            
                            monto_bruto = float(item["Subtotal"])
                            neto_calculado = monto_bruto / (1.0 + tasa_iva_item + tasa_ila_item)
                            iva_calculado = neto_calculado * tasa_iva_item
                            ila_calculado = neto_calculado * tasa_ila_item

                            total_neto_ticket += neto_calculado
                            total_iva_ticket += iva_calculado
                            total_ila_ticket += ila_calculado

                            registros_ventas_batch.append({
                                "folio": transaccion_id_actual,
                                "rut_empresa": str(rut_actual),
                                "fecha": fecha_emision_venta.strftime("%Y-%m-%d") + fecha_hora_actual.strftime(" %H:%M:%S"),
                                "caja": caja_actual, 
                                "documento": tipo_documento,
                                "cliente": cliente_nombre if cliente_nombre else "Cliente General",
                                "codigo_producto": str(item["Código"]), 
                                "detalle": str(item["Descripción"]),
                                "cantidad": float(item["Cantidad"]), 
                                "monto": monto_bruto,
                                "metodo_pago": forma_pago,
                                "neto": round(neto_calculado, 2),
                                "iva": round(iva_calculado, 2),
                                "impuesto_especifico": round(ila_calculado, 2),
                                "modo_emision": modo_str
                            })

                        # --- REGISTRO DE VENTA (NUBE VS SQLITE OFFLINE) ---
                        if not es_offline_para_cobro:
                            try:
                                res_venta = supabase.table("ventas").insert(registros_ventas_batch).execute()
                                if not res_venta.data:
                                    guardar_venta_offline_db(rut_actual, caja_actual, tipo_documento, cliente_nombre, total_venta, forma_pago, modo_str, st.session_state.carrito_ventas)
                                    st.toast("⚠️ Error de envío a la nube. Venta respaldada localmente en la caja.", icon="💾")
                            except Exception as e:
                                guardar_venta_offline_db(rut_actual, caja_actual, tipo_documento, cliente_nombre, total_venta, forma_pago, modo_str, st.session_state.carrito_ventas)
                                st.toast("⚠️ Sin conexión con la nube. Venta respaldada localmente.", icon="💾")
                        else:
                            # Guardado 100% offline en SQLite
                            guardar_venta_offline_db(rut_actual, caja_actual, tipo_documento, cliente_nombre, total_venta, forma_pago, modo_str, st.session_state.carrito_ventas)
                            st.toast("✅ Venta registrada en modo Offline. Se subirá automáticamente al recuperar internet.", icon="💾")

                        if forma_pago in ["Crédito", "Consignación"] and not es_offline_para_cobro:
                            fecha_vencimiento_str = (fecha_hora_actual + timedelta(days=dias_credito)).strftime("%Y-%m-%d")
                            registro_cxc = {
                                "rut_empresa": str(rut_actual),
                                "folio_venta": str(transaccion_id_actual),
                                "cliente": cliente_nombre.strip() if cliente_nombre and cliente_nombre.strip() else "Cliente General",
                                "rut_cliente": cliente_rut.strip() if cliente_rut and cliente_rut.strip() else "Sin RUT",
                                "monto_total": float(total_venta),
                                "saldo_pendiente": float(total_venta),
                                "fecha_emision": fecha_emision_venta.strftime("%Y-%m-%d"),
                                "fecha_vencimiento": fecha_vencimiento_str,
                                "estado": "Pendiente"
                            }
                            try:
                                supabase.table("cuentas_por_cobrar").insert(registro_cxc).execute()
                            except Exception as e:
                                print(f"Error al registrar en Cuentas por Cobrar: {e}")

                        st.session_state.items_recibo_actual = st.session_state.carrito_ventas.copy()
                        linea_ila = f"IMP. ESPECÍFICO: ${total_ila_ticket:,.2f}\n" if total_ila_ticket > 0 else ""
                        
                        info_pago = ""
                        if forma_pago == 'Efectivo':
                            info_pago = f"RECIBIDO: ${efectivo_recibido:,.2f}\nVUELTO: ${cambio:,.2f}"
                        elif forma_pago in ['Crédito', 'Consignación']:
                            info_pago = f"CONDICIÓN: {forma_pago.upper()} (A {dias_credito} DÍAS)\nVENCE: {(fecha_hora_actual + timedelta(days=dias_credito)).strftime('%d/%m/%Y')}"
                        
                        texto_recibo = f"""
========================================
       {cfg_actual.get('nombre_empresa', 'MI EMPRESA')}
       RUT: {cfg_actual.get('rut_empresa', '00.000.000-0')}
       {cfg_actual.get('direccion', 'Santiago')}
========================================
DOCUMENTO: {tipo_documento.upper()} [{modo_operacion.upper()}]
FOLIO N°: {numero_folio_actual}
FECHA EMISIÓN: {fecha_emision_venta.strftime('%d/%m/%Y')}
TERMINAL: {caja_actual}
----------------------------------------
{('CLIENTE: ' + cliente_nombre + (' | RUT: ' + cliente_rut if cliente_rut else '') + '\n----------------------------------------\n') if cliente_nombre else ''}DETALLE:
{lineas_productos}----------------------------------------
SUBTOTAL NETO: ${total_neto_ticket:,.2f}
IVA ({iva_porcentaje:g}%): ${total_iva_ticket:,.2f}
{linea_ila}----------------------------------------
TOTAL GENERAL: ${total_venta:,.2f}
PAGO: {forma_pago.upper()}
{info_pago}
========================================
{cfg_actual.get('pie_pagina', 'Gracias por su preferencia')}
========================================"""

                        st.session_state.ultimo_recibo = texto_recibo
                        st.session_state.ultimo_folio = numero_folio_actual
                        st.session_state.estado_pago = False
                        st.rerun()

    # =========================================================================
    # --- VISTA 3: PANTALLA PRINCIPAL (BUSCADOR Y CARRITO) ---
    # =========================================================================
    else:
        if not df_nube.empty:
            col_cod = 'codigo'
            col_desc = 'descripcion'
            col_precio = 'precio_venta'
            col_stock = 'stock'

            metodo_lectura = st.radio("Método de entrada de código:", ["⌨️ Digitar / Lector Físico", "📷 Usar Cámara del Celular"], horizontal=True, key="radio_metodo_pos")

            if metodo_lectura == "📷 Usar Cámara del Celular":
                st.markdown("Apunta la cámara al código de barras y captura la foto:")
                foto_capturada = st.camera_input("Capturar código de barras", key="cam_pos")
            else:
                st.text_input(
                    "🔍 Escanea el código de barras (El cursor debe estar aquí):", 
                    key="input_scanner", 
                    on_change=procesar_escaneo_pos,
                    help="El lector escribirá aquí y buscará automáticamente el producto al presionar Enter."
                )

            opciones_productos = ["-- Selecciona o busca un producto --"] + [f"{row[col_cod]} - {row[col_desc]}" for idx, row in df_nube.iterrows()]
            prod_sugerido_pos_idx = 0

            producto_seleccionado = st.selectbox(
                "O selecciona manualmente el producto:",
                options=opciones_productos,
                index=prod_sugerido_pos_idx,
                key="selectbox_producto_venta"
            )
        
            if producto_seleccionado != st.session_state.ultimo_prod_sel:
                st.session_state.ultimo_prod_sel = producto_seleccionado
                if producto_seleccionado != "-- Selecciona o busca un producto --":
                    c_buscado = producto_seleccionado.split(" - ")[0]
                    match_row = df_nube[df_nube[col_cod].astype(str) == str(c_buscado)]
                    if not match_row.empty:
                        st.session_state.precio_actual_input = float(match_row.iloc[0][col_precio] or 0.0)
                else:
                    st.session_state.precio_actual_input = 0.0

            with st.form("form_agregar_item"):
                col_cant, col_precio_input = st.columns(2)
                with col_cant:
                    cantidad_vendida = st.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0, format="%.2f")
                with col_precio_input:
                    precio_venta = st.number_input("Precio Unitario ($)", min_value=0.0, step=1.0, value=float(st.session_state.precio_actual_input))

                btn_agregar = st.form_submit_button("➕ Agregar al Carrito de Venta")

                if btn_agregar:
                    if producto_seleccionado == "-- Selecciona o busca un producto --":
                        st.warning("⚠️ Selecciona un producto válido.")
                    else:
                        c_buscado = producto_seleccionado.split(" - ")[0]
                        match_row = df_nube[df_nube[col_cod].astype(str) == str(c_buscado)]
                        
                        stock_disponible = 0.0
                        es_exento = False
                        tasa_ila_item = 0.0
                        
                        if not match_row.empty:
                            fila = match_row.iloc[0]
                            stock_disponible = float(fila[col_stock] or 0.0)
                            es_exento = fila.get("es_exento", False) in [True, "Si", "si", "Sí", "sí", "1"]
                            imp_esp_str = str(fila.get("impuesto_especifico", "")).upper()
                            if "10" in imp_esp_str: tasa_ila_item = 0.10
                            elif "18" in imp_esp_str: tasa_ila_item = 0.18
                            elif "20.5" in imp_esp_str or "20,5" in imp_esp_str: tasa_ila_item = 0.205
                            elif "31.5" in imp_esp_str or "31,5" in imp_esp_str: tasa_ila_item = 0.315
                        
                        unidades_en_carrito = sum(item["Cantidad"] for item in st.session_state.carrito_ventas if item["Código"] == c_buscado)
                        total_intentado = unidades_en_carrito + float(cantidad_vendida)

                        if controlar_stock and total_intentado > stock_disponible:
                            st.error(f"🚨 **¡Inventario Insuficiente en {bodega_actual}!** Stock disponible: {stock_disponible:,.2f}")
                        else:
                            st.session_state.carrito_ventas.append({
                                "Código": c_buscado,
                                "Descripción": producto_seleccionado.split(" - ")[1],
                                "Cantidad": float(cantidad_vendida),
                                "Precio Unitario": float(precio_venta),
                                "Subtotal": float(cantidad_vendida) * float(precio_venta),
                                "Es Exento": es_exento,
                                "Tasa ILA": tasa_ila_item,
                                "es_guia_previa": False
                            })
                            st.rerun()
        else:
            st.info(f"ℹ️ Aún no hay productos registrados en {bodega_actual}.")

        st.divider()
        st.markdown("### 🛒 Carrito de Venta Actual:")
        if len(st.session_state.carrito_ventas) > 0:
            total_general, indices_a_eliminar = 0.0, []
            col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([1.2, 2.5, 1.2, 1.5, 1.5, 0.8])
            col_h1.markdown("**Código**"); col_h2.markdown("**Descripción**"); col_h3.markdown("**Cantidad**"); col_h4.markdown("**Precio**"); col_h5.markdown("**Subtotal**"); col_h6.markdown("**Acción**")
            st.divider()

            for i, item in enumerate(st.session_state.carrito_ventas):
                col_c1, col_c2, col_c3, col_c4, col_c5, col_c6 = st.columns([1.2, 2.5, 1.2, 1.5, 1.5, 0.8])
                with col_c1: st.text(item["Código"])
                desc_texto = item["Descripción"] + (" (📄 de Guía)" if item.get("es_guia_previa") else "")
                with col_c2: st.text(desc_texto)
                with col_c3:
                    nc = st.number_input("Cant", min_value=0.01, step=0.1, value=float(item["Cantidad"]), format="%.2f", key=f"cant_{i}", label_visibility="collapsed")
                    st.session_state.carrito_ventas[i]["Cantidad"] = nc
                    st.session_state.carrito_ventas[i]["Subtotal"] = nc * st.session_state.carrito_ventas[i]["Precio Unitario"]
                with col_c4:
                    np = st.number_input("Prec", min_value=0.0, step=1.0, value=float(item["Precio Unitario"]), key=f"prec_{i}", label_visibility="collapsed")
                    st.session_state.carrito_ventas[i]["Precio Unitario"] = np
                    st.session_state.carrito_ventas[i]["Subtotal"] = st.session_state.carrito_ventas[i]["Cantidad"] * np
                with col_c5:
                    sub = st.session_state.carrito_ventas[i]["Subtotal"]
                    st.text(f"${sub:,.2f}")
                    total_general += sub
                with col_c6:
                    if st.button("🗑️", key=f"del_{i}"): indices_a_eliminar.append(i)

            if indices_a_eliminar:
                for idx in sorted(indices_a_eliminar, reverse=True): st.session_state.carrito_ventas.pop(idx)
                st.rerun()

            st.divider()
            st.markdown(f"### 💰 **Total a Pagar: ${total_general:,.2f}**")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("🗑️ Vaciar Carrito", use_container_width=True):
                    st.session_state.carrito_ventas = []
                    st.session_state.pop("cliente_preseleccionado", None)
                    st.session_state.pop("folio_guia_origen", None) 
                    st.rerun()
            with col_b2:
                if st.button("[F12] 💳 Cobrar", use_container_width=True, key="btn_cobrar_principal") or st.session_state.get('ejecutar_cobro', False):
                    st.session_state.ejecutar_cobro = False
                    st.session_state.estado_pago = True
                    st.rerun()
        else:
            st.info("ℹ️ Carrito vacío.")

        components.html("""
        <script>
        const doc = window.parent.document;
        doc.addEventListener('keydown', function(e) {
            if (e.key === 'F12') {
                e.preventDefault();
                doc.querySelectorAll('button').forEach(btn => { if (btn.innerText.includes('Cobrar')) btn.click(); });
            } else if (e.key === 'Enter') {
                const activeEl = doc.activeElement;
                if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.getAttribute('role') === 'combobox')) {
                    doc.querySelectorAll('button').forEach(btn => { if (btn.innerText.includes('Agregar al Carrito de Venta')) btn.click(); });
                }
            }
        });
        </script>
        """, height=0)

elif menu == "📑 Cuentas por Cobrar":
    mostrar_modulo_cuentas_por_cobrar(ruta_negocio)

elif menu == "🏦 Conciliación y Retiros Seguros": 
    mostrar_modulo_conciliacion_retiros(ruta_negocio)

elif menu == "📈 Reportes y Analítica":
    mostrar_modulo_reportes_avanzados(negocio_seleccionado)

elif menu == "🔑 Control Maestro de Licencias":
    mostrar_encabezado_con_home("🔑 Control Maestro de Licencias y Ciclos Fijos")
    st.info("ℹ️ Panel de administración exclusivo para ver el estado de todos los clientes y modificar sus fechas de vigencia.")

    try:
        res_lic = supabase.table("empresas").select("*").execute()
        lista_empresas_db = res_lic.data if res_lic and res_lic.data else []
    except Exception as e:
        lista_empresas_db = []
        st.error(f"⚠️ Error al conectar con Supabase: {e}")

    if lista_empresas_db:
        hoy_actual = date.today()
        tabla_resumen = []

        for emp in lista_empresas_db:
            rut_cli = str(emp.get("rut_empresa", "N/A"))
            nombre_cli = str(emp.get("empresa_nombre", "Sin Nombre"))
            f_exp_str = str(emp.get("fecha_expiracion", "2026-12-31"))
            
            try:
                dias_restantes = (pd.to_datetime(f_exp_str).date() - hoy_actual).days
            except Exception:
                dias_restantes = 999

            if dias_restantes > 5:
                estado_txt = "🟢 Activa"
            elif 0 <= dias_restantes <= 5:
                estado_txt = "🟡 En Gracia"
            else:
                estado_txt = "🔴 Expirada / Suspendida"

            tabla_resumen.append({
                "RUT (Usuario)": rut_cli,
                "Empresa": nombre_cli,
                "Vencimiento": f_exp_str,
                "Días Restantes": dias_restantes,
                "Estado": estado_txt
            })

        st.dataframe(pd.DataFrame(tabla_resumen), use_container_width=True)

        st.divider()
        st.markdown("### ✏️ Modificar Fechas de Vigencia y Ciclo Fijo")
        
        nombres_clientes_dict = {emp.get("rut_empresa"): f"{emp.get('empresa_nombre')} (RUT: {emp.get('rut_empresa')})" for emp in lista_empresas_db}
        rut_a_modificar = st.selectbox("Selecciona la Empresa a Gestionar:", options=list(nombres_clientes_dict.keys()), format_func=lambda x: nombres_clientes_dict[x])
        
        cliente_sel_data = next((emp for emp in lista_empresas_db if emp.get("rut_empresa") == rut_a_modificar), None)
        
        if cliente_sel_data:
            f_actual_exp_str = cliente_sel_data.get("fecha_expiracion")
            
            try:
                if f_actual_exp_str and str(f_actual_exp_str).strip() not in ["None", "NaT", "nan", ""]:
                    f_default_date = pd.to_datetime(str(f_actual_exp_str)).date()
                else:
                    f_default_date = hoy_actual
            except Exception:
                f_default_date = hoy_actual

            with st.form(f"form_mod_fechas_principal_{rut_a_modificar}"):
                st.write(f"📌 **Editando a:** {cliente_sel_data.get('empresa_nombre')}")
                
                nueva_fecha_fin = st.date_input("Fecha de Finalización del Periodo", value=f_default_date)
                
                estado_licencia = cliente_sel_data.get("licencia_activa")
                estado_licencia = True if estado_licencia is None else bool(estado_licencia)
                
                activar_licencia_check = st.checkbox("Licencia Activa (Desmarcar para suspensión total)", value=estado_licencia)

                if st.form_submit_button("💾 Guardar Nueva Vigencia en Supabase", type="primary"):
                    try:
                        supabase.table("empresas").update({
                            "fecha_expiracion": str(nueva_fecha_fin),
                            "licencia_activa": activar_licencia_check
                        }).eq("rut_empresa", rut_a_modificar).execute()

                        st.success(f"✅ ¡Vigencia actualizada correctamente! Nuevo vencimiento: {nueva_fecha_fin}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar en Supabase: {e}")
    else:
        st.warning("⚠️ No se encontraron registros de empresas en Supabase.")

elif menu == "🔄 Notas de Crédito" or st.session_state.get("modulo_activo") == "nc":
    mostrar_modulo_notas_credito(ruta_negocio)

# --- MÓDULO DE PRODUCCIÓN Y RECETAS ---
elif menu == "🍔 Producción y Recetas":
    # Llamamos a la función que importaste al inicio
    mostrar_modulo_produccion()

elif menu == "🚚 Logística y Distribución (Preventa)":
    mostrar_modulo_distribucion()
import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta, date
import streamlit.components.v1 as components
import sys
import plotly.express as px
from data_manager import guardar_nuevo_cliente, cargar_maestro_clientes
from calendario_pagos import mostrar_modulo_calendario_pagos
from compras_cpp import mostrar_modulo_compras
from supabase import create_client, Client
from fpdf import FPDF
from PIL import Image
from cuadratura import mostrar_modulo_cuadratura_diaria
from historial_ventas import mostrar_modulo_historial_ventas
from notas_credito import mostrar_modulo_notas_credito
from cuentas_por_pagar import mostrar_modulo_cuentas_por_pagar
from produccion_recetas import mostrar_modulo_produccion
# Ocultar el menú predeterminado y la marca de agua de Streamlit
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

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

# ⚙️ 1. CONFIGURACIÓN DE PÁGINA (SIEMPRE LO PRIMERO)
st.set_page_config(
    page_title="CREC-ERP - Gestión Inteligente",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual general
st.markdown("""
    <style>
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
def generar_guia_pdf(cliente_nombre, cliente_rut, carrito, tipo_documento="GUÍA DE DESPACHO", fecha_emision=None):
    from fpdf import FPDF
    from datetime import datetime
    import os

    # 1. Formateo de la fecha
    if fecha_emision is None:
        fecha_str = datetime.now().strftime('%d/%m/%Y')
    elif hasattr(fecha_emision, 'strftime'):
        fecha_str = fecha_emision.strftime('%d/%m/%Y')
    else:
        fecha_str = str(fecha_emision)

    pdf = FPDF(orientation='P', unit='mm', format='Letter')
    pdf.add_page()
  
    # 2. Datos de la empresa
    negocio_actual = str(st.session_state.get('negocio_seleccionado', '')).strip()
    nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
    tenant_dir = os.path.join("clientes_data", negocio_actual) if negocio_actual else "" 

    if tenant_dir:
        ruta_logo = os.path.join(tenant_dir, "logo_empresa.png")
        if os.path.exists(ruta_logo):
            try:
                pdf.image(ruta_logo, x=10, y=8, w=25)
            except Exception:
                pass

    cfg = st.session_state.get('config_ticket', {})
    if not cfg and tenant_dir:
        ruta_config_json = os.path.join(tenant_dir, "config_ticket.json")
        if os.path.exists(ruta_config_json):
            try:
                import json
                with open(ruta_config_json, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass

    nombre_empresa = cfg.get('nombre_empresa') or nombre_empresa_act or negocio_actual or 'MI EMPRESA SPA'
    rut_empresa = cfg.get('rut_empresa') or 'Sin RUT'
    direccion_empresa = cfg.get('direccion') or 'Sin Dirección'
    
    tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa or negocio_actual == "219449970012" else 19.0
    tasa_iva_global = float(cfg.get('iva_tasa', tasa_defecto))
   
    # 3. Cabecera
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 6, str(nombre_empresa), ln=True, align='C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, f"Dirección: {str(direccion_empresa)}", ln=True, align='C')
    pdf.cell(0, 5, f"RUT: {str(rut_empresa)}", ln=True, align='C')
    pdf.ln(5)
   
    titulo_doc = str(tipo_documento).upper()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, titulo_doc, ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, f"Fecha de Emisión: {fecha_str}", ln=True, align='C')
    pdf.ln(5)
   
    c_nombre = cliente_nombre if cliente_nombre and cliente_nombre.strip() else "Consumidor Final"
    c_rut = cliente_rut if cliente_rut and cliente_rut.strip() else "Sin RUT"
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "DATOS DEL CLIENTE", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(115, 6, f"Razón Social / Nombre: {c_nombre}", border=1)
    pdf.cell(60, 6, f"RUT: {c_rut}", border=1, ln=True)
    pdf.ln(5)
   
    # 4. Encabezados de Tabla (Dinámico)
    pdf.set_font("Arial", 'B', 9)
    es_factura = "FACTURA" in titulo_doc
    
    if es_factura:
        pdf.cell(70, 8, "Descripción", border=1, align='C')
        pdf.cell(15, 8, "Cant", border=1, align='C')
        pdf.cell(35, 8, "P. Unit. Neto", border=1, align='C')
        pdf.cell(35, 8, "P. Unit. Bruto", border=1, align='C')
        pdf.cell(35, 8, "Total Bruto", border=1, align='C', ln=True)
    else:
        pdf.cell(90, 8, "Descripción", border=1, align='C')
        pdf.cell(20, 8, "Cant.", border=1, align='C')
        pdf.cell(40, 8, "P. Unitario", border=1, align='C')
        pdf.cell(40, 8, "Total", border=1, align='C', ln=True)
   
    # 5. Detalle y Motor Contable
    pdf.set_font("Arial", '', 9)
    total_general = 0.0
    total_neto = 0.0
    total_iva = 0.0
    total_ila = 0.0 # 🚨 AQUÍ ACUMULAREMOS EL IMPUESTO ESPECÍFICO

    for item in carrito:
        producto = str(item.get('Descripción') or item.get('Producto') or 'Ítem')
        cantidad = float(item.get('Cantidad', 0))
        precio_unitario_bruto = float(item.get('Precio Unitario') or item.get('Precio_Unitario') or 0)
        subtotal_bruto = float(item.get('Subtotal', 0))
        
        tasa_iva_item = 0.0 if item.get("Es Exento", False) else (tasa_iva_global / 100.0)
        tasa_ila_item = float(item.get("Tasa ILA", 0.0))
        
        precio_unitario_neto = precio_unitario_bruto / (1.0 + tasa_iva_item + tasa_ila_item)
        
        if es_factura:
            pdf.cell(70, 7, producto[:35], border=1)
            pdf.cell(15, 7, f"{cantidad:g}", border=1, align='C')
            pdf.cell(35, 7, f"${precio_unitario_neto:,.0f}", border=1, align='R')
            pdf.cell(35, 7, f"${precio_unitario_bruto:,.0f}", border=1, align='R')
            pdf.cell(35, 7, f"${subtotal_bruto:,.0f}", border=1, align='R', ln=True)
        else:
            pdf.cell(90, 7, producto, border=1)
            pdf.cell(20, 7, f"{cantidad:g}", border=1, align='C')
            pdf.cell(40, 7, f"${precio_unitario_bruto:,.0f}", border=1, align='R')
            pdf.cell(40, 7, f"${subtotal_bruto:,.0f}", border=1, align='R', ln=True)
        
        # Matemáticas
        neto_calc = subtotal_bruto / (1.0 + tasa_iva_item + tasa_ila_item)
        iva_calc = neto_calc * tasa_iva_item
        ila_calc = neto_calc * tasa_ila_item # 🚨 CÁLCULO DEL ILA
        
        total_neto += neto_calc
        total_iva += iva_calc
        total_ila += ila_calc # 🚨 SUMAMOS EL ILA
        total_general += subtotal_bruto
       
    # 6. Pie de Página con Desglose Total
    pdf.set_font("Arial", 'B', 10)
    
    if es_factura:
        pdf.cell(155, 7, "SUBTOTAL NETO:", border=1, align='R')
        pdf.cell(35, 7, f"${total_neto:,.0f}", border=1, align='R', ln=True)
        
        pdf.cell(155, 7, f"IVA ({tasa_iva_global:g}%):", border=1, align='R')
        pdf.cell(35, 7, f"${total_iva:,.0f}", border=1, align='R', ln=True)
        
        # 🚨 SOLO MUESTRA LA LÍNEA SI HAY IMPUESTO ESPECÍFICO COBRADO
        if total_ila > 0:
            pdf.cell(155, 7, "IMP. ESPECÍFICO:", border=1, align='R')
            pdf.cell(35, 7, f"${total_ila:,.0f}", border=1, align='R', ln=True)
        
        pdf.cell(155, 8, "TOTAL GENERAL:", border=1, align='R')
        pdf.cell(35, 8, f"${total_general:,.0f}", border=1, align='R', ln=True)
    else:
        pdf.cell(150, 8, "TOTAL GENERAL:", border=1, align='R')
        pdf.cell(40, 8, f"${total_general:,.0f}", border=1, align='R', ln=True)
   
    return pdf.output(dest='S').encode('latin1')

# ----------------- SECCIÓN CUENTAS POR COBRAR (NUBE) -----------------
def mostrar_modulo_cuentas_por_cobrar(ruta_negocio):
    mostrar_encabezado_con_home("📑 Gestión de Cuentas por Cobrar")
    rut_actual = st.session_state.get("negocio_seleccionado")

    st.markdown("### 📊 Estado de Deudas Pendientes y Abonos")
    st.info("💡 Este módulo está conectado en tiempo real a la caja registradora. Las ventas a crédito aparecen aquí automáticamente.")

    # 1. Leer desde Supabase
    df_cxp = pd.DataFrame()
    try:
        res_cxc = supabase.table("cuentas_por_cobrar").select("*").eq("rut_empresa", rut_actual).execute()
        if res_cxc.data:
            df_cxp = pd.DataFrame(res_cxc.data)
    except Exception as e:
        st.error(f"⚠️ Error cargando Cuentas por Cobrar desde la nube: {e}")

    if df_cxp.empty:
        st.info("ℹ️ No hay registros de cuentas por cobrar todavía.")
    else:
        # 2. Calcular días de atraso en tiempo real
        if "fecha_vencimiento" in df_cxp.columns:
            hoy = pd.to_datetime(date.today())
            fechas_venc = pd.to_datetime(df_cxp["fecha_vencimiento"], errors='coerce')
            dias_atraso = (hoy - fechas_venc).dt.days
            # Solo muestra atraso si los días son positivos y el estado es Pendiente
            df_cxp["DiasAtraso"] = dias_atraso.apply(lambda x: x if x > 0 else 0)
            df_cxp.loc[df_cxp["estado"] == "Pagada", "DiasAtraso"] = 0 
        
        # 3. Buscador inteligente
        cliente_filtro = st.text_input("🔍 Buscar por Cliente o Folio de Venta:")
        df_filtrado = df_cxp.copy()
        if cliente_filtro:
            filtro_c = df_filtrado["cliente"].str.contains(cliente_filtro, case=False, na=False)
            filtro_f = df_filtrado["folio_venta"].str.contains(cliente_filtro, case=False, na=False)
            df_filtrado = df_filtrado[filtro_c | filtro_f]
        
        # 4. Formatear la tabla visualmente
        columnas_mostrar = ["folio_venta", "cliente", "monto_total", "saldo_pendiente", "fecha_emision", "fecha_vencimiento", "DiasAtraso", "estado"]
        
        # Validación de seguridad: asegurarse de que las columnas existan
        columnas_existentes = [col for col in columnas_mostrar if col in df_filtrado.columns]
        
        df_display = df_filtrado[columnas_existentes].rename(columns={
            "folio_venta": "Folio Venta",
            "cliente": "Cliente",
            "monto_total": "Monto Original",
            "saldo_pendiente": "Saldo Pendiente",
            "fecha_emision": "Emisión",
            "fecha_vencimiento": "Vencimiento",
            "DiasAtraso": "Días Atraso",
            "estado": "Estado"
        })
        
        st.dataframe(df_display, use_container_width=True)
        
        # Sumar solo lo que está pendiente
        total_pendiente = df_filtrado.loc[df_filtrado["estado"] == "Pendiente", "saldo_pendiente"].sum()
        st.metric(label="💰 Total Dinero en la Calle (Por Cobrar)", value=f"${total_pendiente:,.2f}")
        
        st.divider()
        st.markdown("### 💳 Registrar Abono o Pago")
        
        # 5. Lógica de pagos (Filtra solo las deudas pendientes, usando .copy() para evitar warnings)
        deudas_pendientes = df_cxp[df_cxp["estado"] == "Pendiente"].copy()
        
        if not deudas_pendientes.empty:
            # Crea un listado descriptivo: Folio | Cliente | Saldo
            deudas_pendientes["etiqueta"] = deudas_pendientes["folio_venta"] + " | " + deudas_pendientes["cliente"] + " | Saldo: $" + deudas_pendientes["saldo_pendiente"].astype(str)
            opciones_deuda = deudas_pendientes["etiqueta"].tolist()
            
            deuda_seleccionada = st.selectbox("📌 Selecciona la boleta/factura a abonar:", options=opciones_deuda)
            
            # Rescata los datos de la fila seleccionada
            folio_seleccionado = deuda_seleccionada.split(" | ")[0]
            fila_deuda = deudas_pendientes[deudas_pendientes["folio_venta"] == folio_seleccionado].iloc[0]
            
            saldo_actual = float(fila_deuda["saldo_pendiente"])
            id_deuda = fila_deuda["id"]
            
            monto_abono = st.number_input(f"💵 Monto a abonar (Máximo ${saldo_actual:,.2f}):", min_value=0.0, max_value=saldo_actual, step=100.0)
            
            if st.button("✅ Registrar Abono en la Nube", use_container_width=True, type="primary"):
                if monto_abono > 0:
                    nuevo_saldo = saldo_actual - monto_abono
                    nuevo_estado = "Pagada" if nuevo_saldo <= 0 else "Pendiente"
                    
                    try:
                        # Actualizamos la base de datos
                        supabase.table("cuentas_por_cobrar").update({
                            "saldo_pendiente": nuevo_saldo,
                            "estado": nuevo_estado
                        }).eq("id", int(id_deuda)).execute()
                        
                        if nuevo_estado == "Pagada":
                            st.success(f"🎉 ¡Deuda saldada por completo para el folio {folio_seleccionado}! El registro se mantendrá en el historial como 'Pagada'.")
                        else:
                            st.success(f"🟢 Abono registrado con éxito. Nuevo saldo pendiente: ${nuevo_saldo:,.2f}")
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al registrar el abono en la nube: {e}")
                else:
                    st.warning("⚠️ Ingresa un monto mayor a cero.")
        else:
            st.info("ℹ️ ¡Excelente! No hay clientes con deudas pendientes.")

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
    
    st.markdown("""
        <div style='background-color: #EFF6FF; padding: 15px; border-radius: 8px; border-left: 4px solid #3B82F6; margin-bottom: 20px;'>
            <strong>💡 Control Financiero para Emprendedores:</strong> Este módulo te ayuda a calcular el 
            <strong>retiro seguro de utilidades</strong> basado en tu porcentaje de Markup (margen), evitando que 
            saques dinero destinado a la reposición de mercadería.
        </div>
    """, unsafe_allow_html=True)

    archivo_retiros = os.path.join(ruta_negocio, "Registro_Retiros_Seguros.xlsx")
    if not os.path.exists(archivo_retiros):
        pd.DataFrame(columns=['Fecha', 'VentaTotal', 'MarkupAplicado', 'CostoMercaderia', 'UtilidadRealRetirable', 'RetiroEfectuado', 'Observaciones']).to_excel(archivo_retiros, index=False)

    tab_cr1, tab_cr2, tab_cr3 = st.tabs(["💰 Cálculo de Retiro Seguro (Markup)", "🏦 Conciliación de Cartolas (POS / Banco)", "📂 Historial de Retiros"])

    with tab_cr1:
        st.markdown("### 🎯 Asistente de Retiro Diario sin Desfinanciar el Negocio")
        
        with st.form("form_calculo_retiro"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fecha_calculo = st.date_input("Fecha de la Cuadratura", value=date.today())
                venta_dia_input = st.number_input("💵 Venta Total del Día ($)", min_value=0.0, step=1000.0, value=150000.0)
            with col_c2:
                markup_porcentaje = st.number_input("📈 Markup / Margen Promedio (%)", min_value=1.0, max_value=500.0, value=50.0, step=5.0, help="Porcentaje de margen estimado sobre el costo aplicado a tus productos.")
                observacion_retiro = st.text_input("📝 Notas u Observaciones del Día", value="Cierre diario normal")

            markup_decimal = markup_porcentaje / 100.0
            costo_reposicion = venta_dia_input / (1.0 + markup_decimal)
            utilidad_neta_retirable = venta_dia_input - costo_reposicion

            st.divider()
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric(label="🛒 Venta Total Ingresada", value=f"${venta_dia_input:,.2f}")
            with col_m2:
                st.metric(label="🔒 Fondo Intocable (Reposición)", value=f"${costo_reposicion:,.2f}", delta="Guardar en Caja/Cuenta")
            with col_m3:
                st.metric(label="💵 Utilidad Real Retirable", value=f"${utilidad_neta_retirable:,.2f}", delta="Disponible para Retiro")

            btn_guardar_retiro = st.form_submit_button("💾 Guardar Registro de Retiro Seguro", type="primary")

            if btn_guardar_retiro:
                if venta_dia_input <= 0:
                    st.warning("⚠️ Ingresa una venta válida mayor a 0.")
                else:
                    df_ret_ant = pd.read_excel(archivo_retiros)
                    nuevo_reg_ret = pd.DataFrame([{
                        'Fecha': str(fecha_calculo),
                        'VentaTotal': venta_dia_input,
                        'MarkupAplicado': markup_porcentaje,
                        'CostoMercaderia': costo_reposicion,
                        'UtilidadRealRetirable': utilidad_neta_retirable,
                        'RetiroEfectuado': utilidad_neta_retirable,
                        'Observaciones': observacion_retiro
                    }])
                    pd.concat([df_ret_ant, nuevo_reg_ret], ignore_index=True).to_excel(archivo_retiros, index=False)
                    st.success("✅ ¡Registro guardado con éxito! Se protegió el fondo de reposición de mercadería.")
                    st.rerun()

    with tab_cr2:
        st.markdown("### 🏦 Conciliación de Transacciones (Transbank / Bancos / Transferencias)")
        
        archivo_conciliacion = os.path.join(ruta_negocio, "Conciliacion_Bancaria.xlsx")
        if not os.path.exists(archivo_conciliacion):
            pd.DataFrame(columns=['Fecha', 'Origen', 'MontoVentaPOS', 'MontoAbonadoBanco', 'Diferencia', 'Estado']).to_excel(archivo_conciliacion, index=False)

        df_conci = pd.read_excel(archivo_conciliacion)
        st.dataframe(df_conci, use_container_width=True)

        with st.form("form_nueva_conciliacion"):
            st.markdown("#### ➕ Registrar Validación de Cartola")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                f_conci = st.date_input("Fecha de Cartola", value=date.today(), key="f_con")
                origen_pago = st.selectbox("Origen del Abono", ["Transbank / Débito", "Transbank / Crédito", "Transferencia Bancaria Directa", "Efectivo Depositado"])
            with col_b2:
                monto_pos = st.number_input("Monto Registrado en POS ($)", min_value=0.0, step=100.0, value=0.0, key="m_pos")
                monto_banco = st.number_input("Monto Abonado en Banco ($)", min_value=0.0, step=100.0, value=0.0, key="m_ban")

            diferencia_banco = monto_banco - monto_pos
            if diferencia_banco == 0:
                estado_conci = "Conciliado OK"
            elif diferencia_banco < 0:
                estado_conci = "Diferencia en contra (Comisión o Faltante)"
            else:
                estado_conci = "Abono Mayor"

            if st.form_submit_button("💾 Guardar Validación Bancaria"):
                nuevo_c = pd.DataFrame([{
                    'Fecha': str(f_conci),
                    'Origen': origen_pago,
                    'MontoVentaPOS': monto_pos,
                    'MontoAbonadoBanco': monto_banco,
                    'Diferencia': diferencia_banco,
                    'Estado': estado_conci
                }])
                pd.concat([df_conci, nuevo_c], ignore_index=True).to_excel(archivo_conciliacion, index=False)
                st.success("✅ ¡Conciliación registrada correctamente!")
                st.rerun()

    with tab_cr3:
        st.markdown("### 📂 Historial de Retiros Seguros Realizados")
        if os.path.exists(archivo_retiros):
            df_hist_ret = pd.read_excel(archivo_retiros)
            if not df_hist_ret.empty:
                st.dataframe(df_hist_ret, use_container_width=True)
                total_retirado = df_hist_ret['UtilidadRealRetirable'].sum() if 'UtilidadRealRetirable' in df_hist_ret.columns else 0.0
                st.metric(label="💵 Utilidad Histórica Retirada de forma Segura", value=f"${total_retirado:,.2f}")
            else:
                st.info("ℹ️ No hay registros de retiros todavía.")

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


# --- 4. SISTEMA DE AUTENTICACIÓN Y BLINDAJE DE SEGURIDAD ---
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

if not st.session_state.autenticado:
    st.markdown('<p class="main-title">🔐 CREC-ERP - Acceso Blindado</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Sistema protegido de gestión empresarial</p>', unsafe_allow_html=True)
 
    if st.session_state.intentos_fallidos >= 3:
        st.error("🚨 **Demasiados intentos fallidos.** El acceso temporalmente restringido por seguridad.")
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
                # 1. Validación Admin Master (Tú como Desarrollador)
                if usuario_limpio.lower() in ["admin", "desarrollador", "simon"] and password_limpio == "SIMON1908":
                    st.session_state.autenticado = True
                    st.session_state.es_admin_dev = True
                    st.session_state.usuario_logueado = "Administrador Master"
                    st.session_state.negocio_actual = "admin_general"
                    st.session_state.nombre_empresa = "CREC-ERP Master"
                    st.session_state.rol_usuario = "Administrador"
                    st.session_state.modulos_permitidos = "ALL"
                    st.session_state.intentos_fallidos = 0
                    st.success("🛠️ ¡Acceso Maestro Autorizado!")
                    st.rerun()
                else:
                    acceso_exitoso = False
                    
                    # 🚨 1.5 NUEVO: VALIDACIÓN DEL PROPIETARIO 100% EN LA NUBE (Supabase)
                    try:
                        # Buscamos si el RUT ingresado pertenece a una Empresa dueña
                        res_dueño = supabase.table("empresas").select("*").eq("rut_empresa", usuario_limpio).execute()
                        
                        if res_dueño.data:
                            datos_empresa = res_dueño.data[0]
                            
                            # Validamos contra la nueva columna 'password' de la tabla empresas
                            pass_db = str(datos_empresa.get("password", ""))
                            
                            if pass_db == password_limpio:
                                if datos_empresa.get("licencia_activa", True):
                                    st.session_state.autenticado = True
                                    st.session_state.es_admin_dev = False
                                    st.session_state.negocio_actual = usuario_limpio
                                    st.session_state.usuario_logueado = "Propietario / Administrador"
                                    st.session_state.rol_usuario = "Propietario"
                                    st.session_state.modulos_permitidos = "ALL" # Acceso a TODO
                                    st.session_state.intentos_fallidos = 0
                                    st.session_state.nombre_empresa = datos_empresa.get("empresa_nombre", usuario_limpio)
                                    
                                    st.success(f"👑 ¡Bienvenido Propietario de {st.session_state.nombre_empresa}!")
                                    acceso_exitoso = True
                                    st.rerun()
                                else:
                                    st.error("❌ La licencia de esta empresa se encuentra expirada o inactiva.")
                                    acceso_exitoso = True # Bloqueo intencional
                    except Exception as e:
                        pass
                    
                    # 2. VALIDACIÓN ESTRICTA EN LA NUBE: Cajeros y Operadores
                    if not acceso_exitoso:
                        try:
                            res_usr = supabase.table("usuarios").select("*").eq("rut_usuario", usuario_limpio).execute()
                            
                            if res_usr.data:
                                datos_usr = res_usr.data[0]
                                
                                # BARRERA DE SEGURIDAD 1: La contraseña debe ser EXACTA
                                if str(datos_usr.get("password_hash")) == password_limpio:
                                    
                                    id_empresa = datos_usr.get("empresa_id")
                                    res_emp = supabase.table("empresas").select("rut_empresa", "empresa_nombre", "licencia_activa").eq("id", id_empresa).execute()
                                    
                                    if res_emp.data:
                                        datos_empresa = res_emp.data[0]
                                        
                                        # BARRERA DE SEGURIDAD 2: La empresa debe estar al día
                                        if datos_empresa.get("licencia_activa", True):
                                            rut_negocio = datos_empresa.get("rut_empresa")
                                            nombre_negocio = datos_empresa.get("empresa_nombre")
                                            
                                            modulos_str = datos_usr.get("modulos", "")
                                            modulos_operador = [m.strip() for m in modulos_str.split(",") if m.strip()]
                                            
                                            # BARRERA DE SEGURIDAD 3: Debe tener módulos asignados
                                            if not modulos_operador:
                                                st.error("❌ Tu usuario no tiene módulos asignados. Acceso denegado.")
                                                acceso_exitoso = True 
                                            else:
                                                # ACCESO APROBADO A CAJERO
                                                st.session_state.autenticado = True
                                                st.session_state.es_admin_dev = False
                                                st.session_state.negocio_actual = rut_negocio
                                                st.session_state.usuario_logueado = datos_usr.get("nombre", usuario_limpio)
                                                st.session_state.rol_usuario = datos_usr.get("rol", "Cajero / Vendedor")
                                                st.session_state.modulos_permitidos = modulos_operador
                                                st.session_state.intentos_fallidos = 0
                                                st.session_state.nombre_empresa = nombre_negocio
                                                
                                                st.success(f"🟢 ¡Bienvenido {st.session_state.usuario_logueado}!")
                                                acceso_exitoso = True
                                                st.rerun()
                                        else:
                                            st.error("❌ La licencia de la empresa se encuentra expirada o inactiva.")
                                            acceso_exitoso = True
                        except Exception as e:
                            pass
                        
                    # 3. FALLBACK LOCAL: Por si hay cajeros en el archivo JSON antiguo
                    if not acceso_exitoso:
                        for neg_folder in os.listdir(CLIENTES_DIR):
                            folder_path = os.path.join(CLIENTES_DIR, neg_folder)
                            if os.path.isdir(folder_path):
                                arch_usr = os.path.join(folder_path, "usuarios_negocio.json")
                                if os.path.exists(arch_usr):
                                    with open(arch_usr, "r", encoding="utf-8") as f:
                                        diccionario_users = json.load(f)
                                        if usuario_limpio in diccionario_users:
                                            datos_usr = diccionario_users[usuario_limpio]
                                            
                                            if str(datos_usr.get("password")) == password_limpio:
                                                modulos_str = datos_usr.get("modulos", "")
                                                modulos_operador = [m.strip() for m in modulos_str.split(",") if m.strip()] if isinstance(modulos_str, str) else modulos_str
                                                
                                                if not modulos_operador:
                                                    st.error("❌ Tu usuario no tiene módulos asignados. Acceso denegado.")
                                                    acceso_exitoso = True
                                                else:
                                                    st.session_state.autenticado = True
                                                    st.session_state.es_admin_dev = False
                                                    st.session_state.negocio_actual = neg_folder
                                                    st.session_state.usuario_logueado = datos_usr.get("nombre", usuario_limpio)
                                                    st.session_state.rol_usuario = datos_usr.get("rol", "Cajero / Vendedor")
                                                    st.session_state.modulos_permitidos = modulos_operador
                                                    st.session_state.intentos_fallidos = 0
                                                    
                                                    # Validación segura de empresas_data si existe
                                                    if 'empresas_data' in globals():
                                                        emp_info = next((emp for emp in empresas_data if str(emp.get("rut_empresa")) == neg_folder), None)
                                                        st.session_state.nombre_empresa = emp_info.get("empresa_nombre") if emp_info else neg_folder
                                                    else:
                                                        st.session_state.nombre_empresa = neg_folder
                                                        
                                                    st.success(f"🟢 ¡Bienvenido {st.session_state.usuario_logueado}!")
                                                    acceso_exitoso = True
                                                    st.rerun()
                    
                    # 4. RECHAZO TOTAL
                    if not acceso_exitoso:
                        st.session_state.intentos_fallidos += 1
                        intentos_restantes = 3 - st.session_state.intentos_fallidos
                        st.error(f"❌ Usuario no encontrado o contraseña incorrecta. Te quedan {intentos_restantes} intento(s).")


# --- 5. CONFIGURACIÓN DE RUTAS Y ARCHIVOS DEL NEGOCIO ACTIVO ---
negocio_seleccionado = st.session_state.get("negocio_actual", None)
if negocio_seleccionado and negocio_seleccionado != "admin_general":
    ruta_negocio = os.path.join(CLIENTES_DIR, str(negocio_seleccionado))
    os.makedirs(ruta_negocio, exist_ok=True)
    archivos_en_carpeta = os.listdir(ruta_negocio)
    archivo_base = next((os.path.join(ruta_negocio, f) for f in archivos_en_carpeta if f.startswith("BASE DE DATOS")), os.path.join(ruta_negocio, "BASE DE DATOS.xlsx"))
    archivo_compras = next((os.path.join(ruta_negocio, f) for f in archivos_en_carpeta if f.startswith("Libro_Compras")), os.path.join(ruta_negocio, "Libro_Compras.xlsx"))
else:
    ruta_negocio = CLIENTES_DIR
    archivo_base = None
    archivo_compras = None

st.session_state.negocio_seleccionado = negocio_seleccionado


# --- 6. BARRA LATERAL, PERMISOS Y MENÚ ÚNICO ---

if st.session_state.get("autenticado", False):
    st.sidebar.markdown(f"👤 Usuario: **{st.session_state.get('usuario_logueado', 'Ninguno')}**")
    st.sidebar.markdown(f"🏢 Negocio: *{st.session_state.get('nombre_empresa', 'NINGUNO')}*")

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

if not st.session_state.get("es_admin_dev", False):
    st.sidebar.write("") 
    st.sidebar.link_button("💳 Renovar Licencia Mensual", "https://mpago.la/12ae7ej", type="primary", use_container_width=True)

if not st.session_state.get("es_admin_dev", False):
    try:
        rut_actual = st.session_state.get("negocio_seleccionado") 
        res_licencia = supabase.table("empresas").select("fecha_expiracion").eq("rut_empresa", rut_actual).execute()
        
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
                    st.sidebar.error(f"🚫 **Licencia Expirada** hace {abs(dias_restantes)} días. Tu acceso será suspendido a la brevedad.")
    except Exception as e:
        pass

st.sidebar.divider()

def cargar_permisos():
    if os.path.exists(PERMISOS_FILE):
        with open(PERMISOS_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_permisos(datos):
    with open(PERMISOS_FILE, "w") as f:
        json.dump(datos, f, indent=4)

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
    "⚙️ Configuración General"
]
if st.session_state.get("es_admin_dev", False):
    modulos_totales.append("🔑 Control Maestro de Licencias")

# --- 🧠 CÁLCULO DE MÓDULOS PERMITIDOS SEGÚN SESIÓN ---
if st.session_state.get("modulos_permitidos") == "ALL":
    lista_modulos_permitidos = modulos_totales
else:
    lista_modulos_permitidos = st.session_state.get("modulos_permitidos", ["🏠 Home / Bienvenida"])

if "🏠 Home / Bienvenida" not in lista_modulos_permitidos:
    lista_modulos_permitidos.insert(0, "🏠 Home / Bienvenida")

# --- 🛠️ PANEL DE DESARROLLADOR MAESTRO ---
if st.session_state.get("es_admin_dev", False):
    with st.sidebar.expander("🛠️ Panel de Desarrollador (Licencias y Mantenimiento)"):
        st.success("✔️ Modo Desarrollador Activo")
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
                        datos_nuevo = {
                            "nombre": nombre_comercial,
                            "password": password_cliente,
                            "fecha_expiracion": str(fecha_exp),
                            "activo": True,
                            "modulos": {mod: True for mod in modulos_totales}
                        }
                        guardar_nuevo_cliente(id_negocio, datos_nuevo)
                        
                        db_permisos = cargar_permisos()
                        db_permisos[id_negocio] = {mod: True for mod in modulos_totales}
                        guardar_permisos(db_permisos)
                        
                        try:
                            supabase.table("empresas").insert({
                                "rut_empresa": id_negocio,
                                "empresa_nombre": nombre_comercial,
                                "fecha_expiracion": str(fecha_exp),
                                "licencia_activa": True
                            }).execute()
                        except Exception as e:
                            pass 
                        
                        st.success(f"✨ ¡Negocio '{nombre_comercial}' creado y sincronizado con Supabase!")
                        st.rerun()

        with tab_mant:
            st.markdown("#### 🧹 Reseteo y Limpieza Remota")
            negocio_a_limpiar = st.selectbox("Selecciona Negocio a Gestionar:", negocios_disponibles, key="limpiar_negocio_sel_nico")
            dir_cliente_objetivo = os.path.join(CLIENTES_DIR, negocio_a_limpiar)
            st.warning("⚠️ **Zona de Peligro:** La opción de fábrica eliminará todos los registros locales.")
            confirmar_borrado = st.checkbox("Confirmo que deseo restablecer este negocio a versión de fábrica", key="chk_confirmar_fabrica")

            if st.button("🚨 Restablecer a Versión de Fábrica (Borrar Todo)", type="primary", key="btn_version_fabrica"):
                if not confirmar_borrado:
                    st.error("❌ Debes marcar la casilla de confirmación para autorizar el reseteo.")
                else:
                    try:
                        import shutil
                        for archivo in os.listdir(dir_cliente_objetivo):
                            ruta_archivo = os.path.join(dir_cliente_objetivo, archivo)
                            if os.path.isfile(ruta_archivo) and archivo != "logo_empresa.png":
                                os.remove(ruta_archivo)
                        for carpeta_sub in ["archivador_ventas", "archivador_compras"]:
                            dir_sub = os.path.join(dir_cliente_objetivo, carpeta_sub)
                            if os.path.exists(dir_sub):
                                shutil.rmtree(dir_sub)
                        st.success(f"✨ ¡Negocio '{negocio_a_limpiar}' restablecido a versión de fábrica con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error al restablecer: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("© 2026 CREC-ERP")
st.sidebar.markdown("Desarrollado por **Sebastián Calderón**")


# --- 7. INICIALIZACIÓN DE ESTADOS DE SESIÓN ---
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
    if os.path.exists(path_db):
        df = pd.read_excel(path_db, dtype={'Código': str})
        if 'Activo' in df.columns:
            df = df[df['Activo'].astype(str).str.strip().str.capitalize() == 'Si']
        return df
    return None

df_base = cargar_datos(archivo_base) if ('archivo_base' in globals() and archivo_base) else None

def mostrar_encabezado_con_home(titulo_modulo):
    col_titulo, col_btn = st.columns([4, 1])
    with col_titulo:
        nombre_mostrar = st.session_state.get('nombre_empresa', st.session_state.get('negocio_seleccionado', 'Empresa no seleccionada'))
        st.subheader(f"{titulo_modulo} (Negocio: {nombre_mostrar})")
    with col_btn:
        st.write("")
        if st.button("🏠 Volver al Home", use_container_width=True):
            st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
            st.rerun()

# --- 8. RENDERIZADO DEL HOME FIJO Y MÓDULOS ---
if menu == "🏠 Home / Bienvenida":
    st.markdown(f"<p class='main-title'>🪙 CREC-ERP: {st.session_state.nombre_empresa if 'nombre_empresa' in st.session_state else 'GENERAL'}</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>Selecciona un módulo para comenzar:</p>", unsafe_allow_html=True)
   
    # 🚀 BOTÓN FORZADO EXCLUSIVO PARA EL DESARROLLADOR
    if st.session_state.get("es_admin_dev", False):
        st.error("🛠️ **PANEL DE CONTROL MAESTRO**")
        if st.button("🔑 ABRIR CONTROL DE LICENCIAS Y CLIENTES", type="primary", use_container_width=True):
            st.session_state.menu_seleccionado = "🔑 Control Maestro de Licencias"
            st.rerun()
        st.divider()

    modulos_disponibles_home = [
        {"id": "dash", "nombre_ref": "Dashboard Ejecutivo", "label": "📊 Dashboard Ejecutivo"},
        {"id": "inv", "nombre_ref": "Inventario y Productos", "label": "📦 Inventario y Productos"},
        {"id": "prod", "nombre_ref": "Producción y Recetas", "label": "🍔 Producción y Recetas"}, # 🚨 NUEVO BOTÓN AGREGADO AQUÍ
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
        {"id": "conf", "nombre_ref": "Configuración General", "label": "⚙️ Configuración General"}
    ]

    botones_activos = []
    for mod in modulos_disponibles_home:
        permitido = any(mod["nombre_ref"].lower() in str(p).lower() for p in lista_modulos_permitidos)
        if permitido:
            botones_activos.append(mod)

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
        st.info("ℹ️ Tu licencia actual no tiene módulos activos asignados.")

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
            
            # --- LÓGICA DE CREACIÓN DE PRODUCTOS MULTI-BODEGA ---
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
   
    # 🕒 Selector de Período Temporal en Tiempo Real
    st.markdown("### 🎛️ Filtro Temporal de Análisis")
    col_f1, col_f2 = st.columns([2, 2])
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

    archivo_gastos = os.path.join(ruta_negocio, "Registro_Gastos.xlsx")
    archivo_cxp = os.path.join(ruta_negocio, "Cuentas_por_Cobrar.xlsx")
    archivo_cpp = os.path.join(ruta_negocio, "Cuentas_Por_Pagar.xlsx")
    archivo_cuadratura = os.path.join(ruta_negocio, "Cuadratura_Diaria.xlsx")

    # 1. Cálculo de Ventas Filtradas por Período desde Supabase
    total_ventas_periodo = 0.0
    try:
        res_ventas_nube = supabase.table("ventas").select("fecha, monto, folio").eq("rut_empresa", st.session_state.negocio_seleccionado).execute()
        
        if res_ventas_nube.data:
            df_temp_v = pd.DataFrame(res_ventas_nube.data)
            if not df_temp_v.empty:
                df_temp_v['Fecha_Parsed'] = pd.to_datetime(df_temp_v['fecha'], errors='coerce')
                
                if fecha_limite is not None:
                    if periodo_seleccionado == "Diaria (Hoy)":
                        df_temp_v = df_temp_v[df_temp_v['Fecha_Parsed'].dt.date == hoy_dt.date()]
                    else:
                        df_temp_v = df_temp_v[df_temp_v['Fecha_Parsed'] >= fecha_limite]
                
                if 'monto' in df_temp_v.columns:
                    if "folio" in df_temp_v.columns:
                        total_ventas_periodo = df_temp_v.drop_duplicates(subset=["folio"])['monto'].sum()
                    else:
                        total_ventas_periodo = df_temp_v['monto'].sum()
    except Exception as e:
        print(f"Error cargando ventas desde Supabase para el dashboard: {e}")
        total_ventas_periodo = 0.0

    # 2. Cálculo de Gastos Filtrados por Período
    total_gastos_periodo = 0.0
    df_g_filtrado = pd.DataFrame()
    if os.path.exists(archivo_gastos):
        try:
            df_g = pd.read_excel(archivo_gastos)
            if not df_g.empty and 'Monto' in df_g.columns:
                if 'Fecha' in df_g.columns and fecha_limite is not None:
                    df_g['Fecha_Parsed'] = pd.to_datetime(df_g['Fecha'], errors='coerce')
                    if periodo_seleccionado == "Diaria (Hoy)":
                        df_g_filtrado = df_g[df_g['Fecha_Parsed'].dt.date == hoy_dt.date()]
                    else:
                        df_g_filtrado = df_g[df_g['Fecha_Parsed'] >= fecha_limite]
                else:
                    df_g_filtrado = df_g.copy()
                
                total_gastos_periodo = df_g_filtrado['Monto'].sum()
        except Exception:
            pass

    # 3. Cálculo de Inventario, Margen y Ganancia Real sobre Ventas desde la Nube
    try:
        res_prod = supabase.table("productos").select("costo, precio_venta, stock").eq("rut_empresa", st.session_state.negocio_seleccionado).limit(10000).execute()
        if res_prod.data:
            df_prod_nube = pd.DataFrame(res_prod.data)
            df_prod_nube['costo'] = pd.to_numeric(df_prod_nube['costo'], errors='coerce').fillna(0)
            df_prod_nube['precio_venta'] = pd.to_numeric(df_prod_nube['precio_venta'], errors='coerce').fillna(0)
            df_prod_nube['stock'] = pd.to_numeric(df_prod_nube['stock'], errors='coerce').fillna(0)

            inversion_total = (df_prod_nube['costo'] * df_prod_nube['stock']).sum()
            valor_venta_total = (df_prod_nube['precio_venta'] * df_prod_nube['stock']).sum()
            ganancia_potencial = valor_venta_total - inversion_total
            total_productos = len(df_prod_nube)

            # Cálculos de rentabilidad y margen exactos
            df_m = df_prod_nube[(df_prod_nube['costo'] > 0) & (df_prod_nube['precio_venta'] > 0)]
            if not df_m.empty:
                df_m['markup'] = ((df_m['precio_venta'] - df_m['costo']) / df_m['costo']) * 100
                df_m['margen'] = ((df_m['precio_venta'] - df_m['costo']) / df_m['precio_venta']) * 100
                markup_promedio = df_m['markup'].mean()
                margen_promedio = df_m['margen'].mean()
            else:
                markup_promedio = 0.0
                margen_promedio = 0.0
        else:
            inversion_total = valor_venta_total = ganancia_potencial = 0.0
            total_productos = 0
            markup_promedio = margen_promedio = 0.0
    except Exception:
        inversion_total = valor_venta_total = ganancia_potencial = 0.0
        total_productos = 0
        markup_promedio = margen_promedio = 0.0

    # Ganancia real en dinero basada en las ventas del período y el margen promedio
    ganancia_real_ventas = total_ventas_periodo * (margen_promedio / 100.0)
    utilidad_neta_estimada = total_ventas_periodo - total_gastos_periodo

    st.divider()

    # --- BLOQUE DE KPIS SUPERIORES ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label=f"💰 Venta ({periodo_seleccionado.split()[0]})", value=f"${total_ventas_periodo:,.2f}")
    with col2:
        st.metric(label=f"📉 Gastos ({periodo_seleccionado.split()[0]})", value=f"${total_gastos_periodo:,.2f}", delta="Egresos", delta_color="inverse")
    with col3:
        st.metric(label=f"💼 Utilidad Est. ({periodo_seleccionado.split()[0]})", value=f"${utilidad_neta_estimada:,.2f}", delta="Margen")
    with col4:
        st.metric(label="📦 Total Productos", value=total_productos)

    st.divider()

    # --- BLOQUE DE INVENTARIO ---
    col_inv1, col_inv2, col_inv3 = st.columns(3)
    with col_inv1:
        st.metric(label="📉 Inversión Total (Costo)", value=f"${inversion_total:,.2f}")
    with col_inv2:
        st.metric(label="📈 Valor Venta Potencial", value=f"${valor_venta_total:,.2f}")
    with col_inv3:
        st.metric(label="💰 Ganancia Potencial", value=f"${ganancia_potencial:,.2f}")

    st.divider()

    st.markdown("### 📊 Indicadores de Rentabilidad y Ganancia Real")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(
            label="📈 Markup Promedio (Sobre Costo)", 
            value=f"{markup_promedio:,.1f}%", 
            help="Porcentaje que se le suma al costo para llegar al precio de venta."
        )
    with col_m2:
        st.metric(
            label="🎯 Ganancia Real en Ventas", 
            value=f"${ganancia_real_ventas:,.2f}", 
            delta=f"Margen: {margen_promedio:,.1f}%",
            help="Dinero exacto de ganancia obtenido en base a las ventas del período y tu margen promedio."
        )
    
    st.divider()

    # --- GRÁFICOS Y TENDENCIAS INTERACTIVAS ---
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("#### 📈 Evolución Diaria de Ingresos (Cuadratura)")
        if os.path.exists(archivo_cuadratura):
            try:
                df_cuat = pd.read_excel(archivo_cuadratura)
                if not df_cuat.empty and 'Fecha' in df_cuat.columns and 'VentaTotal' in df_cuat.columns:
                    if fecha_limite is not None and periodo_seleccionado != "Histórico Completo":
                        df_cuat['Fecha_Parsed'] = pd.to_datetime(df_cuat['Fecha'], errors='coerce')
                        if periodo_seleccionado == "Diaria (Hoy)":
                            df_cuat = df_cuat[df_cuat['Fecha_Parsed'].dt.date == hoy_dt.date()]
                        else:
                            df_cuat = df_cuat[df_cuat['Fecha_Parsed'] >= fecha_limite]
                    
                    if not df_cuat.empty:
                        st.line_chart(df_cuat.set_index('Fecha')['VentaTotal'])
                    else:
                        st.info("ℹ️ No hay registros de cuadratura en este período.")
                else:
                    st.info("ℹ️ Sin datos de cuadratura diarios.")
            except Exception:
                st.info("ℹ️ Error leyendo archivo de cuadratura.")
        else:
            st.info("ℹ️ Archivo de cuadratura no encontrado.")

    with col_g2:
        st.markdown("#### 📊 Distribución de Gastos por Categoría")
        with st.expander("💡 ¿Qué significa este gráfico y por qué es importante?"):
            st.write("""
            **¿Qué mide exactamente?** 
            Te muestra de forma visual en qué se está yendo el dinero de tu negocio, calculando qué porcentaje del total de tus egresos corresponde a cada categoría.
            
            **¿Por qué es clave para tu éxito?**
            * **Detección de fugas:** Si la categoría *Gastos Operativos* (arriendo, luz, sueldos) domina la gráfica, significa que los costos fijos de mantener tu local están muy altos.
            * **Equilibrio sano:** Lo ideal en tu negocio es que la porción más grande de esta gráfica sea siempre la **Mercadería**, ya que esa es la inversión que te generará ventas y ganancias reales.
            """)
        if not df_g_filtrado.empty and 'Categoria' in df_g_filtrado.columns and 'Monto' in df_g_filtrado.columns:
            df_cat = df_g_filtrado.groupby('Categoria')['Monto'].sum().reset_index()
            
            fig_dona = px.pie(
                df_cat, 
                values='Monto', 
                names='Categoria', 
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
    st.markdown("### 🔔 Alertas y Salud Financiera del negocio")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if total_gastos_periodo > (total_ventas_periodo * 0.7) and total_ventas_periodo > 0:
            st.error("⚠️ **Alerta Financiera:** Los gastos operativos superan el 70% de las ventas en este período.")
        else:
            st.success("✅ **Salud Financiera Estable:** Niveles de gastos controlados para el período analizado.")
            
    with col_a2:
        if os.path.exists(archivo_cpp):
            try:
                df_prov_pend = pd.read_excel(archivo_cpp)
                pendientes = df_prov_pend[df_prov_pend.get('Estado', '') == 'PENDIENTE'] if 'Estado' in df_prov_pend.columns else pd.DataFrame()
                if not pendientes.empty:
                    st.warning(f"⚠️ Tienes **{len(pendientes)} factura(s) pendiente(s)** de pago a proveedores.")
                else:
                    st.info("ℹ️ No hay facturas de proveedores pendientes de pago.")
            except Exception:
                st.info("ℹ️ Módulo de cuentas por pagar sin registros activos.")
        else:
            st.info("ℹ️ Módulo de cuentas por pagar sin registros activos.")

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
            lista_proveedores = []
            try:
                res_prov_nube = supabase.table("proveedores").select("nombre").eq("rut_empresa", rut_actual).execute()
                if res_prov_nube.data:
                    lista_proveedores = [p["nombre"] for p in res_prov_nube.data if p.get("nombre")]
            except Exception as e:
                print(f"Error cargando proveedores desde Supabase en GRC: {e}")

            if not lista_proveedores:
                lista_proveedores = ["Proveedor General"]

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

            with st.form("form_gri_interno"):
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    folio_gri = st.text_input("N° Folio GRI interno (ej. GRI-2026-001)")
                    motivo_gri = st.selectbox("Motivo del Ingreso Interno", ["Producción Propia", "Hallazgo de Inventario / Conteo", "Devolución de Cliente", "Ajuste Positivo de Bodega", "Otro"])
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
                        codigo_gri = prod_gri_sel.split(" - ")[0]
                        desc_gri = prod_gri_sel.split(" - ")[1]
                        
                        # 1. Actualizar Stock en base principal
                        match_gri = df_base[df_base[col_cod].astype(str) == str(codigo_gri)]
                        if not match_gri.empty:
                            idx_g = match_gri.index[0]
                            stock_actual_g = float(df_base.at[idx_g, col_stock]) if col_stock and not pd.isna(df_base.at[idx_g, col_stock]) else 0.0
                            df_base.at[idx_g, col_stock] = stock_actual_g + cant_gri
                            df_base.to_excel(archivo_base, index=False)

                        # 2. Registrar en base de lotes si aplica
                        if maneja_lote_gri == "Sí":
                            archivo_lotes = os.path.join(ruta_negocio, "base_lotes.xlsx") if 'ruta_negocio' in globals() else "base_lotes.xlsx"
                            nuevo_reg_lote_gri = pd.DataFrame([{
                                "Código": codigo_gri,
                                "Descripción": desc_gri,
                                "Lote": lote_gri,
                                "CantidadDisponible": cant_gri,
                                "FechaVencimiento": venc_gri,
                                "CostoUnitarioFinal": costo_estimado_gri
                            }])
                            if os.path.exists(archivo_lotes):
                                df_lotes_g = pd.read_excel(archivo_lotes, dtype={'Código': str})
                                pd.concat([df_lotes_g, nuevo_reg_lote_gri], ignore_index=True).to_excel(archivo_lotes, index=False)
                            else:
                                nuevo_reg_lote_gri.to_excel(archivo_lotes, index=False)

                        # 3. Registrar en Registro de Compras/Recepciones como GRI
                        nuevo_reg_gri_hist = pd.DataFrame([{
                            "FechaHora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "TipoRecepcion": "GRI",
                            "Proveedor": f"INTERNO ({motivo_gri})",
                            "Factura": folio_gri,
                            "Código": codigo_gri,
                            "Descripción": desc_gri,
                            "Cantidad": cant_gri,
                            "NetoUnitario": costo_estimado_gri,
                            "SubtotalNeto": cant_gri * costo_estimado_gri,
                            "IVA": 0.0,
                            "ImpuestoEspecifico": 0.0,
                            "CostoTotal": cant_gri * costo_estimado_gri,
                            "ManejaLote": maneja_lote_gri,
                            "Lote": lote_gri,
                            "FechaVencimientoLote": venc_gri,
                            "Condicion_Pago": "Interno",
                            "FechaVencimientoPago": str(fecha_gri),
                            "Banco": "",
                            "N_Serie": responsable_gri,
                            "Estado": "Completado"
                        }])
                        archivo_compras_path = os.path.join(ruta_negocio, "Registro_Compras.xlsx") if 'ruta_negocio' in globals() else "Registro_Compras.xlsx"
                        if os.path.exists(archivo_compras_path):
                            df_ec_g = pd.read_excel(archivo_compras_path, dtype={'Código': str, 'Factura': str})
                            pd.concat([df_ec_g, nuevo_reg_gri_hist], ignore_index=True).to_excel(archivo_compras_path, index=False)
                        else:
                            nuevo_reg_gri_hist.to_excel(archivo_compras_path, index=False)

                        # 🗂️ 4. ARCHIVADOR AUTOMÁTICO GRI (Subdirectorio)
                        try:
                            dir_arch_gri = os.path.join(ruta_negocio, "archivador_compras", "gri")
                            os.makedirs(dir_arch_gri, exist_ok=True)
                            doc_gri_txt = f"""========================================
 GUÍA DE RECEPCIÓN INTERNA (GRI)
========================================
FOLIO: {folio_gri}
MOTIVO: {motivo_gri}
RESPONSABLE: {responsable_gri}
FECHA: {fecha_gri}
----------------------------------------
PRODUCTO INGRESADO:
- {desc_gri} (Código: {codigo_gri})
- Cantidad: {cant_gri}
- Costo Ref: ${costo_estimado_gri:,.2f}
- Lote: {lote_gri} (Venc: {venc_gri})
========================================"""
                            ruta_doc_gri = os.path.join(dir_arch_gri, f"GRI_{folio_gri}.txt")
                            with open(ruta_doc_gri, "w", encoding="utf-8") as f_gri:
                                f_gri.write(doc_gri_txt)
                        except Exception as e:
                            print(f"Error archivando GRI: {e}")

                        st.success(f"✅ ¡GRI #{folio_gri} procesada con éxito! Stock actualizado y documento archivado automáticamente.")
                        st.rerun()

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

    if "ultimo_negocio_config" not in st.session_state or st.session_state.ultimo_negocio_config != negocio_seleccionado:
        st.session_state.ultimo_negocio_config = negocio_seleccionado
        if os.path.exists(ruta_config_json):
            try:
                with open(ruta_config_json, "r", encoding="utf-8") as f:
                    st.session_state.config_ticket = json.load(f)
            except Exception:
                st.session_state.config_ticket = {"nombre_empresa": negocio_seleccionado, "rut_empresa": "", "direccion": "", "iva_tasa": 19.0, "pie_pagina": "", "formato_impresion": "80mm (Térmica Estándar)"}
        else:
            st.session_state.config_ticket = {"nombre_empresa": negocio_seleccionado, "rut_empresa": "", "direccion": "", "iva_tasa": 19.0, "pie_pagina": "", "formato_impresion": "80mm (Térmica Estándar)"}

    tab1, tab2, tab3 = st.tabs(["👥 Usuarios y Cajas", "💳 Formas de Pago", "🖨️ Formato de Tickets e Impresión"])

    with tab1:
        st.markdown("### 👥 Administración de Operadores y Permisos")
        st.info("ℹ️ Crea usuarios, edita sus datos y define a qué módulos pueden acceder. Estos datos se guardan directamente en la tabla 'usuarios' de Supabase.")

        rut_actual = st.session_state.get("negocio_seleccionado")

        # --- 0. OBTENER EL ID INTERNO DE LA EMPRESA ---
        empresa_id_actual = None
        try:
            res_empresa = supabase.table("empresas").select("id").eq("rut_empresa", rut_actual).execute()
            if res_empresa.data:
                empresa_id_actual = res_empresa.data[0]["id"]
        except Exception as e:
            st.error(f"⚠️ Error conectando con la tabla empresas: {e}")

        if not empresa_id_actual:
            st.warning("⚠️ No se encontró el ID de la empresa. Verifica la conexión.")
        else:
            # --- 1. LEER USUARIOS DESDE SUPABASE ---
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

            # --- 2. BUSCADOR Y EDICIÓN DE USUARIOS ---
            st.markdown("#### ⚙️ Crear o Editar Permisos de Usuario")
            
            opciones_usuarios = ["-- ✨ Crear Nuevo Usuario --"] + list(db_usuarios.keys())
            usuario_seleccionado = st.selectbox("🔍 Buscar Usuario a Editar (o Crear Nuevo):", opciones_usuarios)
            
            es_nuevo = (usuario_seleccionado == "-- ✨ Crear Nuevo Usuario --")
            
            def_uid = "" if es_nuevo else usuario_seleccionado
            def_nombre = "" if es_nuevo else db_usuarios[usuario_seleccionado].get("nombre", "")
            def_pass = "" if es_nuevo else db_usuarios[usuario_seleccionado].get("password_hash", "")
            def_rol = "Cajero / Vendedor" if es_nuevo else db_usuarios[usuario_seleccionado].get("rol", "Cajero / Vendedor")
            
            modulos_str = "" if es_nuevo else db_usuarios[usuario_seleccionado].get("modulos", "")
            def_modulos = modulos_str.split(", ") if modulos_str else []

            todos_los_modulos = [
                "🏠 Home / Bienvenida", "📊 Dashboard Ejecutivo", "📦 Inventario y Productos", 
                "💰 Módulo de Ventas (POS)", "🛒 Registrar Compra (CPP)", "📉 Mermas y Ajustes", 
                "📈 Informes y Movimientos (Kardex)", "⚠️ Control y Gestión de Inventario", 
                "📊 Módulo de Finanzas", "📒 Cuadratura Diaria", "📑 Cuentas por Cobrar", 
                "📈 Reportes y Analítica", "📚 Historial de Ventas", "🔄 Notas de Crédito", 
                "🏦 Conciliación y Retiros Seguros", "⚙️ Configuración General", "🔑 Control Maestro de Licencias"
            ]

            # 👇 AQUÍ ESTÁ LA MAGIA: clear_on_submit=True limpia las celdas automáticamente
            with st.form("form_crear_editar_operador", clear_on_submit=True):
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    nuevo_user_id = st.text_input("RUT del Usuario *", value=def_uid, disabled=not es_nuevo, help="RUT de inicio de sesión.")
                    nuevo_nombre_usr = st.text_input("Nombre Completo *", value=def_nombre)
                with col_u2:
                    nuevo_pass_usr = st.text_input("Contraseña de Acceso *", type="password", value=def_pass)
                    idx_rol = ["Cajero / Vendedor", "Bodeguero", "Administrador"].index(def_rol) if def_rol in ["Cajero / Vendedor", "Bodeguero", "Administrador"] else 0
                    nuevo_rol_usr = st.selectbox("Rol Principal", options=["Cajero / Vendedor", "Bodeguero", "Administrador"], index=idx_rol)

                st.markdown("**🔐 Asignación de Permisos (Módulos)**")
                modulos_seleccionados = st.multiselect(
                    "Selecciona a qué módulos podrá entrar este usuario:",
                    options=todos_los_modulos,
                    default=[m for m in def_modulos if m in todos_los_modulos]
                )

                texto_boton = "💾 Registrar Nuevo Operador" if es_nuevo else "🔄 Guardar Cambios"
                btn_guardar_usr = st.form_submit_button(texto_boton, type="primary")

                if btn_guardar_usr:
                    user_limpio = nuevo_user_id.strip()
                    if not user_limpio or not nuevo_pass_usr or not nuevo_nombre_usr:
                        st.warning("⚠️ Debes ingresar el RUT, el Nombre y la Contraseña.")
                    else:
                        registro_usuario = {
                            "empresa_id": empresa_id_actual,
                            "rut_usuario": user_limpio,
                            "nombre": nuevo_nombre_usr.strip(),
                            "password_hash": nuevo_pass_usr.strip(),
                            "rol": nuevo_rol_usr,
                            "modulos": ", ".join(modulos_seleccionados)
                        }
                        
                        try:
                            if es_nuevo:
                                supabase.table("usuarios").insert(registro_usuario).execute()
                                st.success(f"✨ ¡Usuario '{nuevo_nombre_usr}' creado con éxito en Supabase!")
                            else:
                                id_db = db_usuarios[usuario_seleccionado]["id"]
                                supabase.table("usuarios").update(registro_usuario).eq("id", id_db).execute()
                                st.success(f"✅ ¡Permisos actualizados para '{nuevo_nombre_usr}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar en Supabase: {e}")

            if not es_nuevo:
                if st.button(f"🗑️ Eliminar usuario '{def_nombre}'", type="secondary"):
                    try:
                        id_db = db_usuarios[usuario_seleccionado]["id"]
                        supabase.table("usuarios").delete().eq("id", id_db).execute()
                        st.success("Usuario eliminado del sistema.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")

            if not es_nuevo:
                if st.button(f"🗑️ Eliminar usuario '{def_nombre}'", type="secondary"):
                    try:
                        id_db = db_usuarios[usuario_seleccionado]["id"]
                        supabase.table("usuarios").delete().eq("id", id_db).execute()
                        st.success("Usuario eliminado del sistema.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")

    with tab2:
        st.markdown("### 💳 Configuración de Formas de Pago Aceptadas")
        with st.form("form_nueva_forma_pago"):
            nueva_forma = st.text_input("Nueva Forma de Pago")
            btn_add_pago = st.form_submit_button("➕ Agregar Forma de Pago")
            if btn_add_pago and nueva_forma and nueva_forma not in st.session_state.formas_pago_erp:
                st.session_state.formas_pago_erp.append(nueva_forma)
                st.success(f"✅ Forma de pago '{nueva_forma}' agregada.")
        for fp in st.session_state.formas_pago_erp:
            st.markdown(f"- 💳 {fp}")

    with tab3:
        st.markdown("### 🖨️ Datos del Comprobante e Impresión")
        with st.form("form_config_ticket"):
            empresa = st.text_input("Nombre Empresa", value=st.session_state.config_ticket.get("nombre_empresa", ""))
            rut = st.text_input("RUT", value=st.session_state.config_ticket.get("rut_empresa", ""))
            direccion = st.text_input("Dirección", value=st.session_state.config_ticket.get("direccion", ""))
           
            iva_personalizado = st.number_input("Tasa de IVA Local (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.config_ticket.get("iva_tasa", 19.0)), step=1.0)
           
            pie = st.text_input("Pie de Página", value=st.session_state.config_ticket.get("pie_pagina", ""))
          
            formatos_disponibles = ["80mm (Térmica Estándar)", "58mm (Térmica Pequeña)", "Carta / A4"]
            formato_actual = st.session_state.config_ticket.get("formato_impresion", "80mm (Térmica Estándar)")
            idx_formato = formatos_disponibles.index(formato_actual) if formato_actual in formatos_disponibles else 0
          
            formato = st.selectbox("Formato", formatos_disponibles, index=idx_formato)
            btn_guardar_config = st.form_submit_button("💾 Guardar Configuración")
          
            if btn_guardar_config:
                st.session_state.config_ticket = {
                    "nombre_empresa": empresa,
                    "rut_empresa": rut,
                    "direccion": direccion,
                    "iva_tasa": iva_personalizado,
                    "pie_pagina": pie,
                    "formato_impresion": formato
                }
                try:
                    with open(ruta_config_json, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.config_ticket, f, ensure_ascii=False, indent=4)
                    st.success("✅ Configuración e IVA guardados permanentemente.")
                except Exception as e:
                    st.error(f"❌ Error al guardar el archivo: {e}")

        st.markdown("---")
        st.markdown("### 🖼️ Logotipo de la Empresa")
        if os.path.exists(ruta_logo):
            st.image(ruta_logo, width=120, caption="Logotipo actual guardado")
   
        logo_cargado = st.file_uploader("Sube una imagen para tu logo (PNG o JPG)", type=["png", "jpg", "jpeg"], key="uploader_logo_empresa")
        if logo_cargado is not None:
            os.makedirs(tenant_dir, exist_ok=True)
            img = Image.open(logo_cargado)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(ruta_logo, "PNG")
            st.success("✅ ¡Logotipo procesado y actualizado con éxito!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🗂️ Administración de archivos")
    st.write("Gestiona la base de datos de tu negocio: descarga plantillas en blanco, exporta tu información actual o importa cargas masivas.")

    accion = st.radio(
        "¿Qué acción deseas realizar?",
        ("Selecciona una opción...", "Descargar plantilla en blanco", "Exportar base de datos actual", "Importar base de datos"),
        index=0,
        key="radio_adm_archivos_config"
    )

    if accion == "Descargar plantilla en blanco":
        st.info("💡 Descarga esta plantilla para completar tus productos respetando los encabezados requeridos para la carga masiva.")
        if os.path.exists(ruta_plantilla_base):
            with open(ruta_plantilla_base, "rb") as f:
                st.download_button(
                    label="⬇️ Descargar Plantilla Base (Excel)",
                    data=f,
                    file_name="plantilla_base_datos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning("⚠️ No se encontró la plantilla base en el sistema.")

    elif accion == "Exportar base de datos actual":
        st.info("📦 Obtén una copia de seguridad con todos los registros actuales de tu inventario o base de datos.")
        if os.path.exists(ruta_bd_actual):
            with open(ruta_bd_actual, "rb") as f:
                st.download_button(
                    label="⬇️ Descargar mi Base de Datos Actual (Excel)",
                    data=f,
                    file_name="BASE_DE_DATOS_actual.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning("⚠️ Todavía no existe un archivo 'BASE DE DATOS.xlsx' registrado para este negocio.")

    elif accion == "Importar base de datos":
        st.warning("⚠️ *Atención:* Al importar una nueva base de datos, se sobrescribirán los datos actuales de tu negocio.")
      
        archivo_cargado = st.file_uploader("Selecciona tu archivo Excel desde tu equipo", type=["xlsx"], key="uploader_importar_bd")
      
        if archivo_cargado is not None:
            if st.button("🚀 Confirmar y Reemplazar Base de Datos"):
                try:
                    df_nuevo = pd.read_excel(archivo_cargado)
                    df_nuevo.to_excel(ruta_bd_actual, index=False)
                    st.success("✅ ¡Base de datos importada y actualizada con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ocurrió un error al procesar el archivo: {e}")

# ----------------- SECCIÓN VENTAS / POS RÁPIDO (CONECTADO A LA NUBE Y AISLADO) -----------------
elif menu == "💰 Módulo de Ventas (POS)":
    caja_actual = param_caja if 'param_caja' in locals() and param_caja else "Caja Principal"
    rut_actual = st.session_state.get("negocio_seleccionado")
    mostrar_encabezado_con_home(f"Terminal de Ventas - {caja_actual}")

    # --- 0. SELECTOR MULTI-BODEGA PARA EL POS ---
    bodegas_pos = ["Bodega Principal"]
    try:
        res_bod = supabase.table("bodegas").select("nombre").eq("rut_empresa", rut_actual).execute()
        if res_bod.data:
            for r in res_bod.data:
                nb = str(r.get("nombre", "")).strip(' "\'')
                if nb and nb not in bodegas_pos:
                    bodegas_pos.append(nb)
    except Exception:
        pass
        
    bodega_actual = st.selectbox("🏢 Selecciona la Bodega / Sucursal de origen:", bodegas_pos)
    st.markdown("---")

    # --- 1. CABECERA (Modificada con Selector de Tipo de Emisión) ---
    col_doc1, col_doc2, col_doc3 = st.columns(3)
    with col_doc1:
        tipo_documento = st.selectbox("📄 Selecciona el documento:", ["Boleta Electrónica", "Factura Electrónica", "Guía de Despacho", "Nota de Venta Interna"])
    with col_doc2:
        fecha_emision_venta = st.date_input("📅 Fecha de Emisión del Documento")
    with col_doc3:
        # ⚙️ NUEVO: Selector para elegir entre Control Interno o SII Oficial
        modo_operacion = st.radio(
            "⚙️ Tipo de Emisión:",
            ["Control Interno (Libre)", "Oficial (SII)"],
            horizontal=True,
            key="radio_modo_emision"
        )
    
    # Convertimos el texto del radio a formato limpio para la base de datos
    modo_str = "INTERNO" if "Interno" in modo_operacion else "OFICIAL"

    # --- 2. LÓGICA: FACTURAR DESDE UNA GUÍA PREVIA ---
    if tipo_documento == "Factura Electrónica":
        viene_de_guia = st.checkbox("🔗 Facturar desde una Guía de Despacho previa")
        if viene_de_guia:
            col_g1, col_g2 = st.columns([3, 1])
            with col_g1:
                folio_guia_a_facturar = st.text_input("🔎 Ingresa el Folio de la Guía (Ej: 1 o FOLIO_1):")
            with col_g2:
                st.write("")
                if st.button("📥 Cargar Guía", use_container_width=True):
                    if folio_guia_a_facturar:
                        try:
                            res_guia = supabase.table("ventas").select("*").eq("rut_empresa", rut_actual).eq("folio", folio_guia_a_facturar.strip()).execute()
                            if res_guia.data:
                                st.session_state.carrito_ventas = []
                                
                                # 🚨 GUARDAMOS EL FOLIO ORIGEN PARA ELIMINARLO DESPUÉS
                                st.session_state.folio_guia_origen = folio_guia_a_facturar.strip()
                                
                                cliente_de_guia = res_guia.data[0].get("cliente", "")
                                if cliente_de_guia and cliente_de_guia != "Cliente General":
                                    st.session_state.cliente_preseleccionado = cliente_de_guia

                                for item in res_guia.data:
                                    cant = float(item["cantidad"])
                                    monto_total = float(item["monto"])
                                    precio_unitario = monto_total / cant if cant > 0 else 0
                                    
                                    st.session_state.carrito_ventas.append({
                                        "Código": item["codigo_producto"],
                                        "Descripción": item["detalle"],
                                        "Cantidad": cant,
                                        "Precio Unitario": precio_unitario,
                                        "Subtotal": monto_total,
                                        "es_guia_previa": True 
                                    })
                                st.success(f"✅ Guía {folio_guia_a_facturar} cargada exitosamente. Lista para facturar.")
                            else:
                                st.warning("⚠️ No se encontró ninguna guía con ese folio.")
                        except Exception as e:
                            st.error(f"❌ Error al buscar la guía: {e}")
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

    # --- 3. SELECCIÓN DE CLIENTES ---
    cliente_nombre, cliente_rut = "", ""
    if tipo_documento in ["Factura Electrónica", "Guía de Despacho"]:
        try:
            res_clientes = supabase.table("clientes").select("rut, nombre").eq("id_negocio", rut_actual).execute()
            df_clientes_pos = pd.DataFrame(res_clientes.data) if res_clientes.data else pd.DataFrame()
        except Exception as e:
            df_clientes_pos = pd.DataFrame()

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
            
        lista_clientes.insert(0, "-- Selecciona un cliente --")
        
        idx_cliente = 0
        if c_nombre_def:
            for i, etiqueta in enumerate(lista_clientes):
                if etiqueta.startswith(c_nombre_def + " ("):
                    idx_cliente = i
                    break

        cliente_elegido = st.selectbox("👤 Selecciona un cliente registrado:", lista_clientes, index=idx_cliente)
      
        if cliente_elegido and cliente_elegido != "-- Selecciona un cliente --" and " (" in cliente_elegido:
            cliente_nombre = cliente_elegido.split(" (")[0]
            cliente_rut = cliente_elegido.split(" (")[1].replace(")", "")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1: cliente_nombre = st.text_input("Razón Social / Nombre del Cliente", value=c_nombre_def)
            with col_f2: cliente_rut = st.text_input("RUT / Identificación Tributaria", value=c_rut_def)

    # --- PANTALLA DE ÉXITO ---
    if st.session_state.ultimo_recibo is not None:
        st.success("🎉 ¡Transacción completada y archivada con éxito!")
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

    # --- PANTALLA DE PAGO ---
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
            elif forma_pago == "Crédito":
                st.warning("⚖️ Esta venta se enviará automáticamente al módulo de Cuentas por Cobrar.")
                dias_credito = st.number_input("⏳ Días de Crédito (Plazo para pagar):", min_value=1, value=30, step=1)
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
                        
                        # ==========================================================
                        # 🔢 GENERACIÓN INTELIGENTE DE FOLIO CORRELATIVO (SUPABASE)
                        # ==========================================================
                        try:
                            res_f = supabase.table("folios_empresa").select("ultimo_folio_usado").eq("rut_empresa", rut_actual).eq("tipo_documento", tipo_documento).eq("modo", modo_str).execute()
                            if res_f.data and len(res_f.data) > 0:
                                numero_folio_actual = int(res_f.data[0]["ultimo_folio_usado"]) + 1
                                supabase.table("folios_empresa").update({"ultimo_folio_usado": numero_folio_actual}).eq("rut_empresa", rut_actual).eq("tipo_documento", tipo_documento).eq("modo", modo_str).execute()
                            else:
                                numero_folio_actual = 1
                                supabase.table("folios_empresa").insert({
                                    "rut_empresa": rut_actual,
                                    "tipo_documento": tipo_documento,
                                    "modo": modo_str,
                                    "ultimo_folio_usado": numero_folio_actual
                                }).execute()
                        except Exception:
                            # Fallback de seguridad si falla la tabla de folios
                            numero_folio_actual = int(datetime.now().strftime("%H%M%S"))

                        transaccion_id_actual = str(numero_folio_actual)
                        lineas_productos = ""
                        venta_exitosa = True
                        
                        # Si viene de una Guía, borramos la original para no duplicar
                        folio_origen = st.session_state.get("folio_guia_origen")
                        if folio_origen and tipo_documento == "Factura Electrónica":
                            try:
                                supabase.table("ventas").delete().eq("rut_empresa", rut_actual).eq("folio", folio_origen).execute()
                                supabase.table("cuentas_por_cobrar").delete().eq("rut_empresa", rut_actual).eq("folio_venta", folio_origen).execute()
                            except Exception:
                                pass 
                        
                        cfg_actual = st.session_state.get("config_ticket", {})
                        nombre_empresa_sesion = str(st.session_state.get("nombre_empresa", "")).upper()
                        tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_sesion or str(rut_actual) == "219449970012" else 19.0
                        iva_porcentaje = float(cfg_actual.get("iva_tasa", tasa_defecto))
                        tasa_iva_global = iva_porcentaje / 100.0
                        
                        total_neto_ticket = 0.0
                        total_iva_ticket = 0.0
                        total_ila_ticket = 0.0
                        
                        for item in st.session_state.carrito_ventas:
                            lineas_productos += f"- {item['Descripción']} (x{int(item['Cantidad'])}) ... ${item['Subtotal']:,.2f}\n"
                            
                            try:
                                if not item.get("es_guia_previa", False):
                                    codigo_vendido = str(item["Código"])
                                    cantidad_vendida = float(item["Cantidad"])

                                    res_receta_pos = supabase.table("recetas").select("*").eq("rut_empresa", rut_actual).eq("codigo_producto_final", codigo_vendido).execute()
                                    
                                    if res_receta_pos.data:
                                        for componente in res_receta_pos.data:
                                            cod_componente = str(componente["codigo_ingrediente"])
                                            cant_por_pack = float(componente["cantidad_usada"])
                                            cantidad_total_a_descontar = cant_por_pack * cantidad_vendida

                                            res_stock_comp = supabase.table("productos").select("stock").eq("rut_empresa", rut_actual).eq("codigo", cod_componente).eq("bodega", bodega_actual).execute()
                                            
                                            if res_stock_comp.data:
                                                stock_actual_comp = float(res_stock_comp.data[0]["stock"] or 0.0)
                                                nuevo_stock_comp = stock_actual_comp - cantidad_total_a_descontar
                                                
                                                supabase.table("productos").update({"stock": nuevo_stock_comp}).eq("rut_empresa", rut_actual).eq("codigo", cod_componente).eq("bodega", bodega_actual).execute()
                                    else:
                                        res_stock = supabase.table("productos").select("stock").eq("rut_empresa", rut_actual).eq("codigo", codigo_vendido).eq("bodega", bodega_actual).execute()
                                        if res_stock.data:
                                            stock_actual = float(res_stock.data[0]["stock"] or 0.0)
                                            nuevo_stock = stock_actual - cantidad_vendida
                                            supabase.table("productos").update({"stock": nuevo_stock}).eq("rut_empresa", rut_actual).eq("codigo", codigo_vendido).eq("bodega", bodega_actual).execute()
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

                            registro_linea = {
                                "folio": transaccion_id_actual,
                                "rut_empresa": rut_actual,
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
                                "modo_emision": modo_str # 👈 Guardamos si es INTERNO u OFICIAL
                            }
                            
                            try:
                                res_venta = supabase.table("ventas").insert(registro_linea).execute()
                                if not res_venta.data:
                                    venta_exitosa = False
                            except Exception as e:
                                venta_exitosa = False

                        if not venta_exitosa:
                            st.error("❌ Ocurrió un error guardando la venta en Supabase.")
                            st.stop()

                        if forma_pago == "Crédito":
                            fecha_vencimiento_str = (fecha_hora_actual + timedelta(days=dias_credito)).strftime("%Y-%m-%d")
                            registro_cxc = {
                                "rut_empresa": rut_actual,
                                "folio_venta": transaccion_id_actual,
                                "cliente": cliente_nombre if cliente_nombre else "Cliente General",
                                "rut_cliente": cliente_rut if cliente_rut else "Sin RUT",
                                "monto_total": float(total_venta),
                                "saldo_pendiente": float(total_venta),
                                "fecha_emision": fecha_emision_venta.strftime("%Y-%m-%d"),
                                "fecha_vencimiento": fecha_vencimiento_str,
                                "estado": "Pendiente"
                            }
                            try:
                                supabase.table("cuentas_por_cobrar").insert(registro_cxc).execute()
                            except Exception as e:
                                pass

                        st.session_state.items_recibo_actual = st.session_state.carrito_ventas.copy()
                        linea_ila = f"IMP. ESPECÍFICO: ${total_ila_ticket:,.2f}\n" if total_ila_ticket > 0 else ""
                        
                        info_pago = ""
                        if forma_pago == 'Efectivo':
                            info_pago = f"RECIBIDO: ${efectivo_recibido:,.2f}\nVUELTO: ${cambio:,.2f}"
                        elif forma_pago == 'Crédito':
                            info_pago = f"CONDICIÓN: A {dias_credito} DÍAS\nVENCE: {(fecha_hora_actual + timedelta(days=dias_credito)).strftime('%d/%m/%Y')}"
                        
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
{('CLIENTE: ' + cliente_nombre + ' | RUT: ' + cliente_rut + '\n----------------------------------------\n') if tipo_documento in ['Factura Electrónica', 'Guía de Despacho'] else ''}DETALLE:
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
                        st.session_state.estado_pago = False
                        st.rerun()

    # --- PANTALLA PRINCIPAL: BUSCADOR Y CARRITO ---
    else:
        df_nube = pd.DataFrame()
        try:
            res_pos = supabase.table("productos").select("codigo, descripcion, precio_venta, stock, es_exento, impuesto_especifico").eq("rut_empresa", rut_actual).eq("bodega", bodega_actual).limit(10000).execute()
            if res_pos.data:
                df_nube = pd.DataFrame(res_pos.data)
        except Exception as e:
            st.error(f"⚠️ Error conectando al inventario en la nube: {e}")

        if not df_nube.empty:
            col_cod = 'codigo'
            col_desc = 'descripcion'
            col_precio = 'precio_venta'
            col_stock = 'stock'

            metodo_lectura = st.radio("Método de entrada de código:", ["⌨️ Digitar / Lector Físico", "📷 Usar Cámara del Celular"], horizontal=True, key="radio_metodo_pos")
            codigo_escan_pos = ""

            if metodo_lectura == "📷 Usar Cámara del Celular":
                st.markdown("Apunta la cámara al código de barras y captura la foto:")
                foto_capturada = st.camera_input("Capturar código de barras", key="cam_pos")
            else:
                codigo_escan_pos = st.text_input("📷 Digita el código o usa tu pistola láser:", key="input_escan_pos")

            opciones_productos = ["-- Selecciona o busca un producto --"] + [f"{row[col_cod]} - {row[col_desc]}" for idx, row in df_nube.iterrows()]
            prod_sugerido_pos_idx = 0
       
            if codigo_escan_pos:
                match_pos = df_nube[df_nube[col_cod].astype(str) == str(codigo_escan_pos)]
                if not match_pos.empty:
                    match_str_pos = f"{match_pos.iloc[0][col_cod]} - {match_pos.iloc[0][col_desc]}"
                    if match_str_pos in opciones_productos:
                        prod_sugerido_pos_idx = opciones_productos.index(match_str_pos)
                        st.session_state.precio_actual_input = float(match_pos.iloc[0][col_precio] or 0.0)
                        st.session_state.ultimo_prod_sel = match_str_pos

            if "ultimo_prod_sel" not in st.session_state: st.session_state.ultimo_prod_sel = ""
            if "precio_actual_input" not in st.session_state: st.session_state.precio_actual_input = 0.0

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
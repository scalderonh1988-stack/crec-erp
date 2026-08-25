import streamlit as st
import pandas as pd
from datetime import datetime
import io
# Importamos la conexión a tu base de datos y la seguridad de negocio
from data_manager import supabase, get_current_tenant

def mostrar_modulo_historial_ventas(ruta_negocio):
    # --- 🛠️ CORRECCIÓN ESTÉTICA Y LÓGICA DEL ENCABEZADO ---
    col_titulo, col_btn = st.columns([4, 1])
    
    with col_titulo:
        st.markdown("### 📚 Historial de Documentos y Ventas Emitidas")
        st.markdown("📌 **Archivo General:** Explora el registro histórico almacenado en la nube con filtros avanzados.")
        
    with col_btn:
        st.write("") # Pequeño espacio para alinear el botón con el título
        if st.button("🏠 Volver al Home", use_container_width=True, key="btn_home_historial_ventas"):
            # Ahora sí ataca a la variable correcta de tu menú lateral
            st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
            st.rerun()
    
    st.markdown("---")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # 1. Obtener los datos directamente desde Supabase
    try:
        res = supabase.table("ventas").select("*").eq("rut_empresa", str(tenant_id)).execute()
        if not res.data:
            st.info("ℹ️ El historial de ventas está vacío actualmente en la base de datos.")
            return
        
        # Convertir la respuesta de Supabase a un DataFrame de Pandas
        df_ventas = pd.DataFrame(res.data)
        
    except Exception as e:
        st.error(f"❌ Error al conectar con Supabase para obtener el historial: {e}")
        return

    # Ordenar por fecha, del más reciente al más antiguo (si existe la columna)
    if 'fecha' in df_ventas.columns:
        df_ventas = df_ventas.sort_values(by="fecha", ascending=False)
        # Normalizar columnas de fecha
        df_ventas['fecha_dt'] = pd.to_datetime(df_ventas['fecha'], errors='coerce')

    # 📂 PESTAÑAS DE NAVEGACIÓN
    tab_gen, tab_doc, tab_pag, tab_comprobante = st.tabs([
        "📂 Vista General", 
        "📄 Por Tipo de Documento", 
        "💳 Método de Pago",
        "🖨️ Descargar Comprobante"
    ])

    st.markdown("#### 🔍 Panel de Filtros Dinámicos")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        busqueda_libre = st.text_input("🔎 Buscar palabra clave (folio, detalle, etc.)", value="")
    with col_f2:
        limite_filas = st.slider("📄 Mostrar cantidad máxima de registros", min_value=10, max_value=500, value=50, step=10, format="%d")

    # Filtrado base por texto libre
    df_filtrado = df_ventas.copy()
    if busqueda_libre:
        mask = df_filtrado.astype(str).apply(lambda x: x.str.contains(busqueda_libre, case=False, na=False)).any(axis=1)
        df_filtrado = df_filtrado[mask]

    with tab_gen:
        st.markdown("#### 📋 Todos los Documentos Emitidos")
        st.dataframe(df_filtrado.head(limite_filas), use_container_width=True)

    with tab_doc:
        st.markdown("#### 📄 Filtrar por Tipo de Documento")
        col_doc = next((c for c in df_ventas.columns if 'documento' in c.lower() or 'tipo' in c.lower()), None)
        if col_doc:
            tipos_disponibles = ["Todos"] + df_ventas[col_doc].dropna().unique().tolist()
            doc_seleccionado = st.selectbox("Seleccione el Tipo de Documento", options=tipos_disponibles)
            
            df_doc = df_filtrado.copy()
            if doc_seleccionado != "Todos":
                df_doc = df_doc[df_doc[col_doc] == doc_seleccionado]
            st.dataframe(df_doc.head(limite_filas), use_container_width=True)
        else:
            st.info("ℹ️ No se detectó una columna específica de 'documento'.")
            st.dataframe(df_filtrado.head(limite_filas), use_container_width=True)

    with tab_pag:
        st.markdown("#### 💳 Filtrar por Método de Pago")
        col_pag = next((c for c in df_ventas.columns if 'metodo_pago' in c.lower() or 'pago' in c.lower()), None)
        if col_pag:
            estados_disponibles = ["Todos"] + df_ventas[col_pag].dropna().unique().tolist()
            pag_seleccionado = st.selectbox("Seleccione el Método de Pago", options=estados_disponibles)
            
            df_pag = df_filtrado.copy()
            if pag_seleccionado != "Todos":
                df_pag = df_pag[df_pag[col_pag] == pag_seleccionado]
            st.dataframe(df_pag.head(limite_filas), use_container_width=True)
        else:
            st.info("ℹ️ No se detectó una columna específica de 'método de pago'.")
            st.dataframe(df_filtrado.head(limite_filas), use_container_width=True)

    with tab_comprobante:
        st.markdown("#### 🖨️ Búsqueda y Descarga de Comprobante Individual")
        st.markdown("Ingresa o selecciona el Folio (ej. `TX-20260818...`) para obtener el detalle exacto.")
        
        col_id = next((c for c in df_ventas.columns if 'folio' in c.lower() or 'id' in c.lower()), None)
        
        if col_id:
            lista_ids = df_ventas[col_id].dropna().astype(str).tolist()
            id_elegido = st.selectbox("Seleccione el Folio", options=lista_ids)
            
            if id_elegido:
                fila_venta = df_ventas[df_ventas[col_id].astype(str) == id_elegido]
                
                if not fila_venta.empty:
                    st.success("✅ ¡Transacción encontrada con éxito!")
                    st.dataframe(fila_venta, use_container_width=True)
                    
                    detalle_texto = "=== COMPROBANTE DE VENTA ===\n\n"
                    for col in fila_venta.columns:
                        detalle_texto += f"{col.upper()}: {fila_venta.iloc[0][col]}\n"
                    
                    st.download_button(
                        label=f"📥 Descargar Comprobante ({id_elegido})",
                        data=detalle_texto,
                        file_name=f"Comprobante_{id_elegido}.txt",
                        mime="text/plain"
                    )
        else:
            st.warning("⚠️ No se encontró la columna de 'folio'.")

    # Botón global de descarga
    st.divider()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_filtrado.to_excel(writer, index=False)
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte en Excel",
        data=excel_data,
        file_name="Historial_Ventas_Supabase.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
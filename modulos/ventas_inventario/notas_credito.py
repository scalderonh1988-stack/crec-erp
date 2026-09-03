import streamlit as st
import pandas as pd
from datetime import datetime
# Importamos la conexión a tu base de datos y la seguridad de negocio
from data_manager import supabase, get_current_tenant

def mostrar_modulo_notas_credito(ruta_negocio):
    # --- 1. BOTÓN DE VOLVER AL HOME ---
    if st.button("🏠 Volver al Home", use_container_width=True):
        st.session_state["modulo_activo"] = "home"
        st.session_state["menu_seleccionado"] = "🏠 Home / Bienvenida"
        st.rerun()
    st.markdown("---")

    # --- 2. TÍTULOS ---
    st.markdown("### 🔄 Emisión de Notas de Crédito y Devoluciones")
    st.markdown("📌 **Gestión Rápida:** Anula ventas, devuelve stock al inventario y ajusta la cuadratura de caja de forma directa.")

    # --- 3. LECTURA DIRECTA DESDE SUPABASE ---
    tenant_id = get_current_tenant()
    
    try:
        respuesta = supabase.table("ventas").select("*").execute()
        
        if not respuesta.data:
            st.info("ℹ️ No hay ventas registradas en la base de datos para procesar devoluciones.")
            return
            
        df_ventas = pd.DataFrame(respuesta.data)
        
        # Filtro estricto: Solo mostramos las ventas de ESTE negocio
        if tenant_id and not df_ventas.empty:
            col_tenant = next((c for c in df_ventas.columns if c in ["rut_empresa", "id_negocio", "rut_negocio", "negocio_id"]), None)
            if col_tenant:
                df_ventas = df_ventas[df_ventas[col_tenant].astype(str) == str(tenant_id)]
        
        if df_ventas.empty:
            st.info("ℹ️ No hay ventas registradas para este negocio en particular.")
            return

    except Exception as e:
        st.error(f"❌ Error al leer las ventas desde Supabase: {e}")
        return

    col_id = next((c for c in df_ventas.columns if 'transaccion' in c.lower() or 'folio' in c.lower() or 'id' in c.lower()), None)
    col_tipo = next((c for c in df_ventas.columns if 'tipo' in c.lower() or 'documento' in c.lower()), None)
    
    if not col_id:
        st.error("❌ No se encontró una columna de Folio/ID de transacción en la tabla de ventas.")
        return

    # --- PREPARAR LA LISTA DESPLEGABLE DESDE EL MÁS RECIENTE ---
    lista_folios = df_ventas[col_id].dropna().astype(str).unique().tolist()
    lista_folios.reverse()
    opciones_folios = ["Seleccione un folio..."] + lista_folios

    st.markdown("---")
    st.markdown("#### 🔍 1. Buscar Documento Original")
    
    col1, col2 = st.columns(2)
    with col1:
        tipo_doc_busqueda = st.selectbox("Tipo de Documento:", ["Todos", "Boleta", "Factura"])
    with col2:
        folio_busqueda = st.selectbox(
            "Seleccione o escriba el Número de Folio:", 
            options=opciones_folios,
            help="💡 Los documentos están conectados en tiempo real a Supabase."
        )

    # --- 4. BÚSQUEDA Y SELECCIÓN ---
    if st.button("🔍 Buscar Documento", type="primary"):
        if folio_busqueda == "Seleccione un folio...":
            st.warning("⚠️ Por favor, seleccione un número de folio.")
        else:
            df_filtrado = df_ventas.copy()
            df_filtrado[col_id] = df_filtrado[col_id].astype(str)
            folio_limpio = str(folio_busqueda).strip()
            
            df_filtrado = df_filtrado[df_filtrado[col_id] == folio_limpio]
            
            if col_tipo and tipo_doc_busqueda != "Todos":
                df_filtrado[col_tipo] = df_filtrado[col_tipo].astype(str)
                df_filtrado = df_filtrado[df_filtrado[col_tipo].str.contains(tipo_doc_busqueda, case=False, na=False)]

            if df_filtrado.empty:
                st.error(f"❌ No se encontró el folio '{folio_limpio}'.")
            else:
                st.success("✅ Documento localizado. Mostrando detalles abajo.")
                st.session_state["venta_encontrada_nc"] = df_filtrado

    # --- 5. SECCIÓN DE DEVOLUCIÓN ---
    if "venta_encontrada_nc" in st.session_state and st.session_state["venta_encontrada_nc"] is not None:
        df_resultado = st.session_state["venta_encontrada_nc"]
        
        # Mostramos la tabla limpia
        cols_mostrar = [c for c in df_resultado.columns if c not in ["rut_empresa", "id"]]
        st.dataframe(df_resultado[cols_mostrar], use_container_width=True)

        st.markdown("#### 📦 2. Tipo de Devolución")
        tipo_devolucion = st.radio("Seleccione el alcance de la Nota de Crédito:", ["Devolución Total (Anulación Completa)", "Devolución Parcial (Editar cantidades)"])

        col_detalle = next((c for c in df_resultado.columns if c.lower() in ['detalle', 'productos', 'carrito', 'items', 'articulos']), None)

        # PREPARAR DATOS PARA DEVOLUCIÓN PARCIAL
        datos_parciales = []
        if tipo_devolucion == "Devolución Parcial (Editar cantidades)" and col_detalle:
            st.markdown("##### 📝 Ajuste de Cantidades a Devolver")
            st.write("Indica en la columna **'Cantidad a Devolver'** cuántas unidades regresarán a la bodega:")
            
            lista_items = []
            for _, row in df_resultado.iterrows():
                detalle_texto = str(row.get(col_detalle, ""))
                monto_linea = float(row.get('monto', 0))
                
                # Desarmamos el string de tu caja para entender qué producto es
                if " (Cant: " in detalle_texto:
                    desc_prod = detalle_texto.split(" (Cant: ")[0]
                    cant_orig = float(detalle_texto.split(" (Cant: ")[1].replace(")", ""))
                    precio_uni = monto_linea / cant_orig if cant_orig > 0 else 0
                    
                    lista_items.append({
                        "Producto": desc_prod,
                        "Cant. Original": cant_orig,
                        "Cantidad a Devolver": 0.0, # El usuario editará esto
                        "Precio Unitario": precio_uni
                    })
            
            if lista_items:
                df_parcial = pd.DataFrame(lista_items)
                datos_parciales_df = st.data_editor(df_parcial, disabled=["Producto", "Cant. Original", "Precio Unitario"], use_container_width=True)
                datos_parciales = datos_parciales_df.to_dict('records')

        # --- 🚀 BOTÓN FINAL: LA MAGIA EN SUPABASE ---
        if st.button("🚀 Emitir Nota de Crédito y Actualizar Inventario", use_container_width=True):
            try:
                folio_original = str(df_resultado.iloc[0][col_id])
                nuevo_folio_nc = f"NC-{folio_original}"
                fecha_hoy = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # LOGICA: DEVOLUCIÓN TOTAL
                if tipo_devolucion == "Devolución Total (Anulación Completa)":
                    for _, row in df_resultado.iterrows():
                        detalle_texto = str(row.get(col_detalle, ""))
                        monto_linea = float(row.get('monto', 0))
                        
                        # 1. Devolver Stock
                        if " (Cant: " in detalle_texto:
                            desc_prod = detalle_texto.split(" (Cant: ")[0]
                            cant_devolver = float(detalle_texto.split(" (Cant: ")[1].replace(")", ""))
                            
                            res_prod = supabase.table("productos").select("codigo, stock").eq("rut_empresa", str(tenant_id)).eq("descripcion", desc_prod).execute()
                            if res_prod.data:
                                p_data = res_prod.data[0]
                                supabase.table("productos").update({"stock": float(p_data["stock"]) + cant_devolver}).eq("rut_empresa", str(tenant_id)).eq("codigo", p_data["codigo"]).execute()
                        
                        # 2. Registrar el impacto negativo en Caja
                        registro_nc = {
                            "folio": nuevo_folio_nc,
                            "rut_empresa": str(tenant_id),
                            "fecha": fecha_hoy,
                            "detalle": f"DEVOLUCIÓN: {detalle_texto}",
                            "monto": -abs(monto_linea), # Salida de dinero
                            "metodo_pago": row.get('metodo_pago', 'Efectivo'),
                            "documento": "Nota de Crédito"
                        }
                        supabase.table("ventas").insert(registro_nc).execute()

                    st.success("✨ ¡Anulación Total exitosa! El dinero se descontó de la caja y el stock volvió a la bodega.")

                # LOGICA: DEVOLUCIÓN PARCIAL
                else: 
                    hubo_devolucion = False
                    for item in datos_parciales:
                        cant_devolver = float(item["Cantidad a Devolver"])
                        if cant_devolver > 0:
                            hubo_devolucion = True
                            desc_prod = item["Producto"]
                            monto_devolver = cant_devolver * item["Precio Unitario"]
                            
                            # 1. Devolver Stock
                            res_prod = supabase.table("productos").select("codigo, stock").eq("rut_empresa", str(tenant_id)).eq("descripcion", desc_prod).execute()
                            if res_prod.data:
                                p_data = res_prod.data[0]
                                supabase.table("productos").update({"stock": float(p_data["stock"]) + cant_devolver}).eq("rut_empresa", str(tenant_id)).eq("codigo", p_data["codigo"]).execute()
                            
                            # 2. Registrar el impacto negativo en Caja
                            registro_nc = {
                                "folio": nuevo_folio_nc,
                                "rut_empresa": str(tenant_id),
                                "fecha": fecha_hoy,
                                "detalle": f"DEVOLUCIÓN PARCIAL: {desc_prod} (Cant: {cant_devolver})",
                                "monto": -abs(monto_devolver),
                                "metodo_pago": "Efectivo",
                                "documento": "Nota de Crédito"
                            }
                            supabase.table("ventas").insert(registro_nc).execute()
                            
                    if hubo_devolucion:
                        st.success("✨ ¡Devolución Parcial exitosa! Inventario y caja actualizados.")
                    else:
                        st.warning("⚠️ No ingresaste ninguna cantidad para devolver. La operación se canceló.")

                # Limpiamos la pantalla
                del st.session_state["venta_encontrada_nc"]
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error crítico al procesar la devolución en la base de datos: {e}")
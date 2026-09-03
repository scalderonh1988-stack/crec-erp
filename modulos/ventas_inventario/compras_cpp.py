import streamlit as st
import pandas as pd
from datetime import datetime
from modulos.servicios.data_manager import supabase, get_current_tenant

def mostrar_modulo_compras(ruta_negocio):
    st.markdown("### 🛒 Módulo de Recepción de Compras (GRC) y Control de Lotes")
    st.markdown("Registra las facturas o guías de tus proveedores. El sistema sumará el stock (tanto de productos como de ingredientes), recalculará el Costo Promedio Ponderado (CPP) y creará el registro de compras.")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- 1. LECTURA DE DATOS MAESTROS DESDE SUPABASE ---
    try:
        # Cargar Proveedores
        res_prov = supabase.table("proveedores").select("nombre").eq("rut_empresa", str(tenant_id)).execute()
        lista_proveedores = [p["nombre"] for p in res_prov.data] if res_prov.data else ["Proveedor General"]
        
        # Cargar Bodegas para saber a qué sucursal llega la compra
        bodegas_existentes = ["Bodega Principal"]
        res_bodegas = supabase.table("bodegas").select("nombre").eq("rut_empresa", str(tenant_id)).execute()
        if res_bodegas.data:
            for row in res_bodegas.data:
                nombre_b = str(row.get("nombre", "")).strip(' "\'')
                if nombre_b and nombre_b not in bodegas_existentes:
                    bodegas_existentes.append(nombre_b)

        # 🚨 CARGAR PRODUCTOS Y 🚨 CARGAR INGREDIENTES PARA LAS COMPRAS
        res_prod = supabase.table("productos").select("codigo, descripcion").eq("rut_empresa", str(tenant_id)).execute()
        df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()

        res_ing = supabase.table("ingredientes").select("codigo, descripcion").eq("rut_empresa", str(tenant_id)).execute()
        df_ing = pd.DataFrame(res_ing.data) if res_ing.data else pd.DataFrame()

        opciones_productos = []
        
        # Agregamos productos al selector unificado con etiqueta visible
        if not df_prod.empty:
            df_prod = df_prod.drop_duplicates(subset=['codigo'])
            for _, row in df_prod.iterrows():
                opciones_productos.append(f"📦 [Producto] {row['codigo']} - {row['descripcion']}")

        # Agregamos ingredientes al selector unificado con etiqueta visible
        if not df_ing.empty:
            df_ing = df_ing.drop_duplicates(subset=['codigo'])
            for _, row in df_ing.iterrows():
                opciones_productos.append(f"🍅 [Insumo] {row['codigo']} - {row['descripcion']}")

    except Exception as e:
        st.error(f"❌ Error al conectar con los maestros en Supabase: {e}")
        lista_proveedores = ["Proveedor General"]
        bodegas_existentes = ["Bodega Principal"]
        opciones_productos = []

    st.divider()
    st.markdown("#### 📄 1. Cabecera del Documento de Compra")
   
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        proveedor_factura = st.selectbox("Nombre del Proveedor", options=lista_proveedores)
        tipo_recepcion = st.selectbox("Tipo de Recepción", ["Factura Electrónica", "Guía de Despacho", "Boleta", "Otro"])
    with col_h2:
        num_factura = st.text_input("Número de Documento (Factura/Guía)", value="FAC-001")
        fecha_emision = st.date_input("Fecha de Emisión / Compra", value=datetime.today())
    with col_h3:
        bodega_destino = st.selectbox("🏢 Bodega / Sucursal de Recepción:", options=bodegas_existentes)
        condicion_pago = st.selectbox("Condición de Pago", ["Contado", "Crédito", "Cheque"])
        fecha_vencimiento_factura = st.date_input("Vencimiento del Pago (si es Crédito)", value=datetime.today())

    st.divider()
    st.markdown("#### 📦 2. Agregar Productos o Insumos al Documento")
   
    if 'items_compra_actual' not in st.session_state:
        st.session_state.items_compra_actual = []

    with st.form("form_agregar_item_compra"):
        c1, c2, c3 = st.columns(3)
        with c1:
            producto_sel = st.selectbox("Código / Ítem", options=["-- Selecciona un producto o insumo --"] + opciones_productos) if opciones_productos else st.text_input("Código")
            lote = st.text_input("Lote de Producción", value="S/L")
        with c2:
            cant_comprada = st.number_input("Cantidad Recibida", min_value=0.01, value=1.0, step=1.0)
            venc_lote = st.text_input("Vencimiento del Lote (Ej: 2026-12-31)", value="Sin Vencimiento")
        with c3:
            neto_unit = st.number_input("Costo Neto Unitario ($)", min_value=0.0, value=0.0, step=100.0)

        btn_add = st.form_submit_button("➕ Añadir Línea al Documento")
        if btn_add:
            if producto_sel and producto_sel != "-- Selecciona un producto o insumo --":
                # Detectamos si es un Producto o un Insumo según la etiqueta visual
                tipo_item = "Insumo" if "[Insumo]" in producto_sel else "Producto"
                
                # Limpiamos el texto para extraer el código y la descripción real
                limpio = producto_sel.replace("📦 [Producto] ", "").replace("🍅 [Insumo] ", "")
                codigo_prod = limpio.split(" - ")[0]
                desc_p = limpio.split(" - ")[1]
               
                st.session_state.items_compra_actual.append({
                    'tipo': tipo_item,
                    'codigo': str(codigo_prod),
                    'descripcion': desc_p,
                    'cantidad': float(cant_comprada),
                    'neto_unitario': float(neto_unit),
                    'subtotal': float(cant_comprada) * float(neto_unit),
                    'lote': lote,
                    'vencimiento_lote': venc_lote
                })
                st.success(f"Línea Agregada: [{tipo_item}] {desc_p} x {cant_comprada}")
            else:
                st.warning("⚠️ Selecciona un ítem válido.")

    # --- Mostrar tabla temporal de las líneas ---
    if st.session_state.items_compra_actual:
        st.markdown(f"##### Ítems en el Documento N° {num_factura} (Destino: {bodega_destino}):")
        df_temp = pd.DataFrame(st.session_state.items_compra_actual)
        st.dataframe(df_temp[['tipo', 'codigo', 'descripcion', 'lote', 'cantidad', 'neto_unitario', 'subtotal']], use_container_width=True)
       
        monto_total_factura = df_temp['subtotal'].sum()
        st.markdown(f"### 💰 **Total Neto de este Documento: ${monto_total_factura:,.2f}**")

        col_acc1, col_acc2 = st.columns(2)
        with col_acc1:
            if st.button("🗑️ Limpiar / Cancelar Recepción"):
                st.session_state.items_compra_actual = []
                st.rerun()
        with col_acc2:
            if st.button("🚀 Guardar Recepción Definitiva (Nube)", type="primary"):
                try:
                    fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # PROCESAR GUARDADO DEFINITIVO EN SUPABASE
                    for item in st.session_state.items_compra_actual:
                        cant_n = float(item['cantidad'])
                        costo_n = float(item['neto_unitario'])
                        
                        if item['tipo'] == "Producto":
                            # 1A. ACTUALIZAR PRODUCTOS (Stock y CPP)
                            res_p = supabase.table("productos").select("*").eq("rut_empresa", str(tenant_id)).eq("codigo", item['codigo']).eq("bodega", bodega_destino).execute()
                            
                            if res_p.data:
                                prod_actual = res_p.data[0]
                                id_fila = prod_actual['id']
                                stock_actual = float(prod_actual.get('stock', 0) or 0)
                                costo_anterior = float(prod_actual.get('costo', 0) or 0)
                                
                                if (stock_actual + cant_n) > 0:
                                    nuevo_cpp = ((stock_actual * costo_anterior) + (cant_n * costo_n)) / (stock_actual + cant_n)
                                else:
                                    nuevo_cpp = costo_n

                                nuevo_stock = stock_actual + cant_n

                                supabase.table("productos").update({
                                    "stock": nuevo_stock,
                                    "costo": round(nuevo_cpp, 2)
                                }).eq("id", id_fila).execute()
                            else:
                                res_general = supabase.table("productos").select("*").eq("rut_empresa", str(tenant_id)).eq("codigo", item['codigo']).limit(1).execute()
                                if res_general.data:
                                    prod_nuevo = res_general.data[0].copy()
                                    del prod_nuevo['id']
                                    prod_nuevo['bodega'] = bodega_destino
                                    prod_nuevo['stock'] = cant_n
                                    prod_nuevo['costo'] = costo_n
                                    supabase.table("productos").insert(prod_nuevo).execute()
                        else:
                            # 1B. 🍅 ACTUALIZAR INGREDIENTES / INSUMOS (Stock y Costo en la tabla ingredientes)
                            res_ing_db = supabase.table("ingredientes").select("*").eq("rut_empresa", str(tenant_id)).eq("codigo", item['codigo']).eq("bodega", bodega_destino).execute()
                            
                            if res_ing_db.data:
                                ing_actual = res_ing_db.data[0]
                                id_ing_fila = ing_actual['id']
                                stock_ing_act = float(ing_actual.get('stock', 0) or 0)
                                costo_ing_ant = float(ing_actual.get('costo', 0) or 0)
                                
                                if (stock_ing_act + cant_n) > 0:
                                    nuevo_cpp_ing = ((stock_ing_act * costo_ing_ant) + (cant_n * costo_n)) / (stock_ing_act + cant_n)
                                else:
                                    nuevo_cpp_ing = costo_n

                                nuevo_stock_ing = stock_ing_act + cant_n

                                supabase.table("ingredientes").update({
                                    "stock": nuevo_stock_ing,
                                    "costo": round(nuevo_cpp_ing, 2)
                                }).eq("id", id_ing_fila).execute()
                            else:
                                res_ing_gen = supabase.table("ingredientes").select("*").eq("rut_empresa", str(tenant_id)).eq("codigo", item['codigo']).limit(1).execute()
                                if res_ing_gen.data:
                                    ing_nuevo = res_ing_gen.data[0].copy()
                                    del ing_nuevo['id']
                                    ing_nuevo['bodega'] = bodega_destino
                                    ing_nuevo['stock'] = cant_n
                                    ing_nuevo['costo'] = costo_n
                                    supabase.table("ingredientes").insert(ing_nuevo).execute()

                        # 2. REGISTRAR LÍNEA EN LA TABLA COMPRAS (Historial)
                        registro_compra = {
                            'fecha_hora': fecha_registro,
                            'tipo_recepcion': tipo_recepcion,
                            'proveedor': proveedor_factura,
                            'factura': num_factura,
                            'codigo': item['codigo'],
                            'descripcion': f"[{item['tipo']}] {item['descripcion']}",
                            'cantidad': cant_n,
                            'neto_unitario': costo_n,
                            'costo_total': item['subtotal'],
                            'lote': item['lote'],
                            'fecha_vencimiento_lote': item['vencimiento_lote'],
                            'condicion_pago': condicion_pago,
                            'id_negocio': str(tenant_id),
                            'bodega_destino': bodega_destino
                        }
                        
                        try:
                            supabase.table("compras").insert(registro_compra).execute()
                        except Exception:
                            del registro_compra['bodega_destino']
                            supabase.table("compras").insert(registro_compra).execute()

                    # 3. CUENTAS POR PAGAR
                    if condicion_pago in ["Crédito", "Cheque"]:
                        nueva_cuenta = {
                            'rut_empresa': str(tenant_id),
                            'proveedor': proveedor_factura,
                            'numero_factura': num_factura,
                            'fecha_emision': str(fecha_emision),
                            'fecha_vencimiento': str(fecha_vencimiento_factura),
                            'monto_total': float(monto_total_factura),
                            'estado': 'PENDIENTE'
                        }
                        supabase.table("cuentas_por_pagar").insert(nueva_cuenta).execute()

                    # Éxito total
                    st.session_state.items_compra_actual = []
                    st.success(f"🎉 ¡Recepción exitosa! Inventario de productos/insumos y CPP actualizados en '{bodega_destino}'.")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error crítico al procesar la factura: {e}")
    else:
        st.info("ℹ️ Añade al menos un producto o insumo para armar el documento de recepción.")
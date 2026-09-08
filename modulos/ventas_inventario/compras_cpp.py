import streamlit as st
import pandas as pd
from datetime import datetime
from modulos.servicios.data_manager import supabase, get_current_tenant

def mostrar_modulo_compras(ruta_negocio):
    st.markdown("### 🛒 Módulo de Recepción de Compras (GRC) y Control de Lotes")
    st.markdown("Registra las facturas o guías de tus proveedores. El sistema sumará el stock, recalculará el Costo Promedio Ponderado (CPP) y creará el registro de compras.")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    tenant_clean = str(tenant_id).strip().lower()

    # --- 1. LECTURA Y ASOCIACIÓN DE PROVEEDORES DESDE SUPABASE ---
    dict_proveedores = {}  # Mapea Nombre -> Datos completos del Proveedor (RUT, ID, etc.)
    lista_proveedores = ["Proveedor General"]
    bodegas_existentes = ["Bodega Principal"]
    opciones_productos = []

    try:
        # Cargar todos los proveedores registrados en la base de datos sin filtrar por id_negocio
        res_prov = supabase.table("proveedores").select("*").execute()

        if res_prov.data:
            for p in res_prov.data:
                # Capturar la razón social / nombre bajo cualquier varianza de columna en Supabase
                nom_p = (
                    p.get("nombre") or 
                    p.get("razon_social") or 
                    p.get("nombre_proveedor") or 
                    p.get("Nombre_Proveedor") or 
                    p.get("proveedor")
                )
                
                if nom_p and str(nom_p).strip():
                    nom_clean = str(nom_p).strip()
                    lista_proveedores.append(nom_clean)
                    dict_proveedores[nom_clean] = p

            lista_proveedores = list(dict.fromkeys(lista_proveedores))

        # Cargar Bodegas pertenecientes al tenant o generales
        res_bodegas = supabase.table("bodegas").select("*").execute()
        if res_bodegas.data:
            for b in res_bodegas.data:
                emp_b = str(b.get("id_negocio") or b.get("rut_empresa") or b.get("rut") or "").strip().lower()
                if not emp_b or emp_b == tenant_clean:
                    nom_b = b.get("nombre") or b.get("bodega") or b.get("nombre_bodega")
                    if nom_b and str(nom_b).strip():
                        bodegas_existentes.append(str(nom_b).strip())
            bodegas_existentes = list(dict.fromkeys(bodegas_existentes))

        # Cargar Productos e Ingredientes para el selector unificado
        res_prod = supabase.table("productos").select("codigo, descripcion").execute()
        df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()

        res_ing = supabase.table("ingredientes").select("codigo, descripcion").execute()
        df_ing = pd.DataFrame(res_ing.data) if res_ing.data else pd.DataFrame()

        if not df_prod.empty:
            df_prod = df_prod.drop_duplicates(subset=['codigo'])
            for _, row in df_prod.iterrows():
                opciones_productos.append(f"📦 [Producto] {row['codigo']} - {row['descripcion']}")

        if not df_ing.empty:
            df_ing = df_ing.drop_duplicates(subset=['codigo'])
            for _, row in df_ing.iterrows():
                opciones_productos.append(f"🍅 [Insumo] {row['codigo']} - {row['descripcion']}")

    except Exception as e:
        st.error(f"❌ Error al conectar con los datos maestros en Supabase: {e}")

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
                tipo_item = "Insumo" if "[Insumo]" in producto_sel else "Producto"
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

    # --- Mostrar detalle y guardar ---
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

                    # Obtener metadatos del proveedor seleccionado para la asociación en DB
                    datos_prov = dict_proveedores.get(proveedor_factura, {})
                    rut_proveedor = datos_prov.get("rut") or datos_prov.get("rut_proveedor") or ""
                    id_proveedor = datos_prov.get("id") or datos_prov.get("id_proveedor") or ""

                    for item in st.session_state.items_compra_actual:
                        cant_n = float(item['cantidad'])
                        costo_n = float(item['neto_unitario'])
                        
                        # Actualización de Inventario y Cálculo de CPP
                        tabla_inv = "productos" if item['tipo'] == "Producto" else "ingredientes"
                        res_inv = supabase.table(tabla_inv).select("*").eq("codigo", item['codigo']).eq("bodega", bodega_destino).execute()

                        if res_inv.data:
                            prod_actual = res_inv.data[0]
                            stock_act = float(prod_actual.get('stock', 0) or 0)
                            costo_ant = float(prod_actual.get('costo', 0) or 0)
                            nuevo_cpp = ((stock_act * costo_ant) + (cant_n * costo_n)) / (stock_act + cant_n) if (stock_act + cant_n) > 0 else costo_n

                            supabase.table(tabla_inv).update({
                                "stock": stock_act + cant_n,
                                "costo": round(nuevo_cpp, 2)
                            }).eq("id", prod_actual['id']).execute()
                        else:
                            res_gen = supabase.table(tabla_inv).select("*").eq("codigo", item['codigo']).limit(1).execute()
                            if res_gen.data:
                                prod_nuevo = res_gen.data[0].copy()
                                prod_nuevo.pop('id', None)
                                prod_nuevo['bodega'] = bodega_destino
                                prod_nuevo['stock'] = cant_n
                                prod_nuevo['costo'] = costo_n
                                supabase.table(tabla_inv).insert(prod_nuevo).execute()

                        # Insertar registro de la compra
                        registro_compra = {
                            'fecha_hora': fecha_registro,
                            'tipo_recepcion': tipo_recepcion,
                            'proveedor': proveedor_factura,
                            'nombre_proveedor': proveedor_factura,
                            'rut_proveedor': str(rut_proveedor),
                            'id_proveedor': str(id_proveedor),
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
                            'rut_empresa': str(tenant_id),
                            'bodega_destino': bodega_destino
                        }
                        
                        try:
                            supabase.table("compras").insert(registro_compra).execute()
                        except Exception:
                            registro_restringido = {
                                'fecha_hora': fecha_registro,
                                'proveedor': proveedor_factura,
                                'factura': num_factura,
                                'codigo': item['codigo'],
                                'descripcion': f"[{item['tipo']}] {item['descripcion']}",
                                'cantidad': cant_n,
                                'neto_unitario': costo_n,
                                'costo_total': item['subtotal'],
                                'id_negocio': str(tenant_id),
                                'rut_empresa': str(tenant_id)
                            }
                            supabase.table("compras").insert(registro_restringido).execute()

                    # Registro en cuentas por pagar si aplica crédito
                    if condicion_pago in ["Crédito", "Cheque"]:
                        nueva_cuenta = {
                            'rut_empresa': str(tenant_id),
                            'id_negocio': str(tenant_id),
                            'proveedor': proveedor_factura,
                            'rut_proveedor': str(rut_proveedor),
                            'numero_factura': num_factura,
                            'fecha_emision': str(fecha_emision),
                            'fecha_vencimiento': str(fecha_vencimiento_factura),
                            'monto_total': float(monto_total_factura),
                            'estado': 'PENDIENTE'
                        }
                        try:
                            supabase.table("cuentas_por_pagar").insert(nueva_cuenta).execute()
                        except Exception as e_cpp:
                            print(f"Aviso en Cuentas por Pagar: {e_cpp}")

                    st.session_state.items_compra_actual = []
                    st.success(f"🎉 ¡Recepción exitosa! Compra asociada correctamente a {proveedor_factura} en '{bodega_destino}'.")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al procesar la factura: {e}")
    else:
        st.info("ℹ️ Añade al menos un producto o insumo para armar el documento de recepción.")
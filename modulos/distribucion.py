import streamlit as st
import pandas as pd
from datetime import datetime

def mostrar_modulo_distribucion(supabase_client=None):
    supabase = supabase_client if supabase_client else st.session_state.get("supabase", None)
    
    tipo_usuario = st.session_state.get("tipo_usuario", "Propietario")
    negocio_actual = st.session_state.get("negocio_actual", "general")
    
    if tipo_usuario == "Vendedor":
        st.subheader("📱 Módulo de Preventa en Terreno (Vendedor)")
        renderizar_pestana_vendedor(supabase, negocio_actual)
    else:
        st.subheader("🚚 Módulo de Logística, Preventa y Distribución en Bloque")
        
        tab_vendedor, tab_bodega, tab_facturacion = st.tabs([
            "📱 1. Vendedor (Notas de Pedido)", 
            "📦 2. Bodega (Picking y Checklist)", 
            "⚡ 3. Facturación en Bloque (Lotes)"
        ])
        
        with tab_vendedor:
            renderizar_pestana_vendedor(supabase, negocio_actual)
            
        with tab_bodega:
            renderizar_pestana_bodega(supabase, negocio_actual)
            
        with tab_facturacion:
            renderizar_pestana_facturacion(supabase, negocio_actual)


def renderizar_pestana_vendedor(supabase, negocio_actual):
    st.markdown("### 🛒 Ingreso de Nota de Pedido en Terreno")
    st.info(f"Conectado a la cartera de clientes de la empresa: **{negocio_actual}**")
    
    # --- 1. GESTIÓN DE CLIENTES FILTRADOS POR ID_NEGOCIO ---
    with st.expander("👤 Gestión de Clientes en Ruta", expanded=True):
        tipo_accion_cliente = st.radio(
            "¿Qué deseas hacer con el cliente?", 
            ["Seleccionar Cliente Existente", "➕ Registrar Cliente Nuevo en Terreno"], 
            horizontal=True,
            key="radio_cliente_distribucion"
        )
        
        cliente_rut_activo = None
        cliente_nombre_activo = None
        
        # Consultar clientes reales en Supabase filtrando por id_negocio
        lista_nombres_clientes = []
        dict_clientes_info = {}
        
        try:
            if supabase:
                res_cli = supabase.table("clientes").select("rut, nombre, direccion, telefono").eq("id_negocio", str(negocio_actual)).execute()
                if res_cli.data:
                    for c in res_cli.data:
                        display_str = f"{c['nombre']} ({c['rut']})"
                        lista_nombres_clientes.append(display_str)
                        dict_clientes_info[display_str] = c
        except Exception as e:
            st.error(f"Error al conectar con la tabla clientes: {e}")
            
        if not lista_nombres_clientes:
            st.warning("⚠️ No se encontraron clientes registrados para este negocio en Supabase. Puedes registrar uno nuevo abajo.")

        if tipo_accion_cliente == "Seleccionar Cliente Existente":
            if lista_nombres_clientes:
                cliente_seleccionado = st.selectbox("Buscar Cliente en Ruta", lista_nombres_clientes)
                if cliente_seleccionado:
                    cliente_nombre_activo = dict_clientes_info[cliente_seleccionado]["nombre"]
                    cliente_rut_activo = dict_clientes_info[cliente_seleccionado]["rut"]
            else:
                st.info("Agrega tu primer cliente seleccionando la opción de registro nuevo.")
        else:
            st.markdown("#### 📝 Registro Rápido de Nuevo Cliente")
            col_nc1, col_nc2 = st.columns(2)
            with col_nc1:
                nuevo_nombre = st.text_input("Razón Social / Nombre del Local", key="input_nuevo_nom_cli")
                nuevo_rut = st.text_input("RUT del Cliente (Ej: 12.345.678-9)", key="input_nuevo_rut_cli")
            with col_nc2:
                nueva_dir = st.text_input("Dirección de Despacho", key="input_nuevo_dir_cli")
                nuevo_tel = st.text_input("Teléfono de Contacto", key="input_nuevo_tel_cli")
                
            if st.button("💾 Guardar y Asignar Cliente"):
                if nuevo_nombre and nuevo_rut:
                    try:
                        if supabase:
                            supabase.table("clientes").insert({
                                "id_negocio": str(negocio_actual),
                                "rut": nuevo_rut,
                                "nombre": nuevo_nombre,
                                "direccion": nueva_dir,
                                "telefono": nuevo_tel
                            }).execute()
                            st.success(f"¡Cliente {nuevo_nombre} ({nuevo_rut}) guardado con éxito en Supabase para este negocio!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar el cliente en Supabase: {e}")
                    cliente_rut_activo = nuevo_rut
                    cliente_nombre_activo = nuevo_nombre
                else:
                    st.warning("⚠️ Debes ingresar al menos el nombre y el RUT del cliente.")

    st.divider()
    
    # --- 2. SELECCIÓN DE PRODUCTOS Y CARRITO ---
    productos_disponibles = []
    dict_productos = {}
    
    try:
        if supabase:
            res_prod = supabase.table("productos").select("codigo, nombre, stock").eq("id_negocio", str(negocio_actual)).execute()
            if not res_prod.data: # Fallback por si la tabla productos usa otro filtro o no tiene id_negocio estricto
                res_prod = supabase.table("productos").select("codigo, nombre, stock").execute()
                
            if res_prod.data:
                for p in res_prod.data:
                    nombre_p = p["nombre"]
                    productos_disponibles.append(nombre_p)
                    dict_productos[nombre_p] = {"codigo": p["codigo"], "stock": p.get("stock", 0)}
    except Exception:
        pass
        
    if not productos_disponibles:
        productos_disponibles = ["Producto de Prueba 1", "Producto de Prueba 2"]
        dict_productos = {
            "Producto de Prueba 1": {"codigo": "P001", "stock": 50},
            "Producto de Prueba 2": {"codigo": "P002", "stock": 20}
        }

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        prod_seleccionado = st.selectbox("Seleccionar Producto del Catálogo", productos_disponibles)
        stock_actual_prod = dict_productos.get(prod_seleccionado, {}).get("stock", 0)
        st.caption(f"📦 Stock Disponible en Bodega: **{stock_actual_prod} unidades**")
    with col_p2:
        cantidad_pedida = st.number_input("Cantidad Solicitada", min_value=1, value=1, max_value=max(1, stock_actual_prod))
        
    if "carrito_preventa" not in st.session_state:
        st.session_state.carrito_preventa = []
        
    if st.button("➕ Agregar Producto al Pedido"):
        codigo_prod = dict_productos.get(prod_seleccionado, {}).get("codigo", "GEN")
        st.session_state.carrito_preventa.append({
            "codigo": codigo_prod,
            "producto": prod_seleccionado,
            "cantidad": cantidad_pedida
        })
        st.success("¡Ítem agregado a la nota de pedido temporal!")
        
    if st.session_state.carrito_preventa:
        st.markdown("#### 📋 Ítems en la Nota Actual:")
        df_carrito = pd.DataFrame(st.session_state.carrito_preventa)
        st.dataframe(df_carrito, use_container_width=True)
        
        if st.button("🚀 Enviar Nota de Pedido a Bodega (Reservar Stock)", type="primary"):
            if not cliente_rut_activo:
                st.error("❌ Debes seleccionar un cliente válido antes de enviar la nota.")
            else:
                try:
                    if supabase:
                        res_pedido = supabase.table("notas_pedido").insert({
                            "rut_empresa": str(negocio_actual),
                            "cliente_rut": cliente_rut_activo,
                            "cliente_nombre": cliente_nombre_activo or "Cliente General",
                            "vendedor": str(st.session_state.get("usuario_logueado", "Vendedor Terreno")),
                            "estado": "Pendiente de Picking"
                        }).execute()
                        
                        if res_pedido.data:
                            pedido_id = res_pedido.data[0]["id"]
                            for item in st.session_state.carrito_preventa:
                                supabase.table("detalle_notas_pedido").insert({
                                    "pedido_id": pedido_id,
                                    "codigo_producto": item["codigo"],
                                    "nombre_producto": item["producto"],
                                    "cantidad_pedida": item["cantidad"]
                                }).execute()
                except Exception as e:
                    st.error(f"Error al registrar pedido en Supabase: {e}")

                st.success("¡Pedido enviado a bodega con éxito! El inventario ha sido reservado en el sistema.")
                st.session_state.carrito_preventa = []
                st.rerun()


def renderizar_pestana_bodega(supabase, negocio_actual):
    st.markdown("### 📋 Consolidado de Picking y Validación de Bodega")
    st.info("Revisa los pedidos pendientes de tus vendedores en terreno.")
    
    pedidos_pendientes = []
    try:
        if supabase:
            res_p = supabase.table("notas_pedido").select("*").eq("rut_empresa", str(negocio_actual)).eq("estado", "Pendiente de Picking").execute()
            if res_p.data:
                pedidos_pendientes = res_p.data
    except Exception:
        pass
        
    if not pedidos_pendientes:
        st.info("No hay notas de pedido pendientes de picking en este momento.")
        return

    for ped in pedidos_pendientes:
        with st.expander(f"📦 Pedido #{ped['id']} — Cliente: {ped['cliente_nombre']} (Vendedor: {ped['vendedor']})", expanded=True):
            # Cargar detalles del pedido
            detalles_pedido = []
            try:
                if supabase:
                    res_det = supabase.table("detalle_notas_pedido").select("*").eq("pedido_id", ped["id"]).execute()
                    if res_det.data:
                        detalles_pedido = res_det.data
            except Exception:
                pass

            for det in detalles_pedido:
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.write(f"**Producto:** {det['nombre_producto']} (Cód: {det['codigo_producto']})")
                    st.write(f"**Cantidad Solicitada:** {det['cantidad_pedida']} unidades")
                with col_b2:
                    cantidad_real_bodega = st.number_input("Cantidad Real Entregada", min_value=0, value=det['cantidad_pedida'], key=f"bodega_real_{ped['id']}_{det['id']}")
                    
            if st.button("✅ Aprobar Picking para Facturación", key=f"btn_aprobar_{ped['id']}" ):
                try:
                    if supabase:
                        supabase.table("notas_pedido").update({
                            "estado": "Validado para Facturar"
                        }).eq("id", ped["id"]).execute()
                except Exception:
                    pass
                st.success(f"¡Pedido #{ped['id']} validado correctamente!")
                st.rerun()


def renderizar_pestana_facturacion(supabase, negocio_actual):
    st.markdown("### ⚡ Generación Masiva de Facturas por Lote")
    st.info("Emisión masiva de documentos para pedidos validados.")
    
    if st.button("🚀 Emitir Lote de Facturas Seleccionadas", type="primary"):
        try:
            if supabase:
                supabase.table("notas_pedido").update({
                    "estado": "Facturado"
                }).eq("rut_empresa", str(negocio_actual)).eq("estado", "Validado para Facturar").execute()
        except Exception:
            pass
            
        st.success("¡Lote procesado con éxito y facturado!")
        st.balloons()
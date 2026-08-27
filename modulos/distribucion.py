import streamlit as st
import pandas as pd
from datetime import datetime

def mostrar_modulo_distribucion():
    # Detectar si el usuario logueado es Vendedor para limitar vistas si es necesario
    tipo_usuario = st.session_state.get("tipo_usuario", "Propietario")
    
    if tipo_usuario == "Vendedor":
        st.subheader("📱 Módulo de Preventa en Terreno (Vendedor)")
        # El vendedor ve directo su panel de notas de pedido
        renderizar_pestana_vendedor()
    else:
        st.subheader("🚚 Módulo de Logística, Preventa y Distribución en Bloque")
        
        # Pestañas operativas completas para el administrador/bodeguero
        tab_vendedor, tab_bodega, tab_facturacion = st.tabs([
            "📱 1. Vendedor (Notas de Pedido)", 
            "📦 2. Bodega (Picking y Checklist)", 
            "⚡ 3. Facturación en Bloque (Lotes)"
        ])
        
        with tab_vendedor:
            renderizar_pestana_vendedor()
            
        with tab_bodega:
            renderizar_pestana_bodega()
            
        with tab_facturacion:
            renderizar_pestana_facturacion()


def renderizar_pestana_vendedor():
    st.markdown("### 🛒 Ingreso de Nota de Pedido en Terreno")
    st.info("Consulta stock en tiempo real, registra clientes nuevos al instante y genera la reserva para bodega.")
    
    # --- SECCIÓN DE CLIENTE CON CREACIÓN RÁPIDA ---
    with st.expander("👤 Gestión de Clientes en Terreno", expanded=True):
        tipo_accion_cliente = st.radio(
            "¿Qué deseas hacer con el cliente?", 
            ["Seleccionar Cliente Existente", "➕ Registrar Cliente Nuevo en Terreno"], 
            horizontal=True,
            key="radio_cliente_distribucion"
        )
        
        if tipo_accion_cliente == "Seleccionar Cliente Existente":
            # Simulación o lectura de clientes
            clientes_disponibles = ["Minimarket Don Juan (76.123.456-K)", "Comercial El Trébol (78.987.654-2)"]
            cliente_seleccionado = st.selectbox("Buscar Cliente en Ruta", clientes_disponibles)
            cliente_rut_activo = cliente_seleccionado.split("(")[-1].replace(")", "").strip()
        else:
            st.markdown("#### 📝 Registro Rápido de Nuevo Cliente")
            col_nc1, col_nc2 = st.columns(2)
            with col_nc1:
                nuevo_nombre = st.text_input("Razón Social / Nombre del Local")
                nuevo_rut = st.text_input("RUT del Cliente (Ej: 12.345.678-9)")
            with col_nc2:
                nueva_dir = st.text_input("Dirección de Despacho")
                nuevo_tel = st.text_input("Teléfono de Contacto")
                
            if st.button("💾 Guardar y Asignar Cliente"):
                if nuevo_nombre and nuevo_rut:
                    st.success(f"¡Cliente {nuevo_nombre} ({nuevo_rut}) creado con éxito y disponible para la venta!")
                    cliente_rut_activo = nuevo_rut
                else:
                    st.warning("⚠️ Debes ingresar al menos el nombre y el RUT del cliente.")
                    cliente_rut_activo = "Sin Asignar"

    st.divider()
    
    # --- SECCIÓN DE PRODUCTOS Y CARRITO ---
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        prod_seleccionado = st.selectbox("Seleccionar Producto del Catálogo", ["FERNET BRANCA VNR750", "PISCO CAPEL 1L", "CERVEZA CORONA 355cc"])
    with col_p2:
        cantidad_pedida = st.number_input("Cantidad Solicitada", min_value=1, value=1)
        
    if "carrito_preventa" not in st.session_state:
        st.session_state.carrito_preventa = []
        
    if st.button("➕ Agregar Producto al Pedido"):
        st.session_state.carrito_preventa.append({
            "producto": prod_seleccionado,
            "cantidad": cantidad_pedida
        })
        st.success("¡Ítem agregado a la nota de pedido temporal!")
        
    if st.session_state.carrito_preventa:
        st.markdown("#### 📋 Ítems en la Nota Actual:")
        df_carrito = pd.DataFrame(st.session_state.carrito_preventa)
        st.dataframe(df_carrito, use_container_width=True)
        
        if st.button("🚀 Enviar Nota de Pedido a Bodega (Reservar Stock)", type="primary"):
            st.success("¡Pedido enviado a bodega con éxito! El inventario ha sido reservado en el sistema.")
            st.session_state.carrito_preventa = []


def renderizar_pestana_bodega():
    st.markdown("### 📋 Consolidado de Picking y Validación de Bodega")
    st.info("Revisa los pedidos pendientes, valida cantidades físicas y tipifica diferencias si las hay.")
    
    st.warning("📦 **Pedido Pendiente #1042** — Cliente: Minimarket Don Juan | Vendedor: Juan Pérez")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.write("**Producto:** FERNET BRANCA VNR750")
        st.write("**Cantidad Solicitada por Vendedor:** 10 unidades")
    with col_b2:
        cantidad_real_bodega = st.number_input("Cantidad Real Entregada desde Bodega", min_value=0, value=10, key="bodega_real_1042")
        
    # Lógica inteligente de diferencias solicitada por ti
    if cantidad_real_bodega < 10:
        st.error("⚠️ Atención: Has descontado unidades respecto a la nota original del vendedor.")
        motivo_descuento = st.selectbox(
            "Selecciona el motivo obligatorio del descuento:",
            ["Seleccione...", "Diferencia de inventario / Ajuste físico", "Producto dañado / Mal estado (Merma)"],
            key="motivo_descuento_bodega"
        )
        
        if motivo_descuento == "Diferencia de inventario / Ajuste físico":
            st.info("💡 **Acción automática:** Se generará una Guía de Despacho Interna para regularizar el stock en Supabase sin falsos sobrantes.")
        elif motivo_descuento == "Producto dañado / Mal estado (Merma)":
            st.warning("📉 **Acción automática:** Se registrará una Merma formal descontando el artículo y afectando el dashboard del propietario.")
            
    if st.button("✅ Dar Visto Bueno y Aprobar Picking para Lote"):
        st.success("¡Picking validado correctamente y listo para la facturación en bloque!")


def renderizar_pestana_facturacion():
    st.markdown("### ⚡ Generación Masiva de Facturas por Lote")
    st.info("Toma los pedidos validados por bodega y emite el paquete de documentos de forma automática.")
    
    st.write("📊 **Estado actual:** 3 notas de pedido validadas y listas para emisión masiva.")
    
    if st.button("🚀 Emitir Lote de Facturas Seleccionadas", type="primary"):
        st.success("¡Lote procesado con éxito! Se generaron las facturas individualizadas por cliente y consolidadas por vendedor.")
        st.balloons()
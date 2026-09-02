import streamlit as st
import pandas as pd
from datetime import datetime
import os
import streamlit.components.v1 as components

# Importamos la conexión a tu base de datos y la seguridad de negocio
from data_manager import supabase, get_current_tenant
# 📜 Importamos el integrador DTE de OpenFactura
from dte_manager import emitir_dte_openfactura

def obtener_datos_empresa(tenant_id):
    """Recopila y normaliza los datos de la empresa desde session_state y Supabase."""
    datos = {}
    
    # 1. Leer variables de Configuración General almacenadas en session_state
    for cfg_key in ['config_empresa', 'config_ticket', 'datos_empresa', 'empresa_actual']:
        if cfg_key in st.session_state and isinstance(st.session_state[cfg_key], dict):
            datos.update(st.session_state[cfg_key])

    # 2. Consultar en la tabla 'empresas' de Supabase probando distintas columnas de filtro
    for col in ["rut_empresa", "rut", "id", "empresa_id", "id_negocio"]:
        try:
            res = supabase.table("empresas").select("*").eq(col, tenant_id).execute()
            if res.data and len(res.data) > 0:
                for k, v in res.data[0].items():
                    if v and not datos.get(k):
                        datos[k] = v
                break
        except Exception:
            continue

    # 3. Normalizar nombres de campos para asegurar compatibilidad con la plantilla DTE/PDF
    rut_val = datos.get("rut_empresa") or datos.get("rut") or datos.get("rut_emisor") or str(tenant_id)
    dir_val = datos.get("direccion_tributaria") or datos.get("direccion_local") or datos.get("direccion") or "Sin Dirección"
    nombre_val = datos.get("razon_social") or datos.get("nombre_fantasia") or datos.get("nombre_empresa") or datos.get("nombre") or "MI EMPRESA"
    giro_val = datos.get("giro") or datos.get("giro_comercial") or ""

    datos.update({
        "rut": rut_val,
        "rut_empresa": rut_val,
        "rut_emisor": rut_val,
        "direccion": dir_val,
        "direccion_tributaria": dir_val,
        "direccion_local": dir_val,
        "razon_social": nombre_val,
        "nombre_empresa": nombre_val,
        "giro": giro_val
    })
    return datos

def mostrar_modulo_ventas(ruta_negocio):
    st.markdown("### 💰 Módulo de Ventas (POS)")
    st.write("Registra tus ventas y actualiza tu inventario en tiempo real (100% Nube).")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    rut_actual = str(tenant_id)
    caja_actual = "Caja Principal"

    # --- INICIALIZAR VARIABLES DE ESTADO ---
    if 'carrito_ventas' not in st.session_state:
        st.session_state.carrito_ventas = []
    if 'estado_pago' not in st.session_state:
        st.session_state.estado_pago = False
    if 'ultimo_recibo' not in st.session_state:
        st.session_state.ultimo_recibo = None
    if 'pdf_dte_actual' not in st.session_state:
        st.session_state.pdf_dte_actual = None
    if 'items_recibo_actual' not in st.session_state:
        st.session_state.items_recibo_actual = None

    # --- ENCABEZADOS Y CONFIGURACIÓN DEL POS ---
    tipo_documento = st.selectbox("Selecciona el documento:", ["Boleta Electrónica", "Factura Electrónica", "Guía de Despacho"])
    
    modo_inventario = st.radio(
        "📦 Modo de trabajo del POS:",
        ["Control Estricto de Stock (Alerta si no hay inventario)", "Venta Libre / Solo Base de Datos"],
        horizontal=True,
        key="radio_modo_inventario"
    )
    controlar_stock = "Estricto" in modo_inventario

    cliente_nombre, cliente_rut = "", ""

    # 1. Lógica de Selección de Clientes
    if tipo_documento in ["Factura Electrónica", "Guía de Despacho"]:
        try:
            res_clientes = supabase.table("clientes").select("rut, nombre").eq("id_negocio", rut_actual).execute()
            df_clientes_pos = pd.DataFrame(res_clientes.data) if res_clientes.data else pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ Error conectando a la base de clientes en la nube: {e}")
            df_clientes_pos = pd.DataFrame()

        if not df_clientes_pos.empty and "nombre" in df_clientes_pos.columns:
            df_clientes_pos["etiqueta"] = df_clientes_pos["nombre"].astype(str) + " (" + df_clientes_pos["rut"].astype(str) + ")"
            lista_clientes = ["-- Selecciona un cliente --"] + df_clientes_pos["etiqueta"].tolist()
            cliente_elegido = st.selectbox("👤 Selecciona un cliente registrado:", lista_clientes)
          
            if cliente_elegido != "-- Selecciona un cliente --" and " (" in cliente_elegido:
                cliente_nombre = cliente_elegido.split(" (")[0]
                cliente_rut = cliente_elegido.split(" (")[1].replace(")", "")
        else:
            st.warning("⚠️ No hay clientes registrados para este negocio en la nube.")
            col_f1, col_f2 = st.columns(2)
            with col_f1: cliente_nombre = st.text_input("Razón Social / Nombre del Cliente")
            with col_f2: cliente_rut = st.text_input("RUT / Identificación Tributaria")

    # --- PANTALLA DE ÉXITO Y RECIBO ---
    if st.session_state.ultimo_recibo is not None:
        st.success("🎉 ¡Transacción completada y archivada con éxito en la Nube!")
        
        if st.session_state.pdf_dte_actual:
            st.link_button("📄 Ver / Imprimir DTE Oficial (OpenFactura PDF)", st.session_state.pdf_dte_actual, use_container_width=True, type="primary")
            st.divider()

        st.markdown(f'<div class="ticket-box" style="background-color:#f9f9f9; padding:15px; border-radius:10px; font-family:monospace; color:#000;">{st.session_state.ultimo_recibo.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
      
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.download_button("📥 Descargar Comprobante Interno", data=st.session_state.ultimo_recibo, file_name="Comprobante.txt", mime="text/plain", use_container_width=True)
        with col_r2:
            if st.button("➕ Nueva Venta", use_container_width=True, type="primary"):
                st.session_state.ultimo_recibo = None
                st.session_state.pdf_dte_actual = None
                st.session_state.estado_pago = False
                st.session_state.carrito_ventas = []
                st.rerun()

    # --- PANTALLA DE PAGO ---
    elif st.session_state.estado_pago:
        st.markdown("### 💳 2. Formas de Pago")
        if len(st.session_state.carrito_ventas) > 0:
            total_venta = sum(item["Subtotal"] for item in st.session_state.carrito_ventas)
            st.info(f"💰 **Total a Pagar: ${total_venta:,.2f}**")
            
            opciones_pago = ["Efectivo", "Tarjeta / Transbank", "Transferencia", "Consignación", "Fiado", "Crédito"]
            forma_pago = st.selectbox("Selecciona la Forma de Pago:", options=opciones_pago)
       
            efectivo_recibido, cambio = total_venta, 0.0
            if forma_pago == "Efectivo":
                efectivo_recibido = st.number_input("💵 Dinero Recibido ($):", min_value=0.0, value=float(total_venta), step=100.0)
                if efectivo_recibido >= total_venta:
                    cambio = efectivo_recibido - total_venta
                    st.success(f"🟢 **Vuelto: ${cambio:,.2f}**")
                else:
                    st.error("🔴 Monto insuficiente.")

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
                        transaccion_id_actual = f"TX_{fecha_hora_actual.strftime('%Y%m%d%H%M%S')}"

                        # Recopilamos y formateamos los datos de la empresa
                        datos_empresa = obtener_datos_empresa(rut_actual)

                        # 📜 1. EMISIÓN DE DTE EN OPENFACTURA (SII)
                        items_para_dte = [
                            {
                                "nombre": item["Descripción"],
                                "cantidad": item["Cantidad"],
                                "precio_unitario": item["Precio Unitario"]
                            }
                            for item in st.session_state.carrito_ventas
                        ]

                        with st.spinner("📄 Procesando emisión con Impuestos Internos (OpenFactura)..."):
                            res_dte = emitir_dte_openfactura(
                                rut_emisor=datos_empresa.get("rut"),
                                tipo_documento=tipo_documento,
                                items=items_para_dte,
                                rut_receptor=cliente_rut if cliente_rut else "66666666-6",
                                razon_social_receptor=cliente_nombre if cliente_nombre else "Cliente General",
                                datos_empresa=datos_empresa
                            )

                        folio_oficial = transaccion_id_actual
                        pdf_oficial_url = None

                        if res_dte.get("exito"):
                            folio_oficial = str(res_dte.get("folio", transaccion_id_actual))
                            pdf_oficial_url = res_dte.get("pdf_url")
                            st.session_state.pdf_dte_actual = pdf_oficial_url
                        else:
                            st.warning(f"⚠️ Alerta DTE: {res_dte.get('error')}. Se registrará la venta localmente con ID interno.")

                        # ☁️ 2. PREPARAR Y GUARDAR EN SUPABASE
                        registros_para_nube = []
                        lineas_productos = ""
                        
                        for item in st.session_state.carrito_ventas:
                            cant_val = float(item['Cantidad'])
                            cant_str = f"{int(cant_val)}" if cant_val.is_integer() else f"{cant_val:.3f}"
                            lineas_productos += f"- {item['Descripción']} (x{cant_str}) ... ${item['Subtotal']:,.2f}\n"
                            
                            registros_para_nube.append({
                                "rut_empresa": datos_empresa.get("rut"),
                                "transaccion_id": transaccion_id_actual,
                                "folio": folio_oficial,
                                "folio_sii": folio_oficial,
                                "pdf_url": pdf_oficial_url,
                                "fecha_hora": fecha_hora_actual.isoformat(),
                                "caja": caja_actual, 
                                "documento": tipo_documento,
                                "cliente": cliente_nombre if cliente_nombre else "Cliente General",
                                "codigo_producto": str(item["Código"]), 
                                "descripcion": str(item["Descripción"]),
                                "cantidad": float(item["Cantidad"]), 
                                "precio_unitario": float(item["Precio Unitario"]),
                                "subtotal": float(item["Subtotal"]), 
                                "forma_pago": forma_pago,
                                "total_boleta": float(total_venta)
                            })

                        try:
                            respuesta_venta = supabase.table("ventas").insert(registros_para_nube).execute()

                            if not respuesta_venta.data:
                                st.error("❌ Supabase no guardó los datos. Verifica la estructura de la tabla 'ventas'.")
                            else:
                                for item in st.session_state.carrito_ventas:
                                    try:
                                        res_stock = supabase.table("productos").select("stock").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).execute()
                                        if res_stock.data:
                                            stock_actual = float(res_stock.data[0]["stock"] or 0.0)
                                            nuevo_stock = stock_actual - float(item["Cantidad"])
                                            supabase.table("productos").update({"stock": nuevo_stock}).eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).execute()
                                    except Exception as e:
                                        st.warning(f"⚠️ No se pudo descontar el stock del producto {item['Código']}")

                                # Generar Recibo de texto impreso
                                nombre_emp = datos_empresa.get("razon_social", "MI EMPRESA")
                                rut_emp = datos_empresa.get("rut", rut_actual)
                                dir_emp = datos_empresa.get("direccion", "Sin Dirección")
                                giro_emp = datos_empresa.get("giro", "")
                                pie_pag = st.session_state.get('config_ticket', {}).get('pie_pagina', 'Gracias por su preferencia')

                                str_giro = f"GIRO: {giro_emp}\n" if giro_emp else ""
                                str_cliente = f"CLIENTE: {cliente_nombre}\nRUT CLIENTE: {cliente_rut}\n----------------------------------------\n" if (tipo_documento in ['Factura Electrónica', 'Guía de Despacho'] or cliente_nombre) else ""

                                texto_recibo = f"""========================================
       {nombre_emp}
       RUT: {rut_emp}
       {dir_emp}
       {str_giro}========================================
DOCUMENTO: {tipo_documento.upper()}
FOLIO SII: N° {folio_oficial}
FECHA: {fecha_hora_actual.strftime('%d/%m/%Y %H:%M:%S')}
TERMINAL: {caja_actual}
----------------------------------------
{str_cliente}DETALLE:
{lineas_productos}----------------------------------------
TOTAL: ${total_venta:,.2f}
PAGO: {forma_pago.upper()}
{('RECIBIDO: $' + f'{efectivo_recibido:,.2f}' + chr(10) + 'VUELTO: $' + f'{cambio:,.2f}') if forma_pago == 'Efectivo' else ''}
========================================
{pie_pag}
========================================"""

                                st.session_state.ultimo_recibo = texto_recibo
                                st.session_state.estado_pago = False
                                st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al enviar la venta a Supabase: {e}")
        else:
            st.warning("⚠️ Carrito vacío.")
            if st.button("Volver"):
                st.session_state.estado_pago = False
                st.rerun()

    # --- PANTALLA PRINCIPAL: BUSCADOR Y CARRITO ---
    else:
        df_nube = pd.DataFrame()
        try:
            res_pos = supabase.table("productos").select("codigo, descripcion, precio_venta, stock, unidad").eq("rut_empresa", rut_actual).limit(10000).execute()
            if res_pos.data:
                df_nube = pd.DataFrame(res_pos.data)
        except Exception as e:
            st.error(f"⚠️ Error conectando al inventario en la nube: {e}")

        if not df_nube.empty:
            metodo_lectura = st.radio("Método de entrada de código:", ["⌨️ Digitar / Lector Físico", "📷 Usar Cámara del Celular"], horizontal=True, key="radio_metodo_pos")
            
            if "prod_seleccionado_key" not in st.session_state:
                st.session_state.prod_seleccionado_key = "-- Selecciona o busca un producto --"
            if "precio_actual_input" not in st.session_state:
                st.session_state.precio_actual_input = 0.0

            opciones_productos = ["-- Selecciona o busca un producto --"] + [f"{row['codigo']} - {row['descripcion']}" for idx, row in df_nube.iterrows()]

            if metodo_lectura == "📷 Usar Cámara del Celular":
                foto_capturada = st.camera_input("Capturar código de barras", key="cam_pos")
                if foto_capturada is not None:
                    st.success("✔️ ¡Foto capturada con éxito!")
            else:
                def procesar_codigo_escaneado():
                    codigo_ingresado = st.session_state.get("input_escan_pos", "").strip()
                    if codigo_ingresado:
                        match_scan = df_nube[df_nube['codigo'].astype(str) == str(codigo_ingresado)]
                        if not match_scan.empty:
                            encontrado_str = f"{match_scan.iloc[0]['codigo']} - {match_scan.iloc[0]['descripcion']}"
                            st.session_state.prod_seleccionado_key = encontrado_str
                            st.session_state.precio_actual_input = float(match_scan.iloc[0]['precio_venta'] or 0.0)
                            st.success(f"✔️ Producto detectado: {encontrado_str}")
                        else:
                            st.warning(f"⚠️ No se encontró ningún producto con el código: {codigo_ingresado}")
                    
                    st.session_state["input_escan_pos"] = ""

                st.text_input(
                    "🔍 Escanea el código de barras (El cursor debe estar aquí):", 
                    key="input_escan_pos", 
                    on_change=procesar_codigo_escaneado,
                    help="El lector escribirá aquí y seleccionará el producto automáticamente al presionar Enter."
                )

            current_val = st.session_state.prod_seleccionado_key
            if current_val not in opciones_productos:
                current_val = "-- Selecciona o busca un producto --"
            idx_actual = opciones_productos.index(current_val)

            def actualizar_desde_selectbox():
                val_elegido = st.session_state.selectbox_producto_venta
                st.session_state.prod_seleccionado_key = val_elegido
                if val_elegido != "-- Selecciona o busca un producto --":
                    c_buscado = val_elegido.split(" - ")[0]
                    match_row = df_nube[df_nube['codigo'].astype(str) == str(c_buscado)]
                    if not match_row.empty:
                        st.session_state.precio_actual_input = float(match_row.iloc[0]['precio_venta'] or 0.0)
                else:
                    st.session_state.precio_actual_input = 0.0

            producto_seleccionado = st.selectbox(
                "O selecciona manualmente el producto:", 
                options=opciones_productos, 
                index=idx_actual, 
                key="selectbox_producto_venta",
                on_change=actualizar_desde_selectbox
            )

            unidad_actual = "UN"
            if st.session_state.prod_seleccionado_key != "-- Selecciona o busca un producto --":
                c_buscado = st.session_state.prod_seleccionado_key.split(" - ")[0]
                match_row = df_nube[df_nube['codigo'].astype(str) == str(c_buscado)]
                if not match_row.empty and 'unidad' in match_row.columns:
                    val_u = str(match_row.iloc[0]['unidad'] or 'UN').strip().upper()
                    if val_u:
                        unidad_actual = val_u

            es_decimal = unidad_actual in ["GR", "KG", "GRAMO", "GRAMOS", "KILO", "KILOS", "LT", "LITRO"]

            with st.form("form_agregar_item"):
                col_cant, col_precio_input = st.columns(2)
                with col_cant:
                    if es_decimal:
                        cantidad_vendida = st.number_input(
                            "Cantidad (Decimales / GR)", 
                            min_value=0.001, 
                            step=0.010, 
                            value=1.000, 
                            format="%.3f",
                            key=f"cant_dec_{st.session_state.prod_seleccionado_key}"
                        )
                    else:
                        cantidad_vendida = st.number_input(
                            "Cantidad (Enteros / UN)", 
                            min_value=1, 
                            step=1, 
                            value=1, 
                            format="%d",
                            key=f"cant_int_{st.session_state.prod_seleccionado_key}"
                        )

                with col_precio_input:
                    precio_venta = st.number_input("Precio Unitario ($)", min_value=0.0, step=1.0, value=float(st.session_state.precio_actual_input))

                btn_agregar = st.form_submit_button("➕ Agregar al Carrito de Venta")

                if btn_agregar:
                    if st.session_state.prod_seleccionado_key == "-- Selecciona o busca un producto --":
                        st.warning("⚠️ Selecciona un producto válido.")
                    else:
                        c_buscado = st.session_state.prod_seleccionado_key.split(" - ")[0]
                        match_row = df_nube[df_nube['codigo'].astype(str) == str(c_buscado)]
                        stock_disponible = float(match_row.iloc[0]['stock'] or 0.0) if not match_row.empty else 0.0

                        unidades_en_carrito = sum(item["Cantidad"] for item in st.session_state.carrito_ventas if item["Código"] == c_buscado)
                        total_intentado = unidades_en_carrito + float(cantidad_vendida)

                        if controlar_stock and total_intentado > stock_disponible:
                            st.error(f"🚨 **¡Inventario Insuficiente!** Stock disponible: {stock_disponible:,.2f} | Intentas vender: {total_intentado:,.2f}")
                        else:
                            st.session_state.carrito_ventas.append({
                                "Código": c_buscado,
                                "Descripción": st.session_state.prod_seleccionado_key.split(" - ")[1],
                                "Cantidad": float(cantidad_vendida),
                                "Precio Unitario": float(precio_venta),
                                "Subtotal": float(cantidad_vendida) * float(precio_venta),
                                "Unidad": unidad_actual
                            })
                            st.session_state.prod_seleccionado_key = "-- Selecciona o busca un producto --"
                            st.success("✅ Producto agregado con éxito.")
                            st.rerun()
        else:
            st.info("ℹ️ Aún no hay productos registrados en tu base de datos.")

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
                with col_c2: st.text(item["Descripción"])
                with col_c3:
                    item_u = str(item.get("Unidad", "UN")).strip().upper()
                    if item_u in ["GR", "KG", "GRAMO", "GRAMOS", "KILO", "KILOS", "LT", "LITRO"]:
                        nc = st.number_input("Cant", min_value=0.001, step=0.01, value=float(item["Cantidad"]), format="%.3f", key=f"cant_{i}", label_visibility="collapsed")
                    else:
                        nc = st.number_input("Cant", min_value=1, step=1, value=int(item["Cantidad"]), format="%d", key=f"cant_{i}", label_visibility="collapsed")
                    
                    st.session_state.carrito_ventas[i]["Cantidad"] = float(nc)
                    st.session_state.carrito_ventas[i]["Subtotal"] = float(nc) * st.session_state.carrito_ventas[i]["Precio Unitario"]
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
                if st.button("🗑️ Vaciar Carrito Completo", use_container_width=True):
                    st.session_state.carrito_ventas = []
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
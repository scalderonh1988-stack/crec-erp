import os
import sys
import json
import re
from datetime import datetime, date, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

# Importaciones desde los módulos de servicios
from modulos.servicios import data_manager
from modulos.servicios import dte_manager

# Funciones y objetos globales requeridos dentro de caja_ventas
from modulos.servicios.data_manager import (
    get_current_tenant,
    supabase
)
from modulos.servicios.dte_manager import emitir_dte_openfactura


def generar_nombre_archivo_doc(tipo_doc, folio, nombre_cliente, fecha_dt):
    """
    Genera el nombre estandarizado del archivo:
    EJ: GD#3MARISELAVALLE04092026
    """
    prefijos = {
        "Guía de Despacho": "GD",
        "Factura Electrónica": "FE",
        "Boleta Electrónica": "BE"
    }
    prefijo = prefijos.get(tipo_doc, "DOC")
    
    # Limpiar nombre del cliente: solo caracteres alfanuméricos en mayúsculas
    nombre_clean = re.sub(r'[^A-Za-z0-9]', '', str(nombre_cliente or "CLIENTE")).upper()
    if not nombre_clean:
        nombre_clean = "CLIENTEGENERAL"
        
    fecha_str = fecha_dt.strftime("%d%m%Y")
    folio_clean = str(folio).replace("TX_", "")
    
    return f"{prefijo}#{folio_clean}{nombre_clean}{fecha_str}"


def _normalizar_datos_empresa(datos):
    """Auxiliar para formatear los datos de la empresa emisora."""
    nombre_val = datos.get("razon_social") or datos.get("empresa_nombre") or datos.get("nombre_fantasia") or datos.get("nombre") or "MI EMPRESA"
    rut_val = datos.get("rut_empresa") or datos.get("rut") or datos.get("rut_emisor") or "Sin RUT"
    dir_val = datos.get("direccion_tributaria") or datos.get("direccion") or datos.get("direccion_local") or "Sin Dirección"
    giro_val = datos.get("giro") or datos.get("giro_emisor") or ""
    comuna_val = datos.get("comuna") or datos.get("comuna_emisor") or ""
    tel_val = datos.get("telefono") or datos.get("telefono_emisor") or datos.get("celular") or ""
    email_val = datos.get("email") or datos.get("correo") or ""
    pie_val = datos.get("pie_pagina") or datos.get("pie_ticket") or "¡Gracias por su preferencia!"

    return {
        "rut": rut_val,
        "rut_empresa": rut_val,
        "rut_emisor": rut_val,
        "direccion": dir_val,
        "direccion_tributaria": dir_val,
        "direccion_emisor": dir_val,
        "razon_social": nombre_val,
        "empresa_nombre": nombre_val,
        "nombre": nombre_val,
        "giro": giro_val,
        "giro_emisor": giro_val,
        "comuna": comuna_val,
        "telefono": tel_val,
        "email": email_val,
        "pie_pagina": pie_val
    }


def obtener_datos_empresa(tenant_id=None):
    """Recopila los datos de la empresa emisora."""
    datos = {}
    
    for cfg_key in ['datos_empresa', 'config_ticket', 'empresa']:
        if cfg_key in st.session_state and isinstance(st.session_state[cfg_key], dict):
            for k, v in st.session_state[cfg_key].items():
                if v and not datos.get(k):
                    datos[k] = str(v).strip()

    for k in ["rut_empresa", "direccion_tributaria", "direccion", "razon_social", "giro", "comuna", "telefono", "email"]:
        if k in st.session_state and st.session_state[k]:
            datos[k] = str(st.session_state[k]).strip()

    candidatos = []
    if isinstance(tenant_id, dict):
        if tenant_id.get("empresa_id"): candidatos.append(str(tenant_id["empresa_id"]))
        if tenant_id.get("rut_usuario"): candidatos.append(str(tenant_id["rut_usuario"]))
        if tenant_id.get("id"): candidatos.append(str(tenant_id["id"]))
    elif tenant_id:
        candidatos.append(str(tenant_id))

    usr_sess = st.session_state.get("usuario") or st.session_state.get("user") or {}
    if isinstance(usr_sess, dict):
        if usr_sess.get("empresa_id"): candidatos.append(str(usr_sess["empresa_id"]))
        if usr_sess.get("rut_usuario"): candidatos.append(str(usr_sess["rut_usuario"]))
        if usr_sess.get("id"): candidatos.append(str(usr_sess["id"]))

    if st.session_state.get("empresa_id_actual"):
        candidatos.append(str(st.session_state["empresa_id_actual"]))
    if st.session_state.get("rut"):
        candidatos.append(str(st.session_state["rut"]))

    candidatos_limpios = []
    for c in candidatos:
        c_clean = str(c).split("-")[0].replace(".", "").strip()
        if c_clean and c_clean not in candidatos_limpios:
            candidatos_limpios.append(c_clean)

    empresa_ids_a_buscar = list(candidatos_limpios)
    for cand in candidatos_limpios:
        try:
            res_u = None
            if cand.isdigit():
                res_u = supabase.table("usuarios").select("empresa_id").eq("id", int(cand)).execute()
            if not res_u or not res_u.data:
                res_u = supabase.table("usuarios").select("empresa_id").ilike("rut_usuario", f"{cand}%").execute()

            if res_u and res_u.data:
                emp_id_found = str(res_u.data[0].get("empresa_id") or "").strip()
                if emp_id_found and emp_id_found not in empresa_ids_a_buscar:
                    empresa_ids_a_buscar.insert(0, emp_id_found)
        except Exception:
            pass

    empresa_encontrada = None
    for target in empresa_ids_a_buscar:
        for tabla in ["empresas", "tenants", "configuracion_negocio"]:
            try:
                res = supabase.table(tabla).select("*").ilike("rut_empresa", f"{target}%").execute()
                if not res.data:
                    res = supabase.table(tabla).select("*").ilike("rut", f"{target}%").execute()
                if not res.data and target.isdigit():
                    res = supabase.table(tabla).select("*").eq("id", int(target)).execute()

                if res.data and len(res.data) > 0:
                    empresa_encontrada = res.data[0]
                    break
            except Exception:
                continue
        if empresa_encontrada:
            break

    if not empresa_encontrada:
        for tabla in ["empresas", "tenants"]:
            try:
                res_fb = supabase.table(tabla).select("*").order("id", desc=True).limit(1).execute()
                if res_fb.data:
                    empresa_encontrada = res_fb.data[0]
                    break
            except Exception:
                pass

    if empresa_encontrada:
        for k, v in empresa_encontrada.items():
            if v:
                datos[k] = str(v).strip()

    return _normalizar_datos_empresa(datos)


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
    if 'ultimo_html' not in st.session_state:
        st.session_state.ultimo_html = None
    if 'pdf_dte_actual' not in st.session_state:
        st.session_state.pdf_dte_actual = None
    if 'nombre_archivo_descarga' not in st.session_state:
        st.session_state.nombre_archivo_descarga = "Comprobante"

    # Persistent client state variables
    if 'cliente_nombre' not in st.session_state:
        st.session_state.cliente_nombre = "Cliente General"
    if 'cliente_rut' not in st.session_state:
        st.session_state.cliente_rut = "66666666-6"
    if 'cliente_direccion' not in st.session_state:
        st.session_state.cliente_direccion = "Sin Dirección"

    # --- ENCABEZADOS Y CONFIGURACIÓN DEL POS ---
    col_doc, col_inv = st.columns(2)
    with col_doc:
        tipo_documento = st.selectbox("Selecciona el documento:", ["Boleta Electrónica", "Factura Electrónica", "Guía de Despacho"])
    with col_inv:
        modo_inventario = st.radio(
            "📦 Modo de trabajo del POS:",
            ["Control Estricto de Stock", "Venta Libre / Solo Base de Datos"],
            horizontal=True,
            key="radio_modo_inventario"
        )
    controlar_stock = "Estricto" in modo_inventario

    # --- LÓGICA DE SELECCIÓN DE CLIENTE ---
    st.markdown("#### 👤 Datos del Cliente / Receptor")
    try:
        res_clientes = supabase.table("clientes").select("rut, nombre, direccion").eq("id_negocio", rut_actual).execute()
        df_clientes_pos = pd.DataFrame(res_clientes.data) if res_clientes.data else pd.DataFrame()
    except Exception:
        df_clientes_pos = pd.DataFrame()

    if not df_clientes_pos.empty and "nombre" in df_clientes_pos.columns:
        df_clientes_pos["etiqueta"] = df_clientes_pos["nombre"].astype(str) + " (" + df_clientes_pos["rut"].astype(str) + ")"
        lista_clientes = ["-- Cliente General --"] + df_clientes_pos["etiqueta"].tolist() + ["+ Ingresar Cliente Manualmente"]
        cliente_elegido = st.selectbox("Selecciona o busca un cliente registrado:", lista_clientes)
      
        if cliente_elegido == "+ Ingresar Cliente Manualmente":
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1: st.session_state.cliente_nombre = st.text_input("Razón Social / Nombre", key="input_cli_nom")
            with col_f2: st.session_state.cliente_rut = st.text_input("RUT Cliente", key="input_cli_rut")
            with col_f3: st.session_state.cliente_direccion = st.text_input("Dirección Cliente", key="input_cli_dir")
        elif cliente_elegido != "-- Cliente General --":
            r_sel = cliente_elegido.split(" (")[1].replace(")", "").strip()
            match_cli = df_clientes_pos[df_clientes_pos["rut"].astype(str) == r_sel]
            if not match_cli.empty:
                st.session_state.cliente_nombre = str(match_cli.iloc[0]["nombre"])
                st.session_state.cliente_rut = str(match_cli.iloc[0]["rut"])
                st.session_state.cliente_direccion = str(match_cli.iloc[0].get("direccion") or "Sin Dirección")
        else:
            st.session_state.cliente_nombre = "Cliente General"
            st.session_state.cliente_rut = "66666666-6"
            st.session_state.cliente_direccion = "Sin Dirección"
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: st.session_state.cliente_nombre = st.text_input("Razón Social / Nombre", value=st.session_state.cliente_nombre, key="input_c1")
        with col_f2: st.session_state.cliente_rut = st.text_input("RUT Cliente", value=st.session_state.cliente_rut, key="input_c2")
        with col_f3: st.session_state.cliente_direccion = st.text_input("Dirección Cliente", value=st.session_state.cliente_direccion, key="input_c3")

    st.divider()

    # --- PANTALLA DE ÉXITO Y RECIBO ---
    if st.session_state.ultimo_recibo is not None:
        st.success("🎉 ¡Transacción completada y archivada con éxito en la Nube!")
        
        if st.session_state.pdf_dte_actual:
            st.link_button("📄 Ver / Imprimir DTE Oficial (OpenFactura PDF)", st.session_state.pdf_dte_actual, use_container_width=True, type="primary")
            st.divider()

        if st.session_state.ultimo_html:
            st.components.v1.html(st.session_state.ultimo_html, height=580, scrolling=True)

        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.download_button(
                "📥 Descargar Documento (.html)", 
                data=st.session_state.ultimo_html, 
                file_name=f"{st.session_state.nombre_archivo_descarga}.html", 
                mime="text/html", 
                use_container_width=True
            )
        with col_r2:
            st.download_button(
                "📥 Descargar Texto (.txt)", 
                data=st.session_state.ultimo_recibo, 
                file_name=f"{st.session_state.nombre_archivo_descarga}.txt", 
                mime="text/plain", 
                use_container_width=True
            )
        with col_r3:
            if st.button("➕ Nueva Venta", use_container_width=True, type="primary"):
                st.session_state.ultimo_recibo = None
                st.session_state.ultimo_html = None
                st.session_state.pdf_dte_actual = None
                st.session_state.estado_pago = False
                st.session_state.carrito_ventas = []
                st.rerun()

    # --- PANTALLA DE PAGO ---
    elif st.session_state.estado_pago:
        st.markdown("### 💳 Formas de Pago")
        if len(st.session_state.carrito_ventas) > 0:
            total_venta = sum(item["Subtotal"] for item in st.session_state.carrito_ventas)
            st.info(f"💰 **Total a Pagar: ${total_venta:,.2f}**")
            
            opciones_pago = ["Efectivo", "Tarjeta / Transbank", "Transferencia", "Consignación", "Fiado", "Crédito"]
            forma_pago = st.selectbox("Selecciona la Forma / Condición de Pago:", options=opciones_pago)
       
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
                if st.button("✅ Confirmar Pago y Generar Documento", use_container_width=True, type="primary"):
                    if forma_pago == "Efectivo" and efectivo_recibido < total_venta:
                        st.warning("⚠️ Monto insuficiente para procesar la venta.")
                    else:
                        fecha_hora_actual = datetime.now()
                        transaccion_id_actual = f"TX_{fecha_hora_actual.strftime('%Y%m%d%H%M%S')}"

                        # 1. DATOS DEL EMISOR (VENDEDOR)
                        datos_empresa = obtener_datos_empresa(rut_actual)

                        # 2. DATOS DEL RECEPTOR (CLIENTE COMPRADOR)
                        cli_nombre = st.session_state.get("cliente_nombre") or "Cliente General"
                        cli_rut = st.session_state.get("cliente_rut") or "66666666-6"
                        cli_dir = st.session_state.get("cliente_direccion") or "Sin Dirección"

                        items_para_dte = [
                            {
                                "nombre": item["Descripción"],
                                "cantidad": item["Cantidad"],
                                "precio_unitario": item["Precio Unitario"]
                            }
                            for item in st.session_state.carrito_ventas
                        ]

                        with st.spinner("📄 Procesando emisión DTE..."):
                            res_dte = emitir_dte_openfactura(
                                rut_emisor=datos_empresa.get("rut"),
                                tipo_documento=tipo_documento,
                                items=items_para_dte,
                                rut_receptor=cli_rut,
                                razon_social_receptor=cli_nombre,
                                datos_empresa=datos_empresa
                            )

                        folio_oficial = "3" if "Guía" in tipo_documento else transaccion_id_actual
                        pdf_oficial_url = None

                        if res_dte.get("exito"):
                            folio_oficial = str(res_dte.get("folio", folio_oficial))
                            pdf_oficial_url = res_dte.get("pdf_url")
                            st.session_state.pdf_dte_actual = pdf_oficial_url

                        # Generar el nombre de archivo estandarizado
                        nombre_archivo_doc = generar_nombre_archivo_doc(
                            tipo_doc=tipo_documento,
                            folio=folio_oficial,
                            nombre_cliente=cli_nombre,
                            fecha_dt=fecha_hora_actual
                        )
                        st.session_state.nombre_archivo_descarga = nombre_archivo_doc

                        # CÁLCULOS TRIBUTARIOS DE DESGLOSE (ESTÁNDAR CHILENO)
                        monto_neto = round(total_venta / 1.19)
                        monto_iva = round(total_venta - monto_neto)
                        imp_especifico = 0.0  # Ajustable según productos con ILA u otros impuestos

                        # Guardar en Supabase
                        registros_para_nube = []
                        lineas_productos = ""
                        filas_tabla_html = ""
                        
                        for item in st.session_state.carrito_ventas:
                            cant_val = float(item['Cantidad'])
                            cant_str = f"{int(cant_val)}" if cant_val.is_integer() else f"{cant_val:.3f}"
                            lineas_productos += f"- {item['Descripción']} (x{cant_str}) ... ${item['Subtotal']:,.2f}\n"
                            
                            filas_tabla_html += f"""
                            <tr>
                                <td style="border: 1px solid #000; padding: 6px; text-align: left;">{item['Descripción']}</td>
                                <td style="border: 1px solid #000; padding: 6px; text-align: center;">{cant_str}</td>
                                <td style="border: 1px solid #000; padding: 6px; text-align: right;">${item['Precio Unitario']:,.2f}</td>
                                <td style="border: 1px solid #000; padding: 6px; text-align: right;">${item['Subtotal']:,.2f}</td>
                            </tr>
                            """

                            registros_para_nube.append({
                                "rut_empresa": datos_empresa.get("rut"),
                                "transaccion_id": transaccion_id_actual,
                                "folio": folio_oficial,
                                "folio_sii": folio_oficial,
                                "pdf_url": pdf_oficial_url,
                                "fecha_hora": fecha_hora_actual.isoformat(),
                                "caja": caja_actual, 
                                "documento": tipo_documento,
                                "cliente": cli_nombre,
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

                            if respuesta_venta.data:
                                # Descontar Stock
                                for item in st.session_state.carrito_ventas:
                                    try:
                                        res_stock = supabase.table("productos").select("stock").eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).execute()
                                        if res_stock.data:
                                            stock_actual = float(res_stock.data[0]["stock"] or 0.0)
                                            nuevo_stock = stock_actual - float(item["Cantidad"])
                                            supabase.table("productos").update({"stock": nuevo_stock}).eq("rut_empresa", rut_actual).eq("codigo", str(item["Código"])).execute()
                                    except Exception:
                                        pass

                                # Datos Emisor
                                nombre_emp = datos_empresa.get("razon_social", "MI EMPRESA")
                                rut_emp = datos_empresa.get("rut", rut_actual)
                                dir_emp = datos_empresa.get("direccion", "Sin Dirección")
                                com_emp = datos_empresa.get("comuna", "")
                                pie_pag = datos_empresa.get("pie_pagina") or "¡Gracias por su preferencia!"

                                # 📄 FORMATO HTML
                                html_recibo = f"""
                                <div style="font-family: Arial, sans-serif; max-width: 650px; margin: auto; padding: 20px; border: 1px solid #000; background-color: #fff; color: #000;">
                                    <div style="text-align: center; margin-bottom: 15px;">
                                        <h2 style="margin: 0; font-size: 20px; font-weight: bold; text-transform: uppercase;">{nombre_emp}</h2>
                                        <p style="margin: 3px 0; font-size: 13px;">Dirección: {dir_emp}{', ' + com_emp if com_emp else ''}</p>
                                        <p style="margin: 3px 0; font-size: 13px; font-weight: bold;">RUT: {rut_emp}</p>
                                    </div>

                                    <div style="text-align: center; margin: 15px 0;">
                                        <h3 style="margin: 0; font-size: 16px; font-weight: bold; text-transform: uppercase;">{tipo_documento.upper()} ELECTRÓNICA</h3>
                                        <p style="margin: 3px 0; font-size: 13px;"><b>Folio N°:</b> {folio_oficial} &nbsp;|&nbsp; <b>Fecha:</b> {fecha_hora_actual.strftime('%d/%m/%Y')}</p>
                                    </div>

                                    <div style="margin-bottom: 15px;">
                                        <h4 style="margin: 0 0 5px 0; font-size: 13px; font-weight: bold; text-transform: uppercase;">DATOS DEL CLIENTE</h4>
                                        <table style="width: 100%; font-size: 12px; border-collapse: collapse; border: 1px solid #000;">
                                            <tr>
                                                <td style="padding: 5px; border: 1px solid #000;"><b>Razón Social / Nombre:</b> {cli_nombre}</td>
                                                <td style="padding: 5px; border: 1px solid #000;"><b>RUT:</b> {cli_rut}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 5px; border: 1px solid #000;"><b>Dirección:</b> {cli_dir}</td>
                                                <td style="padding: 5px; border: 1px solid #000;"><b>Condición de Pago:</b> {forma_pago.upper()}</td>
                                            </tr>
                                        </table>
                                    </div>

                                    <table style="width: 100%; font-size: 12px; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #000;">
                                        <thead>
                                            <tr style="background-color: #f2f2f2;">
                                                <th style="border: 1px solid #000; padding: 5px; text-align: left;">Descripción</th>
                                                <th style="border: 1px solid #000; padding: 5px; text-align: center;">Cant.</th>
                                                <th style="border: 1px solid #000; padding: 5px; text-align: right;">P. Unitario</th>
                                                <th style="border: 1px solid #000; padding: 5px; text-align: right;">Total</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {filas_tabla_html}
                                        </tbody>
                                    </table>

                                    <!-- DESGLOSE AL PIE DE PÁGINA -->
                                    <div style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                                        <table style="width: 50%; font-size: 12px; border-collapse: collapse; border: 1px solid #000;">
                                            <tr>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;"><b>Monto Neto:</b></td>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;">${monto_neto:,.2f}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;"><b>IVA (19%):</b></td>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;">${monto_iva:,.2f}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;"><b>Imp. Específicos:</b></td>
                                                <td style="padding: 4px 8px; border: 1px solid #000; text-align: right;">${imp_especifico:,.2f}</td>
                                            </tr>
                                            <tr style="background-color: #f2f2f2;">
                                                <td style="padding: 6px 8px; border: 1px solid #000; text-align: right; font-weight: bold;">TOTAL GENERAL:</td>
                                                <td style="padding: 6px 8px; border: 1px solid #000; text-align: right; font-weight: bold;">${total_venta:,.2f}</td>
                                            </tr>
                                        </table>
                                    </div>

                                    <div style="text-align: center; font-size: 11px; margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 8px;">
                                        {pie_pag}
                                    </div>
                                </div>
                                """

                                # 📝 FORMATO TEXTO PLANO
                                texto_recibo = f"""========================================
       {nombre_emp}
       RUT: {rut_emp}
       Dirección: {dir_emp}{', ' + com_emp if com_emp else ''}
========================================
DOCUMENTO: {tipo_documento.upper()}
FOLIO: N° {folio_oficial}
FECHA: {fecha_hora_actual.strftime('%d/%m/%Y %H:%M:%S')}
TERMINAL: {caja_actual}
----------------------------------------
DATOS DEL CLIENTE:
Razón Social / Nombre: {cli_nombre}
RUT Cliente: {cli_rut}
Dirección: {cli_dir}
Condición de Pago: {forma_pago.upper()}
----------------------------------------
DETALLE:
{lineas_productos}----------------------------------------
DESGLOSE DE VALORES:
MONTO NETO:        ${monto_neto:,.2f}
IVA (19%):         ${monto_iva:,.2f}
IMP. ESPECÍFICOS:  ${imp_especifico:,.2f}
TOTAL GENERAL:     ${total_venta:,.2f}
----------------------------------------
PAGO: {forma_pago.upper()}
{('RECIBIDO: $' + f'{efectivo_recibido:,.2f}' + chr(10) + 'VUELTO: $' + f'{cambio:,.2f}') if forma_pago == 'Efectivo' else ''}
========================================
{pie_pag}
========================================"""

                                st.session_state.ultimo_recibo = texto_recibo
                                st.session_state.ultimo_html = html_recibo
                                st.session_state.estado_pago = False
                                st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al registrar en la nube: {e}")
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

            st.selectbox(
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
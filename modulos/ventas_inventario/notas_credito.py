import streamlit as st
import pandas as pd
from datetime import datetime
from modulos.servicios.data_manager import supabase, get_current_tenant
from modulos.servicios.dte_manager import emitir_dte_openfactura, validar_rut


def mostrar_modulo_notas_credito(ruta_negocio):
    # --- 1. BOTÓN DE VOLVER AL HOME ---
    if st.button("🏠 Volver al Home", use_container_width=True):
        st.session_state["modulo_activo"] = "home"
        st.session_state["menu_seleccionado"] = "🏠 Home / Bienvenida"
        st.rerun()
    st.markdown("---")

    # --- 2. TÍTULOS ---
    st.markdown("### 🔄 Emisión de Notas de Crédito y Devoluciones (DTE 61)")
    st.markdown(
        "📌 **Gestión Tributaria & Operativa:** Genera Notas de Crédito Electrónicas (DTE Tipo 61) "
        "ante el SII, anula o corrige documentos, reingresa stock a bodega y ajusta saldos."
    )

    # --- 3. LECTURA DIRECTA DESDE SUPABASE ---
    tenant_id = get_current_tenant()

    try:
        respuesta = (
            supabase.table("ventas")
            .select("*")
            .eq("rut_empresa", str(tenant_id))
            .order("fecha", desc=True)
            .limit(1000)
            .execute()
        )

        if not respuesta.data:
            st.info("ℹ️ No hay ventas registradas en la base de datos para procesar devoluciones.")
            return

        df_ventas = pd.DataFrame(respuesta.data)

        if df_ventas.empty:
            st.info("ℹ️ No hay ventas registradas para este negocio.")
            return

    except Exception as e:
        st.error(f"❌ Error al consultar ventas en Supabase: {e}")
        return

    col_id = next((c for c in df_ventas.columns if c in ["folio", "id", "transaccion"]), "folio")
    col_tipo = next((c for c in df_ventas.columns if c in ["documento", "tipo_documento"]), "documento")

    # --- PREPARAR BUSCADOR DE FOLIOS ---
    lista_folios = df_ventas[col_id].dropna().astype(str).unique().tolist()
    opciones_folios = ["-- Seleccionar Folio --"] + lista_folios

    st.markdown("---")
    st.markdown("#### 🔍 1. Buscar Documento Original")

    col1, col2 = st.columns(2)
    with col1:
        tipo_doc_busqueda = st.selectbox("Tipo de Documento a Buscar:", ["Todos", "Boleta Electrónica", "Factura Electrónica", "Guía de Despacho", "Nota de Venta Interna"])
    with col2:
        folio_busqueda = st.selectbox(
            "Seleccione el Número de Folio:",
            options=opciones_folios,
            help="💡 Selecciona el folio del documento a anular o modificar."
        )

    # --- 4. BÚSQUEDA Y SELECCIÓN ---
    if st.button("🔍 Buscar Documento", type="primary"):
        if folio_busqueda == "-- Seleccionar Folio --":
            st.warning("⚠️ Selecciona un número de folio válido.")
        else:
            df_filtrado = df_ventas.copy()
            df_filtrado[col_id] = df_filtrado[col_id].astype(str)
            folio_limpio = str(folio_busqueda).strip()

            df_filtrado = df_filtrado[df_filtrado[col_id] == folio_limpio]

            if tipo_doc_busqueda != "Todos" and col_tipo in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado[col_tipo].str.contains(tipo_doc_busqueda, case=False, na=False)]

            if df_filtrado.empty:
                st.error(f"❌ No se encontró el folio '{folio_limpio}' para el documento seleccionado.")
            else:
                st.success("✅ Documento localizado exitosamente.")
                st.session_state["venta_encontrada_nc"] = df_filtrado

    # --- 5. SECCIÓN DE EMISIÓN DE NOTA DE CRÉDITO ---
    if "venta_encontrada_nc" in st.session_state and st.session_state["venta_encontrada_nc"] is not None:
        df_resultado = st.session_state["venta_encontrada_nc"]
        primera_fila = df_resultado.iloc[0]

        # Datos clave del documento original
        doc_origen = str(primera_fila.get("documento", "Boleta Electrónica"))
        folio_origen = str(primera_fila.get("folio", ""))
        fecha_origen = str(primera_fila.get("fecha", ""))[:10]
        modo_origen = str(primera_fila.get("modo_emision", "INTERNO")).upper()
        cliente_origen = str(primera_fila.get("cliente", "Cliente General"))
        rut_cliente_origen = str(primera_fila.get("rut_cliente", "66666666-6"))

        # Mostrar encabezado de resumen
        c_meta1, c_meta2, c_meta3, c_meta4 = st.columns(4)
        c_meta1.metric("Folio Origen", folio_origen)
        c_meta2.metric("Documento", doc_origen)
        c_meta3.metric("Modo Emisión", modo_origen)
        c_meta4.metric("Cliente", cliente_origen[:20])

        cols_mostrar = [c for c in ["folio", "fecha", "codigo_producto", "detalle", "cantidad", "neto", "iva", "monto", "metodo_pago"] if c in df_resultado.columns]
        st.dataframe(df_resultado[cols_mostrar], use_container_width=True)

        st.markdown("#### 📦 2. Tipo y Alcance de la Devolución")
        tipo_devolucion = st.radio(
            "Seleccione el alcance de la Nota de Crédito:",
            ["Devolución Total (Anulación Completa)", "Devolución Parcial (Editar cantidades)"],
            key="radio_tipo_nc"
        )

        motivo_nc = st.text_input("📝 Motivo de la Nota de Crédito / Anulación:", value="Anulación por devolución de productos / error en venta")

        # PREPARAR DATOS PARA DEVOLUCIÓN PARCIAL
        datos_parciales = []
        if tipo_devolucion == "Devolución Parcial (Editar cantidades)":
            st.markdown("##### 📝 Ajuste de Cantidades a Devolver")
            st.write("Indica en la columna **'Cantidad a Devolver'** cuántas unidades regresarán a inventario:")

            lista_items = []
            for _, row in df_resultado.iterrows():
                cant_orig = float(row.get("cantidad", 1))
                monto_total_linea = float(row.get("monto", 0))
                precio_uni = monto_total_linea / cant_orig if cant_orig > 0 else 0

                lista_items.append({
                    "Código": str(row.get("codigo_producto", "")),
                    "Producto": str(row.get("detalle", "Producto")),
                    "Cant. Original": cant_orig,
                    "Cantidad a Devolver": 0.0,
                    "Precio Unitario": precio_uni
                })

            if lista_items:
                df_parcial = pd.DataFrame(lista_items)
                datos_parciales_df = st.data_editor(
                    df_parcial,
                    disabled=["Código", "Producto", "Cant. Original", "Precio Unitario"],
                    use_container_width=True,
                    key="editor_nc_parcial"
                )
                datos_parciales = datos_parciales_df.to_dict("records")

        st.markdown("---")

        # --- 🚀 BOTÓN DE EMISIÓN E INTEGRACIÓN DTE ---
        if st.button("🚀 Emitir Nota de Crédito y Procesar Devolución", type="primary", use_container_width=True):
            try:
                fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                es_oficial = (modo_origen == "OFICIAL")
                
                # 1. Armar detalle de ítems y montos a devolver
                items_a_procesar = []
                monto_total_devolucion = 0.0

                if tipo_devolucion == "Devolución Total (Anulación Completa)":
                    for _, row in df_resultado.iterrows():
                        cant_dev = float(row.get("cantidad", 1))
                        monto_lin = float(row.get("monto", 0))
                        p_unit = monto_lin / cant_dev if cant_dev > 0 else 0
                        monto_total_devolucion += monto_lin

                        items_a_procesar.append({
                            "codigo": str(row.get("codigo_producto", "")),
                            "nombre": str(row.get("detalle", "Producto")),
                            "cantidad": cant_dev,
                            "precio_unitario": p_unit,
                            "monto": monto_lin
                        })
                else:
                    for item in datos_parciales:
                        cant_dev = float(item["Cantidad a Devolver"])
                        if cant_dev > 0:
                            p_unit = float(item["Precio Unitario"])
                            monto_lin = cant_dev * p_unit
                            monto_total_devolucion += monto_lin

                            items_a_procesar.append({
                                "codigo": str(item["Código"]),
                                "nombre": str(item["Producto"]),
                                "cantidad": cant_dev,
                                "precio_unitario": p_unit,
                                "monto": monto_lin
                            })

                if not items_a_procesar:
                    st.warning("⚠️ No has seleccionado cantidades válidas para devolver.")
                    st.stop()

                # 2. Timbrado ante el SII si el documento original fue OFICIAL
                folio_nc_final = f"NC-{folio_origen}"
                pdf_url_nc = None
                xml_url_nc = None

                if es_oficial:
                    st.toast("⚡ Generando Nota de Crédito Electrónica (DTE 61) con el SII...", icon="📡")
                    
                    items_dte_payload = [
                        {
                            "nombre": i["nombre"],
                            "cantidad": i["cantidad"],
                            "precio_unitario": i["precio_unitario"],
                            "es_exento": False
                        }
                        for i in items_a_procesar
                    ]

                    mapa_tipo_origen = {
                        "Boleta Electrónica": 39,
                        "Factura Electrónica": 33,
                        "Guía de Despacho": 52
                    }
                    codigo_doc_origen = mapa_tipo_origen.get(doc_origen, 39)

                    referencias_sii = [{
                        "NroLinRef": 1,
                        "TpoDocRef": codigo_doc_origen,
                        "FolioRef": str(folio_origen),
                        "FchRef": fecha_origen,
                        "CodRef": 1 if "Total" in tipo_devolucion else 3,
                        "RazonRef": motivo_nc[:90]
                    }]

                    res_dte_nc = emitir_dte_openfactura(
                        rut_emisor=tenant_id,
                        tipo_documento="Nota de Crédito Electrónica",
                        items=items_dte_payload,
                        rut_receptor=rut_cliente_origen if rut_cliente_origen else "66666666-6",
                        razon_social_receptor=cliente_origen if cliente_origen else "Cliente General",
                        referencias=referencias_sii
                    )

                    if res_dte_nc.get("exito"):
                        folio_nc_final = str(res_dte_nc.get("folio"))
                        pdf_url_nc = res_dte_nc.get("pdf_url")
                        xml_url_nc = res_dte_nc.get("xml_url")
                        st.toast(f"✅ Nota de Crédito N° {folio_nc_final} Timbrada Exitosamente", icon="📜")
                    else:
                        err_dte = res_dte_nc.get("error", "Fallo al emitir DTE 61")
                        st.error(f"🚨 Error de Timbrado SII: {err_dte}")
                        st.stop()

                # 3. Reingresar Stock y Registrar en Base de Datos (Supabase)
                bodega_target = st.session_state.get("bodega_pos_seleccionada", "Bodega Principal")
                registros_nc_batch = []

                for item in items_a_procesar:
                    if item["codigo"] and item["cantidad"] > 0:
                        try:
                            supabase.rpc("actualizar_stock_atomico", {
                                "p_rut_empresa": str(tenant_id),
                                "p_codigo": str(item["codigo"]),
                                "p_bodega": str(bodega_target),
                                "p_cantidad": float(item["cantidad"]),
                                "p_operacion": "ENTRADA"
                            }).execute()
                        except Exception as err_stk:
                            print(f"Error reingresando stock: {err_stk}")

                    neto_nc = round(item["monto"] / 1.19, 2)
                    iva_nc = round(item["monto"] - neto_nc, 2)

                    registros_nc_batch.append({
                        "folio": folio_nc_final,
                        "rut_empresa": str(tenant_id),
                        "fecha": fecha_hoy,
                        "caja": "Caja Principal",
                        "documento": "Nota de Crédito",
                        "cliente": cliente_origen,
                        "rut_cliente": rut_cliente_origen,
                        "codigo_producto": item["codigo"],
                        "detalle": f"NC ({motivo_nc}): {item['nombre']}",
                        "cantidad": -abs(item["cantidad"]),
                        "monto": -abs(item["monto"]),
                        "neto": -abs(neto_nc),
                        "iva": -abs(iva_nc),
                        "metodo_pago": primera_fila.get("metodo_pago", "Efectivo"),
                        "modo_emision": modo_origen,
                        "estado_dte": "EMITIDO",
                        "pdf_url": pdf_url_nc,
                        "xml_url": xml_url_nc
                    })

                supabase.table("ventas").insert(registros_nc_batch).execute()

                # 4. Ajustar Cuentas por Cobrar si corresponde
                try:
                    res_cxc = supabase.table("cuentas_por_cobrar").select("*").eq("rut_empresa", str(tenant_id)).eq("folio_venta", str(folio_origen)).execute()
                    if res_cxc.data:
                        for cxc in res_cxc.data:
                            saldo_act = float(cxc.get("saldo_pendiente", 0))
                            nuevo_saldo = max(0.0, saldo_act - monto_total_devolucion)
                            est = "Pagado" if nuevo_saldo == 0 else "Pendiente"
                            supabase.table("cuentas_por_cobrar").update({
                                "saldo_pendiente": nuevo_saldo,
                                "estado": est
                            }).eq("id", cxc["id"]).execute()
                except Exception as err_cxc:
                    print(f"Error ajustando CxC: {err_cxc}")

                st.success(f"🎉 ¡Nota de Crédito {folio_nc_final} emitida exitosamente! Inventario y caja actualizados.")
                if pdf_url_nc:
                    st.link_button("📄 Descargar DTE Nota de Crédito (PDF)", pdf_url_nc, use_container_width=True)

                del st.session_state["venta_encontrada_nc"]
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error crítico procesando la Nota de Crédito: {e}")
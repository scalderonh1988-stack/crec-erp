import io
from datetime import datetime
import pandas as pd
import streamlit as st
from modulos.servicios.data_manager import get_current_tenant, supabase


def mostrar_modulo_historial_ventas(ruta_negocio):
    # --- 🛠️ ENCABEZADO Y NAVEGACIÓN ---
    col_titulo, col_btn = st.columns([4, 1])

    with col_titulo:
        st.markdown("### 📚 Historial de Documentos y Ventas Emitidas")
        st.markdown(
            "📌 **Archivo General:** Explora el registro histórico almacenado"
            " en la nube con filtros avanzados."
        )

    with col_btn:
        st.write("")
        if st.button(
            "🏠 Volver al Home",
            use_container_width=True,
            key="btn_home_historial_ventas",
        ):
            st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
            st.rerun()

    st.markdown("---")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error(
            "❌ No se ha identificado el negocio. Por favor, inicia sesión"
            " nuevamente."
        )
        return

    # 1. Obtener los datos directamente desde Supabase (Optimizado con límite y orden)
    try:
        res = (
            supabase.table("ventas")
            .select("*")
            .eq("rut_empresa", str(tenant_id))
            .order("fecha", desc=True)
            .limit(2000)
            .execute()
        )

        if not res.data:
            st.info(
                "ℹ️ El historial de ventas está vacío actualmente en la base"
                " de datos."
            )
            return

        df_ventas = pd.DataFrame(res.data)

    except Exception as e:
        st.error(
            f"❌ Error al conectar con Supabase para obtener el historial: {e}"
        )
        return

    # Normalizar y ordenar por fecha
    if "fecha" in df_ventas.columns:
        df_ventas["fecha_dt"] = pd.to_datetime(
            df_ventas["fecha"], errors="coerce"
        )
        df_ventas = df_ventas.sort_values(by="fecha_dt", ascending=False)

    # Identificación explícita y prioritaria de columnas clave
    col_folio = "folio" if "folio" in df_ventas.columns else next(
        (c for c in df_ventas.columns if "folio" in c.lower()), None
    )
    col_doc = next(
        (c for c in df_ventas.columns if "documento" in c.lower() or "tipo" in c.lower()),
        None,
    )

    # 📂 PESTAÑAS DE NAVEGACIÓN
    tab_gen, tab_doc, tab_pag, tab_comprobante, tab_eliminar = st.tabs([
        "📂 Vista General",
        "📄 Por Tipo de Documento",
        "💳 Método de Pago",
        "🖨️ Descargar Comprobante",
        "🗑️ Eliminar / Anular Venta",
    ])

    st.markdown("#### 🔍 Panel de Filtros Dinámicos")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        busqueda_libre = st.text_input(
            "🔎 Buscar palabra clave (folio, detalle, etc.)", value=""
        )
    with col_f2:
        limite_filas = st.slider(
            "📄 Mostrar cantidad máxima de registros",
            min_value=10,
            max_value=500,
            value=50,
            step=10,
            format="%d",
        )

    # Filtrado base por texto libre
    df_filtrado = df_ventas.copy()
    if busqueda_libre:
        mask = (
            df_filtrado.astype(str)
            .apply(
                lambda x: x.str.contains(busqueda_libre, case=False, na=False)
            )
            .any(axis=1)
        )
        df_filtrado = df_filtrado[mask]

    with tab_gen:
        st.markdown("#### 📋 Todos los Documentos Emitidos")
        st.dataframe(df_filtrado.head(limite_filas), use_container_width=True)

    with tab_doc:
        st.markdown("#### 📄 Filtrar por Tipo de Documento")
        if col_doc:
            tipos_disponibles = ["Todos"] + list(
                df_ventas[col_doc].dropna().unique()
            )
            doc_seleccionado = st.selectbox(
                "Seleccione el Tipo de Documento", options=tipos_disponibles
            )

            df_doc = df_filtrado.copy()
            if doc_seleccionado != "Todos":
                df_doc = df_doc[df_doc[col_doc] == doc_seleccionado]
            st.dataframe(df_doc.head(limite_filas), use_container_width=True)
        else:
            st.info("ℹ️ No se detectó una columna específica de 'documento'.")
            st.dataframe(
                df_filtrado.head(limite_filas), use_container_width=True
            )

    with tab_pag:
        st.markdown("#### 💳 Filtrar por Método de Pago")
        col_pag = next(
            (
                c
                for c in df_ventas.columns
                if "metodo_pago" in c.lower() or "pago" in c.lower()
            ),
            None,
        )
        if col_pag:
            estados_disponibles = ["Todos"] + list(
                df_ventas[col_pag].dropna().unique()
            )
            pag_seleccionado = st.selectbox(
                "Seleccione el Método de Pago", options=estados_disponibles
            )

            df_pag = df_filtrado.copy()
            if pag_seleccionado != "Todos":
                df_pag = df_pag[df_pag[col_pag] == pag_seleccionado]
            st.dataframe(df_pag.head(limite_filas), use_container_width=True)
        else:
            st.info(
                "ℹ️ No se detectó una columna específica de 'método de pago'."
            )
            st.dataframe(
                df_filtrado.head(limite_filas), use_container_width=True
            )

    with tab_comprobante:
        st.markdown("#### 🖨️ Búsqueda y Descarga de Comprobante Individual")
        st.markdown(
            "Ingresa o selecciona el Folio (ej. `TX-20260818...`) para obtener"
            " el detalle exacto."
        )

        if col_folio:
            lista_ids = df_ventas[col_folio].dropna().astype(str).unique().tolist()
            id_elegido = st.selectbox("Seleccione el Folio", options=lista_ids, key="sb_folio_comprobante")

            if id_elegido:
                fila_venta = df_ventas[
                    df_ventas[col_folio].astype(str) == id_elegido
                ]

                if not fila_venta.empty:
                    st.success("✅ ¡Transacción encontrada con éxito!")
                    st.dataframe(fila_venta, use_container_width=True)

                    # Reconstrucción multi-ítem completa del ticket
                    primera_fila = fila_venta.iloc[0]
                    detalle_texto = "=== COMPROBANTE DE VENTA ===\n\n"
                    detalle_texto += f"FOLIO: {id_elegido}\n"
                    detalle_texto += (
                        f"FECHA: {primera_fila.get('fecha', 'N/A')}\n"
                    )
                    detalle_texto += f"CLIENTE: {primera_fila.get('cliente', 'Cliente General')}\n"
                    detalle_texto += (
                        f"DOCUMENTO: {primera_fila.get('documento', 'N/A')}\n"
                    )
                    detalle_texto += f"MÉTODO PAGO: {primera_fila.get('metodo_pago', 'N/A')}\n"
                    detalle_texto += (
                        "----------------------------------------\n"
                    )
                    detalle_texto += "DETALLE DE PRODUCTOS:\n"

                    total_general = 0.0
                    for _, item in fila_venta.iterrows():
                        cant = item.get("cantidad", 1)
                        prod = item.get(
                            "detalle",
                            item.get("producto", "Producto sin nombre"),
                        )
                        monto = item.get("monto", item.get("subtotal", 0.0))

                        try:
                            monto_num = float(monto)
                        except (ValueError, TypeError):
                            monto_num = 0.0

                        total_general += monto_num
                        detalle_texto += (
                            f"- {prod} (x{cant}) ... ${monto_num:,.2f}\n"
                        )

                    detalle_texto += (
                        "----------------------------------------\n"
                    )
                    detalle_texto += f"TOTAL: ${total_general:,.2f}\n"
                    detalle_texto += "========================================\n"

                    st.download_button(
                        label=f"📥 Descargar Comprobante ({id_elegido})",
                        data=detalle_texto,
                        file_name=f"Comprobante_{id_elegido}.txt",
                        mime="text/plain",
                    )
        else:
            st.warning("⚠️ No se encontró la columna de 'folio'.")

    # --- 🗑️ PESTAÑA: ELIMINACIÓN Y ANULACIÓN DE VENTAS EN SUPABASE ---
    with tab_eliminar:
        st.markdown("#### 🚨 Anulación y Borrado Permanente de Transacciones")
        st.warning(
            "⚠️ **Zona de Cuidado:** Selecciona el Tipo de Documento y el Número de Folio para "
            "eliminar el documento completo almacenado en Supabase."
        )

        if col_folio:
            col_sel_doc, col_sel_folio = st.columns(2)

            # 1. Selección previa por Tipo de Documento
            with col_sel_doc:
                if col_doc:
                    docs_disponibles = ["Todos"] + list(df_ventas[col_doc].dropna().unique())
                    doc_a_eliminar = st.selectbox(
                        "📄 Tipo de Documento:",
                        options=docs_disponibles,
                        key="sb_doc_eliminar"
                    )
                else:
                    doc_a_eliminar = "Todos"
                    st.info("ℹ️ No se detectó columna de Tipo de Documento.")

            # Filtrar DataFrame según tipo de documento seleccionado
            df_filtrado_doc = df_ventas.copy()
            if col_doc and doc_a_eliminar != "Todos":
                df_filtrado_doc = df_filtrado_doc[df_filtrado_doc[col_doc] == doc_a_eliminar]

            # 2. Selección del Número de Folio (listará solo folios únicos del tipo de doc seleccionado)
            with col_sel_folio:
                lista_folios_disponibles = [""] + df_filtrado_doc[col_folio].dropna().astype(str).unique().tolist()
                folio_a_eliminar = st.selectbox(
                    "📌 Número de Folio:",
                    options=lista_folios_disponibles,
                    key="sb_folio_eliminar"
                )

            if folio_a_eliminar:
                # Obtener TODAS las filas/ítems asociados a este folio
                filas_a_eliminar = df_filtrado_doc[df_filtrado_doc[col_folio].astype(str) == str(folio_a_eliminar)]

                if not filas_a_eliminar.empty:
                    st.write(f"🔍 **Registros a eliminar ({len(filas_a_eliminar)} ítem(s) en Folio `{folio_a_eliminar}` | Tipo `{doc_a_eliminar}`):**")
                    st.dataframe(filas_a_eliminar, use_container_width=True)

                    reingresar_stock = st.checkbox(
                        "📦 Devolver automáticamente las unidades al Inventario (Bodega)",
                        value=False,
                        key="cb_reingresar_stock"
                    )

                    st.markdown("---")
                    st.error("❓ **¿Está seguro que desea eliminar estos registros?**")
                    
                    confirmar_pregunta = st.checkbox(
                        f"Sí, confirmo que deseo eliminar el documento completo con Folio {folio_a_eliminar}",
                        key="cb_confirmar_pregunta_seguridad"
                    )

                    if st.button("🔥 Confirmar y Eliminar Documento Completo", type="primary", use_container_width=True):
                        if not confirmar_pregunta:
                            st.warning("⚠️ Debes marcar la casilla de confirmación para validar la pregunta de seguridad.")
                        else:
                            try:
                                # 1. Reingreso opcional de stock en bodega para cada ítem del folio
                                if reingresar_stock:
                                    bodega_defecto = st.session_state.get("bodega_pos_seleccionada", "Bodega Principal")
                                    for _, item in filas_a_eliminar.iterrows():
                                        cod_prod = item.get("codigo_producto", item.get("codigo", ""))
                                        cant = float(item.get("cantidad", 0))
                                        bodega = item.get("bodega", bodega_defecto)

                                        if cod_prod and cant > 0:
                                            supabase.rpc(
                                                'actualizar_stock_atomico',
                                                {
                                                    'p_rut_empresa': str(tenant_id),
                                                    'p_codigo': str(cod_prod),
                                                    'p_bodega': str(bodega),
                                                    'p_cantidad': cant,
                                                    'p_operacion': 'ENTRADA'
                                                }
                                            ).execute()

                                # 2. Limpieza preventiva en cuentas por cobrar si corresponde
                                try:
                                    supabase.table("cuentas_por_cobrar").delete().eq("rut_empresa", str(tenant_id)).eq("folio_venta", str(folio_a_eliminar)).execute()
                                except Exception:
                                    pass

                                # 3. Borrar explícitamente TODAS las filas que coincidan con la columna 'folio'
                                delete_query = (
                                    supabase.table("ventas")
                                    .delete()
                                    .eq("rut_empresa", str(tenant_id))
                                    .eq(col_folio, str(folio_a_eliminar))
                                )
                                
                                if col_doc and doc_a_eliminar != "Todos":
                                    delete_query = delete_query.eq(col_doc, str(doc_a_eliminar))
                                    
                                delete_query.execute()

                                st.success(f"🎉 Documento completo con Folio **{folio_a_eliminar}** eliminado exitosamente de Supabase.")
                                st.rerun()

                            except Exception as err_del:
                                st.error(f"❌ Error al intentar eliminar los registros en Supabase: {err_del}")
        else:
            st.error("❌ No se encontró la columna 'folio' en la tabla de ventas.")

    # Botón global de descarga
    st.divider()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_filtrado.to_excel(writer, index=False)
    excel_data = output.getvalue()

    st.download_button(
        label="📥 Descargar Reporte Completo en Excel",
        data=excel_data,
        file_name="Historial_Ventas_Supabase.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
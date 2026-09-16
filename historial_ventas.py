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

    # 1. Obtener datos desde Supabase
    try:
        res = (
            supabase.table("ventas")
            .select("*")
            .eq("rut_empresa", str(tenant_id))
            .order("fecha", desc=True)
            .limit(3000)
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

    # Normalización de fecha y definición estricta de columnas Supabase
    if "fecha" in df_ventas.columns:
        df_ventas["fecha_dt"] = pd.to_datetime(
            df_ventas["fecha"], errors="coerce"
        )
        df_ventas = df_ventas.sort_values(by="fecha_dt", ascending=False)

    # 🎯 COLUMNAS EXACTAS DE LA TABLA VENTAS
    col_folio = "folio" if "folio" in df_ventas.columns else df_ventas.columns[0]
    col_doc = "documento" if "documento" in df_ventas.columns else None

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
            st.info("ℹ️ No se detectó la columna 'documento'.")
            st.dataframe(
                df_filtrado.head(limite_filas), use_container_width=True
            )

    with tab_pag:
        st.markdown("#### 💳 Filtrar por Método de Pago")
        col_pag = "metodo_pago" if "metodo_pago" in df_ventas.columns else None
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
            st.info("ℹ️ No se detectó la columna 'metodo_pago'.")
            st.dataframe(
                df_filtrado.head(limite_filas), use_container_width=True
            )

    with tab_comprobante:
        st.markdown("#### 🖨️ Búsqueda y Descarga de Comprobante Individual")
        
        lista_ids = df_ventas[col_folio].dropna().astype(str).unique().tolist()
        id_elegido = st.selectbox("Seleccione el Folio", options=lista_ids, key="sb_folio_comprobante")

        if id_elegido:
            fila_venta = df_ventas[
                df_ventas[col_folio].astype(str) == id_elegido
            ]

            if not fila_venta.empty:
                st.success("✅ ¡Transacción encontrada con éxito!")
                st.dataframe(fila_venta, use_container_width=True)

                primera_fila = fila_venta.iloc[0]
                detalle_texto = "=== COMPROBANTE DE VENTA ===\n\n"
                detalle_texto += f"FOLIO: {id_elegido}\n"
                detalle_texto += f"FECHA: {primera_fila.get('fecha', 'N/A')}\n"
                detalle_texto += f"CLIENTE: {primera_fila.get('cliente', 'Cliente General')}\n"
                detalle_texto += f"DOCUMENTO: {primera_fila.get('documento', 'N/A')}\n"
                detalle_texto += f"MÉTODO PAGO: {primera_fila.get('metodo_pago', 'N/A')}\n"
                detalle_texto += "----------------------------------------\n"
                detalle_texto += "DETALLE DE PRODUCTOS:\n"

                total_general = 0.0
                for _, item in fila_venta.iterrows():
                    cant = item.get("cantidad", 1)
                    prod = item.get("detalle", item.get("producto", "Producto sin nombre"))
                    monto = item.get("monto", 0.0)

                    try:
                        monto_num = float(monto)
                    except (ValueError, TypeError):
                        monto_num = 0.0

                    total_general += monto_num
                    detalle_texto += f"- {prod} (x{cant}) ... ${monto_num:,.2f}\n"

                detalle_texto += "----------------------------------------\n"
                detalle_texto += f"TOTAL: ${total_general:,.2f}\n"
                detalle_texto += "========================================\n"

                st.download_button(
                    label=f"📥 Descargar Comprobante ({id_elegido})",
                    data=detalle_texto,
                    file_name=f"Comprobante_{id_elegido}.txt",
                    mime="text/plain",
                )

    # --- 🗑️ PESTAÑA: ELIMINACIÓN Y ANULACIÓN DE VENTAS EN SUPABASE ---
    with tab_eliminar:
        st.markdown("#### 🚨 Anulación y Borrado Permanente por Folio")
        st.warning(
            "⚠️ **Operación Directa en Base de Datos:** Al eliminar un **Folio**, se borrarán "
            "**TODAS** las líneas asociadas a ese mismo folio en la tabla `ventas` de Supabase."
        )

        col_sel_doc, col_sel_folio = st.columns(2)

        # 1. Filtro opcional por Tipo de Documento
        with col_sel_doc:
            if col_doc:
                docs_disponibles = ["Todos"] + list(df_ventas[col_doc].dropna().unique())
                doc_a_eliminar = st.selectbox(
                    "📄 Filtrar Tipo de Documento:",
                    options=docs_disponibles,
                    key="sb_doc_eliminar_v3"
                )
            else:
                doc_a_eliminar = "Todos"

        # Aplicar filtro de documento si seleccionó alguno
        df_filtrado_doc = df_ventas.copy()
        if col_doc and doc_a_eliminar != "Todos":
            df_filtrado_doc = df_filtrado_doc[df_filtrado_doc[col_doc] == doc_a_eliminar]

        # 2. Selección del Folio (extrae valores únicos de la columna 'folio')
        with col_sel_folio:
            folios_unicos = [""] + df_filtrado_doc["folio"].dropna().astype(str).unique().tolist()
            folio_a_eliminar = st.selectbox(
                "📌 Seleccione el Folio a eliminar:",
                options=folios_unicos,
                key="sb_folio_eliminar_v3"
            )

        if folio_a_eliminar:
            # Seleccionar TODAS las filas que coincidan con la columna 'folio'
            filas_a_eliminar = df_ventas[df_ventas["folio"].astype(str) == str(folio_a_eliminar)]

            if not filas_a_eliminar.empty:
                st.info(f"🔎 **Se detectaron {len(filas_a_eliminar)} fila(s)/línea(s) asociadas al Folio `{folio_a_eliminar}`:**")
                st.dataframe(filas_a_eliminar, use_container_width=True)

                reingresar_stock = st.checkbox(
                    "📦 Reingresar automáticamente el stock de estas líneas a Bodega",
                    value=False,
                    key="cb_reingresar_stock_v3"
                )

                st.markdown("---")
                st.error(f"❓ **Confirmación:** ¿Desea eliminar definitivamente el Folio `{folio_a_eliminar}` y sus {len(filas_a_eliminar)} línea(s)?")
                
                confirmar_pregunta = st.checkbox(
                    f"Sí, acepto borrar de Supabase todas las {len(filas_a_eliminar)} filas del Folio {folio_a_eliminar}",
                    key="cb_confirmar_pregunta_v3"
                )

                if st.button("🔥 Eliminar Folio Completo de Supabase", type="primary", use_container_width=True):
                    if not confirmar_pregunta:
                        st.warning("⚠️ Debe marcar la casilla de confirmación antes de ejecutar la eliminación.")
                    else:
                        try:
                            # 1. Devuelve stock si está activado
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

                            # 2. Borrar de cuentas por cobrar asociadas
                            try:
                                supabase.table("cuentas_por_cobrar").delete().eq("rut_empresa", str(tenant_id)).eq("folio_venta", str(folio_a_eliminar)).execute()
                            except Exception:
                                pass

                            # 3. Borrado definitivo en la columna EXACTA 'folio'
                            supabase.table("ventas").delete().eq("rut_empresa", str(tenant_id)).eq("folio", str(folio_a_eliminar)).execute()

                            st.success(f"🎉 El Folio **{folio_a_eliminar}** con sus **{len(filas_a_eliminar)} líneas** fue eliminado exitosamente de Supabase.")
                            st.rerun()

                        except Exception as err_del:
                            st.error(f"❌ Error al eliminar en Supabase: {err_del}")

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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
import streamlit as st
import pandas as pd
from datetime import date

def mostrar_modulo_cuadratura_diaria(*args, **kwargs):
    st.markdown("### 📒 Cuadratura Diaria y Cuaderno de Caja (Nube)")
    st.markdown("📌 **Control de Caja Inteligente:** Gestiona tus ingresos generales y registra tus cierres directamente en Supabase.")

    # 1. Obtener el RUT actual de la sesión de forma segura
    rut_actual = st.session_state.get("negocio_seleccionado")
    if not rut_actual:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión.")
        st.stop()

    # 2. Obtener el cliente de Supabase de forma segura (desde session_state o globales)
    supabase = st.session_state.get("supabase", None)
    if not supabase:
        try:
            # Intento alternativo si está definido de forma global en app.py
            supabase = globals().get("supabase", None)
        except Exception:
            pass

    if not supabase:
        st.error("❌ No se encontró la conexión activa a Supabase. Verifica tu sesión.")
        st.stop()

    # 3. Inputs de Carga Diaria con números limpios
    fecha_cuat = st.date_input("Fecha de Cuadratura", value=date.today())
    
    st.markdown("#### 💰 Ingresos Generales de Caja")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        efectivo_c = float(st.number_input("💵 Efectivo ($)", min_value=0.0, step=1000.0, value=0.0, format="%.0f"))
    with col_f2:
        transferencia_c = float(st.number_input("📱 Transferencias ($)", min_value=0.0, step=1000.0, value=0.0, format="%.0f"))
    with col_f3:
        debito_c = float(st.number_input("💳 Débito / Tarjetas ($)", min_value=0.0, step=1000.0, value=0.0, format="%.0f"))

    col_f4, col_f5 = st.columns(2)
    with col_f4:
        otros_ingresos_c = float(st.number_input("➕ Otros Ingresos ($)", min_value=0.0, step=1000.0, value=0.0, format="%.0f"))
    with col_f5:
        markup_general = st.number_input("📈 Markup Productos Generales (%)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)

    aplicar_cigarros = st.toggle("🚬 ¿Aplicar control diferenciado para Cigarrillos / Exentos en este cierre?", value=True)
    
    cigarrillos_c = 0.0
    markup_cigarros = 0.0

    if aplicar_cigarros:
        st.markdown("#### 🚬 Control Específico de Cigarrillos")
        col_cig1, col_cig2 = st.columns(2)
        with col_cig1:
            cigarrillos_c = float(st.number_input("🚬 Venta de Cigarrillos ($)", min_value=0.0, step=1000.0, value=0.0, format="%.0f"))
        with col_cig2:
            markup_cigarros = st.number_input("📉 Markup Específico Cigarrillos (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)

    ventas_generales = efectivo_c + transferencia_c + debito_c + otros_ingresos_c
    venta_total_calculada = ventas_generales + cigarrillos_c

    costo_general = ventas_generales / (1.0 + (markup_general / 100.0))
    costo_cigarros = (cigarrillos_c / (1.0 + (markup_cigarros / 100.0))) if (aplicar_cigarros and cigarrillos_c > 0) else 0.0
    
    costo_reposicion_total = costo_general + costo_cigarros
    utilidad_neta_disponible = venta_total_calculada - costo_reposicion_total

    st.divider()
    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    with col_res1:
        st.metric(label="🪙 Venta Total Día", value=f"${venta_total_calculada:,.2f}")
    with col_res2:
        st.metric(label="🚬 Venta Cigarrillos", value=f"${cigarrillos_c:,.2f}")
    with col_res3:
        st.metric(label="🔒 Fondo Reposición Total", value=f"${costo_reposicion_total:,.2f}", delta="Intocable")
    with col_res4:
        st.metric(label="💵 Utilidad Retirable Segura", value=f"${utilidad_neta_disponible:,.2f}", delta="Disponible")

    observaciones_c = st.text_input("📝 Observaciones del Cierre de Caja", value="Cierre normal")

    btn_guardar_cuat = st.button("💾 Guardar Cuadratura en la Nube", type="primary")

    if btn_guardar_cuat:
        if venta_total_calculada <= 0:
            st.warning("⚠️ Debes ingresar al menos un monto en los ingresos de caja.")
        else:
            nuevo_registro = {
                "rut_empresa": rut_actual,
                "fecha": str(fecha_cuat),
                "efectivo": efectivo_c,
                "transferencia": transferencia_c,
                "debito": debito_c,
                "cigarros": cigarrillos_c if aplicar_cigarros else 0.0,
                "otros_ingresos": otros_ingresos_c,
                "venta_total": venta_total_calculada,
                "markup_general": markup_general,
                "markup_cigarros": markup_cigarros if aplicar_cigarros else 0.0,
                "costo_reposicion": costo_reposicion_total,
                "utilidad_retirable": utilidad_neta_disponible,
                "observaciones": observaciones_c
            }
            try:
                supabase.table("cuadratura_diaria").insert(nuevo_registro).execute()
                st.success("✅ ¡Cuadratura guardada y sincronizada con la nube con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar en Supabase: {e}")

    # 4. SECCIÓN DE ACUMULADOS Y REPORTES DESDE LA NUBE
    st.markdown("---")
    st.markdown("### 📊 Acumulados y Reportes Progresivos (Nube)")
    
    df_cuadratura = pd.DataFrame()
    try:
        res_cuat = supabase.table("cuadratura_diaria").select("*").eq("rut_empresa", rut_actual).execute()
        if res_cuat.data:
            df_cuadratura = pd.DataFrame(res_cuat.data)
    except Exception as e:
        st.error(f"⚠️ Error cargando cuadraturas desde Supabase: {e}")

    if not df_cuadratura.empty:
        df_cuadratura['Fecha_dt'] = pd.to_datetime(df_cuadratura['fecha'], errors='coerce')
        hoy = pd.Timestamp.today().normalize()

        tab_p1, tab_p2, tab_p3, tab_p4, tab_p5 = st.tabs([
            "📅 Diario (Selección)", "📈 Semanal", "📊 Quincenal", "📆 Mensual", "📚 Histórico Completo"
        ])

        with tab_p1:
            st.markdown("#### Detalle del Día Seleccionado")
            fecha_filtro = st.date_input("Consultar Fecha Específica", value=date.today(), key="filtro_fecha_dia")
            df_dia = df_cuadratura[df_cuadratura['Fecha_dt'].dt.date == fecha_filtro]
            if not df_dia.empty:
                tot_dia = df_dia['venta_total'].sum()
                util_dia = df_dia['utilidad_retirable'].sum()
                st.metric("Venta Total del Día", f"${tot_dia:,.2f}")
                st.metric("Utilidad Retirable del Día", f"${util_dia:,.2f}")
            else:
                st.info("No hay registros para la fecha seleccionada.")

        with tab_p2:
            st.markdown("#### Acumulado Últimos 7 Días")
            inicio_semana = hoy - pd.Timedelta(days=7)
            df_sem = df_cuadratura[df_cuadratura['Fecha_dt'] >= inicio_semana]
            st.metric("Venta Acumulada Semana", f"${df_sem['venta_total'].sum():,.2f}")
            st.metric("Utilidad Acumulada Semana", f"${df_sem['utilidad_retirable'].sum():,.2f}")

        with tab_p3:
            st.markdown("#### Acumulado Últimos 15 Días")
            inicio_quin = hoy - pd.Timedelta(days=15)
            df_quin = df_cuadratura[df_cuadratura['Fecha_dt'] >= inicio_quin]
            st.metric("Venta Acumulada Quincena", f"${df_quin['venta_total'].sum():,.2f}")
            st.metric("Utilidad Acumulada Quincena", f"${df_quin['utilidad_retirable'].sum():,.2f}")

        with tab_p4:
            st.markdown("#### Acumulado Mes en Curso")
            df_mes = df_cuadratura[(df_cuadratura['Fecha_dt'].dt.month == hoy.month) & (df_cuadratura['Fecha_dt'].dt.year == hoy.year)]
            st.metric("Venta Acumulada Mes", f"${df_mes['venta_total'].sum():,.2f}")
            st.metric("Utilidad Acumulada Mes", f"${df_mes['utilidad_retirable'].sum():,.2f}")

        with tab_p5:
            st.markdown("#### Historial y Gestión de Registros")
            for index, row in df_cuadratura.iterrows():
                col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 1])
                with col_h1:
                    fecha_txt = str(row['fecha']) if pd.notna(row['fecha']) else "S/F"
                    st.markdown(f"**Fecha:** {fecha_txt}")
                with col_h2:
                    v_total = float(row['venta_total']) if pd.notna(row['venta_total']) else 0.0
                    st.markdown(f"**Total:** ${v_total:,.2f}")
                    obs = str(row['observaciones']) if pd.notna(row['observaciones']) else "Sin obs"
                    st.caption(f"Obs: {obs}")
                with col_h3:
                    u_retirable = float(row['utilidad_retirable']) if pd.notna(row['utilidad_retirable']) else 0.0
                    st.markdown(f"**Utilidad:** ${u_retirable:,.2f}")
                with col_h4:
                    row_id = row.get('id')
                    if st.button("🗑️", key=f"del_cuat_nube_{row_id}_{index}"):
                        try:
                            supabase.table("cuadratura_diaria").delete().eq("id", row_id).execute()
                            st.success("🗑️ ¡Registro eliminado de la nube con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
                st.divider()
    else:
        st.info("ℹ️ Aún no hay registros de cuadratura diarios guardados en la nube para este negocio.")
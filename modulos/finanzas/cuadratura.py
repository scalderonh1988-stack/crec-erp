import streamlit as st
import pandas as pd
from datetime import date
import os

def mostrar_modulo_cuadratura_diaria(ruta_negocio):
    st.markdown("### 📒 Cuadratura Diaria y Cuaderno de Caja")
    st.markdown("📌 **Control de Caja Inteligente:** Gestiona tus ingresos generales y controla tus cierres de forma limpia.")

    archivo_cuadratura = os.path.join(ruta_negocio, "Cuadratura_Diaria.xlsx")
    
    columnas_requeridas = [
        'ID', 'Fecha', 'Efectivo', 'Transferencia', 'Debito', 'Cigarros', 'Otros_Ingresos', 
        'VentaTotal', 'MarkupGeneral', 'MarkupCigarros', 'CostoReposicion', 'UtilidadRetirable', 'Observaciones'
    ]

    if not os.path.exists(archivo_cuadratura):
        pd.DataFrame(columns=columnas_requeridas).to_excel(archivo_cuadratura, index=False)

    # 1. Inputs de Carga Diaria con números limpios
    fecha_cuat = st.date_input("Fecha de Cuadratura", value=date.today())
    
    st.markdown("#### 💰 Ingresos Generales de Caja")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        efectivo_c = float(st.number_input("💵 Efectivo ($)", min_value=0, step=1000, value=0, format="%d"))
    with col_f2:
        transferencia_c = float(st.number_input("📱 Transferencias ($)", min_value=0, step=1000, value=0, format="%d"))
    with col_f3:
        debito_c = float(st.number_input("💳 Débito / Tarjetas ($)", min_value=0, step=1000, value=0, format="%d"))

    col_f4, col_f5 = st.columns(2)
    with col_f4:
        otros_ingresos_c = float(st.number_input("➕ Otros Ingresos ($)", min_value=0, step=1000, value=0, format="%d"))
    with col_f5:
        markup_general = st.number_input("📈 Markup Productos Generales (%)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)

    aplicar_cigarros = st.toggle("🚬 ¿Aplicar control diferenciado para Cigarrillos / Exentos en este cierre?", value=True)
    
    cigarrillos_c = 0.0
    markup_cigarros = 0.0

    if aplicar_cigarros:
        st.markdown("#### 🚬 Control Específico de Cigarrillos")
        col_cig1, col_cig2 = st.columns(2)
        with col_cig1:
            cigarrillos_c = float(st.number_input("🚬 Venta de Cigarrillos ($)", min_value=0, step=1000, value=0, format="%d"))
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

    btn_guardar_cuat = st.button("💾 Guardar Cuadratura y Retiro", type="primary")

    if btn_guardar_cuat:
        if venta_total_calculada <= 0:
            st.warning("⚠️ Debes ingresar al menos un monto en los ingresos de caja.")
        else:
            df_cuat_ant = pd.read_excel(archivo_cuadratura)
            nuevo_id = str(pd.Timestamp.now().timestamp())
            
            nuevo_registro = pd.DataFrame([{
                'ID': nuevo_id,
                'Fecha': str(fecha_cuat),
                'Efectivo': efectivo_c,
                'Transferencia': transferencia_c,
                'Debito': debito_c,
                'Cigarros': cigarrillos_c if aplicar_cigarros else 0.0,
                'Otros_Ingresos': otros_ingresos_c,
                'VentaTotal': venta_total_calculada,
                'MarkupGeneral': markup_general,
                'MarkupCigarros': markup_cigarros if aplicar_cigarros else 0.0,
                'CostoReposicion': costo_reposicion_total,
                'UtilidadRetirable': utilidad_neta_disponible,
                'Observaciones': observaciones_c
            }])
            pd.concat([df_cuat_ant, nuevo_registro], ignore_index=True).to_excel(archivo_cuadratura, index=False)
            st.success("✅ ¡Cuadratura guardada con éxito!")
            st.rerun()

    # 2. SECCIÓN DE ACUMULADOS Y REPORTES PROGRESIVOS
    st.markdown("---")
    st.markdown("### 📊 Acumulados y Reportes Progresivos")
    
    if os.path.exists(archivo_cuadratura):
        df_cuadratura = pd.read_excel(archivo_cuadratura)
        if not df_cuadratura.empty:
            for col in columnas_requeridas:
                if col not in df_cuadratura.columns:
                    df_cuadratura[col] = 0.0 if col in ['VentaTotal', 'UtilidadRetirable'] else ""
            
            if 'ID' not in df_cuadratura.columns or df_cuadratura['ID'].isna().all():
                df_cuadratura['ID'] = [str(i) for i in range(len(df_cuadratura))]

            df_cuadratura['Fecha_dt'] = pd.to_datetime(df_cuadratura['Fecha'], errors='coerce')
            hoy = pd.Timestamp.today().normalize()

            tab_p1, tab_p2, tab_p3, tab_p4, tab_p5 = st.tabs([
                "📅 Diario (Selección)", "📈 Semanal", "📊 Quincenal", "📆 Mensual", "📚 Histórico Completo"
            ])

            with tab_p1:
                st.markdown("#### Detalle del Día Seleccionado")
                fecha_filtro = st.date_input("Consultar Fecha Específica", value=date.today(), key="filtro_fecha_dia")
                df_dia = df_cuadratura[df_cuadratura['Fecha_dt'].dt.date == fecha_filtro]
                if not df_dia.empty:
                    tot_dia = df_dia['VentaTotal'].sum()
                    util_dia = df_dia['UtilidadRetirable'].sum()
                    st.metric("Venta Total del Día", f"${tot_dia:,.2f}")
                    st.metric("Utilidad Retirable del Día", f"${util_dia:,.2f}")
                else:
                    st.info("No hay registros para la fecha seleccionada.")

            with tab_p2:
                st.markdown("#### Acumulado Últimos 7 Días")
                inicio_semana = hoy - pd.Timedelta(days=7)
                df_sem = df_cuadratura[df_cuadratura['Fecha_dt'] >= inicio_semana]
                st.metric("Venta Acumulada Semana", f"${df_sem['VentaTotal'].sum():,.2f}")
                st.metric("Utilidad Acumulada Semana", f"${df_sem['UtilidadRetirable'].sum():,.2f}")

            with tab_p3:
                st.markdown("#### Acumulado Últimos 15 Días")
                inicio_quin = hoy - pd.Timedelta(days=15)
                df_quin = df_cuadratura[df_cuadratura['Fecha_dt'] >= inicio_quin]
                st.metric("Venta Acumulada Quincena", f"${df_quin['VentaTotal'].sum():,.2f}")
                st.metric("Utilidad Acumulada Quincena", f"${df_quin['UtilidadRetirable'].sum():,.2f}")

            with tab_p4:
                st.markdown("#### Acumulado Mes en Curso")
                df_mes = df_cuadratura[(df_cuadratura['Fecha_dt'].dt.month == hoy.month) & (df_cuadratura['Fecha_dt'].dt.year == hoy.year)]
                st.metric("Venta Acumulada Mes", f"${df_mes['VentaTotal'].sum():,.2f}")
                st.metric("Utilidad Acumulada Mes", f"${df_mes['UtilidadRetirable'].sum():,.2f}")

            with tab_p5:
                st.markdown("#### Historial y Gestión de Registros")
                for index, row in df_cuadratura.iterrows():
                    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 1])
                    with col_h1:
                        fecha_txt = str(row['Fecha']) if pd.notna(row['Fecha']) else "S/F"
                        st.markdown(f"**Fecha:** {fecha_txt}")
                    with col_h2:
                        v_total = float(row['VentaTotal']) if pd.notna(row['VentaTotal']) else 0.0
                        st.markdown(f"**Total:** ${v_total:,.2f}")
                        obs = str(row['Observaciones']) if pd.notna(row['Observaciones']) else "Sin obs"
                        st.caption(f"Obs: {obs}")
                    with col_h3:
                        u_retirable = float(row['UtilidadRetirable']) if pd.notna(row['UtilidadRetirable']) else 0.0
                        st.markdown(f"**Utilidad:** ${u_retirable:,.2f}")
                    with col_h4:
                        row_id = str(row['ID']) if pd.notna(row['ID']) else str(index)
                        if st.button("🗑️", key=f"del_cuat_{row_id}_{index}"):
                            df_filtrado = df_cuadratura.drop(index)
                            df_filtrado.drop(columns=['Fecha_dt'], errors='ignore').to_excel(archivo_cuadratura, index=False)
                            st.success("🗑️ ¡Registro eliminado con éxito!")
                            st.rerun()
                    st.divider()
        else:
            st.info("ℹ️ No hay registros guardados todavía.")
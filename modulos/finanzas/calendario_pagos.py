import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def mostrar_modulo_calendario_pagos(ruta_negocio):
    st.markdown("### 📅 Calendario de Pagos y Alerta Semanal")
    st.markdown("Monitorea los compromisos financieros de la semana en curso y detecta facturas vencidas.")

    archivo_cxp = os.path.join(ruta_negocio, "Cuentas_Por_Pagar.xlsx")

    if not os.path.exists(archivo_cxp):
        st.warning(f"⚠️ No se encuentra el archivo de cuentas por pagar para este negocio. Registra facturas primero.")
        return

    # 1. Cargamos las cuentas por pagar
    df_cxp = pd.read_excel(archivo_cxp)

    if df_cxp.empty:
        st.info("ℹ️ El registro de cuentas por pagar está vacío.")
        return

    # Filtramos solo las facturas PENDIENTES
    if 'Estado' in df_cxp.columns:
        pendientes = df_cxp[df_cxp['Estado'].str.upper() == 'PENDIENTE'].copy()
    else:
        pendientes = df_cxp.copy()

    if pendientes.empty:
        st.success("🎉 ¡Excelente noticia! No hay facturas pendientes en el sistema.")
        return

    # Convertimos las fechas a formato datetime
    pendientes['Fecha_Vencimiento'] = pd.to_datetime(pendientes['Fecha_Vencimiento'], errors='coerce')
   
    # Definimos el rango de la semana (Lunes a Domingo actual)
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana = inicio_semana.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_semana = inicio_semana + timedelta(days=6, hours=23, minutes=59, seconds=59)

    # Filtramos las facturas que vencen esta semana
    vencen_esta_semana = pendientes[
        (pendientes['Fecha_Vencimiento'] >= inicio_semana) &
        (pendientes['Fecha_Vencimiento'] <= fin_semana)
    ]

    # Filtramos las vencidas de semanas anteriores
    vencidas = pendientes[pendientes['Fecha_Vencimiento'] < inicio_semana]

    st.divider()
    st.markdown(f"**Semana Actual:** {inicio_semana.strftime('%d/%m/%Y')} al {fin_semana.strftime('%d/%m/%Y')}")

    # --- MÉTRICAS DE ALERTA ---
    col1, col2 = st.columns(2)
    with col1:
        total_semana = vencen_esta_semana['Monto_Total'].sum() if not vencen_esta_semana.empty else 0
        st.metric(label="🚨 A Pagar Esta Semana", value=f"${total_semana:,.0f}", delta=f"{len(vencen_esta_semana)} facturas")
    with col2:
        total_atrasado = vencidas['Monto_Total'].sum() if not vencidas.empty else 0
        st.metric(label="⚠️ Deuda Vencida (Atrasada)", value=f"${total_atrasado:,.0f}", delta=f"{len(vencidas)} facturas", delta_color="inverse")

    st.divider()

    # --- MOSTRAR FACTURAS QUE VENCEN ESTA SEMANA ---
    st.markdown("### 🔔 Vencimientos de Esta Semana")
    if not vencen_esta_semana.empty:
        st.warning(f"Tienes **{len(vencen_esta_semana)} factura(s)** que expiran en el transcurso de estos días.")
        st.dataframe(vencen_esta_semana, use_container_width=True)
    else:
        st.info("✔️ Estás al día: no hay facturas que expiren durante esta semana.")

    # --- MOSTRAR FACTURAS ATRASADAS ---
    if not vencidas.empty:
        st.markdown("### ❌ Facturas con Vencimiento Vencido")
        st.error(f"Atención: Hay **{len(vencidas)} factura(s)** de semanas anteriores que aún no han sido marcadas como pagadas.")
        st.dataframe(vencidas, use_container_width=True)
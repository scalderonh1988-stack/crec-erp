import streamlit as st
import pandas as pd
from datetime import date
# Importamos la conexión a tu base de datos y la seguridad de negocio
from data_manager import supabase, get_current_tenant

def mostrar_modulo_cuentas_por_pagar(ruta_negocio):
    st.markdown("### 💳 Módulo de Cuentas por Pagar y Proveedores")
    st.markdown("Administra y registra las facturas pendientes de tus proveedores. Cambia el estado a 'Pagado' cuando saldes la deuda (100% Nube).")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- 1. FORMULARIO PARA NUEVA FACTURA MANUAL ---
    with st.expander("➕ Registrar Nueva Factura de Proveedor Manualmente"):
        with st.form("form_nueva_cuenta_manual"):
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                prov_m = st.text_input("Nombre del Proveedor")
                num_fac_m = st.text_input("Número de Factura")
                monto_m = st.number_input("Monto Total ($)", min_value=0.0, step=100.0, value=0.0)
            with col_c2:
                f_emision = st.date_input("Fecha de Emisión", value=date.today())
                f_venc = st.date_input("Fecha de Vencimiento", value=date.today())
           
            btn_guardar_cuenta = st.form_submit_button("💾 Guardar Factura Pendiente")
            
            if btn_guardar_cuenta:
                if not prov_m or not num_fac_m or monto_m <= 0:
                    st.warning("⚠️ Completa todos los campos obligatorios y un monto mayor a 0.")
                else:
                    try:
                        nueva_fila = {
                            'rut_empresa': str(tenant_id),
                            'proveedor': prov_m,
                            'numero_factura': num_fac_m,
                            'fecha_emision': str(f_emision),
                            'fecha_vencimiento': str(f_venc),
                            'monto_total': float(monto_m),
                            'estado': 'PENDIENTE'
                        }
                        supabase.table("cuentas_por_pagar").insert(nueva_fila).execute()
                        st.success("✅ ¡Factura registrada correctamente en la nube!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar en la base de datos: {e}")

    st.divider()

    # --- 2. LECTURA DIRECTA DESDE SUPABASE ---
    try:
        res = supabase.table("cuentas_por_pagar").select("*").eq("rut_empresa", str(tenant_id)).execute()
        df_cuentas = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"❌ Error al conectar con Supabase: {e}")
        df_cuentas = pd.DataFrame()

    if df_cuentas.empty:
        st.info("ℹ️ No hay cuentas por pagar registradas para este local.")
    else:
        # Filtramos las pendientes para sumar la deuda
        df_pendientes = df_cuentas[df_cuentas['estado'].astype(str).str.upper() == 'PENDIENTE']
        deuda_total_pendiente = df_pendientes['monto_total'].sum() if not df_pendientes.empty else 0.0

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(label="🔥 Deuda Total Pendiente", value=f"${deuda_total_pendiente:,.0f}")
        with col_m2:
            st.metric(label="📄 Total Documentos Registrados", value=len(df_cuentas))

        st.divider()
        st.markdown("#### 📂 Listado General de Cuentas")
        st.markdown("Utiliza el botón **'✅ Marcar Pagado'** al lado de cada documento para actualizar su estado de inmediato.")

        for idx, row in df_cuentas.iterrows():
            estado_actual = str(row.get('estado', 'PENDIENTE')).upper()
            es_pendiente = estado_actual == 'PENDIENTE'

            c_info, c_action = st.columns([8, 2])
            with c_info:
                st.info(f"🏢 **{row.get('proveedor', '')}** | Fac: **{row.get('numero_factura', '')}** | Emisión: {row.get('fecha_emision', '')} | Vence: **{row.get('fecha_vencimiento', '')}** | Monto: **${float(row.get('monto_total', 0)):,.0f}** | Estado: **{estado_actual}**")
           
            with c_action:
                if es_pendiente:
                    if st.button("✅ Marcar Pagado", key=f"pagar_cta_{idx}_{row.get('numero_factura')}", type="primary"):
                        try:
                            # Actualizamos el estado a PAGADO en Supabase
                            supabase.table("cuentas_por_pagar").update({"estado": "PAGADO"}).eq("rut_empresa", str(tenant_id)).eq("id", row.get('id')).execute()
                            st.success(f"🎉 ¡Factura {row.get('numero_factura', '')} marcada como Pagada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar el pago: {e}")
                else:
                    st.success("✔ Pagado")
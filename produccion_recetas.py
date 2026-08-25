import streamlit as st
import pandas as pd
from data_manager import supabase, get_current_tenant

def mostrar_modulo_produccion():
    st.markdown("### 🍔 Módulo de Producción y Fichas Técnicas")
    st.markdown("Diseña tus recetas uniendo un 'Producto Final' con sus 'Ingredientes'. El costo de producción se calculará en tiempo real según tus compras.")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- 1. LECTURA DE PRODUCTOS E INGREDIENTES ---
    try:
        res_prod = supabase.table("productos").select("codigo, descripcion, costo").eq("rut_empresa", str(tenant_id)).execute()
        df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al conectar con Supabase: {e}")
        return

    if df_prod.empty:
        st.warning("⚠️ No hay productos en la base de datos para armar recetas.")
        return

    # Filtramos duplicados en caso de que un producto esté en varias bodegas
    df_prod_unico = df_prod.drop_duplicates(subset=['codigo'])
    opciones_productos = [f"{row['codigo']} - {row['descripcion']}" for _, row in df_prod_unico.iterrows()]

    st.divider()
    st.markdown("#### 1️⃣ Selecciona el Producto a Preparar (Producto Final)")
    producto_final_sel = st.selectbox("Elige el plato o producto ensamblado que venderás en el POS:", ["-- Selecciona un producto --"] + opciones_productos)

    if producto_final_sel != "-- Selecciona un producto --":
        codigo_final = producto_final_sel.split(" - ")[0]
        nombre_final = producto_final_sel.split(" - ")[1]

        col1, col2 = st.columns([1, 1.2])

        # --- 2. FORMULARIO PARA AGREGAR INGREDIENTES ---
        with col1:
            st.markdown(f"##### ➕ Añadir ingrediente a: {nombre_final}")
            with st.form("form_agregar_ingrediente"):
                ingrediente_sel = st.selectbox("Selecciona la Materia Prima:", opciones_productos)
                cantidad_usada = st.number_input("Cantidad (Ej: 0.15 para 150g / 2 para 2 unidades)", min_value=0.001, value=1.000, step=0.050, format="%.3f")
                
                btn_guardar_ing = st.form_submit_button("💾 Guardar Ingrediente", type="primary")
                
                if btn_guardar_ing:
                    cod_ing = ingrediente_sel.split(" - ")[0]
                    nom_ing = ingrediente_sel.split(" - ")[1]
                    
                    if cod_ing == codigo_final:
                        st.error("❌ Un producto no puede ser ingrediente de sí mismo.")
                    else:
                        nueva_linea = {
                            "rut_empresa": str(tenant_id),
                            "codigo_producto_final": codigo_final,
                            "codigo_ingrediente": cod_ing,
                            "nombre_ingrediente": nom_ing,
                            "cantidad_usada": float(cantidad_usada)
                        }
                        try:
                            supabase.table("recetas").insert(nueva_linea).execute()
                            st.success(f"✅ {nom_ing} agregado a la receta.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar en Supabase: {e}")

        # --- 3. VISUALIZACIÓN DE LA FICHA TÉCNICA Y COSTEO REAL ---
        with col2:
            st.markdown(f"##### 🧾 Ficha Técnica Actual")
            try:
                res_receta = supabase.table("recetas").select("id, nombre_ingrediente, codigo_ingrediente, cantidad_usada").eq("rut_empresa", str(tenant_id)).eq("codigo_producto_final", codigo_final).execute()
                df_receta = pd.DataFrame(res_receta.data) if res_receta.data else pd.DataFrame()
            except Exception:
                df_receta = pd.DataFrame()

            if not df_receta.empty:
                costo_total_receta = 0.0
                
                # Motor de Costeo Dinámico (Busca el costo actual de cada ingrediente)
                for i, row in df_receta.iterrows():
                    match_ing = df_prod_unico[df_prod_unico['codigo'] == row['codigo_ingrediente']]
                    costo_unitario = float(match_ing['costo'].values[0]) if not match_ing.empty else 0.0
                    
                    subtotal_ingrediente = costo_unitario * float(row['cantidad_usada'])
                    costo_total_receta += subtotal_ingrediente
                    
                    df_receta.at[i, 'Costo Actual ($)'] = subtotal_ingrediente

                # Formateo visual de la tabla
                df_mostrar = df_receta[['nombre_ingrediente', 'cantidad_usada', 'Costo Actual ($)']].rename(columns={
                    'nombre_ingrediente': 'Ingrediente',
                    'cantidad_usada': 'Cantidad'
                })
                st.dataframe(df_mostrar, use_container_width=True)
                
                st.info(f"💰 **Costo Real de Producción (Hoy): ${costo_total_receta:,.2f}**")
                
                # Opciones de edición
                id_a_borrar = st.selectbox("Selecciona un ingrediente para eliminar:", ["-- Ninguno --"] + df_receta['nombre_ingrediente'].tolist())
                if id_a_borrar != "-- Ninguno --":
                    if st.button("🗑️ Eliminar Ingrediente Seleccionado"):
                        id_real = df_receta[df_receta['nombre_ingrediente'] == id_a_borrar]['id'].values[0]
                        supabase.table("recetas").delete().eq("id", int(id_real)).execute()
                        st.rerun()
            else:
                st.info("ℹ️ Aún no has agregado ingredientes a esta ficha técnica.")
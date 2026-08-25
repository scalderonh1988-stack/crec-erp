import streamlit as st
import pandas as pd
from data_manager import supabase, get_current_tenant

def mostrar_modulo_produccion():
    if st.button("🏠 Volver al Home"):
        st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
        st.rerun()

    st.markdown("### 🍔 Módulo de Producción y Fichas Técnicas")
    st.markdown("Diseña tus recetas uniendo un 'Producto Final' o 'Pack' con sus 'Ingredientes'. El costo se calcula en tiempo real y podrás publicarlo en el POS.")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- 1. LECTURA DE DATOS ---
    try:
        res_prod = supabase.table("productos").select("codigo, descripcion, precio_venta").eq("rut_empresa", str(tenant_id)).execute()
        df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()

        res_ing = supabase.table("ingredientes").select("codigo, descripcion, costo, bodega").eq("rut_empresa", str(tenant_id)).execute()
        df_ing = pd.DataFrame(res_ing.data) if res_ing.data else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al conectar con Supabase: {e}")
        return

    st.divider()
    st.markdown("#### 1️⃣ Selecciona o Crea el Producto Final / Pack")

    nombres_existentes = df_prod['descripcion'].tolist() if not df_prod.empty else []
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        tipo_accion = st.radio("Acción:", ["Seleccionar producto existente", "✨ Crear nuevo producto o pack aquí mismo"])
    
    with col_sel2:
        if tipo_accion == "Seleccionar producto existente":
            if not nombres_existentes:
                st.warning("⚠️ No hay productos creados aún. Usa la opción de crear nuevo.")
                nombre_final = ""
                codigo_final = ""
            else:
                prod_elegido = st.selectbox("Elige el producto:", nombres_existentes)
                match_p = df_prod[df_prod['descripcion'] == prod_elegido]
                codigo_final = match_p['codigo'].values[0] if not match_p.empty else ""
                nombre_final = prod_elegido
        else:
            # 🚨 AQUÍ CAMBIÓ: Primero escribes el nombre con total libertad
            nombre_final = st.text_input("Nombre del Producto / Pack (Ej: PACK VERANO o SÁNDWICH ITALIANO)")
            
            # El código se autogenera de forma limpia quitando espacios y acentos, pero puedes editarlo si deseas
            codigo_sugerido = nombre_final.upper().strip().replace(" ", "-").replace(":", "").replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U") if nombre_final else ""
            codigo_final = st.text_input("Código Interno (Autogenerado, editable)", value=codigo_sugerido)

    if codigo_final and nombre_final:
        st.markdown(f"--- \n### 🛠️ Armando Ficha Técnica para: **{nombre_final}** (Cód: `{codigo_final}`)")
        
        col1, col2 = st.columns([1, 1.2])

        # --- 2. FORMULARIO PARA AGREGAR INGREDIENTES ---
        with col1:
            st.markdown("##### ➕ Añadir Insumos / Componentes")
            if df_ing.empty:
                st.warning("⚠️ No tienes ingredientes registrados en la pestaña 'Ingredientes'.")
            else:
                opciones_ingredientes = [f"{row['codigo']} - {row['descripcion']} (Costo: ${row['costo']})" for _, row in df_ing.iterrows()]
                
                with st.form("form_agregar_ingrediente_receta"):
                    ingrediente_sel = st.selectbox("Selecciona la Materia Prima / Insumo:", opciones_ingredientes)
                    cantidad_usada = st.number_input("Cantidad a usar", min_value=0.001, value=1.000, step=0.050, format="%.3f")
                    
                    btn_guardar_ing = st.form_submit_button("➕ Agregar a la Receta", type="primary")
                    
                    if btn_guardar_ing:
                        cod_ing = ingrediente_sel.split(" - ")[0]
                        nom_ing = ingrediente_sel.split(" - ")[1].split(" (Costo:")[0]
                        
                        nueva_linea = {
                            "rut_empresa": str(tenant_id),
                            "codigo_producto_final": str(codigo_final).strip(),
                            "codigo_ingrediente": cod_ing,
                            "nombre_ingrediente": nom_ing,
                            "cantidad_usada": float(cantidad_usada)
                        }
                        try:
                            supabase.table("recetas").insert(nueva_linea).execute()
                            st.success(f"✅ {nom_ing} agregado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")

        # --- 3. VISUALIZACIÓN Y PUBLICACIÓN EN EL POS ---
        with col2:
            st.markdown("##### 🧾 Ficha Técnica y Costo Real")
            try:
                res_receta = supabase.table("recetas").select("id, nombre_ingrediente, codigo_ingrediente, cantidad_usada").eq("rut_empresa", str(tenant_id)).eq("codigo_producto_final", str(codigo_final)).execute()
                df_receta = pd.DataFrame(res_receta.data) if res_receta.data else pd.DataFrame()
            except Exception:
                df_receta = pd.DataFrame()

            costo_total_receta = 0.0
            if not df_receta.empty:
                for i, row in df_receta.iterrows():
                    match_ing = df_ing[df_ing['codigo'] == row['codigo_ingrediente']]
                    costo_unitario = float(match_ing['costo'].values[0]) if not match_ing.empty else 0.0
                    subtotal_ingrediente = costo_unitario * float(row['cantidad_usada'])
                    costo_total_receta += subtotal_ingrediente
                    df_receta.at[i, 'Costo Actual ($)'] = subtotal_ingrediente

                df_mostrar = df_receta[['nombre_ingrediente', 'cantidad_usada', 'Costo Actual ($)']].rename(columns={
                    'nombre_ingrediente': 'Componente / Ingrediente',
                    'cantidad_usada': 'Cantidad'
                })
                st.dataframe(df_mostrar, use_container_width=True)
                
                st.info(f"💰 **Costo Real de Producción / Armado: ${costo_total_receta:,.2f}**")
                
                id_a_borrar = st.selectbox("Eliminar componente:", ["-- Ninguno --"] + df_receta['nombre_ingrediente'].tolist())
                if id_a_borrar != "-- Ninguno --":
                    if st.button("🗑️ Borrar Componente"):
                        id_real = df_receta[df_receta['nombre_ingrediente'] == id_a_borrar]['id'].values[0]
                        supabase.table("recetas").delete().eq("id", int(id_real)).execute()
                        st.rerun()
            else:
                st.info("ℹ️ Aún no hay componentes en esta receta.")

            st.divider()
            st.markdown("##### 🚀 Publicar Producto / Pack en el POS")
            precio_venta_publico = st.number_input("Precio de Venta al Público ($)", min_value=0.0, value=3500.0, step=100.0)
            
            if st.button("💾 Guardar y Publicar en el Punto de Venta", type="primary"):
                if precio_venta_publico <= 0:
                    st.warning("⚠️ Ingresa un precio de venta válido.")
                else:
                    datos_producto_final = {
                        "rut_empresa": str(tenant_id),
                        "codigo": str(codigo_final).strip(),
                        "descripcion": str(nombre_final).strip(),
                        "costo": round(costo_total_receta, 2),
                        "precio_venta": float(precio_venta_publico),
                        "stock": 0.0,
                        "categoria": "COMBOS / ELABORADOS",
                        "activo": "Si",
                        "disponible_venta": True
                    }
                    try:
                        supabase.table("productos").upsert(datos_producto_final, on_conflict="rut_empresa,codigo").execute()
                        st.success(f"🎉 ¡'{nombre_final}' publicado con éxito! Ya se puede cobrar en el POS con su costo real de ${costo_total_receta:,.2f}.")
                    except Exception as e:
                        st.error(f"❌ Error al publicar: {e}")
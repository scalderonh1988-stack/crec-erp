import streamlit as st
import pandas as pd
from data_manager import supabase, get_current_tenant

def mostrar_modulo_produccion():
    if st.button("🏠 Volver al Home"):
        st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
        st.rerun()

    st.markdown("### 🍔 Módulo de Producción y Fichas Técnicas")
    st.markdown("Diseña tus recetas eligiendo si es un **Pack** (de productos terminados) o una **Elaboración** (con ingredientes y materia prima).")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- 1. LECTURA DE AMBAS TABLAS ---
    try:
        # Productos (para venta y para armar Packs)
        res_prod = supabase.table("productos").select("codigo, descripcion, costo, precio_venta").eq("rut_empresa", str(tenant_id)).execute()
        df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()

        # Ingredientes (para sándwiches, platos y preparaciones)
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
                st.warning("⚠️ No hay productos creados aún.")
                nombre_final = ""
                codigo_final = ""
            else:
                prod_elegido = st.selectbox("Elige el producto:", nombres_existentes)
                match_p = df_prod[df_prod['descripcion'] == prod_elegido]
                codigo_final = match_p['codigo'].values[0] if not match_p.empty else ""
                nombre_final = prod_elegido
        else:
            nombre_final = st.text_input("Nombre del Plato o Pack (Ej: SÁNDWICH ITALIANO o PACK VERANO)")
            codigo_sugerido = nombre_final.upper().strip().replace(" ", "-").replace(":", "").replace("+", "-").replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U") if nombre_final else ""
            codigo_final = st.text_input("Código Interno (Autogenerado, editable)", value=codigo_sugerido)

    if codigo_final and nombre_final:
        st.markdown(f"--- \n### 🛠️ Armando Receta para: **{nombre_final}** (Cód: `{codigo_final}`)")
        
        # 🚨 SELECTOR INTELIGENTE: ¿Qué tipo de receta es?
        tipo_receta = st.radio(
            "Selecciona el tipo de componentes para esta receta:",
            ["📦 Es un Pack (Usa productos terminados de inventario)", "🍅 Es una Elaboración (Usa ingredientes / materia prima)"],
            horizontal=True
        )

        col1, col2 = st.columns([1, 1.2])

        # --- 2. FORMULARIO DINÁMICO SEGÚN EL TIPO SELECCIONADO ---
        with col1:
            if "📦 Es un Pack" in tipo_receta:
                st.markdown("##### ➕ Añadir Productos al Pack")
                if df_prod.empty:
                    st.warning("⚠️ No hay productos en el inventario.")
                else:
                    dict_productos = {}
                    opciones_busqueda = []
                    for _, row in df_prod.iterrows():
                        if str(row['codigo']).strip() != str(codigo_final).strip():
                            etiqueta = f"{row['codigo']} - {row['descripcion']} (Costo: ${row['costo']})"
                            opciones_busqueda.append(etiqueta)
                            dict_productos[etiqueta] = row['codigo']

                    if not opciones_busqueda:
                        st.warning("⚠️ No hay otros productos disponibles.")
                    else:
                        with st.form("form_pack"):
                            componente_sel = st.selectbox("🔍 Busca el producto terminado:", options=opciones_busqueda)
                            cantidad_usada = st.number_input("Cantidad de unidades", min_value=0.001, value=1.000, step=1.0, format="%.2f")
                            btn_g = st.form_submit_button("➕ Agregar al Pack", type="primary")
                            
                            if btn_g and componente_sel:
                                cod_comp = componente_sel.split(" - ")[0]
                                nom_comp = componente_sel.split(" - ")[1].split(" (Costo:")[0]
                                guardado_receta(tenant_id, codigo_final, cod_comp, nom_comp, cantidad_usada)

            else:
                st.markdown("##### ➕ Añadir Insumos / Materia Prima")
                if df_ing.empty:
                    st.warning("⚠️ No tienes ingredientes registrados en la pestaña 'Ingredientes'.")
                else:
                    opciones_ing = [f"{row['codigo']} - {row['descripcion']} (Costo: ${row['costo']})" for _, row in df_ing.iterrows()]
                    with st.form("form_ing"):
                        ingrediente_sel = st.selectbox("🔍 Busca el ingrediente:", options=opciones_ing)
                        cantidad_usada = st.number_input("Cantidad (Ej: 1 unidad o 0.150 para gramos)", min_value=0.001, value=1.000, step=0.050, format="%.3f")
                        btn_g = st.form_submit_button("➕ Agregar a la Elaboración", type="primary")
                        
                        if btn_g and ingrediente_sel:
                            cod_comp = ingrediente_sel.split(" - ")[0]
                            nom_comp = ingrediente_sel.split(" - ")[1].split(" (Costo:")[0]
                            guardado_receta(tenant_id, codigo_final, cod_comp, nom_comp, cantidad_usada)

        # --- 3. VISUALIZACIÓN Y COSTEO ---
        with col2:
            st.markdown(f"##### 🧾 Ficha Técnica y Costo Real")
            try:
                res_receta = supabase.table("recetas").select("id, nombre_ingrediente, codigo_ingrediente, cantidad_usada").eq("rut_empresa", str(tenant_id)).eq("codigo_producto_final", str(codigo_final)).execute()
                df_receta = pd.DataFrame(res_receta.data) if res_receta.data else pd.DataFrame()
            except Exception:
                df_receta = pd.DataFrame()

            costo_total_receta = 0.0
            if not df_receta.empty:
                for i, row in df_receta.iterrows():
                    # Buscamos el costo tanto en productos como en ingredientes de forma inteligente
                    match_prod = df_prod[df_prod['codigo'] == row['codigo_ingrediente']]
                    match_ing = df_ing[df_ing['codigo'] == row['codigo_ingrediente']]
                    
                    costo_unitario = 0.0
                    if not match_prod.empty:
                        costo_unitario = float(match_prod['costo'].values[0])
                    elif not match_ing.empty:
                        costo_unitario = float(match_ing['costo'].values[0])
                        
                    subtotal = costo_unitario * float(row['cantidad_usada'])
                    costo_total_receta += subtotal
                    df_receta.at[i, 'Costo Actual ($)'] = subtotal

                df_mostrar = df_receta[['nombre_ingrediente', 'cantidad_usada', 'Costo Actual ($)']].rename(columns={
                    'nombre_ingrediente': 'Componente / Ingrediente',
                    'cantidad_usada': 'Cantidad'
                })
                st.dataframe(df_mostrar, use_container_width=True)
                
                st.info(f"💰 **Costo Real de Producción / Armado: ${costo_total_receta:,.2f}**")
                
                id_a_borrar = st.selectbox("Eliminar componente:", ["-- Ninguno --"] + df_receta['nombre_ingrediente'].tolist())
                if id_a_borrar != "-- Ninguno --":
                    if st.button("🗑️ Quitar Componente"):
                        id_real = df_receta[df_receta['nombre_ingrediente'] == id_a_borrar]['id'].values[0]
                        supabase.table("recetas").delete().eq("id", int(id_real)).execute()
                        st.rerun()
            else:
                st.info("ℹ️ Aún no hay componentes en esta receta.")

            st.divider()
            st.markdown("##### 🚀 Publicar en el POS")
            precio_venta_p = st.number_input("Precio de Venta al Público ($)", min_value=0.0, value=3500.0, step=100.0)
            
            if st.button("💾 Guardar y Publicar en el Punto de Venta", type="primary"):
                if precio_venta_p <= 0:
                    st.warning("⚠️ Ingresa un precio válido.")
                else:
                    datos_finales = {
                        "rut_empresa": str(tenant_id),
                        "codigo": str(codigo_final).strip(),
                        "descripcion": str(nombre_final).strip(),
                        "costo": round(costo_total_receta, 2),
                        "precio_venta": float(precio_venta_p),
                        "stock": 0.0,
                        "categoria": "COMBOS / ELABORADOS",
                        "activo": "Si",
                        "disponible_venta": True
                    }
                    try:
                        supabase.table("productos").upsert(datos_finales, on_conflict="rut_empresa,codigo").execute()
                        st.success(f"🎉 ¡'{nombre_final}' publicado con éxito! Costo real: ${costo_total_receta:,.2f}.")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

def guardado_receta(tenant_id, codigo_final, cod_comp, nom_comp, cantidad_usada):
    nueva_linea = {
        "rut_empresa": str(tenant_id),
        "codigo_producto_final": str(codigo_final).strip(),
        "codigo_ingrediente": cod_comp,
        "nombre_ingrediente": nom_comp,
        "cantidad_usada": float(cantidad_usada)
    }
    try:
        supabase.table("recetas").insert(nueva_linea).execute()
        st.success(f"✅ {nom_comp} agregado con éxito.")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error al guardar: {e}")
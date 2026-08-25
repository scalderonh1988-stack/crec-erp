import streamlit as st
import pandas as pd
from data_manager import supabase, get_current_tenant

def mostrar_modulo_produccion():
    if st.button("🏠 Volver al Home"):
        st.session_state.menu_seleccionado = "🏠 Home / Bienvenida"
        st.rerun()

    st.markdown("### 🍔 Módulo de Producción, Recetas y Materia Prima")
    st.markdown("Administra tus insumos a granel o paquetes y diseña tus fichas técnicas o packs para el POS.")

    tenant_id = get_current_tenant()
    if not tenant_id:
        st.error("❌ No se ha identificado el negocio. Por favor, inicia sesión nuevamente.")
        return

    # --- PESTAÑAS INTERNAS DEL MÓDULO ---
    tab_recetas, tab_gestion_ing = st.tabs(["🛠️ Armado de Recetas y Packs", "🍅 Gestión y Compra de Ingredientes"])

    # ==========================================
    # PESTAÑA 1: ARMADO DE RECETAS Y PACKS
    # ==========================================
    with tab_recetas:
        try:
            res_prod = supabase.table("productos").select("codigo, descripcion, costo, precio_venta").eq("rut_empresa", str(tenant_id)).execute()
            df_prod = pd.DataFrame(res_prod.data) if res_prod.data else pd.DataFrame()

            res_ing = supabase.table("ingredientes").select("codigo, descripcion, costo, bodega").eq("rut_empresa", str(tenant_id)).execute()
            df_ing = pd.DataFrame(res_ing.data) if res_ing.data else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Error al conectar con Supabase: {e}")
            return

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
                nombre_final = st.text_input("Nombre del Plato o Pack (Ej: PACK VERANO WHISKY)")
                codigo_sugerido = nombre_final.upper().strip().replace(" ", "-").replace(":", "").replace("+", "-").replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U") if nombre_final else ""
                codigo_final = st.text_input("Código Interno (Autogenerado, editable)", value=codigo_sugerido)

        if codigo_final and nombre_final:
            st.markdown(f"--- \n### 🛠️ Armando Receta para: **{nombre_final}** (Cód: `{codigo_final}`)")
            
            tipo_receta = st.radio(
                "Selecciona el tipo de componentes para esta receta:",
                ["📦 Es un Pack (Usa productos terminados de inventario)", "🍅 Es una Elaboración (Usa ingredientes / materia prima)"],
                horizontal=True
            )

            col1, col2 = st.columns([1, 1.2])

            with col1:
                if "📦 Es un Pack" in tipo_receta:
                    st.markdown("##### ➕ Añadir Productos al Pack")
                    if df_prod.empty:
                        st.warning("⚠️ No hay productos en el inventario.")
                    else:
                        opciones_busqueda = []
                        for _, row in df_prod.iterrows():
                            if str(row['codigo']).strip() != str(codigo_final).strip():
                                etiqueta = f"{row['codigo']} - {row['descripcion']} (Costo: ${row['costo']})"
                                opciones_busqueda.append(etiqueta)

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
                        st.warning("⚠️ No tienes ingredientes registrados en la pestaña de Gestión de Ingredientes.")
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
                        costo_unitario = 0.0
                        cod_buscado = str(row['codigo_ingrediente']).strip()
                        
                        if not df_prod.empty and 'codigo' in df_prod.columns:
                            match_prod = df_prod[df_prod['codigo'].astype(str).str.strip() == cod_buscado]
                            if not match_prod.empty:
                                costo_unitario = float(match_prod['costo'].values[0])
                        
                        if costo_unitario == 0.0 and not df_ing.empty and 'codigo' in df_ing.columns:
                            match_ing = df_ing[df_ing['codigo'].astype(str).str.strip() == cod_buscado]
                            if not match_ing.empty:
                                costo_unitario = float(match_ing['costo'].values[0])
                            
                        subtotal = costo_unitario * float(row['cantidad_usada'])
                        costo_total_receta += subtotal
                        df_receta.loc[i, 'Costo Actual ($)'] = subtotal

                    df_mostrar = df_receta[['nombre_ingrediente', 'cantidad_usada', 'Costo Actual ($)']].rename(columns={
                        'nombre_ingrediente': 'Componente / Ingrediente',
                        'cantidad_usada': 'Cantidad'
                    })
                    st.dataframe(df_mostrar, use_container_width=True)
                    
                    st.info(f"💰 **Costo Real de Producción / Armado: ${costo_total_receta:,.2f}**")
                    
                    # 🚨 NUEVO: Desglose Tributario e Impuestos del Pack
                    nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
                    tasa_iva = 22.0 if "URUGUAY" in nombre_empresa_act or str(tenant_id) == "219449970012" else 19.0
                    
                    costo_neto_pack = costo_total_receta / (1.0 + (tasa_iva / 100.0))
                    iva_credito_pack = costo_total_receta - costo_neto_pack
                    
                    with st.expander("🏛️ Ver Desglose Tributario del Costo (IVA y Neto)"):
                        st.markdown(f"- **Costo Neto:** ${costo_neto_pack:,.2f}")
                        st.markdown(f"- **IVA Crédito ({tasa_iva:g}%):** ${iva_credito_pack:,.2f}")
                        st.markdown(f"- **Costo Bruto Total:** ${costo_total_receta:,.2f}")

                    # 🚨 NUEVO: Cuadro visible de Nombre y Código del Pack antes de publicar
                    st.markdown("##### 📝 Identificación Oficial del Pack")
                    col_id1, col_id2 = st.columns(2)
                    with col_id1:
                        nombre_pack_final = st.text_input("Nombre del Pack para el POS", value=nombre_final)
                    with col_id2:
                        codigo_pack_final = st.text_input("Código de Barras / Interno", value=codigo_final)

                    id_a_borrar = st.selectbox("Eliminar componente:", ["-- Ninguno --"] + df_receta['nombre_ingrediente'].tolist())
                    if id_a_borrar != "-- Ninguno --":
                        if st.button("🗑️ Quitar Componente"):
                            id_real = df_receta[df_receta['nombre_ingrediente'] == id_a_borrar]['id'].values[0]
                            supabase.table("recetas").delete().eq("id", int(id_real)).execute()
                            st.rerun()
                else:
                    st.info("ℹ️ Aún no hay componentes en esta receta.")
                    nombre_pack_final = nombre_final
                    codigo_pack_final = codigo_final

                st.divider()
                st.markdown("##### 🚀 Publicar en el POS")
                precio_venta_p = st.number_input("Precio de Venta al Público ($)", min_value=0.0, value=3500.0, step=100.0)
                
                # Cálculo rápido de margen proyectado con el impuesto desglosado
                if precio_venta_p > 0 and costo_total_receta > 0:
                    margen_estimado = ((precio_venta_p - costo_total_receta) / precio_venta_p) * 100
                    st.caption(f"📈 Margen de ganancia bruto estimado: **{margen_estimado:.1f}%**")

                if st.button("💾 Guardar y Publicar en el Punto de Venta", type="primary"):
                    if precio_venta_p <= 0:
                        st.warning("⚠️ Ingresa un precio válido.")
                    elif not nombre_pack_final or not codigo_pack_final:
                        st.warning("⚠️ El nombre y el código del pack son obligatorios.")
                    else:
                        datos_finales = {
                            "rut_empresa": str(tenant_id),
                            "codigo": str(codigo_pack_final).strip(),
                            "descripcion": str(nombre_pack_final).strip(),
                            "costo": round(costo_total_receta, 2),
                            "precio_venta": float(precio_venta_p),
                            "stock": 0.0,
                            "categoria": "COMBOS / ELABORADOS",
                            "activo": "Si",
                            "disponible_venta": True
                        }
                        try:
                            supabase.table("productos").upsert(datos_finales, on_conflict="rut_empresa,codigo").execute()
                            st.success(f"🎉 ¡'{nombre_pack_final}' publicado con éxito! Costo real: ${costo_total_receta:,.2f}.")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

    # ==========================================
    # PESTAÑA 2: GESTIÓN DE INGREDIENTES
    # ==========================================
    with tab_gestion_ing:
        st.markdown("#### 🍅 Registro y Control de Materia Prima e Insumos")
        st.info("💡 Registra aquí insumos a granel o paquetes. No aparecen en el POS, se usan exclusivamente para armar las recetas.")
        
        try:
            res_ing_tab = supabase.table("ingredientes").select("*").eq("rut_empresa", str(tenant_id)).execute()
            df_insumos_tabla = pd.DataFrame(res_ing_tab.data) if res_ing_tab.data else pd.DataFrame()
        except Exception:
            df_insumos_tabla = pd.DataFrame()

        if not df_insumos_tabla.empty:
            st.markdown("##### Insumos Actuales en Bodega:")
            st.dataframe(df_insumos_tabla[['codigo', 'descripcion', 'categoria', 'bodega', 'stock', 'costo']], use_container_width=True)
        else:
            st.info("ℹ️ No hay ingredientes registrados todavía.")

        with st.form("form_crear_ingrediente_produccion", clear_on_submit=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                codigo_ing = st.text_input("Código del Insumo (Ej: INS-001) *")
                descripcion_ing = st.text_input("Nombre del Ingrediente (Ej: Salchichas) *")
                categoria_ing = st.selectbox("Categoría", ["VEGETALES", "CARNES", "PANADERIA", "SALSAS", "LACTEOS", "OTROS"])
                formato_ing = st.selectbox("Formato de Compra", ["Unidad", "Granel (Kg / Litros)", "Paquete / Caja"])
                
            with col_i2:
                bodega_ing_sel = st.text_input("🏢 Bodega / Sucursal:", value="Bodega Principal")
                stock_ing = st.number_input("Cantidad Comprada (Ej: 1 paquete, o 2.5 kilos)", min_value=0.0, step=0.1, format="%.2f")
                unidades_paquete = st.number_input("Si es Paquete, ¿Cuántas unidades trae?", min_value=1.0, value=1.0, step=1.0)
                costo_bruto_ing = st.number_input("Costo Bruto TOTAL de esta compra ($)", min_value=0.0, step=100.0)

            if st.form_submit_button("💾 Guardar Ingrediente"):
                if not codigo_ing or not descripcion_ing:
                    st.warning("⚠️ El Código y Nombre del ingrediente son obligatorios.")
                else:
                    nombre_empresa_act = str(st.session_state.get("nombre_empresa", "")).upper()
                    tasa_defecto = 22.0 if "URUGUAY" in nombre_empresa_act or str(tenant_id) == "219449970012" else 19.0
                    
                    stock_real_guardar = float(stock_ing) * float(unidades_paquete)
                    costo_bruto_unitario = (costo_bruto_ing / stock_real_guardar) if stock_real_guardar > 0 else costo_bruto_ing
                    costo_neto_calc = costo_bruto_unitario / (1.0 + (tasa_defecto / 100.0)) if costo_bruto_unitario > 0 else 0.0

                    descripcion_final = f"{descripcion_ing.strip()} (Paq. x{int(unidades_paquete)})" if formato_ing == "Paquete / Caja" else descripcion_ing.strip()

                    nuevo_ingrediente_nube = {
                        "rut_empresa": str(tenant_id),
                        "codigo": codigo_ing.strip(),
                        "descripcion": descripcion_final,
                        "categoria": categoria_ing,
                        "bodega": bodega_ing_sel.strip(' "\''),
                        "stock": stock_real_guardar,
                        "costo": round(costo_neto_calc, 2)
                    }
                    try:
                        supabase.table("ingredientes").insert(nuevo_ingrediente_nube).execute()
                        st.success(f"✅ ¡Ingrediente guardado con éxito!")
                        st.rerun()
                    except Exception as e: 
                        st.error(f"❌ Error al guardar (¿Código duplicado?): {e}")

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
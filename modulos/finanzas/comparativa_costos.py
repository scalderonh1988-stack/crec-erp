import pandas as pd
import openpyxl
import os

print("🔍 Analizando variaciones de precios de compra frente a la base maestra...")

archivo_base = "BASE DE DATOS.xlsx"
archivo_recepcion = "Recepcion_Proveedor.xlsx"
archivo_reporte = "Reporte_Variacion_Costos.xlsx"

if not os.path.exists(archivo_base) or not os.path.exists(archivo_recepcion):
    print("❌ Error crítico: Falta el archivo maestro o el archivo de recepción del proveedor.")
else:
    # 1. Leemos la base de datos y la recepción actual asegurando códigos en texto
    df_base = pd.read_excel(archivo_base, dtype={'Código': str})
    df_rec = pd.read_excel(archivo_recepcion, dtype={'Código': str})

    # Identificamos las columnas de costo
    col_costo_base = next((col for col in df_base.columns if 'costo' in col.lower()), None)
    
    if not col_costo_base:
        print("⚠️ No se encontró la columna de costo en la base de datos maestra.")
    else:
        # Verificamos si en la recepción viene el nuevo costo
        col_costo_rec = next((col for col in df_rec.columns if 'costo' in col.lower() or 'nuevo' in col.lower()), None)

        if not col_costo_rec:
            print("⚠️ El archivo 'Recepcion_Proveedor.xlsx' no tiene una columna de costo (ej. 'Nuevo_Costo').")
        else:
            resultados_comparativa = []

            # 2. Cruzamos los datos para comparar
            for _, row_rec in df_rec.iterrows():
                cod = str(row_rec['Código']).strip()
                costo_nuevo = float(row_rec[col_costo_rec]) if pd.notna(row_rec[col_costo_rec]) else 0

                # Buscamos el producto en la base maestra
                match = df_base[df_base['Código'].astype(str).str.strip() == cod]

                if not match.empty:
                    descripcion = match['Descripción'].values[0] if 'Descripción' in match.columns else "Sin descripción"
                    costo_antiguo = float(match[col_costo_base].values[0]) if pd.notna(match[col_costo_base].values[0]) else 0

                    # Calculamos la variación
                    diferencia_dinero = costo_nuevo - costo_antiguo
                    
                    if costo_antiguo > 0:
                        variacion_porcentaje = (diferencia_dinero / costo_antiguo) * 100
                    else:
                        variacion_porcentaje = 0

                    # Determinamos el estado de la variación
                    if diferencia_dinero > 0:
                        estado = "📈 ALZA DE PRECIO"
                    elif diferencia_dinero < 0:
                        estado = "📉 BAJA DE PRECIO"
                    else:
                        estado = "✔️ SIN VARIACIÓN"

                    resultados_comparativa.append({
                        'Código': cod,
                        'Descripción': descripcion,
                        'Costo_Anterior': costo_antiguo,
                        'Costo_Nuevo_Factura': costo_nuevo,
                        'Variacion_Dinero': round(diferencia_dinero, 2),
                        'Variacion_%': round(variacion_porcentaje, 2),
                        'Estado_Alerta': estado
                    })

            # 3. Generamos el reporte de variaciones
            if resultados_comparativa:
                df_variaciones = pd.DataFrame(resultados_comparativa)

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "VariacionCostos"

                headers = list(df_variaciones.columns)
                ws.append(headers)

                for _, row in df_variaciones.iterrows():
                    fila_valores = [str(row[col]) if col == 'Código' else row[col] for col in headers]
                    ws.append(fila_valores)

                # Blindamos estrictamente la columna A con formato de texto '@'
                for cell in ws['A']:
                    if cell.row > 1:
                        cell.number_format = '@'
                        cell.data_type = 's'

                wb.save(archivo_reporte)
                print(f"✅ ¡Comparativa de precios generada con éxito!")
                print(f"📁 Archivo de control guardado como: '{archivo_reporte}'.")
                
                # Mostramos un resumen rápido en pantalla de las variaciones detectadas
                print("\n--- RESUMEN DE VARIACIONES ---")
                for item in resultados_comparativa:
                    print(f"• [{item['Código']}] {item['Descripción']} | Anterior: ${item['Costo_Anterior']} -> Nuevo: ${item['Costo_Nuevo_Factura']} ({item['Variacion_%']}%) -> {item['Estado_Alerta']}")
            else:
                print("ℹ️ No se encontraron coincidencias de códigos entre la recepción y la base de datos.")
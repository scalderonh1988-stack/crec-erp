import pandas as pd
import os

print("📦 Iniciando Módulo de Alertas de Sobrestock e Inventario Excesivo...")

archivo_base = "BASE DE DATOS.xlsx"

if not os.path.exists(archivo_base):
    print(f"❌ Error crítico: No se encuentra el archivo maestro '{archivo_base}'.")
else:
    df_base = pd.read_excel(archivo_base, dtype={'Código': str})
    
    # Identificamos columnas clave
    col_stock = next((col for col in df_base.columns if 'stock' in str(col).lower() or 'cantidad' in str(col).lower() or 'existencia' in str(col).lower()), None)
    col_desc = next((col for col in df_base.columns if 'descripción' in str(col).lower() or 'nombre' in str(col).lower()), 'Descripción')

    if not col_stock:
        print("⚠️ No se encontró la columna de Stock en la base maestra.")
    else:
        # Definimos el umbral de sobrestock: Por ejemplo, tener stock para más de 4 semanas (1 mes) se considera exceso
        semanas_limite = 4.0

        print("\n=========================================================")
        print("🚨 ASISTENTE DE CONTROL DE SOBRESTOCK")
        print(f"⚠️ Umbral de alerta: Productos con más de {semanas_limite} semanas de inventario")
        print("=========================================================")
        print(f"{'Código':<15} | {'Descripción':<25} | {'Stock Actual':<12} | {'Semanas de Stock':<16} | {'Estado':<15}")
        print("-" * 80)

        alertas_sobrestock = []

        for idx, row in df_base.iterrows():
            codigo = str(row.get('Código', 'N/D'))
            desc = str(row.get(col_desc, 'Sin descripción'))[:25]
            
            try:
                stock_actual = float(row.get(col_stock, 0)) if pd.notna(row.get(col_stock)) else 0.0
            except (ValueError, TypeError):
                stock_actual = 0.0

            # Demanda semanal estimada (mismo estándar de prueba de 10 unidades semanales)
            demanda_semanal = 10.0 

            if demanda_semanal > 0:
                # Cuántas semanas de venta tenemos aseguradas con el stock actual
                semanas_inventario = stock_actual / demanda_semanal
            else:
                semanas_inventario = 0.0

            # Si el stock supera el límite de semanas establecido, hay sobrestock
            if semanas_inventario > semanas_limite:
                exceso = round(semanas_inventario, 1)
                print(f"{codigo:<15} | {desc:<25} | {stock_actual:<12} | {exceso} semanas      | 🛑 SOBRESTOCK")
                
                alertas_sobrestock.append({
                    'Codigo': codigo,
                    'Descripcion': desc,
                    'Stock_Actual': stock_actual,
                    'Semanas': exceso
                })

        print("-" * 80)
        if not alertas_sobrestock:
            print("✔️ Tu inventario está optimizado. No hay productos con exceso de stock.")
        else:
            print(f"💡 Se detectaron {len(alertas_sobrestock)} productos con capital inmovilizado por sobrestock.")
        print("=========================================================")
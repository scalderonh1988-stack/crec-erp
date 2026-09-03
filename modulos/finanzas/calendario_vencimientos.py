import pandas as pd
import os
from datetime import datetime, date

print("🚦 Iniciando Calendario de Vencimientos con Semáforo Gerencial...")

archivo_base = "BASE DE DATOS.xlsx"

if not os.path.exists(archivo_base):
    print(f"❌ Error crítico: No se encuentra el archivo maestro '{archivo_base}'.")
else:
    df_base = pd.read_excel(archivo_base, dtype={'Código': str})
    
    col_venc = next((col for col in df_base.columns if 'vencimiento' in str(col).lower() or 'vence' in str(col).lower()), None)
    col_desc = next((col for col in df_base.columns if 'descripción' in str(col).lower() or 'nombre' in str(col).lower()), 'Descripción')
    col_stock = next((col for col in df_base.columns if 'stock' in str(col).lower() or 'cantidad' in str(col).lower()), None)

    if not col_venc:
        print("⚠️ No se encontró una columna de Fecha de Vencimiento en la base maestra.")
    else:
        hoy = date.today()
        
        print("\n=========================================================")
        print(f"🚦 SEMÁFORO DE VENCIMIENTOS DE INVENTARIO (Fecha: {hoy.strftime('%Y-%m-%d')})")
        print("=========================================================")

        rojo = []      # <= 7 días o vencidos
        amarillo = []  # Entre 8 y 15 días
        verde = []     # Entre 16 y 30 días
        seguros = []   # Más de 30 días

        for idx, row in df_base.iterrows():
            codigo = str(row.get('Código', 'N/D'))
            desc = str(row.get(col_desc, 'Sin descripción'))
            stock = row.get(col_stock, 0) if col_stock else "N/D"
            val_venc = row.get(col_venc)

            if pd.isna(val_venc) or str(val_venc).strip().lower() in ['sin vencimiento', 'nan', '']:
                continue

            try:
                if isinstance(val_venc, str):
                    fecha_venc = datetime.strptime(val_venc.strip(), '%Y-%m-%d').date()
                elif isinstance(val_venc, datetime):
                    fecha_venc = val_venc.date()
                else:
                    continue
            except ValueError:
                continue

            dias_restantes = (fecha_venc - hoy).days

            item_info = {
                'Codigo': codigo,
                'Descripcion': desc,
                'Stock': stock,
                'Fecha': fecha_venc,
                'Dias': dias_restantes
            }

            if dias_restantes <= 7:
                rojo.append(item_info)
            elif 8 <= dias_restantes <= 15:
                amarillo.append(item_info)
            elif 16 <= dias_restantes <= 30:
                verde.append(item_info)
            else:
                seguros.append(item_info)

        # 1. Alerta ROJA (<= 7 días o vencidos)
        if rojo:
            print("\n🔴 LUZ ROJA (Urgente: Vencidos o vencen en 7 días o menos):")
            print("-" * 65)
            for r in rojo:
                if r['Dias'] < 0:
                    print(f"❌ [{r['Codigo']}] {r['Descripcion']} | Stock: {r['Stock']} | Venció hace {abs(r['Dias'])} días")
                else:
                    print(f"🚨 [{r['Codigo']}] {r['Descripcion']} | Stock: {r['Stock']} | Vence en {r['Dias']} días ({r['Fecha']})")
        else:
            print("\n✔️ Luz Roja limpia: No hay productos críticos en los próximos 7 días.")

        # 2. Alerta AMARILLA (8 a 15 días)
        if amarillo:
            print("\n🟡 LUZ AMARILLA (Precaución: Vencen entre 8 y 15 días - Liquidar / Oferta):")
            print("-" * 65)
            for a in amarillo:
                print(f"⚠️ [{a['Codigo']}] {a['Descripcion']} | Stock: {a['Stock']} | Vence en {a['Dias']} días ({a['Fecha']})")
        else:
            print("\n✔️ Luz Amarilla limpia: No hay productos en rango de 8 a 15 días.")

        # 3. Alerta VERDE (16 a 30 días)
        if verde:
            print("\n🟢 LUZ VERDE (Atención preventiva: Vencen entre 16 y 30 días):")
            print("-" * 65)
            for vd in verde:
                print(f"✅ [{vd['Codigo']}] {vd['Descripcion']} | Stock: {vd['Stock']} | Vence en {vd['Dias']} días ({vd['Fecha']})")
        else:
            print("\n✔️ Luz Verde limpia: No hay productos en rango de 16 a 30 días.")

        print("=========================================================")
        print("💡 Gestión de Inventario: Utiliza este semáforo para programar rebajas progresivas antes de que la mercadería caiga en la zona roja.")
        print("=========================================================")
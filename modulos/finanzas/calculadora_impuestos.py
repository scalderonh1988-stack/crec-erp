import pandas as pd
import os

print("🧮 Iniciando Asistente Contable de Impuestos (F29)...")

archivo_ventas = "Ventas_Diarias.xlsx"
archivo_gastos = "Gastos_Negocio.xlsx"
archivo_base = "BASE DE DATOS.xlsx"

# 1. Calculamos el IVA Débito (Impuesto por las ventas realizadas)
total_ventas_brutas = 0.0
if os.path.exists(archivo_ventas):
    df_v = pd.read_excel(archivo_ventas)
    if 'Total_Venta' in df_v.columns:
        total_ventas_brutas = df_v['Total_Venta'].sum()

# Desglose: Venta Neta y IVA Débito (19%)
iva_tasa = 0.19
venta_neta = total_ventas_brutas / (1 + iva_tasa)
iva_debito = total_ventas_brutas - venta_neta

# 2. Estimamos IVA Crédito (Impuesto por compras/gastos con factura)
iva_credito = 0.0
if os.path.exists(archivo_gastos):
    df_g = pd.read_excel(archivo_gastos)
    # Filtramos o buscamos los que tengan documento de factura
    if 'Documento' in df_g.columns and 'Monto' in df_g.columns:
        facturas_gastos = df_g[df_g['Documento'].str.lower().str.contains('factura', na=False)]
        monto_facturas_gastos = facturas_gastos['Monto'].sum()
        iva_credito += monto_facturas_gastos - (monto_facturas_gastos / (1 + iva_tasa))

# También sumamos compras de mercadería si están registradas en la base maestra con costo con IVA
if os.path.exists(archivo_base):
    df_b = pd.read_excel(archivo_base)
    col_costo = next((col for col in df_b.columns if 'costo' in col.lower()), None)
    if col_costo:
        total_costo_inventario = pd.to_numeric(df_b[col_costo], errors='coerce').sum()
        # Estimamos el IVA crédito asociado al inventario adquirido
        iva_credito_inventario = total_costo_inventario - (total_costo_inventario / (1 + iva_tasa))
        iva_credito += iva_credito_inventario

# 3. IVA a Pagar (Débito - Crédito)
iva_a_pagar = iva_debito - iva_credito

print("\n=========================================================")
print("📊 SIMULACIÓN FORMULARIO 29 (F29) - IMPUESTOS MENSUALES")
print("=========================================================")
print(f"🛒 Ventas Brutas Totales: ${total_ventas_brutas:,.2f}")
print(f"📤 IVA Débito Fiscal (A cargo por ventas): ${iva_debito:,.2f}")
print(f"📥 IVA Crédito Fiscal (A favor por compras/gastos): ${iva_credito:,.2f}")
print("---------------------------------------------------------")

if iva_a_pagar > 0:
    print(f"🚨 IVA A PAGAR AL FISCO: ${iva_a_pagar:,.2f}")
    print("💡 Consejo contable: ¡Este dinero de IVA no es ganancia del negocio! Resérvalo intocable para el pago en Tesorería.")
elif iva_a_pagar == 0:
    print("✔️ IVA CALZADO: El débito y el crédito están equilibrados (Saldo $0).")
else:
    print(f"✅ REMANENTE DE IVA A FAVOR: ${abs(iva_a_pagar):,.2f}")
    print("💡 Tienes crédito fiscal acumulado para descontar el próximo mes.")
print("=========================================================")
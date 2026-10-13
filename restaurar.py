import os
import numpy as np
import pandas as pd
from supabase import create_client

# 1. Tus credenciales de Supabase
SUPABASE_URL = "https://dmkjlcjrobszhwasrofc.supabase.co"
SUPABASE_KEY = "supabasekey"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Lista de archivos y sus RUTs
tareas = [
    {
        "archivo": "base de datos comercial fyc.xlsx",
        "rut": "78380617-7"
    },
    {
        "archivo": "base datos sapiron.xlsx",
        "rut": "15382273-5"
    },
    {
        "archivo": "envirotech uruguayBASE DE DATOS.xlsx",
        "rut": "219449970012"
    }
]

# Columnas oficiales permitidas en tu base de datos de Supabase
columnas_permitidas = [
    'codigo', 'descripcion', 'formato_envase', 'unidad', 
    'costo', 'precio_venta', 'dun14', 'categoria', 
    'es_exento', 'impuesto_especifico', 'disponible_venta', 
    'activo', 'rut_empresa'
]

for item in tareas:
    nombre_archivo = item["archivo"]
    rut = item["rut"]
    
    print(f"Procesando '{nombre_archivo}' para el RUT {rut}...")
    
    if not os.path.exists(nombre_archivo):
        print(f"❌ ADVERTENCIA: No se encontró el archivo '{nombre_archivo}'.")
        continue
        
    df = pd.read_excel(nombre_archivo)
    
    # Asignar el RUT de la empresa
    df['rut_empresa'] = rut
    
    # Estandarizar nombres de columnas
    df = df.rename(columns={
        'Código': 'codigo',
        'Descripción': 'descripcion',
        'Nombre': 'descripcion',
        'Formato / Envase': 'formato_envase',
        'Unidad': 'unidad',
        'Costo': 'costo',
        'Precio de Venta': 'precio_venta',
        'Precio': 'precio_venta',
        'DUN14': 'dun14',
        'Categoría': 'categoria',
        'Es Exento': 'es_exento',
        'Impuesto Específico': 'impuesto_especifico',
        'Disponible venta': 'disponible_venta',
        'Activo': 'activo'
    })
    
    # Mantener únicamente las columnas que existen en la base de datos (evita errores por columnas extra)
    cols_a_usar = [c for c in columnas_permitidas if c in df.columns]
    df = df[cols_a_usar]
    
    # Reemplazar nulos
    df = df.replace({np.nan: None})
    
    # Eliminar duplicados si los hubiera
    df = df.drop_duplicates(subset=['rut_empresa', 'codigo'])
    
    registros = df.to_dict(orient="records")
    
    # Subir en bloques de 500
    for i in range(0, len(registros), 500):
        lote = registros[i:i+500]
        supabase.table("productos").upsert(lote, on_conflict="rut_empresa,codigo").execute()
        
    print(f"-> ¡{len(registros)} productos restaurados con éxito para el RUT {rut}!\n")

print("¡Proceso finalizado con éxito! Todas las bases de datos están listas.")
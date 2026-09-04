import requests
import json
from datetime import datetime

# URL Sandbox de OpenFactura (Haulmer)
OPENFACTURA_SANDBOX_URL = "https://dev-api.haulmer.com/v2/dte/issue"

# API Key de prueba pública (Reemplazar por tu API Key personal si aplica)
SANDBOX_API_KEY = "9245922d05404d71b84f0f03227d8e87"


def emitir_dte_openfactura(
    rut_emisor: str = None,
    tipo_documento: str = "Boleta Electrónica",
    items: list = None,
    rut_receptor: str = "66666666-6",
    razon_social_receptor: str = "Cliente General",
    giro_receptor: str = "Sin Giro",
    direccion_receptor: str = "Santiago",
    comuna_receptor: str = "Santiago",
    datos_empresa: dict = None,
    api_key: str = None,
    **kwargs
) -> dict:
    """
    Emite un Documento Tributario Electrónico (DTE) a través de la API de OpenFactura.
    
    Tipos de Documento soportados por código SII:
    - 'Boleta Electrónica': 39
    - 'Factura Electrónica': 33
    - 'Guía de Despacho': 52
    """
    if items is None:
        items = []

    datos_empresa = datos_empresa or {}

    # 1. Obtención dinámica de API Key (Prioridad: parámetro > datos_empresa > Sandbox por defecto)
    key_final = (
        api_key 
        or datos_empresa.get("api_key") 
        or datos_empresa.get("openfactura_api_key") 
        or SANDBOX_API_KEY
    )

    # 2. Mapeo de códigos SII
    mapa_sii = {
        "Boleta Electrónica": 39,
        "Factura Electrónica": 33,
        "Guía de Despacho": 52
    }
    codigo_sii = mapa_sii.get(tipo_documento, 39)

    # 3. Resolución de RUT Emisor
    rut_emisor_final = (
        rut_emisor 
        or datos_empresa.get("rut") 
        or datos_empresa.get("rut_empresa") 
        or ""
    )
    rut_emisor_clean = str(rut_emisor_final).replace(".", "").strip().upper()

    # 4. Formatear detalle de productos (soporta enteros y decimales)
    detalles = []
    for item in items:
        cant = float(item.get("cantidad", 1))
        precio = float(item.get("precio_unitario", 0))
        
        qty_val = int(cant) if cant.is_integer() else round(cant, 3)
        prc_val = int(precio) if precio.is_integer() else round(precio, 2)

        detalles.append({
            "NmbItem": str(item.get("nombre", "Producto")).strip()[:80],
            "QtyItem": qty_val,
            "PrcItem": prc_val
        })

    # 5. Fecha actual de emisión (YYYY-MM-DD)
    fecha_emision = datetime.now().strftime("%Y-%m-%d")

    # 6. Construcción del payload JSON para OpenFactura
    payload = {
        "response": ["PDF", "TIMBRE", "XML"],
        "dte": {
            "Encabezado": {
                "IdDoc": {
                    "TipoDTE": codigo_sii,
                    "FchEmis": fecha_emision
                },
                "Emisor": {
                    "RUTEmisor": rut_emisor_clean
                },
                "Receptor": {
                    "RUTRecep": str(rut_receptor).replace(".", "").strip().upper(),
                    "RznSocRecep": str(razon_social_receptor).strip(),
                    "GiroRecep": str(giro_receptor).strip(),
                    "DirRecep": str(direccion_receptor).strip(),
                    "CmnaRecep": str(comuna_receptor).strip()
                }
            },
            "Detalle": detalles
        }
    }

    headers = {
        "apikey": key_final,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            OPENFACTURA_SANDBOX_URL, 
            data=json.dumps(payload), 
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            
            folio_obtenido = data.get("FOLIO") or data.get("folio") or data.get("TOKEN") or "N/A"
            pdf_url = data.get("pdf") or data.get("pdf_url") or data.get("url")

            return {
                "exito": True,
                "folio": str(folio_obtenido),
                "pdf_url": pdf_url,
                "timbre": data.get("timbre"),
                "raw_response": data
            }
        else:
            return {
                "exito": False,
                "error": f"Error API {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            "exito": False,
            "error": f"Excepción de conexión: {str(e)}"
        }
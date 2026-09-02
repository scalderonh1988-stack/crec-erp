import requests
import json

# URL Sandbox de OpenFactura (Haulmer)
OPENFACTURA_SANDBOX_URL = "https://dev-api.haulmer.com/v2/dte/issue"

# API Key de prueba pública (Reemplazar por tu API Key personal de Sandbox)
SANDBOX_API_KEY = "9245922d05404d71b84f0f03227d8e87"

def emitir_dte_openfactura(
    rut_emisor: str,
    tipo_documento: str,
    items: list,
    rut_receptor: str = "66666666-6",
    razon_social_receptor: str = "Cliente General",
    giro_receptor: str = "Sin Giro",
    direccion_receptor: str = "Santiago",
    comuna_receptor: str = "Santiago",
    api_key: str = SANDBOX_API_KEY
) -> dict:
    """
    Emite un Documento Tributario Electrónico (DTE) a través de la API de OpenFactura.
    
    Tipos de Documento soportados por código SII:
    - 'Boleta Electrónica': 39
    - 'Factura Electrónica': 33
    - 'Guía de Despacho': 52
    """
    mapa_sii = {
        "Boleta Electrónica": 39,
        "Factura Electrónica": 33,
        "Guía de Despacho": 52
    }
    
    codigo_sii = mapa_sii.get(tipo_documento, 39)
    
    # Formatear detalle de productos
    detalles = []
    for item in items:
        detalles.append({
            "NmbItem": item["nombre"],
            "QtyItem": int(item["cantidad"]),
            "PrcItem": int(item["precio_unitario"])
        })
    
    # Construcción de estructura JSON para OpenFactura
    payload = {
        "response": ["PDF", "TIMBRE", "XML"],
        "dte": {
            "Encabezado": {
                "IdDoc": {
                    "TipoDTE": codigo_sii,
                    "FchEmis": ""  # Si se deja vacío, toma la fecha/hora actual
                },
                "Emisor": {
                    "RUTEmisor": rut_emisor.replace(".", "").upper()
                },
                "Receptor": {
                    "RUTRecep": rut_receptor.replace(".", "").upper(),
                    "RznSocRecep": razon_social_receptor,
                    "GiroRecep": giro_receptor,
                    "DirRecep": direccion_receptor,
                    "CmnaRecep": comuna_receptor
                }
            },
            "Detalle": detalles
        }
    }
    
    headers = {
        "apikey": api_key,
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
            return {
                "exito": True,
                "folio": data.get("TOKEN") or data.get("FOLIO", "N/A"),
                "pdf_url": data.get("pdf"),
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
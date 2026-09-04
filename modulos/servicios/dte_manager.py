import requests
import json
from datetime import datetime

# URL Sandbox de OpenFactura (Haulmer)
OPENFACTURA_SANDBOX_URL = "https://dev-api.haulmer.com/v2/dte/issue"
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
    if items is None:
        items = []

    datos_empresa = datos_empresa or {}

    # 1. API Key (Empresa u OpenFactura Sandbox)
    key_final = (
        api_key 
        or datos_empresa.get("api_key") 
        or datos_empresa.get("openfactura_api_key") 
        or SANDBOX_API_KEY
    )

    # 2. Mapeo de código SII
    mapa_sii = {
        "Boleta Electrónica": 39,
        "Factura Electrónica": 33,
        "Guía de Despacho": 52
    }
    codigo_sii = mapa_sii.get(tipo_documento, 39)

    # 3. RUT Emisor
    rut_emisor_final = (
        rut_emisor 
        or datos_empresa.get("rut") 
        or datos_empresa.get("rut_empresa") 
        or ""
    )
    rut_emisor_clean = str(rut_emisor_final).replace(".", "").strip().upper()

    if not rut_emisor_clean or "SIN" in rut_emisor_clean:
        return {
            "exito": False,
            "error": "El RUT del emisor es inválido o no está registrado ('Sin RUT'). Revisa la configuración de la empresa."
        }

    # 4. Detalle de Ítems
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

    fecha_emision = datetime.now().strftime("%Y-%m-%d")

    # 5. Encabezado completo según requerimiento de OpenFactura / SII
    emisor_payload = {
        "RUTEmisor": rut_emisor_clean,
        "RznSoc": str(datos_empresa.get("razon_social") or datos_empresa.get("nombre_negocio") or "MI EMPRESA")[:100],
        "GiroEmis": str(datos_empresa.get("giro") or "GIRO COMERCIAL")[:80],
        "Acteco": int(datos_empresa.get("acteco") or 471100),
        "DirOrigen": str(datos_empresa.get("direccion") or "Santiago")[:70],
        "CmnaOrigen": str(datos_empresa.get("comuna") or datos_empresa.get("ciudad") or "Santiago")[:20]
    }

    receptor_payload = {
        "RUTRecep": str(rut_receptor).replace(".", "").strip().upper(),
        "RznSocRecep": str(razon_social_receptor).strip()[:100],
        "GiroRecep": str(giro_receptor or "Sin Giro").strip()[:40],
        "DirRecep": str(direccion_receptor or "Sin Dirección").strip()[:70],
        "CmnaRecep": str(comuna_receptor or "Santiago").strip()[:20]
    }

    payload = {
        "response": ["PDF", "TIMBRE", "XML"],
        "dte": {
            "Encabezado": {
                "IdDoc": {
                    "TipoDTE": codigo_sii,
                    "FchEmis": fecha_emision
                },
                "Emisor": emisor_payload,
                "Receptor": receptor_payload
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
            timeout=12
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
            msg_err = response.text
            try:
                err_json = response.json()
                msg_err = err_json.get("message") or err_json.get("error") or response.text
            except Exception:
                pass
            return {
                "exito": False,
                "error": f"OpenFactura HTTP {response.status_code}: {msg_err}"
            }
            
    except Exception as e:
        return {
            "exito": False,
            "error": f"Fallo de conexión DTE: {str(e)}"
        }
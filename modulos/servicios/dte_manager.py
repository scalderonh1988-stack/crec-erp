import os
import json
import requests
import streamlit as st
from datetime import datetime

# Endpoints oficiales de Haulmer / OpenFactura
URL_PRODUCTION = "https://api.haulmer.com/v2/dte/issue"
URL_SANDBOX = "https://dev-api.haulmer.com/v2/dte/issue"


def validar_rut(rut: str) -> bool:
    """Valida formato y Dígito Verificador (Módulo 11) para RUTs chilenos."""
    rut_clean = str(rut).replace(".", "").replace("-", "").strip().upper()
    if len(rut_clean) < 2:
        return False
    
    cuerpo, dv = rut_clean[:-1], rut_clean[-1]
    if not cuerpo.isdigit():
        return False

    suma = 0
    multiplicador = 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1

    resto = suma % 11
    dv_esperado = 11 - resto
    
    if dv_esperado == 11:
        dv_calc = "0"
    elif dv_esperado == 10:
        dv_calc = "K"
    else:
        dv_calc = str(dv_esperado)

    return dv == dv_calc


def _obtener_config_openfactura() -> tuple[str, str]:
    """Recupera la API Key y selecciona la URL según el entorno (Production/Sandbox)."""
    api_key = ""
    entorno = "production"

    try:
        if "openfactura" in st.secrets:
            api_key = str(st.secrets["openfactura"].get("api_key", "")).strip()
            entorno = str(st.secrets["openfactura"].get("environment", "production")).lower().strip()
        elif "OPENFACTURA_API_KEY" in st.secrets:
            api_key = str(st.secrets["OPENFACTURA_API_KEY"]).strip()
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("OPENFACTURA_API_KEY", "").strip()
        entorno = os.getenv("OPENFACTURA_ENV", "production").lower().strip()

    target_url = URL_SANDBOX if entorno in ["sandbox", "dev", "development"] else URL_PRODUCTION
    return api_key, target_url


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
    items = items or []
    datos_empresa = datos_empresa or {}

    # 1. Obtener API Key y Endpoint objetivo
    key_config, url_endpoint = _obtener_config_openfactura()
    key_final = api_key or datos_empresa.get("api_key") or datos_empresa.get("openfactura_api_key") or key_config

    if not key_final:
        return {
            "exito": False,
            "error": "No se encontró la clave API de OpenFactura/Haulmer. Configura 'openfactura.api_key' en .streamlit/secrets.toml"
        }

    # 2. Mapeo de código SII
    mapa_sii = {
        "Boleta Electrónica": 39,
        "Factura Electrónica": 33,
        "Guía de Despacho": 52
    }
    codigo_sii = mapa_sii.get(tipo_documento, 39)

    # 3. Validar y Limpiar RUT Emisor
    rut_emisor_final = rut_emisor or datos_empresa.get("rut") or datos_empresa.get("rut_empresa") or ""
    rut_emisor_clean = str(rut_emisor_final).replace(".", "").strip().upper()

    if not rut_emisor_clean or not validar_rut(rut_emisor_clean):
        return {
            "exito": False,
            "error": f"El RUT del emisor ('{rut_emisor_clean}') es inválido o no está registrado. Revisa la configuración del negocio."
        }

    # 4. Validar Receptor según el tipo de documento
    rut_recep_clean = str(rut_receptor).replace(".", "").strip().upper()
    if not validar_rut(rut_recep_clean):
        return {
            "exito": False,
            "error": f"El RUT del receptor ('{rut_recep_clean}') es inválido (Falló validación Módulo 11)."
        }

    if codigo_sii == 33:  # Factura Electrónica: Datos estrictos requeridos por el SII
        if not razon_social_receptor or razon_social_receptor.strip() == "Cliente General":
            return {"exito": False, "error": "Para Factura Electrónica se requiere una Razón Social válida."}
        if not giro_receptor or giro_receptor.strip() == "Sin Giro":
            return {"exito": False, "error": "Para Factura Electrónica se requiere especificar el Giro Comercial del cliente."}
        if not direccion_receptor or direccion_receptor.strip() == "Sin Dirección":
            return {"exito": False, "error": "Para Factura Electrónica se requiere la Dirección del cliente."}

    # 5. Procesamiento de Ítems y Cálculo Tributario
    detalles = []
    monto_neto_total = 0
    monto_exento_total = 0

    for idx, item in enumerate(items, start=1):
        cant = float(item.get("cantidad", 1))
        precio_bruto_o_neto = float(item.get("precio_unitario", 0))
        es_exento = item.get("es_exento", False)

        cant_val = int(cant) if cant.is_integer() else round(cant, 3)
        precio_val = int(round(precio_bruto_o_neto))
        subtotal_item = int(round(cant_val * precio_val))

        detalle_item = {
            "NroLinDet": idx,
            "NmbItem": str(item.get("nombre", "Producto")).strip()[:80],
            "QtyItem": cant_val,
            "PrcItem": precio_val
        }

        if es_exento:
            detalle_item["IndExe"] = 1
            monto_exento_total += subtotal_item
        else:
            monto_neto_total += subtotal_item

        detalles.append(detalle_item)

    # 6. Cálculo de Totales Tributarios según Tipo DTE
    if codigo_sii == 39:
        # En Boleta Electrónica los precios ingresados incluyen IVA
        total_bruto = monto_neto_total
        neto_calculado = int(round(total_bruto / 1.19))
        iva_calculado = total_bruto - neto_calculado
        monto_total_final = total_bruto + monto_exento_total
    else:
        # En Factura Electrónica el acumulado es Neto
        neto_calculado = monto_neto_total
        iva_calculado = int(round(neto_calculado * 0.19))
        monto_total_final = neto_calculado + iva_calculado + monto_exento_total

    totales_payload = {
        "MntNeto": neto_calculado,
        "MntExe": monto_exento_total,
        "IVA": iva_calculado,
        "MntTotal": monto_total_final
    }

    # 7. Construcción del Payload Oficial
    fecha_emision = datetime.now().strftime("%Y-%m-%d")

    emisor_payload = {
        "RUTEmisor": rut_emisor_clean,
        "RznSoc": str(datos_empresa.get("razon_social") or datos_empresa.get("nombre_negocio") or "MI EMPRESA")[:100],
        "GiroEmis": str(datos_empresa.get("giro") or "GIRO COMERCIAL")[:80],
        "Acteco": int(datos_empresa.get("acteco") or 471100),
        "DirOrigen": str(datos_empresa.get("direccion") or "Santiago")[:70],
        "CmnaOrigen": str(datos_empresa.get("comuna") or datos_empresa.get("ciudad") or "Santiago")[:20]
    }

    receptor_payload = {
        "RUTRecep": rut_recep_clean,
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
                "Receptor": receptor_payload,
                "Totales": totales_payload
            },
            "Detalle": detalles
        }
    }

    headers = {
        "apikey": key_final,
        "Content-Type": "application/json"
    }

    # 8. Petición HTTP a OpenFactura
    try:
        response = requests.post(
            url_endpoint, 
            data=json.dumps(payload), 
            headers=headers,
            timeout=15
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            folio_obtenido = data.get("FOLIO") or data.get("folio") or data.get("TOKEN") or "N/A"
            pdf_url = data.get("pdf") or data.get("pdf_url") or data.get("url")

            return {
                "exito": True,
                "folio": str(folio_obtenido),
                "pdf_url": pdf_url,
                "xml_url": data.get("xml"),
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
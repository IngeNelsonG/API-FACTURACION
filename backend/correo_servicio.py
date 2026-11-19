"""
correo_servicio.py - Envío de Factura por Correo Electrónico (Gmail SMTP)
Permite enviar la factura electrónica con su PDF adjunto utilizando el servidor SMTP de Gmail
o simulación controlada si aún no se han configurado credenciales en el .env.
"""
import base64
import json
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Cargar variables de entorno desde .env si existe (backend/ o raíz del proyecto)
_base_dir = os.path.dirname(os.path.abspath(__file__))
for _env_file in (os.path.join(_base_dir, '.env'), os.path.join(_base_dir, '..', '.env')):
    if os.path.exists(_env_file):
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

def enviar_factura_correo(destinatario: str, factura: dict, persona: dict, pdf_bytes: bytes) -> dict:
    """
    Envía un correo electrónico con el PDF de la factura adjunto al adquiriente.
    Usa smtplib nativo de Python para conectarse a Gmail.
    """
    numero_factura = factura['numero']
    nombre_cliente = persona.get('nombre', 'Estimado(a) Cliente')
    total_formateado = f"${factura['total']:,.2f} COP"

    smtp_host = os.getenv('SMTP_HOST', SMTP_HOST)
    smtp_port = int(os.getenv('SMTP_PORT', SMTP_PORT))
    smtp_email = os.getenv('SMTP_EMAIL', SMTP_EMAIL)
    smtp_password = os.getenv('SMTP_PASSWORD', SMTP_PASSWORD)
    gmail_webhook_url = os.getenv('GMAIL_WEBHOOK_URL', '').strip()
    gmail_webhook_secret = os.getenv('GMAIL_WEBHOOK_SECRET', '').strip()
    resend_api_key = os.getenv('RESEND_API_KEY', '').strip()
    resend_from = os.getenv('RESEND_FROM', 'Facturación DIAN <onboarding@resend.dev>').strip()

    # Verificar si hay algún proveedor configurado (Google Apps Script, Resend HTTPS o Gmail SMTP)
    if not gmail_webhook_url and not resend_api_key and (not smtp_email or not smtp_password):
        return {
            "enviado": True,
            "modo": "simulado_pendiente_credenciales",
            "destinatario": destinatario,
            "mensaje": (
                "Factura preparada con éxito y PDF adjunto generado. "
                "Para despacho real configure GMAIL_WEBHOOK_URL, RESEND_API_KEY o SMTP_EMAIL/SMTP_PASSWORD."
            )
        }

    # Construir el mensaje MIME multipart
    msg = MIMEMultipart()
    msg['From'] = f"Facturación DIAN <{smtp_email}>"
    msg['To'] = destinatario
    msg['Subject'] = f"Factura Electrónica de Venta No. {numero_factura} - DIAN Colombia"

    # Cuerpo del correo en HTML estilizado
    cuerpo_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f7fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }}
            .header {{ background-color: #1a365d; color: #ffffff; padding: 24px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .header p {{ margin: 4px 0 0; font-size: 13px; opacity: 0.9; }}
            .content {{ padding: 24px; color: #2d3748; line-height: 1.6; }}
            .badge {{ display: inline-block; background-color: #ebf8ff; color: #2b6cb0; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 13px; }}
            .resumen {{ background-color: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin: 20px 0; }}
            .resumen table {{ width: 100%; border-collapse: collapse; }}
            .resumen td {{ padding: 6px 0; font-size: 14px; }}
            .resumen td.valor {{ text-align: right; font-weight: bold; color: #1a365d; }}
            .cufe-box {{ font-family: monospace; font-size: 11px; background-color: #edf2f7; padding: 10px; border-radius: 4px; word-break: break-all; color: #4a5568; }}
            .footer {{ background-color: #edf2f7; padding: 16px; text-align: center; font-size: 12px; color: #718096; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Facturación Electrónica DIAN</h1>
                <p>Notificación Oficial de Emisión de Documento Tributario</p>
            </div>
            <div class="content">
                <p>Hola <b>{nombre_cliente}</b>,</p>
                <p>Le informamos que ha sido emitida su <b>Factura Electrónica de Venta</b> conforme a las directrices de la DIAN para personas naturales.</p>
                
                <p>Estado del documento: <span class="badge">EMITIDA / VÁLIDA</span></p>

                <div class="resumen">
                    <table>
                        <tr>
                            <td>Número de Factura:</td>
                            <td class="valor">{numero_factura}</td>
                        </tr>
                        <tr>
                            <td>Concepto:</td>
                            <td class="valor">{factura.get('concepto', 'Servicios')}</td>
                        </tr>
                        <tr>
                            <td>Subtotal:</td>
                            <td class="valor">${factura['subtotal']:,.2f} COP</td>
                        </tr>
                        <tr>
                            <td>IVA (19%):</td>
                            <td class="valor">${factura['iva']:,.2f} COP</td>
                        </tr>
                        <tr style="border-top: 2px solid #cbd5e0;">
                            <td style="padding-top: 10px; font-weight: bold; font-size: 15px;">TOTAL FACTURA:</td>
                            <td class="valor" style="padding-top: 10px; font-size: 16px; color: #2b6cb0;">{total_formateado}</td>
                        </tr>
                    </table>
                    <p style="font-size: 12px; color: #666;">
                        Al pagar desde una cuenta bancaria, el banco retendrá el 4x1000 (GMF) estimado en
                        ${factura['impuesto_4x1000']:,.2f} COP. Este valor no hace parte del total de la factura.
                    </p>
                </div>

                <p><b>CUFE (Código Único de Facturación Electrónica):</b></p>
                <div class="cufe-box">{factura.get('cufe', 'N/A')}</div>

                <p style="margin-top: 20px;">En el archivo adjunto encontrará el documento en formato <b>PDF oficial</b> para su contabilidad y declaración tributaria.</p>
            </div>
            <div class="footer">
                Proyecto Facturación DIAN - Grupo 5 - Materia de Cloud<br>
                Este es un mensaje institucional generado automáticamente por el sistema.
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))

    # Opción 1 (HTTPS puerto 443, gratis desde tu propia cuenta Google sin dominio): Apps Script
    if gmail_webhook_url:
        payload = {
            "secret": gmail_webhook_secret,
            "to": destinatario,
            "subject": msg['Subject'],
            "html": cuerpo_html,
            "filename": f"Factura_{numero_factura}.pdf",
            "pdf_base64": base64.b64encode(pdf_bytes).decode('ascii') if pdf_bytes else "",
        }
        req = urllib.request.Request(
            gmail_webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AlbaFacturacion/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                cuerpo_resp = resp.read().decode('utf-8', errors='replace')
            try:
                resp_json = json.loads(cuerpo_resp)
                if resp_json.get('ok') is False:
                    return {
                        "enviado": False,
                        "modo": "error_gmail_webhook",
                        "destinatario": destinatario,
                        "error": resp_json.get('error', 'Error en Google Apps Script')
                    }
            except ValueError:
                pass
            return {
                "enviado": True,
                "modo": "gmail_https_apps_script",
                "destinatario": destinatario,
                "mensaje": f"Correo enviado exitosamente desde Gmail a {destinatario} con la factura {numero_factura} adjunta."
            }
        except Exception as e:
            return {
                "enviado": False,
                "modo": "error_gmail_webhook",
                "destinatario": destinatario,
                "error": str(e)
            }

    # Opción 2 (HTTPS puerto 443, compatible con Render Free Tier): Resend API
    if resend_api_key:
        payload = {
            "from": resend_from,
            "to": [destinatario],
            "subject": msg['Subject'],
            "html": cuerpo_html,
        }
        if pdf_bytes:
            payload["attachments"] = [{
                "filename": f"Factura_{numero_factura}.pdf",
                "content": base64.b64encode(pdf_bytes).decode('ascii'),
            }]
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Cloudflare bloquea el User-Agent por defecto de Python-urllib (error 1010)
                "User-Agent": "AlbaFacturacion/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            return {
                "enviado": True,
                "modo": "resend_https_real",
                "destinatario": destinatario,
                "mensaje": f"Correo enviado exitosamente a {destinatario} con la factura {numero_factura} adjunta."
            }
        except urllib.error.HTTPError as e:
            detalle = e.read().decode('utf-8', errors='replace')
            try:
                detalle_json = json.loads(detalle)
                detalle = detalle_json.get('message') or detalle
            except ValueError:
                pass
            return {
                "enviado": False,
                "modo": "error_resend",
                "destinatario": destinatario,
                "error": f"Resend HTTP {e.code}: {detalle}"
            }
        except Exception as e:
            return {
                "enviado": False,
                "modo": "error_resend",
                "destinatario": destinatario,
                "error": str(e)
            }

    # Opción 2: Adjuntar PDF y enviar vía Gmail SMTP
    if pdf_bytes:
        adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
        adjunto.add_header('Content-Disposition', 'attachment', filename=f"Factura_{numero_factura}.pdf")
        msg.attach(adjunto)

    # Conectar y enviar vía Gmail SMTP
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.sendmail(smtp_email, [destinatario], msg.as_string())
        server.quit()

        return {
            "enviado": True,
            "modo": "smtp_gmail_real",
            "destinatario": destinatario,
            "mensaje": f"Correo enviado exitosamente a {destinatario} con la factura {numero_factura} adjunta."
        }
    except Exception as e:
        return {
            "enviado": False,
            "modo": "error_smtp",
            "destinatario": destinatario,
            "error": str(e)
        }

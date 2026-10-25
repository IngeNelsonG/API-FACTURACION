"""
correo_servicio.py - Envío de Factura por Correo Electrónico (Gmail SMTP)
Permite enviar la factura electrónica con su PDF adjunto utilizando el servidor SMTP de Gmail
o simulación controlada si aún no se han configurado credenciales en el .env.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
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

    # Verificar si están configuradas las credenciales reales de Gmail
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return {
            "enviado": True,
            "modo": "simulado_pendiente_credenciales",
            "destinatario": destinatario,
            "mensaje": (
                "Factura preparada con éxito y PDF adjunto generado. "
                "Para despacho real por Gmail, configure SMTP_EMAIL y SMTP_PASSWORD en el archivo .env."
            )
        }

    # Construir el mensaje MIME multipart
    msg = MIMEMultipart()
    msg['From'] = f"Facturación DIAN <{SMTP_EMAIL}>"
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
                        <tr>
                            <td>Gravamen 4x1000:</td>
                            <td class="valor">${factura['impuesto_4x1000']:,.2f} COP</td>
                        </tr>
                        <tr style="border-top: 2px solid #cbd5e0;">
                            <td style="padding-top: 10px; font-weight: bold; font-size: 15px;">TOTAL FACTURA:</td>
                            <td class="valor" style="padding-top: 10px; font-size: 16px; color: #2b6cb0;">{total_formateado}</td>
                        </tr>
                    </table>
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

    # Adjuntar el archivo PDF
    if pdf_bytes:
        adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
        adjunto.add_header('Content-Disposition', 'attachment', filename=f"Factura_{numero_factura}.pdf")
        msg.attach(adjunto)

    # Conectar y enviar vía Gmail SMTP
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, [destinatario], msg.as_string())
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

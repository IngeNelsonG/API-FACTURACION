"""
facturacion_servicio.py - Lógica de Negocio Tributaria y Generación de Factura PDF
Implementa las reglas de cálculo de impuestos DIAN y renderizado de PDF profesional con ReportLab.
"""
import hashlib
import io
import os
from datetime import datetime, timedelta, timezone

# -----------------------------------------------------------------------------
# Compatibilidad con Python 3.8: ReportLab 4 llama md5(usedforsecurity=False),
# argumento que solo existe desde Python 3.9. Si no está soportado, se envuelve
# hashlib.md5 para ignorarlo. Debe ir ANTES de importar reportlab, porque sus
# módulos hacen "from hashlib import md5" al importarse.
# -----------------------------------------------------------------------------
try:
    hashlib.md5(b"", usedforsecurity=False)
except TypeError:
    _md5_original = hashlib.md5

    def _md5_compatible(*args, usedforsecurity=True, **kwargs):
        return _md5_original(*args, **kwargs)

    hashlib.md5 = _md5_compatible

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Constantes Tributarias DIAN para Personas Naturales
NIT_EMISOR = "901234567-8"
NOMBRE_EMISOR = "GRUPO 5 - FACTURACIÓN ELECTRÓNICA DIAN"
ACTIVIDAD_EMISOR = "Servicios Profesionales y Tecnológicos - Persona Natural"
DIRECCION_EMISOR = "Carrera 7 # 71-21, Bogotá D.C., Colombia"
CLAVE_TECNICA = "dian_clave_tecnica_2026_cloud"

TARIFA_IVA = 0.19   # Tarifa general del IVA (art. 468 E.T.)
TARIFA_GMF = 0.004  # Gravamen a los Movimientos Financieros, 4x1000 (art. 872 E.T.)


def calcular_impuestos(subtotal: float):
    """
    Liquida los tributos de una factura de venta en Colombia:

    - IVA 19% sobre el subtotal (base gravable, art. 447 E.T.).
    - Total de la factura = Subtotal + IVA.

    - 4x1000 (GMF): NO hace parte de la factura. Lo retiene el banco cuando se
      mueve el dinero para pagarla, y su base es el valor total de esa
      transacción (art. 874 E.T.). Aquí se calcula solo como dato INFORMATIVO:
      0.4% del total que se va a pagar. No se suma al total.
    """
    subtotal = round(float(subtotal), 2)
    iva = round(subtotal * TARIFA_IVA, 2)
    total = round(subtotal + iva, 2)
    impuesto_4x1000 = round(total * TARIFA_GMF, 2)  # informativo, fuera del total

    return {
        "subtotal": subtotal,
        "iva": iva,
        "total": total,
        "impuesto_4x1000": impuesto_4x1000,
        "impuesto_4x1000_incluido_en_total": False,
    }

def generar_cufe(numero: str, fecha_str: str, subtotal: float, iva: float, total: float, doc_adquiriente: str) -> str:
    """
    Genera el CUFE (Código Único de Facturación Electrónica).
    Aplica el algoritmo SHA-256 sobre la cadena de valores tributarios del Anexo DIAN.
    """
    cadena = f"{numero}{fecha_str}{subtotal:.2f}{iva:.2f}{total:.2f}{NIT_EMISOR}{doc_adquiriente}{CLAVE_TECNICA}"
    return hashlib.sha256(cadena.encode('utf-8')).hexdigest()

# =============================================================================
# PDF CON LA ESTÉTICA DE ALBA (misma paleta y tipografía del frontend)
# =============================================================================
VINOTINTO = colors.HexColor("#7A1035")
VINOTINTO_OSCURO = colors.HexColor("#5E0D2F")
AZUL_CLARO = colors.HexColor("#7CC8F2")
AZUL_SUAVE = colors.HexColor("#E5F3FC")
ROSA_SUAVE = colors.HexColor("#FBE1EC")
TEXTO = colors.HexColor("#13183A")
TEXTO_SUAVE = colors.HexColor("#4B5272")
BORDE = colors.HexColor("#E6E3EC")
FONDO_TABLA = colors.HexColor("#EEF0F6")
FONDO_TARJETA = colors.HexColor("#F8F7FB")

# Colores de los estados (iguales a los badges del dashboard)
ESTADOS_PDF = {
    "PAGADA": ("Pagada", colors.HexColor("#17663F"), colors.HexColor("#DFF1E7")),
    "EMITIDA": ("Pendiente de pago", colors.HexColor("#1B2F6E"), colors.HexColor("#E1E7F6")),
    "ANULADA": ("Anulada", colors.HexColor("#4A4F5C"), colors.HexColor("#E4E5EA")),
}

ZONA_COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano


def _registrar_fuentes():
    """Registra Poppins (backend/fonts). Si no está, se usa Helvetica."""
    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    archivos = {
        "Poppins": "Poppins-Regular.ttf",
        "Poppins-Medium": "Poppins-Medium.ttf",
        "Poppins-Bold": "Poppins-Bold.ttf",
        "Poppins-Italic": "Poppins-Italic.ttf",
    }
    try:
        for nombre, archivo in archivos.items():
            if nombre not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(nombre, os.path.join(carpeta, archivo)))
        return {"regular": "Poppins", "medium": "Poppins-Medium", "bold": "Poppins-Bold", "italic": "Poppins-Italic"}
    except Exception:
        return {"regular": "Helvetica", "medium": "Helvetica-Bold", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique"}


def _cop(valor) -> str:
    """119000 -> '$ 119.000' ; 1234.5 -> '$ 1.234,50' (formato colombiano)."""
    valor = float(valor or 0)
    if valor == int(valor):
        return "$ " + f"{int(valor):,}".replace(",", ".")
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$ " + texto


def _fecha_colombia(fecha) -> str:
    """'2026-11-19 01:22:34' (UTC de SQLite) -> '18/11/2026 · 8:22 p. m.' (hora Colombia)."""
    try:
        dt = datetime.strptime(str(fecha)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    local = dt.astimezone(ZONA_COLOMBIA)
    hora = local.hour % 12 or 12
    sufijo = "a. m." if local.hour < 12 else "p. m."
    return f"{local:%d/%m/%Y} · {hora}:{local:%M} {sufijo}"


def _cubica(p0, q, p2):
    """Convierte una curva cuadrática (SVG 'Q') en cúbica para ReportLab."""
    c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (q[0] - p2[0]), p2[1] + 2 / 3 * (q[1] - p2[1]))
    return c1, c2, p2


def _dibujar_logo(c, x, y, ancho, color):
    """Dibuja el ícono de Alba (documento con líneas de velocidad), mismo trazo del SVG del front."""
    escala = ancho / 520.0
    c.saveState()
    c.translate(x, y + 320 * escala)
    c.scale(escala, -escala)  # el SVG tiene el eje Y hacia abajo
    c.setStrokeColor(color)
    c.setLineWidth(36)
    c.setLineCap(1)
    c.setLineJoin(1)

    p = c.beginPath()  # Documento
    p.moveTo(185, 22); p.lineTo(338, 22)
    p.curveTo(*sum(_cubica((338, 22), (352, 22), (362, 32)), ()))
    p.lineTo(480, 150)
    p.curveTo(*sum(_cubica((480, 150), (490, 160), (492, 172)), ()))
    p.lineTo(502, 240)
    p.curveTo(*sum(_cubica((502, 240), (506, 297), (452, 297)), ()))
    p.lineTo(180, 297)
    c.drawPath(p, stroke=1, fill=0)

    p = c.beginPath()  # Esquina doblada
    p.moveTo(352, 26); p.lineTo(352, 118)
    p.curveTo(*sum(_cubica((352, 118), (352, 150), (384, 150)), ()))
    p.lineTo(468, 150)
    c.drawPath(p, stroke=1, fill=0)

    for x0, y0, x1 in ((35, 102, 255), (90, 168, 298), (22, 230, 182), (266, 230, 365)):
        c.line(x0, y0, x1, y0)  # Líneas de velocidad
    c.restoreState()


def generar_pdf_factura(factura: dict, persona: dict) -> bytes:
    """
    Genera el PDF de la factura electrónica con la identidad visual de Alba
    (vinotinto + azul claro, tipografía Poppins). Retorna los bytes en memoria.
    """
    f = _registrar_fuentes()
    ancho_pag, alto_pag = letter
    margen = 40
    alto_banda = 96

    def fondo_pagina(c, _doc):
        """Encabezado vinotinto con logo y número + pie de página (se pinta en el canvas)."""
        c.saveState()
        # Banda superior
        c.setFillColor(VINOTINTO)
        c.rect(0, alto_pag - alto_banda, ancho_pag, alto_banda, stroke=0, fill=1)
        # Formas decorativas (como las manchas del sitio)
        c.setFillColor(VINOTINTO_OSCURO)
        c.circle(ancho_pag - 60, alto_pag - 10, 95, stroke=0, fill=1)
        c.setFillColor(AZUL_CLARO)
        c.setFillAlpha(0.3)
        p_clip = c.beginPath()
        p_clip.rect(0, alto_pag - alto_banda, ancho_pag, alto_banda)
        c.clipPath(p_clip, stroke=0, fill=0)
        c.circle(ancho_pag - 205, alto_pag - alto_banda + 22, 18, stroke=0, fill=1)
        c.circle(ancho_pag - 175, alto_pag - 16, 9, stroke=0, fill=1)
        c.setFillAlpha(1)
        c.restoreState()
        c.saveState()

        # Logo + marca
        _dibujar_logo(c, margen, alto_pag - 66, 60, colors.white)
        c.setFillColor(colors.white)
        c.setFont(f["bold"], 26)
        c.drawString(margen + 72, alto_pag - 54, "Alba")
        c.setFillColor(AZUL_CLARO)
        c.setFont(f["regular"], 8.5)
        c.drawString(margen + 73, alto_pag - 68, "FACTURACIÓN ELECTRÓNICA")

        # Tipo de documento y número
        c.setFillColor(AZUL_CLARO)
        c.setFont(f["medium"], 8.5)
        c.drawRightString(ancho_pag - margen, alto_pag - 40, "FACTURA ELECTRÓNICA DE VENTA")
        c.setFillColor(colors.white)
        c.setFont(f["bold"], 22)
        c.drawRightString(ancho_pag - margen, alto_pag - 64, factura["numero"])

        # Pie de página
        c.setStrokeColor(BORDE)
        c.setLineWidth(0.8)
        c.line(margen, 46, ancho_pag - margen, 46)
        c.setFont(f["regular"], 7.5)
        c.setFillColor(TEXTO_SUAVE)
        c.drawString(margen, 32, "Alba · Facturación Electrónica · Cloud Computing — Grupo 5")
        c.drawRightString(ancho_pag - margen, 32, f"Página {_doc.page}")
        c.setFillColor(VINOTINTO)
        c.rect(0, 0, ancho_pag, 6, stroke=0, fill=1)
        c.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=margen, rightMargin=margen,
        topMargin=alto_banda + 18, bottomMargin=56,
        title=f"Factura {factura['numero']}", author="Alba · Grupo 5",
    )
    ancho = ancho_pag - 2 * margen

    # ---- Estilos ----
    def estilo(nombre, fuente="regular", tam=9, color=TEXTO, **kw):
        return ParagraphStyle(nombre, fontName=f[fuente], fontSize=tam, leading=tam * 1.4, textColor=color, **kw)

    seccion = estilo("Seccion", "bold", 8, VINOTINTO, spaceAfter=4)
    etiqueta = estilo("Etiqueta", "regular", 7.5, TEXTO_SUAVE)
    valor = estilo("Valor", "medium", 9.5, TEXTO)
    valor_der = estilo("ValorDer", "medium", 9.5, TEXTO, alignment=2)
    normal = estilo("Normal", "regular", 9, TEXTO)
    normal_der = estilo("NormalDer", "regular", 9, TEXTO, alignment=2)
    th = estilo("Th", "medium", 8.5, TEXTO)
    th_der = estilo("ThDer", "medium", 8.5, TEXTO, alignment=2)

    def tarjeta(filas, anchos, fondo=FONDO_TARJETA):
        t = Table(filas, colWidths=anchos)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), fondo),
            ("ROUNDEDCORNERS", [10, 10, 10, 10]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ]))
        return t

    story = []

    # ---- 1. Emisor + datos de la factura ----
    estado = str(factura.get("estado", "EMITIDA")).upper()
    txt_estado, color_estado, fondo_estado = ESTADOS_PDF.get(estado, ESTADOS_PDF["EMITIDA"])
    ancho_badge = pdfmetrics.stringWidth(txt_estado, f["medium"], 8.5) + 20
    badge = Table([[Paragraph(txt_estado, estilo("Badge", "medium", 8.5, color_estado, alignment=1))]],
                  colWidths=[ancho_badge], hAlign="RIGHT")
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fondo_estado),
        ("ROUNDEDCORNERS", [9, 9, 9, 9]),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    emisor = tarjeta([
        [Paragraph("EMISOR", seccion)],
        [Paragraph(NOMBRE_EMISOR, estilo("Emisor", "bold", 10.5, TEXTO))],
        [Paragraph(f"NIT {NIT_EMISOR}", normal)],
        [Paragraph(ACTIVIDAD_EMISOR, estilo("Act", "regular", 8.5, TEXTO_SUAVE))],
        [Paragraph(DIRECCION_EMISOR, estilo("Dir", "regular", 8.5, TEXTO_SUAVE))],
    ], [ancho * 0.56 - 6])

    fecha_txt = _fecha_colombia(factura.get("fecha_emision"))
    fecha_dia, fecha_hora = fecha_txt.split(" · ")
    ancho_info = ancho * 0.44 - 6
    der = estilo("InfoDer", "medium", 9, TEXTO, alignment=2)
    info = tarjeta([
        [Paragraph("DATOS DE LA FACTURA", seccion), ""],
        [Paragraph("Fecha de emisión", normal), Paragraph(fecha_dia, der)],
        [Paragraph("Hora", normal), Paragraph(fecha_hora, der)],
        [Paragraph("Estado", normal), badge],
        [Paragraph("Resolución DIAN", normal), Paragraph("18764000001", der)],
        [Paragraph("Rango autorizado", normal), Paragraph("SETP-0001 a 9999", der)],
    ], [ancho_info * 0.48, ancho_info * 0.52], fondo=AZUL_SUAVE)
    info.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0)), ("ALIGN", (1, 3), (1, 3), "RIGHT"), ("VALIGN", (0, 1), (-1, -1), "MIDDLE")]))

    cabecera = Table([[emisor, info]], colWidths=[ancho * 0.56, ancho * 0.44])
    cabecera.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
    ]))
    story += [cabecera, Spacer(1, 14)]

    # ---- 2. Cliente ----
    story.append(Paragraph("CLIENTE (ADQUIRIENTE)", seccion))
    col = ancho / 3

    def celda(lbl, txt):
        return [Paragraph(lbl.upper(), etiqueta), Paragraph(str(txt or "N/A"), valor)]

    cliente = tarjeta([
        [Paragraph(persona.get("nombre", "N/A"), estilo("Cli", "bold", 12, TEXTO)), "", ""],
        [celda("Cédula", persona.get("cedula")), celda("RUT", persona.get("rut")), celda("Teléfono", persona.get("telefono"))],
        [celda("Correo", persona.get("correo")), celda("Dirección", persona.get("direccion")), ""],
    ], [col, col, col])
    cliente.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)), ("SPAN", (1, 2), (2, 2)),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6), ("TOPPADDING", (0, 2), (-1, 2), 6),
    ]))
    story += [cliente, Spacer(1, 14)]

    # ---- 3. Detalle ----
    story.append(Paragraph("DETALLE DE BIENES O SERVICIOS", seccion))
    items = Table([
        [Paragraph("CANT.", th), Paragraph("DESCRIPCIÓN", th), Paragraph("VALOR UNITARIO", th_der), Paragraph("TOTAL", th_der)],
        [Paragraph("1", normal), Paragraph(factura.get("concepto", "Servicio"), normal),
         Paragraph(_cop(factura["subtotal"]), normal_der), Paragraph(_cop(factura["subtotal"]), valor_der)],
    ], colWidths=[58, ancho - 58 - 115 - 105, 115, 105])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FONDO_TABLA),
        ("ROUNDEDCORNERS", [10, 10, 0, 0]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.8, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [items, Spacer(1, 10)]

    # ---- 4. Totales (alineados a la derecha, total en "pastilla" rosada como el simulador) ----
    ancho_tot = 270
    filas_tot = Table([
        [Paragraph("Subtotal", normal), Paragraph(_cop(factura["subtotal"]), normal_der)],
        [Paragraph("IVA (19%)", normal), Paragraph(_cop(factura["iva"]), normal_der)],
    ], colWidths=[ancho_tot * 0.55, ancho_tot * 0.45])
    filas_tot.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    total = Table([[
        Paragraph("Total a pagar", estilo("TotL", "bold", 11, VINOTINTO)),
        Paragraph(_cop(factura["total"]), estilo("TotV", "bold", 15, VINOTINTO, alignment=2)),
    ]], colWidths=[ancho_tot * 0.45, ancho_tot * 0.55])
    total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ROSA_SUAVE),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    gmf = Table([[
        Paragraph("4x1000 que retendrá el banco*", estilo("GmfL", "italic", 8, TEXTO_SUAVE)),
        Paragraph(_cop(factura.get("impuesto_4x1000", 0)), estilo("GmfV", "italic", 8, TEXTO_SUAVE, alignment=2)),
    ]], colWidths=[ancho_tot * 0.7, ancho_tot * 0.3])
    gmf.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    bloque_tot = Table([[filas_tot], [total], [gmf]], colWidths=[ancho_tot])
    bloque_tot.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 6),
    ]))
    nota = Paragraph(
        "* El 4x1000 (Gravamen a los Movimientos Financieros) lo retiene la entidad financiera "
        "al mover el dinero para pagar esta factura; se calcula sobre el total (0.4%) y "
        "<b>no se suma</b> al valor de la factura.",
        estilo("Nota", "regular", 7.5, TEXTO_SUAVE),
    )
    fila_totales = Table([[nota, bloque_tot]], colWidths=[ancho - ancho_tot, ancho_tot])
    fila_totales.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "BOTTOM"), ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 30),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    story += [fila_totales, Spacer(1, 14)]

    # ---- 5. CUFE + texto legal ----
    cufe = tarjeta([
        [Paragraph("CÓDIGO ÚNICO DE FACTURACIÓN ELECTRÓNICA (CUFE)", seccion)],
        [Paragraph(factura.get("cufe", "N/A"), ParagraphStyle(
            "Cufe", fontName="Courier", fontSize=8, leading=11, textColor=TEXTO, wordWrap="CJK"))],
        [Paragraph(
            "Generado con SHA-256 a partir del número, fecha, valores, NIT del emisor y documento del adquiriente. "
            "Esta factura electrónica de venta es título valor y cumple con los requisitos del Estatuto Tributario "
            "y las resoluciones vigentes de la DIAN para personas naturales obligadas a facturar. "
            "Generada automáticamente por Alba, la API de Facturación Cloud del Grupo 5.",
            estilo("Legal", "regular", 7, TEXTO_SUAVE))],
    ], [ancho])
    story.append(cufe)

    doc.build(story, onFirstPage=fondo_pagina, onLaterPages=fondo_pagina)
    buffer.seek(0)
    return buffer.getvalue()

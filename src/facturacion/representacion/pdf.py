"""Representación gráfica (PDF) de la factura electrónica de venta.

Todo texto que proviene del usuario (razón social, descripciones, notas...) se
escapa con ``xml.sax.saxutils.escape`` antes de pasar a ``Paragraph``, porque
reportlab interpreta etiquetas como ``<b>`` o ``<font>``: el contenido de la
factura nunca debe interpretarse como marcado.

El sistema solo opera contra el ambiente de habilitación de la DIAN, así que
cada página lleva una franja que advierte que el documento no tiene validez
tributaria, además del QR y el pie de página.
"""

from __future__ import annotations

import io
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from facturacion.dominio.cufe import formatear_hora
from facturacion.dominio.factura import Factura, FormaPago
from facturacion.representacion.qr import generar_qr_png

TITULO = "FACTURA ELECTRÓNICA DE VENTA"
LEYENDA_AMBIENTE = "AMBIENTE DE PRUEBAS / HABILITACIÓN - SIN VALIDEZ TRIBUTARIA"
SELLO_SIN_VALIDEZ = "SIN VALIDEZ - AMBIENTE DE PRUEBAS"
ESTADO_ACEPTADA = "aceptada"

_MARGEN = 15 * mm
_TAMANO_QR = 30 * mm
_ANCHO_PAGINA, _ALTO_PAGINA = letter

_NOMBRES_FORMA_PAGO = {FormaPago.CONTADO: "Contado", FormaPago.CREDITO: "Crédito"}


def formatear_moneda(valor: Decimal) -> str:
    """Formato colombiano: ``$ 1.234.567,89`` (punto de miles, coma decimal)."""
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"$ {texto}"


def _formatear_numero(valor: Decimal) -> str:
    """Cantidades y porcentajes sin ceros sobrantes, con coma decimal."""
    texto = format(valor.normalize(), "f")
    return texto.replace(".", ",")


def _p(texto: str, estilo: ParagraphStyle) -> Paragraph:
    """Paragraph a partir de texto plano: escapa el marcado y conserva saltos de línea."""
    return Paragraph(escape(texto).replace("\n", "<br/>"), estilo)


def _partir(texto: str, ancho: int) -> list[str]:
    return [texto[i : i + ancho] for i in range(0, len(texto), ancho)] or [""]


def generar_pdf(
    factura: Factura, contenido_qr: str, estado_dian: str, *, comprimir: bool = True
) -> bytes:
    """Genera el PDF de la factura. ``comprimir=False`` deja el texto legible (pruebas)."""
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontSize=8, leading=10)
    pequeno = ParagraphStyle("pequeno", parent=normal, fontSize=7, leading=9)
    negrita = ParagraphStyle("negrita", parent=normal, fontName="Helvetica-Bold")
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=13, leading=16, alignment=2)
    derecha = ParagraphStyle("derecha", parent=normal, alignment=2)

    emisor = factura.emisor
    adquiriente = factura.adquiriente
    numeracion = factura.numeracion
    totales = factura.totales
    imagen_qr = ImageReader(io.BytesIO(generar_qr_png(contenido_qr)))
    aceptada = estado_dian.strip().lower() == ESTADO_ACEPTADA

    def decorar_pagina(canvas: Canvas, documento: SimpleDocTemplate) -> None:
        canvas.saveState()
        # Franja superior: el sistema solo emite en el ambiente de habilitación.
        canvas.setFillColor(colors.HexColor("#B00020"))
        canvas.rect(0, _ALTO_PAGINA - 7 * mm, _ANCHO_PAGINA, 7 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(_ANCHO_PAGINA / 2, _ALTO_PAGINA - 4.8 * mm, LEYENDA_AMBIENTE)

        if not aceptada:
            canvas.setFillColor(colors.Color(0.8, 0, 0, alpha=0.15))
            canvas.setFont("Helvetica-Bold", 42)
            canvas.translate(_ANCHO_PAGINA / 2, _ALTO_PAGINA / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, SELLO_SIN_VALIDEZ)
            canvas.rotate(-45)
            canvas.translate(-_ANCHO_PAGINA / 2, -_ALTO_PAGINA / 2)

        # QR en la esquina inferior derecha de cada página.
        canvas.drawImage(
            imagen_qr,
            _ANCHO_PAGINA - _MARGEN - _TAMANO_QR,
            10 * mm,
            width=_TAMANO_QR,
            height=_TAMANO_QR,
        )
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            _MARGEN,
            14 * mm,
            f"Representación gráfica de la factura electrónica - Estado DIAN: {estado_dian}",
        )
        canvas.drawString(
            _MARGEN, 10 * mm, f"{numeracion.numero_completo} - Página {documento.page}"
        )
        canvas.restoreState()

    elementos: list = []

    # --- Encabezado: emisor y título ---
    datos_emisor = [
        _p(emisor.razon_social, negrita),
        _p(f"NIT {emisor.nit}-{emisor.dv}", normal),
        _p(emisor.direccion, normal),
        _p(f"{emisor.ciudad}, {emisor.departamento}", normal),
        _p(f"Tel. {emisor.telefono}", normal),
        _p(emisor.email, normal),
    ]
    datos_titulo = [
        _p(TITULO, titulo),
        _p(f"No. {numeracion.numero_completo}", ParagraphStyle("num", parent=titulo)),
    ]
    encabezado = Table([[datos_emisor, datos_titulo]], colWidths=["55%", "45%"])
    encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elementos += [encabezado, Spacer(1, 4 * mm)]

    # --- Datos generales y adquiriente ---
    documento_adq = adquiriente.numero_documento
    if adquiriente.dv:
        documento_adq = f"{documento_adq}-{adquiriente.dv}"
    generales = [
        ("Fecha de emisión", factura.fecha_emision.isoformat()),
        ("Hora de emisión", formatear_hora(factura)),
        ("Forma de pago", _NOMBRES_FORMA_PAGO.get(factura.forma_pago, str(factura.forma_pago))),
    ]
    if factura.fecha_vencimiento is not None:
        generales.append(("Fecha de vencimiento", factura.fecha_vencimiento.isoformat()))
    generales.append(("Moneda", factura.moneda))
    datos_adq = [
        ("Adquiriente", adquiriente.nombre),
        ("Documento", f"{documento_adq} (tipo {adquiriente.tipo_documento.value})"),
        ("Dirección", adquiriente.direccion),
        ("Ciudad", f"{adquiriente.ciudad}, {adquiriente.departamento}".strip(", ")),
        ("Teléfono", adquiriente.telefono),
        ("Correo", adquiriente.email),
    ]
    filas = max(len(generales), len(datos_adq))
    celdas = []
    for i in range(filas):
        fila = []
        for grupo in (datos_adq, generales):
            if i < len(grupo):
                fila += [_p(grupo[i][0], negrita), _p(grupo[i][1], normal)]
            else:
                fila += ["", ""]
        celdas.append(fila)
    tabla_datos = Table(celdas, colWidths=["14%", "41%", "18%", "27%"])
    tabla_datos.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    elementos += [tabla_datos, Spacer(1, 4 * mm)]

    # --- Ítems ---
    encabezado_items = ["Código", "Descripción", "Cantidad", "Valor unitario", "% IVA", "Subtotal"]
    filas_items: list[list] = [[_p(texto, negrita) for texto in encabezado_items]]
    for linea in factura.lineas:
        filas_items.append(
            [
                _p(linea.codigo, normal),
                _p(linea.descripcion, normal),
                _p(_formatear_numero(linea.cantidad), derecha),
                _p(formatear_moneda(linea.precio_unitario), derecha),
                _p(f"{_formatear_numero(linea.porcentaje_iva)} %", derecha),
                _p(formatear_moneda(linea.subtotal), derecha),
            ]
        )
    tabla_items = Table(
        filas_items, colWidths=["11%", "39%", "10%", "15%", "8%", "17%"], repeatRows=1
    )
    tabla_items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E0E0")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elementos += [tabla_items, Spacer(1, 4 * mm)]

    # --- Totales ---
    filas_totales = [["Subtotal", formatear_moneda(totales.subtotal)]]
    for impuesto in totales.impuestos_iva:
        filas_totales.append(
            [
                f"IVA {_formatear_numero(impuesto.porcentaje)} % "
                f"(base {formatear_moneda(impuesto.base)})",
                formatear_moneda(impuesto.valor),
            ]
        )
    filas_totales.append(["Total impuestos", formatear_moneda(totales.total_impuestos)])
    filas_totales.append(["TOTAL A PAGAR", formatear_moneda(totales.total_a_pagar)])
    tabla_totales = Table(
        [[_p(a, negrita), _p(b, derecha)] for a, b in filas_totales],
        colWidths=[60 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    tabla_totales.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    elementos += [tabla_totales, Spacer(1, 4 * mm)]

    # --- Notas ---
    if factura.notas:
        elementos += [_p("Notas", negrita), _p(factura.notas, normal), Spacer(1, 3 * mm)]

    # --- Resolución y CUFE ---
    resolucion = (
        f"Resolución DIAN No. {numeracion.resolucion} del {numeracion.fecha_desde.isoformat()}"
        f" - Prefijo {numeracion.prefijo} desde {numeracion.rango_desde} hasta "
        f"{numeracion.rango_hasta}, vigencia desde {numeracion.fecha_desde.isoformat()} "
        f"hasta {numeracion.fecha_hasta.isoformat()}"
    )
    elementos.append(_p(resolucion, pequeno))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_p("CUFE:", negrita))
    # El CUFE es una sola "palabra" de 96 caracteres: se parte en trozos fijos.
    elementos.append(_p("\n".join(_partir(factura.cufe, 48)), pequeno))

    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=letter,
        leftMargin=_MARGEN,
        rightMargin=_MARGEN,
        topMargin=_MARGEN,
        bottomMargin=_MARGEN + _TAMANO_QR + 2 * mm,
        title=f"{TITULO} {numeracion.numero_completo}",
        author=emisor.razon_social,
        creator="API de facturación electrónica",
        pageCompression=1 if comprimir else 0,
    )
    documento.build(elementos, onFirstPage=decorar_pagina, onLaterPages=decorar_pagina)
    return salida.getvalue()

"""
facturacion_servicio.py - Lógica de Negocio Tributaria y Generación de Factura PDF
Implementa las reglas de cálculo de impuestos DIAN y renderizado de PDF profesional con ReportLab.
"""
import hashlib
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

# Constantes Tributarias DIAN para Personas Naturales
NIT_EMISOR = "901234567-8"
NOMBRE_EMISOR = "GRUPO 5 - FACTURACIÓN ELECTRÓNICA DIAN"
ACTIVIDAD_EMISOR = "Servicios Profesionales y Tecnológicos - Persona Natural"
DIRECCION_EMISOR = "Carrera 7 # 71-21, Bogotá D.C., Colombia"
CLAVE_TECNICA = "dian_clave_tecnica_2026_cloud"

def calcular_impuestos(subtotal: float):
    """
    Calcula los tributos aplicables en Colombia para facturación DIAN:
    - IVA: 19%
    - Gravamen a los Movimientos Financieros (4x1000): 0.4% (0.004)
    - Total: Subtotal + IVA + 4x1000
    """
    subtotal = round(float(subtotal), 2)
    iva = round(subtotal * 0.19, 2)
    impuesto_4x1000 = round(subtotal * 0.004, 2)
    total = round(subtotal + iva + impuesto_4x1000, 2)
    
    return {
        "subtotal": subtotal,
        "iva": iva,
        "impuesto_4x1000": impuesto_4x1000,
        "total": total
    }

def generar_cufe(numero: str, fecha_str: str, subtotal: float, iva: float, total: float, doc_adquiriente: str) -> str:
    """
    Genera el CUFE (Código Único de Facturación Electrónica).
    Aplica el algoritmo SHA-256 sobre la cadena de valores tributarios del Anexo DIAN.
    """
    cadena = f"{numero}{fecha_str}{subtotal:.2f}{iva:.2f}{total:.2f}{NIT_EMISOR}{doc_adquiriente}{CLAVE_TECNICA}"
    return hashlib.sha256(cadena.encode('utf-8')).hexdigest()

def generar_pdf_factura(factura: dict, persona: dict) -> bytes:
    """
    Genera un archivo PDF profesional de la factura electrónica utilizando ReportLab.
    Retorna los bytes del PDF generado en memoria.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Paleta de colores profesional
    color_primario = colors.HexColor("#1A365D")   # Azul DIAN profundo
    color_secundario = colors.HexColor("#2B6CB0") # Azul intermedio
    color_fondo = colors.HexColor("#EDF2F7")      # Gris suave
    color_borde = colors.HexColor("#CBD5E0")

    # Estilos tipográficos
    estilo_titulo = ParagraphStyle(
        'TituloFactura',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=color_primario,
        spaceAfter=4
    )
    estilo_subtitulo = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor("#4A5568")
    )
    estilo_etiqueta = ParagraphStyle(
        'Etiqueta',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=color_primario
    )
    estilo_valor = ParagraphStyle(
        'Valor',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor("#2D3748")
    )
    estilo_cufe = ParagraphStyle(
        'Cufe',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        textColor=colors.HexColor("#4A5568"),
        wordWrap='CJK'
    )

    # 1. ENCABEZADO: Emisor vs Datos de Factura
    datos_emisor = [
        Paragraph(f"<b>{NOMBRE_EMISOR}</b>", estilo_titulo),
        Paragraph(f"<b>NIT:</b> {NIT_EMISOR}", estilo_subtitulo),
        Paragraph(f"<b>Actividad:</b> {ACTIVIDAD_EMISOR}", estilo_subtitulo),
        Paragraph(f"<b>Dirección:</b> {DIRECCION_EMISOR}", estilo_subtitulo),
    ]

    datos_factura_caja = [
        [Paragraph("<b>FACTURA ELECTRÓNICA DE VENTA</b>", ParagraphStyle('H', parent=estilo_etiqueta, textColor=colors.white, alignment=1))],
        [Paragraph(f"<b>No: {factura['numero']}</b>", ParagraphStyle('Num', parent=estilo_titulo, fontSize=14, textColor=color_primario, alignment=1))],
        [Paragraph(f"<b>Fecha:</b> {factura.get('fecha_emision', datetime.now().strftime('%Y-%m-%d %H:%M'))}", estilo_subtitulo)],
        [Paragraph(f"<b>Estado:</b> <font color='green'><b>{factura.get('estado', 'EMITIDA')}</b></font>", estilo_subtitulo)],
        [Paragraph("Resolución DIAN No. 18764000001 de 2026", estilo_subtitulo)],
        [Paragraph("Rango: SETP-0001 a SETP-9999", estilo_subtitulo)],
    ]

    tabla_caja_factura = Table(datos_factura_caja, colWidths=[220])
    tabla_caja_factura.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), color_primario),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, color_secundario),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, color_fondo),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    tabla_encabezado = Table([
        [datos_emisor, tabla_caja_factura]
    ], colWidths=[320, 220])
    tabla_encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(tabla_encabezado)
    story.append(Spacer(1, 15))

    # 2. DATOS DEL ADQUIRIENTE (PERSONA NATURAL)
    story.append(Paragraph("<b>INFORMACIÓN DEL ADQUIRIENTE (CLIENTE)</b>", estilo_etiqueta))
    story.append(HRFlowable(width="100%", thickness=1.5, color=color_secundario, spaceAfter=8, spaceBefore=2))

    tabla_cliente_datos = [
        [
            Paragraph("<b>Nombre / Razón Social:</b>", estilo_etiqueta),
            Paragraph(persona.get('nombre', 'N/A'), estilo_valor),
            Paragraph("<b>Cédula / Documento:</b>", estilo_etiqueta),
            Paragraph(persona.get('cedula', 'N/A'), estilo_valor),
        ],
        [
            Paragraph("<b>RUT:</b>", estilo_etiqueta),
            Paragraph(persona.get('rut', 'N/A'), estilo_valor),
            Paragraph("<b>Teléfono:</b>", estilo_etiqueta),
            Paragraph(persona.get('telefono', 'N/A'), estilo_valor),
        ],
        [
            Paragraph("<b>Dirección:</b>", estilo_etiqueta),
            Paragraph(persona.get('direccion', 'N/A'), estilo_valor),
            Paragraph("<b>Correo Electrónico:</b>", estilo_etiqueta),
            Paragraph(persona.get('correo', 'N/A'), estilo_valor),
        ],
    ]
    tabla_cliente = Table(tabla_cliente_datos, colWidths=[120, 150, 120, 150])
    tabla_cliente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color_fondo),
        ('BOX', (0, 0), (-1, -1), 0.5, color_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, color_borde),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_cliente)
    story.append(Spacer(1, 15))

    # 3. DETALLE DE CONCEPTOS
    story.append(Paragraph("<b>DETALLE DE BIENES O SERVICIOS</b>", estilo_etiqueta))
    story.append(HRFlowable(width="100%", thickness=1.5, color=color_secundario, spaceAfter=8, spaceBefore=2))

    encabezado_items = [
        Paragraph("<b>Cant.</b>", ParagraphStyle('Th', parent=estilo_etiqueta, textColor=colors.white, alignment=1)),
        Paragraph("<b>Descripción / Concepto</b>", ParagraphStyle('Th', parent=estilo_etiqueta, textColor=colors.white)),
        Paragraph("<b>Vr. Unitario</b>", ParagraphStyle('Th', parent=estilo_etiqueta, textColor=colors.white, alignment=2)),
        Paragraph("<b>Total</b>", ParagraphStyle('Th', parent=estilo_etiqueta, textColor=colors.white, alignment=2)),
    ]

    fila_item = [
        Paragraph("1", ParagraphStyle('Td', parent=estilo_valor, alignment=1)),
        Paragraph(factura.get('concepto', 'Servicio General'), estilo_valor),
        Paragraph(f"$ {factura['subtotal']:,.2f} COP", ParagraphStyle('Td', parent=estilo_valor, alignment=2)),
        Paragraph(f"$ {factura['subtotal']:,.2f} COP", ParagraphStyle('Td', parent=estilo_valor, alignment=2)),
    ]

    tabla_items = Table([encabezado_items, fila_item], colWidths=[40, 280, 110, 110])
    tabla_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), color_primario),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, color_borde),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla_items)
    story.append(Spacer(1, 12))

    # 4. LIQUIDACIÓN DE IMPUESTOS Y TOTALES (TRIBUTOS DIAN)
    totales_datos = [
        [Paragraph("<b>Subtotal (Base Imponible):</b>", estilo_etiqueta), Paragraph(f"$ {factura['subtotal']:,.2f} COP", ParagraphStyle('R', parent=estilo_valor, alignment=2))],
        [Paragraph("<b>IVA Generado (19%):</b>", estilo_etiqueta), Paragraph(f"$ {factura['iva']:,.2f} COP", ParagraphStyle('R', parent=estilo_valor, alignment=2))],
        [Paragraph("<b>Gravamen Financiero (4x1000):</b>", estilo_etiqueta), Paragraph(f"$ {factura['impuesto_4x1000']:,.2f} COP", ParagraphStyle('R', parent=estilo_valor, alignment=2))],
        [Paragraph("<b>TOTAL A PAGAR:</b>", ParagraphStyle('T', parent=estilo_titulo, fontSize=11, textColor=color_primario)), Paragraph(f"<b>$ {factura['total']:,.2f} COP</b>", ParagraphStyle('TR', parent=estilo_titulo, fontSize=11, textColor=color_primario, alignment=2))],
    ]

    tabla_totales = Table(totales_datos, colWidths=[360, 180])
    tabla_totales.setStyle(TableStyle([
        ('BACKGROUND', (0, 3), (-1, 3), color_fondo),
        ('GRID', (0, 0), (-1, -1), 0.5, color_borde),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_totales)
    story.append(Spacer(1, 15))

    # 5. BLOQUE CUFE Y VALIDEZ DIAN
    story.append(Paragraph("<b>CÓDIGO ÚNICO DE FACTURACIÓN ELECTRÓNICA (CUFE)</b>", estilo_etiqueta))
    story.append(HRFlowable(width="100%", thickness=1, color=color_secundario, spaceAfter=4, spaceBefore=2))
    story.append(Paragraph(factura.get('cufe', 'N/A'), estilo_cufe))
    story.append(Spacer(1, 8))

    texto_legal = (
        "Esta factura electrónica de venta es título valor y cumple con todos los requisitos del Estatuto Tributario "
        "y resoluciones vigentes de la DIAN para personas naturales obligadas a facturar. Generada automáticamente "
        "por la API de Facturación Cloud - Universidad - Grupo 5."
    )
    story.append(Paragraph(texto_legal, estilo_subtitulo))

    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

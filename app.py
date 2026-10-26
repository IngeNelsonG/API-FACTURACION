"""
app.py - API Principal de Facturación Electrónica DIAN para Personas Naturales
Proyecto Cloud - 8vo Semestre - Grupo 5

Desarrollada sobre Flask + SQLite3 nativo + Autenticación JWT.
Cumple con la estructura de clase y los requerimientos del documento de compromiso.
"""
import datetime
import io
import os
import sqlite3
from functools import wraps

import jwt
from flask import Flask, jsonify, request, send_file

# Cargar variables de entorno desde .env si existe
_env_file = os.path.join(os.path.dirname(__file__), '.env')
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

from correo_servicio import enviar_factura_correo
from database import get_db, init_db
from facturacion_servicio import calcular_impuestos, generar_cufe, generar_pdf_factura

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# -----------------------------------------------------------------------------
# DECORADOR DE AUTENTICACIÓN JWT (@token_required)
# Exactamente según la Diapositiva 29 y 30 de la clase
# -----------------------------------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Falta el token de autorización en el encabezado Authorization'}), 401
        
        try:
            # Soportar formato "Bearer <token>" o token directo
            token_limpio = token.replace('Bearer ', '').strip()
            payload = jwt.decode(token_limpio, app.config['SECRET_KEY'], algorithms=['HS256'])
            setattr(request, 'usuario_actual', payload)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'El token ha expirado. Por favor inicie sesión nuevamente'}), 401
        except (jwt.PyJWTError, Exception):
            return jsonify({'error': 'Token inválido o firma alterada'}), 401
            
        return f(*args, **kwargs)
    return decorador

# -----------------------------------------------------------------------------
# RUTAS BÁSICAS Y DE INFORMACIÓN
# -----------------------------------------------------------------------------
@app.route('/')
def root():
    return jsonify({
        "proyecto": "API de Facturación Electrónica DIAN - Personas Naturales",
        "materia": "Cloud Computing Para El Desarrollo De Software",
        "grupo": "Grupo 5",
        "integrantes": [
            "Nelson Felipe Gonzales Gordillo",
            "Daniel Esteban Alarcón Rojas",
            "Gabriel Felipe Bastidas Alvarado",
            "Michelt Carolina Camargo Cobo"
        ],
        "endpoints_principales": {
            "autenticacion": "POST /login",
            "crud_personas": "GET /personas, POST /personas, PUT /personas/<id>, DELETE /personas/<id>",
            "facturacion_dian": "GET /facturas, POST /facturas, GET /facturas/<id>/pdf, POST /facturas/<id>/enviar-correo"
        }
    }), 200

# -----------------------------------------------------------------------------
# AUTENTICACIÓN: LOGIN Y GENERACIÓN DE JWT
# -----------------------------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    usuario = data.get('usuario')
    clave = data.get('clave')

    if not usuario or not clave:
        return jsonify({'error': 'Debe proporcionar usuario y clave'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios WHERE usuario = ? AND clave = ?', (usuario, clave))
    usuario_encontrado = cursor.fetchone()
    conn.close()

    if usuario_encontrado:
        # Generar token JWT con vigencia de 2 horas
        expiracion = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        token = jwt.encode({
            'id': usuario_encontrado['id'],
            'usuario': usuario_encontrado['usuario'],
            'rol': usuario_encontrado['rol'],
            'exp': expiracion
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'mensaje': 'Autenticación exitosa',
            'token': token,
            'usuario': usuario_encontrado['usuario'],
            'rol': usuario_encontrado['rol'],
            'expira': expiracion.isoformat()
        }), 200

    return jsonify({'error': 'Credenciales inválidas. Verifique usuario y clave'}), 401

# =============================================================================
# RECURSO PRINCIPAL: CRUD PERSONA NATURAL
# Slide 35: Dominio propio con mínimo 4 campos
# Campos: nombre, rut, cedula, direccion, correo, telefono
# =============================================================================

# 1. GET /personas (Público - lista todas las personas)
@app.route('/personas', methods=['GET'])
def get_personas():
    conn = get_db()
    cursor = conn.cursor()
    filas = cursor.execute('SELECT * FROM personas ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(f) for f in filas]), 200

# 2. GET /personas/<id> (Público - consulta detalle por ID)
@app.route('/personas/<int:persona_id>', methods=['GET'])
def get_persona(persona_id):
    conn = get_db()
    cursor = conn.cursor()
    fila = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,)).fetchone()
    conn.close()

    if fila is None:
        return jsonify({'error': f'Persona natural con ID {persona_id} no encontrada'}), 404
    return jsonify(dict(fila)), 200

# 3. POST /personas (Protegido con @token_required - creación)
@app.route('/personas', methods=['POST'])
@token_required
def create_persona():
    data = request.get_json() or {}
    
    # Validar campos obligatorios
    campos_requeridos = ['nombre', 'rut', 'cedula', 'direccion', 'correo']
    for campo in campos_requeridos:
        if not data.get(campo):
            return jsonify({'error': f'El campo obligatorio "{campo}" está ausente'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO personas (nombre, rut, cedula, direccion, correo, telefono)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('nombre'),
            data.get('rut'),
            data.get('cedula'),
            data.get('direccion'),
            data.get('correo'),
            data.get('telefono', '')
        ))
        conn.commit()
        nuevo_id = cursor.lastrowid
        persona_creada = cursor.execute('SELECT * FROM personas WHERE id = ?', (nuevo_id,)).fetchone()
        conn.close()
        return jsonify(dict(persona_creada)), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Ya existe una persona registrada con esa cédula'}), 409

# 4. PUT /personas/<id> (Protegido con @token_required - actualización)
@app.route('/personas/<int:persona_id>', methods=['PUT'])
@token_required
def update_persona(persona_id):
    data = request.get_json() or {}
    conn = get_db()
    cursor = conn.cursor()

    fila = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,)).fetchone()
    if fila is None:
        conn.close()
        return jsonify({'error': f'Persona natural con ID {persona_id} no encontrada'}), 404

    # Actualizar con los nuevos valores o mantener los actuales
    cursor.execute('''
        UPDATE personas
        SET nombre = ?, rut = ?, cedula = ?, direccion = ?, correo = ?, telefono = ?
        WHERE id = ?
    ''', (
        data.get('nombre', fila['nombre']),
        data.get('rut', fila['rut']),
        data.get('cedula', fila['cedula']),
        data.get('direccion', fila['direccion']),
        data.get('correo', fila['correo']),
        data.get('telefono', fila['telefono']),
        persona_id
    ))
    conn.commit()
    persona_actualizada = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,)).fetchone()
    conn.close()
    return jsonify(dict(persona_actualizada)), 200

# 5. DELETE /personas/<id> (Protegido con @token_required - eliminación)
@app.route('/personas/<int:persona_id>', methods=['DELETE'])
@token_required
def delete_persona(persona_id):
    conn = get_db()
    cursor = conn.cursor()

    fila = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,)).fetchone()
    if fila is None:
        conn.close()
        return jsonify({'error': f'Persona natural con ID {persona_id} no encontrada'}), 404

    cursor.execute('DELETE FROM personas WHERE id = ?', (persona_id,))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': f'Persona natural con ID {persona_id} eliminada exitosamente'}), 200

# =============================================================================
# FUNCIONALIDAD ESPECIAL: FACTURACIÓN ELECTRÓNICA DIAN
# Cálculo de impuestos (IVA 19%, Gravamen 4x1000), CUFE, PDF y envío de correo
# =============================================================================

# 1. GET /facturas (Público - lista todas las facturas con datos del cliente)
@app.route('/facturas', methods=['GET'])
def get_facturas():
    conn = get_db()
    cursor = conn.cursor()
    query = '''
        SELECT f.*, p.nombre AS cliente_nombre, p.cedula AS cliente_cedula, p.correo AS cliente_correo
        FROM facturas f
        JOIN personas p ON f.persona_id = p.id
        ORDER BY f.id DESC
    '''
    filas = cursor.execute(query).fetchall()
    conn.close()
    return jsonify([dict(f) for f in filas]), 200

# 2. GET /facturas/<id> (Público - detalle de factura)
@app.route('/facturas/<int:factura_id>', methods=['GET'])
def get_factura(factura_id):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
        SELECT f.*, p.nombre AS cliente_nombre, p.cedula AS cliente_cedula, p.rut AS cliente_rut,
               p.direccion AS cliente_direccion, p.correo AS cliente_correo, p.telefono AS cliente_telefono
        FROM facturas f
        JOIN personas p ON f.persona_id = p.id
        WHERE f.id = ?
    '''
    fila = cursor.execute(query, (factura_id,)).fetchone()
    conn.close()

    if fila is None:
        return jsonify({'error': f'Factura con ID {factura_id} no encontrada'}), 404
    return jsonify(dict(fila)), 200

# 3. POST /facturas (Protegido con @token_required - emisión y liquidación de factura)
@app.route('/facturas', methods=['POST'])
@token_required
def create_factura():
    data = request.get_json() or {}
    persona_id = data.get('persona_id')
    concepto = data.get('concepto')
    subtotal = data.get('subtotal')

    if not persona_id or not concepto or subtotal is None:
        return jsonify({'error': 'Debe enviar persona_id, concepto y subtotal'}), 400

    try:
        subtotal_val = float(subtotal)
        if subtotal_val <= 0:
            return jsonify({'error': 'El subtotal debe ser un valor numérico positivo'}), 400
    except ValueError:
        return jsonify({'error': 'El subtotal debe ser un número válido'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Validar que la persona exista en el sistema
    persona = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id,)).fetchone()
    if persona is None:
        conn.close()
        return jsonify({'error': f'La persona natural con ID {persona_id} no existe'}), 404

    # 1. Calcular tributos DIAN (IVA 19%, 4x1000)
    calculos = calcular_impuestos(subtotal_val)

    # 2. Asignar número consecutivo oficial DIAN
    cursor.execute('SELECT COUNT(*) as count FROM facturas')
    total_facturas = cursor.fetchone()['count'] + 1
    numero_factura = f"SETP-{total_facturas:04d}"

    # 3. Generar el CUFE (Código Único de Facturación Electrónica)
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cufe = generar_cufe(
        numero=numero_factura,
        fecha_str=fecha_actual,
        subtotal=calculos['subtotal'],
        iva=calculos['iva'],
        total=calculos['total'],
        doc_adquiriente=persona['cedula']
    )

    # 4. Guardar en SQLite
    cursor.execute('''
        INSERT INTO facturas (numero, persona_id, concepto, subtotal, iva, impuesto_4x1000, total, cufe, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'EMITIDA')
    ''', (
        numero_factura,
        persona_id,
        concepto,
        calculos['subtotal'],
        calculos['iva'],
        calculos['impuesto_4x1000'],
        calculos['total'],
        cufe
    ))
    conn.commit()
    nueva_factura_id = cursor.lastrowid
    factura_creada = cursor.execute('SELECT * FROM facturas WHERE id = ?', (nueva_factura_id,)).fetchone()
    conn.close()

    return jsonify({
        'mensaje': 'Factura electrónica emitida exitosamente ante la DIAN',
        'factura': dict(factura_creada),
        'desglose_tributario': calculos
    }), 201

# 4. DELETE /facturas/<id> (Protegido con @token_required - anulación de factura)
@app.route('/facturas/<int:factura_id>', methods=['DELETE'])
@token_required
def anular_factura(factura_id):
    conn = get_db()
    cursor = conn.cursor()

    fila = cursor.execute('SELECT * FROM facturas WHERE id = ?', (factura_id,)).fetchone()
    if fila is None:
        conn.close()
        return jsonify({'error': f'Factura con ID {factura_id} no encontrada'}), 404

    cursor.execute("UPDATE facturas SET estado = 'ANULADA' WHERE id = ?", (factura_id,))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': f'Factura No. {fila["numero"]} anulada exitosamente'}), 200

# 5. GET /facturas/<id>/pdf (Público - descarga representación gráfica PDF)
@app.route('/facturas/<int:factura_id>/pdf', methods=['GET'])
def descargar_pdf(factura_id):
    conn = get_db()
    cursor = conn.cursor()
    factura = cursor.execute('SELECT * FROM facturas WHERE id = ?', (factura_id,)).fetchone()

    if factura is None:
        conn.close()
        return jsonify({'error': f'Factura con ID {factura_id} no encontrada'}), 404

    persona = cursor.execute('SELECT * FROM personas WHERE id = ?', (factura['persona_id'],)).fetchone()
    conn.close()

    # Generar el PDF profesional en memoria
    pdf_bytes = generar_pdf_factura(dict(factura), dict(persona))

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f"Factura_{factura['numero']}.pdf"
    )

# 6. POST /facturas/<id>/enviar-correo (Protegido con @token_required - envío al cliente)
@app.route('/facturas/<int:factura_id>/enviar-correo', methods=['POST'])
@token_required
def enviar_correo(factura_id):
    conn = get_db()
    cursor = conn.cursor()
    factura = cursor.execute('SELECT * FROM facturas WHERE id = ?', (factura_id,)).fetchone()

    if factura is None:
        conn.close()
        return jsonify({'error': f'Factura con ID {factura_id} no encontrada'}), 404

    persona = cursor.execute('SELECT * FROM personas WHERE id = ?', (factura['persona_id'],)).fetchone()

    # Generar el PDF para adjuntarlo en el correo
    pdf_bytes = generar_pdf_factura(dict(factura), dict(persona))

    # Realizar el envío de correo
    resultado_envio = enviar_factura_correo(
        destinatario=persona['correo'],
        factura=dict(factura),
        persona=dict(persona),
        pdf_bytes=pdf_bytes
    )

    if resultado_envio.get('enviado'):
        cursor.execute('UPDATE facturas SET correo_enviado = 1 WHERE id = ?', (factura_id,))
        conn.commit()

    conn.close()
    return jsonify(resultado_envio), (200 if resultado_envio.get('enviado') else 500)

# -----------------------------------------------------------------------------
# INICIALIZACIÓN Y ARRANQUE
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    init_db()

    puerto = int(os.getenv('PORT', '5000'))

    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        puerto_ocupado = (s.connect_ex(('127.0.0.1', puerto)) == 0)

    if puerto_ocupado and puerto == 5000:
        puerto = 5001

    print("==============================================================")
    print("API DE FACTURACIÓN ELECTRÓNICA DIAN - GRUPO 5")
    print(f"Servidor Flask iniciado en http://localhost:{puerto}")
    print(f"Acceso en red local: http://0.0.0.0:{puerto}")
    print("==============================================================")
    app.run(host='0.0.0.0', port=puerto, debug=True)

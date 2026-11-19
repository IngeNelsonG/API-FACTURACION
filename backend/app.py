"""
app.py - API Principal de Facturación Electrónica DIAN para Personas Naturales
Proyecto Cloud - 8vo Semestre - Grupo 5

Desarrollada sobre Flask + SQLite3 nativo + Autenticación JWT.
Cumple con la estructura de clase y los requerimientos del documento de compromiso.
"""
import datetime
import io
import os
import re
import sqlite3
from functools import wraps

import jwt
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

# Cargar variables de entorno desde .env si existe.
# Se busca primero en backend/ y luego en la raíz del proyecto (donde está el .env).
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

from correo_servicio import enviar_factura_correo
from database import get_db, init_db
from facturacion_servicio import calcular_impuestos, generar_cufe, generar_pdf_factura

app = Flask(__name__)
# Valor por defecto solo para desarrollo/CI; en la nube SIEMPRE definir SECRET_KEY
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-cambiar-en-produccion')

# CORS: permite que el frontend React (Vite) consuma la API desde otro origen.
# CORS_ORIGINS acepta varios orígenes separados por coma.
_cors_env = os.getenv('CORS_ORIGINS', '').strip()
if _cors_env:
    # Producción / nube: solo los orígenes indicados en el .env
    _cors_origins = [o.strip() for o in _cors_env.split(',') if o.strip()]
else:
    # Desarrollo: cualquier puerto en localhost, 127.0.0.1 o la red local (192.168.x.x).
    # Así no falla si Vite arranca en 5174 o si se abre el front por la IP del equipo.
    _cors_origins = [r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?"]
CORS(app, resources={r"/*": {"origins": _cors_origins}},
     allow_headers=['Content-Type', 'Authorization'],
     expose_headers=['Content-Disposition'])

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
            "autenticacion": "POST /login, POST /registro",
            "crud_personas": "GET /personas, POST /personas, PUT /personas/<id>, DELETE /personas/<id>",
            "facturacion_dian": "GET /facturas, POST /facturas, PATCH /facturas/<id>/pagar, GET /facturas/<id>/pdf, POST /facturas/<id>/enviar-correo"
        }
    }), 200

# -----------------------------------------------------------------------------
# HELPERS DE ENTITY SCOPING POR ROL (cliente vs admin/facturador)
# -----------------------------------------------------------------------------
def _usuario_actual():
    return getattr(request, 'usuario_actual', None) or {}


def _es_cliente():
    return _usuario_actual().get('rol') == 'cliente'


def _persona_id_cliente():
    return _usuario_actual().get('persona_id')


def _verificar_acceso_persona(persona_id_objetivo):
    """
    Asegura que un usuario con rol 'cliente' solo acceda a recursos de su
    propia persona_id. Si intenta acceder a los de otro cliente, retorna 403.
    """
    if _es_cliente():
        persona_propia = _persona_id_cliente()
        if persona_propia is None or persona_propia != persona_id_objetivo:
            return jsonify({
                'error': 'Prohibido: no tiene permiso para acceder a los recursos de otro cliente'
            }), 403
    return None


# -----------------------------------------------------------------------------
# AUTENTICACIÓN: LOGIN Y GENERACIÓN DE JWT
# -----------------------------------------------------------------------------
def _clave_valida(clave_guardada, clave_recibida):
    """
    Las cuentas creadas con /registro guardan la clave con hash (pbkdf2).
    El usuario inicial 'profe' viene en texto plano (como en clase), así que
    se aceptan ambos formatos.
    """
    if clave_guardada.startswith(('pbkdf2:', 'scrypt:')):
        return check_password_hash(clave_guardada, clave_recibida)
    return clave_guardada == clave_recibida


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    usuario = (data.get('usuario') or '').strip()
    clave = data.get('clave')

    if not usuario or not clave:
        return jsonify({'error': 'Debe proporcionar usuario y clave'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.*, p.nombre AS nombre
        FROM usuarios u
        LEFT JOIN personas p ON p.id = u.persona_id
        WHERE u.usuario = ?
    ''', (usuario,))
    usuario_encontrado = cursor.fetchone()
    conn.close()

    if usuario_encontrado and _clave_valida(usuario_encontrado['clave'], clave):
        # Generar token JWT con vigencia de 2 horas (incluye persona_id para entity scoping)
        expiracion = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
        token = jwt.encode({
            'id': usuario_encontrado['id'],
            'usuario': usuario_encontrado['usuario'],
            'rol': usuario_encontrado['rol'],
            'persona_id': usuario_encontrado['persona_id'],
            'exp': expiracion
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'mensaje': 'Autenticación exitosa',
            'token': token,
            'usuario': usuario_encontrado['usuario'],
            'nombre': usuario_encontrado['nombre'],
            'rol': usuario_encontrado['rol'],
            'persona_id': usuario_encontrado['persona_id'],
            'expira': expiracion.isoformat()
        }), 200

    return jsonify({'error': 'Credenciales inválidas. Verifique usuario y clave'}), 401


# 1.1 POST /registro (Público - crea la cuenta y registra a la persona como cliente)
_PATRON_USUARIO = re.compile(r'^[A-Za-z0-9._-]{3,30}$')


@app.route('/registro', methods=['POST'])
def registro():
    data = request.get_json() or {}
    usuario = (data.get('usuario') or '').strip()
    clave = data.get('clave') or ''
    persona = {campo: (data.get(campo) or '').strip()
               for campo in ('nombre', 'cedula', 'rut', 'direccion', 'correo', 'telefono')}

    # Validaciones
    for campo in ('nombre', 'cedula', 'rut', 'direccion', 'correo'):
        if not persona[campo]:
            return jsonify({'error': f'El campo obligatorio "{campo}" está ausente'}), 400
    if not _PATRON_USUARIO.match(usuario):
        return jsonify({'error': 'El usuario debe tener entre 3 y 30 caracteres (letras, números, punto, guion o guion bajo)'}), 400
    if len(clave) < 6:
        return jsonify({'error': 'La clave debe tener al menos 6 caracteres'}), 400
    if '@' not in persona['correo'] or '.' not in persona['correo'].split('@')[-1]:
        return jsonify({'error': 'El correo electrónico no es válido'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        if cursor.execute('SELECT 1 FROM usuarios WHERE usuario = ?', (usuario,)).fetchone():
            return jsonify({'error': f'El usuario "{usuario}" ya existe, elige otro'}), 409
        if cursor.execute('SELECT 1 FROM personas WHERE cedula = ?', (persona['cedula'],)).fetchone():
            return jsonify({'error': 'Ya existe una persona registrada con esa cédula'}), 409

        # Persona (cliente) + usuario en una sola transacción
        cursor.execute('''
            INSERT INTO personas (nombre, rut, cedula, direccion, correo, telefono)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (persona['nombre'], persona['rut'], persona['cedula'],
              persona['direccion'], persona['correo'], persona['telefono']))
        persona_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO usuarios (usuario, clave, rol, persona_id)
            VALUES (?, ?, ?, ?)
        ''', (usuario, generate_password_hash(clave, method='pbkdf2:sha256'), 'cliente', persona_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'El usuario o la cédula ya están registrados'}), 409
    finally:
        conn.close()

    return jsonify({
        'mensaje': 'Cuenta creada exitosamente. Ya puedes iniciar sesión.',
        'usuario': usuario,
        'persona_id': persona_id,
    }), 201

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
    if _es_cliente():
        return jsonify({'error': 'Prohibido: los clientes no pueden registrar otras personas'}), 403
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
    denegado = _verificar_acceso_persona(persona_id)
    if denegado:
        return denegado

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
    denegado = _verificar_acceso_persona(persona_id)
    if denegado:
        return denegado

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
# Cálculo de impuestos (IVA 19% + 4x1000 informativo), CUFE, PDF y envío de correo
# =============================================================================

def _obtener_factura_con_permiso(conn, factura_id, query=None):
    """
    Busca una factura por ID y valida el entity scoping del usuario actual.
    Retorna (fila, None) o (None, respuesta_error) con 404 o 403.
    """
    sql = query or 'SELECT * FROM facturas WHERE id = ?'
    fila = conn.execute(sql, (factura_id,)).fetchone()
    if fila is None:
        return None, (jsonify({'error': f'Factura con ID {factura_id} no encontrada'}), 404)
    denegado = _verificar_acceso_persona(fila['persona_id'])
    if denegado:
        return None, denegado
    return fila, None


# 1. GET /facturas (Protegido con @token_required + entity scoping por cliente)
@app.route('/facturas', methods=['GET'])
@token_required
def get_facturas():
    conn = get_db()
    cursor = conn.cursor()
    base_query = '''
        SELECT f.*, p.nombre AS cliente_nombre, p.cedula AS cliente_cedula, p.correo AS cliente_correo
        FROM facturas f
        JOIN personas p ON f.persona_id = p.id
    '''
    if _es_cliente():
        persona_id = _persona_id_cliente()
        if persona_id is None:
            conn.close()
            return jsonify([]), 200
        filas = cursor.execute(
            f'{base_query} WHERE f.persona_id = ? ORDER BY f.id DESC',
            (persona_id,),
        ).fetchall()
    else:
        filas = cursor.execute(f'{base_query} ORDER BY f.id DESC').fetchall()
    conn.close()
    return jsonify([dict(f) for f in filas]), 200


# 2. GET /facturas/<id> (Protegido con @token_required + entity scoping 403)
@app.route('/facturas/<int:factura_id>', methods=['GET'])
@token_required
def get_factura(factura_id):
    conn = get_db()
    query = '''
        SELECT f.*, p.nombre AS cliente_nombre, p.cedula AS cliente_cedula, p.rut AS cliente_rut,
               p.direccion AS cliente_direccion, p.correo AS cliente_correo, p.telefono AS cliente_telefono
        FROM facturas f
        JOIN personas p ON f.persona_id = p.id
        WHERE f.id = ?
    '''
    fila, error_resp = _obtener_factura_con_permiso(conn, factura_id, query=query)
    conn.close()

    if error_resp:
        return error_resp
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
        persona_id_val = int(persona_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'El persona_id debe ser un número entero válido'}), 400

    denegado = _verificar_acceso_persona(persona_id_val)
    if denegado:
        return denegado

    try:
        subtotal_val = float(subtotal)
        if subtotal_val <= 0:
            return jsonify({'error': 'El subtotal debe ser un valor numérico positivo'}), 400
    except (TypeError, ValueError):
        return jsonify({'error': 'El subtotal debe ser un número válido'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Validar que la persona exista en el sistema
    persona = cursor.execute('SELECT * FROM personas WHERE id = ?', (persona_id_val,)).fetchone()
    if persona is None:
        conn.close()
        return jsonify({'error': f'La persona natural con ID {persona_id_val} no existe'}), 404

    # 1. Calcular tributos: IVA 19% (total = subtotal + IVA) y 4x1000 informativo
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
        persona_id_val,
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

    fila, error_resp = _obtener_factura_con_permiso(conn, factura_id)
    if error_resp:
        conn.close()
        return error_resp

    cursor.execute("UPDATE facturas SET estado = 'ANULADA' WHERE id = ?", (factura_id,))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': f'Factura No. {fila["numero"]} anulada exitosamente'}), 200


# 4.1 PATCH /facturas/<id>/pagar (Protegido - registra el pago de una factura)
# Ciclo de vida: EMITIDA (pendiente de pago) -> PAGADA | EMITIDA -> ANULADA
@app.route('/facturas/<int:factura_id>/pagar', methods=['PATCH'])
@token_required
def pagar_factura(factura_id):
    conn = get_db()
    cursor = conn.cursor()

    fila, error_resp = _obtener_factura_con_permiso(conn, factura_id)
    if error_resp:
        conn.close()
        return error_resp

    if fila['estado'] == 'ANULADA':
        conn.close()
        return jsonify({'error': f'La factura No. {fila["numero"]} está anulada y no puede pagarse'}), 409
    if fila['estado'] == 'PAGADA':
        conn.close()
        return jsonify({'error': f'La factura No. {fila["numero"]} ya está pagada'}), 409

    cursor.execute("UPDATE facturas SET estado = 'PAGADA' WHERE id = ?", (factura_id,))
    conn.commit()
    factura = cursor.execute('SELECT * FROM facturas WHERE id = ?', (factura_id,)).fetchone()
    conn.close()
    return jsonify({
        'mensaje': f'Factura No. {fila["numero"]} marcada como pagada',
        'factura': dict(factura)
    }), 200


# 5. GET /facturas/<id>/pdf (Protegido con @token_required + entity scoping 403)
@app.route('/facturas/<int:factura_id>/pdf', methods=['GET'])
@token_required
def descargar_pdf(factura_id):
    conn = get_db()
    factura, error_resp = _obtener_factura_con_permiso(conn, factura_id)
    if error_resp:
        conn.close()
        return error_resp

    persona = conn.execute('SELECT * FROM personas WHERE id = ?', (factura['persona_id'],)).fetchone()
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
    factura, error_resp = _obtener_factura_con_permiso(conn, factura_id)
    if error_resp:
        conn.close()
        return error_resp

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

    # Con debug=True Flask reinicia el proceso (reloader). El proceso hijo hereda el
    # puerto que ya abrió el padre, así que solo el proceso inicial verifica si está libre.
    # (Antes el hijo veía el 5000 "ocupado" por su propio padre y mostraba 5001 por error.)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            puerto_ocupado = (s.connect_ex(('127.0.0.1', puerto)) == 0)

        if puerto_ocupado and puerto == 5000:
            puerto = 5001
            # El hijo del reloader debe usar el mismo puerto que eligió el padre
            os.environ['PORT'] = str(puerto)

    print("==============================================================")
    print("API DE FACTURACIÓN ELECTRÓNICA DIAN - GRUPO 5")
    print(f"Servidor Flask iniciado en http://localhost:{puerto}")
    print(f"Acceso en red local: http://0.0.0.0:{puerto}")
    print("==============================================================")
    app.run(host='0.0.0.0', port=puerto, debug=True)

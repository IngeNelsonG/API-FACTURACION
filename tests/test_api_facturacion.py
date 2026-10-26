"""
test_api_facturacion.py - Suite Completa de Pruebas Automatizadas
Verifica los requisitos del proyecto:
1. Base común (CRUD, JWT, SQLite persistencia)
2. Funcionalidad especial (Cálculo de impuestos DIAN, CUFE, PDF y Correo)
"""
import os
import pytest
import tempfile

# Asegurar que las pruebas usen una base de datos temporal limpia
os.environ['DB_NAME'] = 'test_facturacion.db'

from app import app
from database import init_db, get_db

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Inicializa la base de datos de pruebas antes de correr los tests."""
    init_db()
    yield
    # Limpieza al finalizar
    if os.path.exists('test_facturacion.db'):
        os.remove('test_facturacion.db')

@pytest.fixture
def client():
    """Retorna un cliente de pruebas de Flask."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def obtener_token_valido(client):
    """Función de ayuda para obtener un token JWT válido de login."""
    res = client.post('/login', json={'usuario': 'profe', 'clave': 'cloud2026'})
    data = res.get_json()
    return data['token']


# =============================================================================
# 1. PRUEBAS DE RUTAS BÁSICAS Y HTTP INFO
# =============================================================================
def test_root_salud(client):
    """Verifica que la ruta raíz responda 200 con la información del proyecto."""
    res = client.get('/')
    assert res.status_code == 200
    data = res.get_json()
    assert "API de Facturación Electrónica DIAN" in data['proyecto']
    assert "Grupo 5" in data['grupo']

def test_validacion_campos_factura(client):
    """Verifica que emitir factura con datos inválidos o incompletos devuelva 400 Bad Request."""
    token = obtener_token_valido(client)
    headers = {'Authorization': f'Bearer {token}'}

    # Petición sin subtotal
    res_invalido = client.post('/facturas', json={'persona_id': 1, 'concepto': 'Prueba'}, headers=headers)
    assert res_invalido.status_code == 400
    assert 'error' in res_invalido.get_json()

    # Petición con subtotal negativo o cero
    res_negativo = client.post('/facturas', json={'persona_id': 1, 'concepto': 'Prueba', 'subtotal': -500}, headers=headers)
    assert res_negativo.status_code == 400
    assert 'error' in res_negativo.get_json()


# =============================================================================
# 2. PRUEBAS DE AUTENTICACIÓN JWT (LOGIN)
# =============================================================================
def test_login_exitoso(client):
    """Prueba que el login con credenciales correctas entregue un JWT."""
    res = client.post('/login', json={'usuario': 'profe', 'clave': 'cloud2026'})
    assert res.status_code == 200
    data = res.get_json()
    assert 'token' in data
    assert data['usuario'] == 'profe'

def test_login_fallido(client):
    """Prueba que credenciales incorrectas devuelvan 401 Unauthorized."""
    res = client.post('/login', json={'usuario': 'profe', 'clave': 'clave_incorrecta'})
    assert res.status_code == 401
    assert 'error' in res.get_json()


# =============================================================================
# 3. PRUEBAS DE PROTECCIÓN DE ENDPOINTS CON @token_required
# =============================================================================
def test_endpoints_protegidos_sin_token(client):
    """Verifica que POST, PUT y DELETE rechacen peticiones sin token con 401."""
    # Intentar crear persona sin token
    res_crear = client.post('/personas', json={'nombre': 'Test'})
    assert res_crear.status_code == 401

    # Intentar actualizar persona sin token
    res_act = client.put('/personas/1', json={'telefono': '123'})
    assert res_act.status_code == 401

    # Intentar crear factura sin token
    res_fac = client.post('/facturas', json={'persona_id': 1, 'subtotal': 50000})
    assert res_fac.status_code == 401


# =============================================================================
# 4. PRUEBAS CRUD DE PERSONA NATURAL (RECURSO PRINCIPAL)
# =============================================================================
def test_crud_persona_natural_completo(client):
    """Prueba las operaciones completas del CRUD con token de autorización."""
    token = obtener_token_valido(client)
    headers = {'Authorization': f'Bearer {token}'}

    # 1. Crear persona (POST protegido)
    persona_datos = {
        'nombre': 'Carlos Mendoza Silva',
        'rut': '987654321-9',
        'cedula': '987654321',
        'direccion': 'Avenida Siempre Viva 742',
        'correo': 'carlos.mendoza@example.com',
        'telefono': '3009876543'
    }
    res_post = client.post('/personas', json=persona_datos, headers=headers)
    assert res_post.status_code == 201
    persona_creada = res_post.get_json()
    persona_id = persona_creada['id']
    assert persona_creada['nombre'] == 'Carlos Mendoza Silva'

    # 2. Consultar por ID (GET público)
    res_get = client.get(f'/personas/{persona_id}')
    assert res_get.status_code == 200
    assert res_get.get_json()['cedula'] == '987654321'

    # 3. Actualizar datos (PUT protegido)
    res_put = client.put(f'/personas/{persona_id}', json={
        'telefono': '3200001122',
        'direccion': 'Nueva Dirección Central # 45'
    }, headers=headers)
    assert res_put.status_code == 200
    assert res_put.get_json()['telefono'] == '3200001122'

    # 4. Listar todas las personas (GET público)
    res_list = client.get('/personas')
    assert res_list.status_code == 200
    assert len(res_list.get_json()) >= 2

    # 5. Eliminar persona (DELETE protegido)
    res_del = client.delete(f'/personas/{persona_id}', headers=headers)
    assert res_del.status_code == 200
    assert 'eliminada exitosamente' in res_del.get_json()['mensaje']

    # 6. Confirmar eliminación (GET puntual debe responder 404)
    res_verif = client.get(f'/personas/{persona_id}')
    assert res_verif.status_code == 404


# =============================================================================
# 5. PRUEBAS DE FUNCIONALIDAD ESPECIAL: FACTURACIÓN DIAN
# =============================================================================
def test_emision_factura_con_calculo_impuestos(client):
    """
    Verifica el cálculo tributario de la DIAN:
    Subtotal: $100,000 COP
    IVA 19%: $19,000 COP
    4x1000: $400 COP
    Total: $119,400 COP
    """
    token = obtener_token_valido(client)
    headers = {'Authorization': f'Bearer {token}'}

    factura_req = {
        'persona_id': 1,
        'concepto': 'Consultoría en Arquitectura Cloud',
        'subtotal': 100000.0
    }
    res = client.post('/facturas', json=factura_req, headers=headers)
    assert res.status_code == 201
    data = res.get_json()
    
    factura = data['factura']
    desglose = data['desglose_tributario']

    # Verificación de cálculos
    assert desglose['subtotal'] == 100000.0
    assert desglose['iva'] == 19000.0
    assert desglose['impuesto_4x1000'] == 400.0
    assert desglose['total'] == 119400.0

    # Verificación de datos de la DIAN
    assert factura['numero'].startswith('SETP-')
    assert len(factura['cufe']) == 64  # SHA-256 genera un hash de 64 caracteres hex
    assert factura['estado'] == 'EMITIDA'

def test_descargar_pdf_factura(client):
    """Verifica que el endpoint devuelva un PDF válido generado con ReportLab."""
    res = client.get('/facturas/1/pdf')
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data.startswith(b'%PDF-')  # Encabezado estándar de archivo PDF

def test_enviar_correo_factura(client):
    """Verifica la ejecución del servicio de correo con adjunto de la factura."""
    token = obtener_token_valido(client)
    headers = {'Authorization': f'Bearer {token}'}

    res = client.post('/facturas/1/enviar-correo', headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data['enviado'] is True

def test_anulacion_factura(client):
    """Verifica que una factura pueda ser anulada con DELETE protegido."""
    token = obtener_token_valido(client)
    headers = {'Authorization': f'Bearer {token}'}

    res = client.delete('/facturas/1', headers=headers)
    assert res.status_code == 200
    
    # Comprobar que en la base de datos el estado haya cambiado a ANULADA
    res_get = client.get('/facturas/1')
    assert res_get.get_json()['estado'] == 'ANULADA'

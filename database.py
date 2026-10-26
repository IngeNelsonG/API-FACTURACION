"""
database.py - Gestión de la Base de Datos SQLite
Alineado con el contenido de la clase de Cloud (api-clase.txt)
"""
import os
import sqlite3

DB_NAME = os.getenv('DB_NAME', 'facturacion.db')

def get_db():
    """
    Retorna una conexión a la base de datos SQLite.
    Se activa sqlite3.Row para acceder a las columnas por nombre (como diccionarios).
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Inicializa las tablas necesarias para la API:
    1. usuarios: Para el login y autenticación JWT.
    2. personas: Recurso principal (Persona Natural con RUT, Cédula, etc.).
    3. facturas: Recurso de facturación electrónica DIAN con cálculo de impuestos.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Tabla de usuarios para login JWT
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT DEFAULT 'facturador'
        )
    ''')

    # 2. Tabla de Personas Naturales (Recurso principal con más de 4 campos requeridos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            rut TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            direccion TEXT NOT NULL,
            correo TEXT NOT NULL,
            telefono TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Tabla de Facturas (Funcionalidad Especial DIAN)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            persona_id INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            subtotal REAL NOT NULL,
            iva REAL NOT NULL,
            impuesto_4x1000 REAL NOT NULL,
            total REAL NOT NULL,
            cufe TEXT NOT NULL,
            estado TEXT DEFAULT 'EMITIDA',
            correo_enviado INTEGER DEFAULT 0,
            fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (persona_id) REFERENCES personas (id)
        )
    ''')

    # Insertar usuario inicial si no existe (idéntico a lo visto en clase)
    cursor.execute('SELECT COUNT(*) as count FROM usuarios WHERE usuario = ?', ('profe',))
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO usuarios (usuario, clave, rol)
            VALUES (?, ?, ?)
        ''', ('profe', 'cloud2026', 'admin'))

    # Insertar un cliente de prueba inicial si la tabla está vacía
    cursor.execute('SELECT COUNT(*) as count FROM personas')
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO personas (nombre, rut, cedula, direccion, correo, telefono)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'Juan Carlos Pérez Gómez',
            '1020304050-1',
            '1020304050',
            'Calle 100 # 15-20, Bogotá',
            'juan.perez@example.com',
            '3101234567'
        ))

    conn.commit()
    conn.close()

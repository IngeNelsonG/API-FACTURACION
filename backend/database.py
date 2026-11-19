"""
database.py - Gestión de la Base de Datos (SQLite local / PostgreSQL en la nube)
Usa PostgreSQL automáticamente cuando existe la variable de entorno DATABASE_URL
(p. ej. Render PostgreSQL) y SQLite como respaldo local o en pruebas automatizadas.
"""
import datetime
import os
import sqlite3

try:
    import psycopg2
    import psycopg2.extras
    _HAS_PSYCOPG2 = True
    IntegrityError = (sqlite3.IntegrityError, psycopg2.IntegrityError)
except ImportError:  # pragma: no cover - entorno sin psycopg2 instalado
    psycopg2 = None
    _HAS_PSYCOPG2 = False
    IntegrityError = (sqlite3.IntegrityError,)


def _database_url():
    url = os.getenv('DATABASE_URL', '').strip()
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url


def is_postgres() -> bool:
    return bool(_database_url())


def _normalize_pg_row(row):
    """Convierte valores datetime de Postgres a string UTC '%Y-%m-%d %H:%M:%S' igual que SQLite."""
    if row is None:
        return None
    out = dict(row)
    for k, v in out.items():
        if isinstance(v, datetime.datetime):
            out[k] = v.strftime('%Y-%m-%d %H:%M:%S')
    return out


class _PgCursorWrapper:
    """Adaptador de cursor psycopg2 compatible con la interfaz sqlite3.Cursor."""

    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def execute(self, sql, params=()):
        pg_sql = sql.replace('?', '%s')
        es_insert = pg_sql.lstrip().upper().startswith('INSERT')
        if es_insert and 'RETURNING' not in pg_sql.upper():
            pg_sql = f"{pg_sql.rstrip().rstrip(';')} RETURNING id"
            self._cur.execute(pg_sql, params)
            fila = self._cur.fetchone()
            self.lastrowid = fila['id'] if fila else None
        else:
            self._cur.execute(pg_sql, params)
        return self

    def fetchone(self):
        return _normalize_pg_row(self._cur.fetchone())

    def fetchall(self):
        return [_normalize_pg_row(r) for r in self._cur.fetchall()]


class _PgConnWrapper:
    """Adaptador de conexión psycopg2 compatible con sqlite3.Connection."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _PgCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    """
    Retorna una conexión a la base de datos (PostgreSQL si DATABASE_URL está definida,
    o SQLite en desarrollo/pruebas). Las filas soportan acceso por nombre de columna y dict().
    """
    url = _database_url()
    if url:
        if not _HAS_PSYCOPG2:
            raise RuntimeError('DATABASE_URL configurada pero falta instalar psycopg2-binary')
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        return _PgConnWrapper(conn)

    db_name = os.getenv('DB_NAME', 'facturacion.db')
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn


def _init_postgres(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS personas (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            rut TEXT NOT NULL,
            cedula TEXT UNIQUE NOT NULL,
            direccion TEXT NOT NULL,
            correo TEXT NOT NULL,
            telefono TEXT,
            fecha_registro TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC')
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT DEFAULT 'facturador',
            persona_id INTEGER REFERENCES personas (id)
        )
    ''')
    cursor.execute('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS persona_id INTEGER REFERENCES personas (id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id SERIAL PRIMARY KEY,
            numero TEXT UNIQUE NOT NULL,
            persona_id INTEGER NOT NULL REFERENCES personas (id),
            concepto TEXT NOT NULL,
            subtotal DOUBLE PRECISION NOT NULL,
            iva DOUBLE PRECISION NOT NULL,
            impuesto_4x1000 DOUBLE PRECISION NOT NULL,
            total DOUBLE PRECISION NOT NULL,
            cufe TEXT NOT NULL,
            estado TEXT DEFAULT 'EMITIDA',
            correo_enviado INTEGER DEFAULT 0,
            fecha_emision TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC')
        )
    ''')


def _init_sqlite(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT DEFAULT 'facturador'
        )
    ''')

    columnas_usuarios = [c['name'] for c in cursor.execute('PRAGMA table_info(usuarios)').fetchall()]
    if 'persona_id' not in columnas_usuarios:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN persona_id INTEGER REFERENCES personas (id)')

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


def init_db():
    """
    Inicializa las tablas (usuarios, personas, facturas) y carga los datos iniciales
    ('profe' admin y cliente de prueba inicial) si la base está vacía.
    """
    conn = get_db()
    cursor = conn.cursor()

    if is_postgres():
        _init_postgres(cursor)
    else:
        _init_sqlite(cursor)

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

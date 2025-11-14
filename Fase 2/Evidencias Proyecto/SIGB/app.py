import mysql.connector
from flask import Flask, render_template, request, jsonify, g
from configuracion import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
app = Flask(__name__)
app.secret_key = 'tonecaps' 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Definición del modelo de usuario para Flask-Login
class User(UserMixin):
    def __init__(self, id, nombre, rol, password_hash):
        self.id = id
        self.nombre = nombre
        self.rol = rol
        self.password_hash = password_hash
        
    def check_password(self, password):
        # Utiliza la función de Flask-Login para verificar el hash
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    """Callback para recargar el objeto Usuario desde la ID de la sesión."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_usuario, nombre, rol, password_hash FROM USUARIOS WHERE id_usuario = %s", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            return User(user_data['id_usuario'], user_data['nombre'], user_data['rol'], user_data['password_hash'])
        return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        return None

# Función decoradora auxiliar para requerir un rol específico
def role_required(role_name):
    """
    Decora las rutas para asegurar que el usuario esté logueado y tenga el rol especificado.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # Si no está autenticado, redirigir al login (configurado en login_manager.login_view)
                return jsonify({'error': 'Acceso denegado. Se requiere iniciar sesión.'}), 401
            
            # Verificar si el rol del usuario coincide con el rol requerido
            if current_user.rol != role_name:
                return jsonify({'error': f'Acceso denegado. Se requiere el rol: {role_name}.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Función específica para el rol de administrador
def admin_required(f):
    return role_required('Admin')(f)

# **********************************************************
# 1. CONFIGURACIÓN DE BASE DE DATOS Y CONEXIÓN
# **********************************************************

# Usamos las variables importadas de configuracion.py
db_config = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'database': MYSQL_DATABASE
}

def get_db_connection():
    """Establece y devuelve una conexión a la base de datos usando las credenciales de configuracion.py."""
    try:
        if 'db' not in g:
            g.db = mysql.connector.connect(**db_config)
        return g.db
    except mysql.connector.Error as err:
        print(f"Error de conexión a MySQL. Por favor, verifica el archivo 'configuracion.py' y que MySQL esté activo: {err}")
        return None

@app.teardown_appcontext
def close_db_connection(exception):
    """Cierra la conexión a la base de datos al finalizar la solicitud."""
    db = g.pop('db', None)
    if db is not None and db.is_connected():
        db.close()



# **********************************************************
# 2. RUTAS HTML (Vistas)
# **********************************************************

@app.route('/')
def index():
    """Ruta principal."""
    return "Bienvenido al Sistema de Gestión de Biblioteca (SIGB). Usa /catalogacion para el módulo."

@app.route('/catalogacion')
def catalogacion():
    """Muestra la vista de catalogación de materiales (catalogacion.html)."""
    return render_template('catalogacion.html')

@app.route('/circulacion')
def circulacion():
    """Muestra la vista del módulo de Circulación (prestamos y devoluciones)."""
    return render_template('circulacion.html')

@app.route('/opac')
def opac():
    """Muestra la interfaz pública de consulta (OPAC)."""
    return render_template('opac.html')

@app.route('/admin/usuarios')
@login_required
@role_required('Admin') # Solo el Admin puede ver la gestión de usuarios
def admin_usuarios():
    """Muestra la vista de administración de usuarios (admin_usuarios.html)."""
    return render_template('admin_usuarios.html')

@app.route('/admin/reportes')
@login_required
@role_required('Bibliotecario') # Opcional: Podrías poner 'Admin' si es muy restringido
def admin_reportes():
    """Muestra la vista de reportes de gestión (admin_reportes.html)."""
    return render_template('admin_reportes.html')

@app.route('/admin/catalogos')
@login_required
@role_required('Bibliotecario') # Opcional: Podrías poner 'Admin' si es muy restringido
def admin_catalogos():
    """Muestra la vista para gestionar Autor, Editorial y Categoría."""
    return render_template('admin_tablas_apoyo.html')
# **********************************************************
# 3. RUTAS DE API (Módulo de Catalogación - CRUD COMPLETO)
# **********************************************************
# HU-CAT02: Guardar un nuevo material (CREATE) - AHORA SOPORTA MÚLTIPLES CATEGORÍAS (HU-CAT06)
@app.route('/api/catalogacion/guardar', methods=['POST'])
@login_required # Debe estar logueado
@role_required('Bibliotecario') # Solo bibliotecario o admin
def guardar_material():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    # ... (El código SQL_MATERIAL y VALUES_MATERIAL es el mismo) ...
    sql_material = """
    INSERT INTO MATERIALES (
        titulo, anio_publicacion, isbn, ejemplares_totales, ejemplares_disponibles, 
        tipo, disponible, EDITORIAL_id_editorial, AUTOR_id_autor
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        # La variable 'ejemplares' debe convertirse a INT
        ejemplares_input = data.get('ejemplares', 1) 
        ejemplares = int(ejemplares_input)
        
        # También asegurar conversión para FKs y Año
        anio = int(data.get('anio'))
        editorial_id = int(data.get('editorial_id'))
        autor_id = int(data.get('autor_id'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Error de formato: Los valores de stock, año e IDs deben ser números enteros.'}), 400
    values_material = (
        data.get('titulo'),
        data.get('anio'),
        data.get('isbn'),
        ejemplares,           # ejemplares_totales
        ejemplares,           # ejemplares_disponibles
        'Libro',              # tipo
        'S',                  # disponible
        data.get('editorial_id'), 
        data.get('autor_id')      
    )
    
    # 🚨 CAMBIO CLAVE para HU-CAT06: Esperar una lista de IDs de categorías
    categorias_ids = data.get('categorias_ids', [])
    if not isinstance(categorias_ids, list):
        categorias_ids = [categorias_ids] if categorias_ids else []

    try:
        cursor = conn.cursor()
        
        # 1. Insertar el Material
        cursor.execute(sql_material, values_material)
        material_id = cursor.lastrowid # Obtener el ID generado
        
        # 2. Insertar las Categorías en la tabla N:M (Loop)
        if categorias_ids:
            sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
            for cat_id in categorias_ids:
                cursor.execute(sql_cat, (material_id, cat_id))
        
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g

        return jsonify({'message': 'Material catalogado y vinculado a categorías correctamente.', 'id': material_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al guardar material: {err}")
        return jsonify({'error': f'Error al guardar en BD: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()
    pass


# HU-CAT03: Listar todos los materiales (READ)
@app.route('/api/catalogacion/listar', methods=['GET'])
def listar_materiales():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    sql = """
    SELECT 
        M.id_material,
        M.titulo,
        M.isbn,
        M.ejemplares_totales,
        M.ejemplares_disponibles,
        M.anio_publicacion AS anio,
        A.nombre_autor,
        E.nombre_editorial
    FROM 
        MATERIALES M
    JOIN 
        AUTOR A ON M.AUTOR_id_autor = A.id_autor
    JOIN 
        EDITORIAL E ON M.EDITORIAL_id_editorial = E.id_editorial
    ORDER BY M.id_material DESC
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        materiales = cursor.fetchall()
        
        return jsonify(materiales), 200

    except Exception as e:
        print(f"Error al listar materiales: {e}")
        return jsonify({'error': 'Error en la consulta SQL de listado'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CAT04 (Parte: Obtener Material para Edición)
@app.route('/api/catalogacion/obtener/<int:material_id>', methods=['GET'])
@login_required # Proteger contra acceso no autorizado
@role_required('Bibliotecario')
def obtener_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    sql = """
    SELECT 
        M.id_material, M.titulo, M.anio_publicacion AS anio, M.isbn,
        M.ejemplares_totales, M.ejemplares_disponibles,
        M.EDITORIAL_id_editorial AS editorial_id, 
        M.AUTOR_id_autor AS autor_id,
        GROUP_CONCAT(MC.CATEGORIAS_id_categoria) AS categorias_ids # Devuelve una cadena de IDs de categorías
    FROM MATERIALES M
    LEFT JOIN MATERIALES_CATEGORIAS MC ON M.id_material = MC.MATERIALES_id_material
    WHERE M.id_material = %s
    GROUP BY M.id_material
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (material_id,))
        material = cursor.fetchone()
        
        if material:
            # Convertir la cadena de categorías (ej: '1,3,5') a una lista de enteros
            if material['categorias_ids']:
                material['categorias_ids'] = [int(x) for x in material['categorias_ids'].split(',')]
            else:
                material['categorias_ids'] = []
                
            return jsonify(material), 200
        else:
            return jsonify({'error': 'Material no encontrado'}), 404
            
    except Exception as e:
        print(f"Error al obtener material: {e}")
        return jsonify({'error': 'Error en la consulta'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CAT04: Guardar los cambios de un material (UPDATE) - INCLUYE HU-CAT06
@app.route('/api/catalogacion/editar/<int:material_id>', methods=['PUT'])
@login_required
@role_required('Bibliotecario')
def editar_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    try:
        ejemplares_totales_input = data.get('ejemplares_totales')
        ejemplares_disponibles_input = data.get('ejemplares_disponibles')
        
        # 1. Validación de existencia (no deben ser nulos/vacíos)
        if not ejemplares_totales_input or not ejemplares_disponibles_input:
            return jsonify({'error': 'El stock total y disponible son obligatorios.'}), 400
            
        # 2. Conversión segura
        ejemplares_totales = int(ejemplares_totales_input)
        ejemplares_disponibles = int(ejemplares_disponibles_input)
        
        # También asegurar conversión para FKs y Año
        anio = int(data.get('anio'))
        editorial_id = int(data.get('editorial_id'))
        autor_id = int(data.get('autor_id'))

    except (ValueError, TypeError):
        return jsonify({'error': 'Error de formato: Stock, año e IDs deben ser números enteros válidos.'}), 400    # Validación de Regla de Negocio
    if ejemplares_disponibles > ejemplares_totales:
        return jsonify({'error': 'El número de ejemplares disponibles no puede ser mayor al total de ejemplares.'}), 400

    sql_material = """
    UPDATE MATERIALES SET 
        titulo = %s, anio_publicacion = %s, isbn = %s, 
        ejemplares_totales = %s, ejemplares_disponibles = %s,
        EDITORIAL_id_editorial = %s, AUTOR_id_autor = %s,
        tipo = 'Libro', disponible = 'S' 
    WHERE id_material = %s
    """
    
    values_material = (
        data.get('titulo'), data.get('anio'), data.get('isbn'), 
        ejemplares_totales, ejemplares_disponibles,
        data.get('editorial_id'), data.get('autor_id'),
        material_id
    )
    
    # GESTIÓN DE CATEGORÍAS N:M (HU-CAT06)
    categorias_ids_raw = data.get('categorias_ids', [])
    if categorias_ids_raw is None:
        categorias_ids = []
    elif not isinstance(categorias_ids_raw, list):
        categorias_ids = [categorias_ids_raw]
    else:
        categorias_ids = categorias_ids_raw
    
    try:
        categorias_ids = [int(cid) for cid in categorias_ids if cid]
    except ValueError:
        return jsonify({'error': 'Los IDs de categorías deben ser números enteros válidos.'}), 400
    
    try:
        cursor = conn.cursor()
        
        # 1. Actualizar el Material
        cursor.execute(sql_material, values_material)
        
        # 2. GESTIÓN DE CATEGORÍAS N:M (Borrar todo y re-insertar la selección actual)
        cursor.execute("DELETE FROM MATERIALES_CATEGORIAS WHERE MATERIALES_id_material = %s", (material_id,))
        
        if categorias_ids:
            sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
            for cat_id in categorias_ids:
                cursor.execute(sql_cat, (material_id, cat_id))
        
        conn.commit()
        # 🚨 CORRECCIÓN CLAVE: Cierre de conexión después del commit
        if 'db' in g: g.db.close(); g.pop('db', None)
        
        return jsonify({'message': f'Material {material_id} actualizado y categorías vinculadas correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al actualizar material: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CAT05: Eliminar un material (DELETE)
@app.route('/api/catalogacion/eliminar/<int:material_id>', methods=['DELETE'])
@login_required
@role_required('Bibliotecario')
def eliminar_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. VERIFICACIÓN DE REGLA DE NEGOCIO: No se puede eliminar si hay ejemplares prestados
        cursor.execute("SELECT ejemplares_totales, ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", (material_id,))
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404
            
        if material['ejemplares_totales'] != material['ejemplares_disponibles']:
            prestados = material['ejemplares_totales'] - material['ejemplares_disponibles']
            return jsonify({'error': f'Imposible eliminar. Aún hay {prestados} ejemplares prestados o en circulación.'}), 400

        # 2. ELIMINACIÓN SEGURA 
        sql = "DELETE FROM MATERIALES WHERE id_material = %s"
        cursor.execute(sql, (material_id,))
        conn.commit()
        
        # 🚨 CORRECCIÓN CLAVE: Cierre de conexión después del commit
        if 'db' in g: g.db.close(); g.pop('db', None)
        
        if cursor.rowcount > 0:
            return jsonify({'message': f'Material {material_id} eliminado correctamente.'}), 200
        else:
            return jsonify({'error': 'No se pudo eliminar el material.'}), 500

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()


# **********************************************************
# 3.1 RUTAS DE API (CRUD Tablas de Apoyo: AUTOR) - T03 COMPLETADA
# **********************************************************

# T03 (Parte A): Registrar nuevo Autor (CREATE)
@app.route('/api/autor/guardar', methods=['POST'])
@login_required # <--- AÑADIR ESTO
@role_required('Bibliotecario') # <--- AÑADIR ESTO
def guardar_autor():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    nombre = data.get('nombre_autor')
    
    if not nombre:
        return jsonify({'error': 'El nombre del autor es obligatorio.'}), 400

    sql = "INSERT INTO AUTOR (nombre_autor) VALUES (%s)"
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (nombre,))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': 'Autor registrado con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T03 (Parte B): Eliminar Autor (DELETE)
@app.route('/api/autor/eliminar/<int:autor_id>', methods=['DELETE'])
@login_required # <--- AÑADIR ESTO
@role_required('Bibliotecario') # <--- AÑADIR ESTO
def eliminar_autor(autor_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
        # 1. Eliminar
        sql = "DELETE FROM AUTOR WHERE id_autor = %s"
        cursor.execute(sql, (autor_id,))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        if cursor.rowcount > 0:
            return jsonify({'message': f'Autor {autor_id} eliminado correctamente.'}), 200
        else:
            return jsonify({'error': 'Autor no encontrado o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        # Captura el error de restricción de clave externa (FK)
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar el autor: tiene materiales bibliográficos asociados.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T03: CRUD para EDITORIAL (CREATE)
@app.route('/api/editorial/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
def guardar_editorial():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    # Espera la clave 'nombre_editorial' del frontend
    nombre = data.get('nombre_editorial') 
    
    if not nombre:
        return jsonify({'error': 'El nombre de la editorial es obligatorio.'}), 400

    sql = "INSERT INTO EDITORIAL (nombre_editorial) VALUES (%s)"
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (nombre,))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': 'Editorial registrada con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T03: CRUD para EDITORIAL (DELETE)
@app.route('/api/editorial/eliminar/<int:editorial_id>', methods=['DELETE'])
@login_required
@role_required('Bibliotecario')
def eliminar_editorial(editorial_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
        sql = "DELETE FROM EDITORIAL WHERE id_editorial = %s"
        cursor.execute(sql, (editorial_id,))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        if cursor.rowcount > 0:
            return jsonify({'message': f'Editorial {editorial_id} eliminada correctamente.'}), 200
        else:
            return jsonify({'error': 'Editorial no encontrada o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        # Captura el error de restricción de clave externa (FK)
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar la editorial: tiene materiales bibliográficos asociados.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T03: CRUD para CATEGORIAS (CREATE)
@app.route('/api/categoria/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
def guardar_categoria():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    # Espera la clave 'nombre_categoria' del frontend
    nombre = data.get('nombre_categoria') 
    # La tabla CATEGORIAS requiere descripción
    descripcion = data.get('descripcion', 'Sin descripción proporcionada.') 
    
    if not nombre:
        return jsonify({'error': 'El nombre de la categoría es obligatorio.'}), 400

    sql = "INSERT INTO CATEGORIAS (nombre_categoria, descripcion) VALUES (%s, %s)"
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (nombre, descripcion))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': 'Categoría registrada con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T03: CRUD para CATEGORIAS (DELETE)
@app.route('/api/categoria/eliminar/<int:categoria_id>', methods=['DELETE'])
@login_required
@role_required('Bibliotecario')
def eliminar_categoria(categoria_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
        sql = "DELETE FROM CATEGORIAS WHERE id_categoria = %s"
        cursor.execute(sql, (categoria_id,))
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        if cursor.rowcount > 0:
            return jsonify({'message': f'Categoría {categoria_id} eliminada correctamente.'}), 200
        else:
            return jsonify({'error': 'Categoría no encontrada o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        # Captura el error de restricción de clave externa (FK)
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar la categoría: está asignada a uno o más materiales.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# **********************************************************
# 3.2 RUTAS DE API (Setup Tabla USUARIOS) - T06 COMPLETADA
# **********************************************************

# T06: Registrar un nuevo usuario (CREATE)
# T06: Registrar un nuevo usuario (CREATE) - VERSIÓN FINAL CORREGIDA
@app.route('/api/usuario/registrar', methods=['POST'])
@login_required
@admin_required # Solo el Administrador puede crear cuentas de personal
def registrar_usuario():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    # Validaciones mínimas de existencia de campos
    required_fields = ['nombre', 'rut', 'correo', 'telefono', 'rol']
    if not all(data.get(field) for field in required_fields):
        # ⚠️ Esta validación DEBE ir antes de crear el hash o construir el SQL.
        return jsonify({'error': 'Faltan campos obligatorios para el registro del usuario.'}), 400
    
    # Generar hash temporal para cumplir con la restricción NOT NULL
    from werkzeug.security import generate_password_hash
    password_temporal = 'temporal' # Contraseña de primer uso
    hashed_password = generate_password_hash(password_temporal, method='pbkdf2:sha256') 

    sql = """
    INSERT INTO USUARIOS (nombre, rut, correo, telefono, rol, password_hash)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (
        data.get('nombre'),
        data.get('rut'),
        data.get('correo'),
        data.get('telefono'),
        data.get('rol'), 
        hashed_password # 🚨 Valor 6 de 6 para el INSERT
    )
    
    try:
        cursor = conn.cursor()
        # 🚨 Solo ejecutar la sentencia SQL una vez
        cursor.execute(sql, values)
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': 'Usuario registrado con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        # Captura errores de unicidad (ej. RUT o Correo duplicado)
        if err.errno == 1062: 
            return jsonify({'error': 'Error: El RUT o Correo ya está registrado en el sistema.'}), 400
        print(f"Error SQL al registrar usuario: {err}")
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# T07: Implementar un sistema de cache básico para las listas de apoyo
@app.route('/api/listas_catalogacion', methods=['GET'])
def cargar_listas_catalogacion():
    # Usar caché en el objeto 'g'
    if 'listas_cache' in g:
        return jsonify(g.listas_cache), 200

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    data = {}
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Consulta para Autores
        cursor.execute("SELECT id_autor, nombre_autor FROM AUTOR")
        data['autores'] = cursor.fetchall()  # <--- CLAVE CORRECTA: 'autores'

        # Consulta para Editoriales
        cursor.execute("SELECT id_editorial, nombre_editorial FROM EDITORIAL")
        data['editoriales'] = cursor.fetchall() # <--- CLAVE CORRECTA: 'editoriales'
        
        # Consulta para Categorías
        cursor.execute("SELECT id_categoria, nombre_categoria FROM CATEGORIAS")
        data['categorias'] = cursor.fetchall() # <--- CLAVE CORRECTA: 'categorias'
        
        # Guardar en caché 
        g.listas_cache = data 
        
        return jsonify(data), 200

    except Exception as e:
        print(f"Error al cargar listas de apoyo: {e}")
        return jsonify({'error': 'Error en la consulta SQL'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# **********************************************************
# 4. RUTAS DE API (MÓDULO DE CIRCULACIÓN)
# **********************************************************

# HU-CIRC01: Registrar Préstamo (CREATE/UPDATE Transaccional)
@app.route('/api/circulacion/prestamo', methods=['POST'])
@login_required 
@role_required('Bibliotecario') 
def registrar_prestamo():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    rut_usuario = data.get('rut_usuario')
    material_id = data.get('material_id')
    
    # 🚨 NOTA: La fecha de devolución debería calcularse aquí (ej. 14 días después)
    # Por simplicidad, usaremos la fecha actual del sistema.

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. VALIDAR USUARIO (Criterio de Aceptación: Usuario debe existir)
        cursor.execute("SELECT id_usuario FROM USUARIOS WHERE rut = %s", (rut_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado o RUT inválido.'}), 404
        id_usuario = usuario['id_usuario']
        
        # 2. VALIDAR MATERIAL Y STOCK (Criterio de Aceptación: Debe haber ejemplares disponibles)
        cursor.execute(
            "SELECT ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", 
            (material_id,)
        )
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404

        if material['ejemplares_disponibles'] < 1:
            return jsonify({'error': 'No hay ejemplares disponibles para préstamo.'}), 400
            
        # 3. REGISTRAR EL PRÉSTAMO
        sql_prestamo = """
        INSERT INTO PRESTAMOS (fecha_prestamo, fecha_devolucion, estado_prestamo, USUARIOS_id_usuario, MATERIALES_id_material)
        VALUES (NOW(), DATE_ADD(CURDATE(), INTERVAL 14 DAY), 'Activo', %s, %s)
        """
        cursor.execute(sql_prestamo, (id_usuario, material_id))
        
        # 4. DECREMENTAR STOCK (Criterio de Aceptación: ejemplares_disponibles decrementa en 1)
        sql_stock_update = """
        UPDATE MATERIALES SET ejemplares_disponibles = ejemplares_disponibles - 1
        WHERE id_material = %s
        """
        cursor.execute(sql_stock_update, (material_id,))

        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': 'Préstamo registrado con éxito. Stock actualizado.', 'id_prestamo': cursor.lastrowid}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al registrar préstamo: {err}")
        return jsonify({'error': f'Error transaccional al registrar préstamo: {err.msg}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CIRC02 & HU-CIRC03: Registrar Devolución y Calcular Multas (UPDATE Transaccional)
@app.route('/api/circulacion/devolucion', methods=['POST'])
@login_required 
@role_required('Bibliotecario') 
def registrar_devolucion():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    id_prestamo = data.get('id_prestamo')
    
    if not id_prestamo:
        return jsonify({'error': 'ID de Préstamo es obligatorio.'}), 400

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. VERIFICAR PRÉSTAMO Y OBTENER FECHAS
        cursor.execute(
            "SELECT MATERIALES_id_material, estado_prestamo, fecha_devolucion FROM PRESTAMOS WHERE id_prestamo = %s",
            (id_prestamo,)
        )
        prestamo = cursor.fetchone()
        
        if not prestamo:
            return jsonify({'error': 'Préstamo no encontrado.'}), 404
            
        if prestamo['estado_prestamo'] != 'Activo':
            return jsonify({'error': f'El préstamo {id_prestamo} ya fue devuelto o cancelado.'}), 400
            
        material_id = prestamo['MATERIALES_id_material']
        
        # 2. CÁLCULO DE MULTAS (HU-CIRC03)
        # Usamos DATEDIFF para calcular los días de retraso
        sql_multa = """
        SELECT GREATEST(0, DATEDIFF(CURDATE(), %s)) AS dias_retraso
        """
        # La fecha esperada de devolución es prestamo['fecha_devolucion']
        cursor.execute(sql_multa, (prestamo['fecha_devolucion'],))
        dias_retraso = cursor.fetchone()['dias_retraso']
        
        monto_multa = dias_retraso * 500 # Tarifa de $500 por día
        
        # 3. ACTUALIZAR ESTADO DEL PRÉSTAMO, FECHA REAL Y MONTO DE MULTA
        # NOTA: Asumo que la tabla PRESTAMOS tiene ahora una columna 'monto_multa'
        # Si no la tiene, tendrás que añadirla con SQL. (ALTER TABLE PRESTAMOS ADD COLUMN monto_multa DECIMAL(10, 2) DEFAULT 0)
        sql_prestamo_update = """
        UPDATE PRESTAMOS SET 
            estado_prestamo = 'Devuelto', 
            fecha_devolucion_real = CURDATE(),
            monto_multa = %s
        WHERE id_prestamo = %s
        """
        cursor.execute(sql_prestamo_update, (monto_multa, id_prestamo))
        
        # 4. INCREMENTAR STOCK
        sql_stock_update = """
        UPDATE MATERIALES SET ejemplares_disponibles = ejemplares_disponibles + 1
        WHERE id_material = %s
        """
        cursor.execute(sql_stock_update, (material_id,))

        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        # 5. RETORNAR RESULTADO DE MULTA AL FRONTEND
        if monto_multa > 0:
             return jsonify({
                 'message': f'Devolución registrada con éxito. ¡ATENCIÓN! Se generó una multa por {dias_retraso} días de retraso.',
                 'multa': monto_multa,
                 'dias_retraso': dias_retraso
             }), 200
        
        return jsonify({'message': f'Devolución de Préstamo {id_prestamo} registrada con éxito. Sin multas.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al registrar devolución: {err}")
        return jsonify({'error': f'Error transaccional al registrar devolución: {err.msg}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()


# HU-CIRC04: Módulo de visualización de Préstamos Activos y Vencidos (READ)
@app.route('/api/circulacion/prestamos_activos', methods=['GET'])
def listar_prestamos_activos():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    # Consulta avanzada para obtener préstamos activos, el título del material y el RUT del usuario
    sql = """
    SELECT 
        P.id_prestamo,
        P.fecha_prestamo,
        P.fecha_devolucion,
        P.estado_prestamo,
        M.titulo AS titulo_material,
        U.rut AS rut_usuario
    FROM 
        PRESTAMOS P
    JOIN 
        MATERIALES M ON P.MATERIALES_id_material = M.id_material
    JOIN 
        USUARIOS U ON P.USUARIOS_id_usuario = U.id_usuario
    WHERE 
        P.estado_prestamo = 'Activo'
    ORDER BY P.fecha_devolucion ASC;
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        prestamos = cursor.fetchall()
        
        # El cálculo de "VENCIDO" se realiza en el front-end (circulacion.html)
        return jsonify(prestamos), 200

    except Exception as e:
        print(f"Error al listar préstamos activos: {e}")
        return jsonify({'error': 'Error en la consulta SQL de listado de préstamos'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# **********************************************************
# 5. RUTAS DE API (MÓDULO OPAC - CONSULTA PÚBLICA)
# **********************************************************

# HU-CONS01: Motor de Búsqueda avanzado
@app.route('/api/opac/buscar', methods=['GET'])
def buscar_materiales():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    # Obtener parámetros de búsqueda (opcionales)
    query_text = request.args.get('query', '')
    categoria_id = request.args.get('categoria_id', type=int)
    
    base_sql = """
    SELECT 
        M.id_material, M.titulo, M.isbn, M.anio_publicacion, M.ejemplares_disponibles,
        A.nombre_autor, E.nombre_editorial,
        GROUP_CONCAT(C.nombre_categoria SEPARATOR ', ') AS categorias
    FROM 
        MATERIALES M
    JOIN 
        AUTOR A ON M.AUTOR_id_autor = A.id_autor
    JOIN 
        EDITORIAL E ON M.EDITORIAL_id_editorial = E.id_editorial
    LEFT JOIN 
        MATERIALES_CATEGORIAS MC ON M.id_material = MC.MATERIALES_id_material
    LEFT JOIN 
        CATEGORIAS C ON MC.CATEGORIAS_id_categoria = C.id_categoria
    WHERE 1=1 
    """
    params = []
    
    # Filtro por texto (Título o Autor)
    if query_text:
        base_sql += " AND (M.titulo LIKE %s OR A.nombre_autor LIKE %s)"
        params.extend([f'%{query_text}%', f'%{query_text}%'])
    
    # Filtro por Categoría
    if categoria_id:
        base_sql += " AND M.id_material IN (SELECT MATERIALES_id_material FROM MATERIALES_CATEGORIAS WHERE CATEGORIAS_id_categoria = %s)"
        params.append(categoria_id)

    # Agrupación y Ordenamiento
    base_sql += " GROUP BY M.id_material ORDER BY M.titulo ASC"
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(base_sql, tuple(params))
        resultados = cursor.fetchall()
        
        return jsonify(resultados), 200

    except Exception as e:
        print(f"Error al realizar la búsqueda en OPAC: {e}")
        return jsonify({'error': 'Error en la consulta SQL de búsqueda'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()    

# HU-CONS02: Obtener Detalle Completo del Material (READ)
@app.route('/api/opac/detalle/<int:material_id>', methods=['GET'])
def obtener_detalle_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    sql = """
    SELECT 
        M.id_material, M.titulo, M.isbn, M.anio_publicacion, 
        M.ejemplares_totales, M.ejemplares_disponibles, M.tipo,
        A.nombre_autor, E.nombre_editorial,
        GROUP_CONCAT(C.nombre_categoria SEPARATOR ', ') AS categorias
    FROM 
        MATERIALES M
    JOIN 
        AUTOR A ON M.AUTOR_id_autor = A.id_autor
    JOIN 
        EDITORIAL E ON M.EDITORIAL_id_editorial = E.id_editorial
    LEFT JOIN 
        MATERIALES_CATEGORIAS MC ON M.id_material = MC.MATERIALES_id_material
    LEFT JOIN 
        CATEGORIAS C ON MC.CATEGORIAS_id_categoria = C.id_categoria
    WHERE 
        M.id_material = %s
    GROUP BY M.id_material
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (material_id,))
        detalle = cursor.fetchone()
        
        if detalle:
            return jsonify(detalle), 200
        else:
            return jsonify({'error': 'Material no encontrado.'}), 404

    except Exception as e:
        print(f"Error al obtener detalle del material: {e}")
        return jsonify({'error': 'Error en la consulta SQL de detalle.'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CONS03: Registrar Reserva Remota
@app.route('/api/opac/reservar', methods=['POST'])
@login_required # Solo usuarios logueados pueden reservar
def registrar_reserva():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    material_id = data.get('material_id')
    id_usuario = current_user.id # El ID del usuario logueado

    try:
        cursor = conn.cursor(dictionary=True)

        # 1. VERIFICAR MATERIAL Y STOCK (Criterio de Aceptación: Debe haber justificación para reservar)
        cursor.execute(
            "SELECT titulo, ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", 
            (material_id,)
        )
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404

        if material['ejemplares_disponibles'] > 0:
            # Regla de Negocio: Solo permitir reservas si el material no está disponible (stock = 0)
            return jsonify({'error': 'El material está disponible actualmente. No necesita reserva.'}), 400

        # 2. VERIFICAR RESERVAS ACTIVAS DEL USUARIO (Evitar duplicados)
        cursor.execute(
            "SELECT id_reserva FROM RESERVAS WHERE USUARIOS_id_usuario = %s AND MATERIALES_id_material = %s AND estado_reserva = 'Pendiente'", 
            (id_usuario, material_id)
        )
        if cursor.fetchone():
            return jsonify({'error': 'Ya tienes una reserva activa para este material.'}), 400
            
        # 3. REGISTRAR LA RESERVA
        sql_reserva = """
        INSERT INTO RESERVAS (fecha_reserva, estado_reserva, USUARIOS_id_usuario, MATERIALES_id_material)
        VALUES (CURDATE(), 'Pendiente', %s, %s)
        """
        cursor.execute(sql_reserva, (id_usuario, material_id))

        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': f'Reserva registrada con éxito para el material: {material["titulo"]}. Recibirás una notificación cuando esté disponible.'}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al registrar reserva: {err}")
        return jsonify({'error': f'Error transaccional al registrar reserva: {err.msg}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# **********************************************************
# 6. MÓDULO DE ADMINISTRACIÓN CORE (HU-ADMIN01)
# **********************************************************
# HU-ADMIN01
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        rut = data.get('rut')
        password = data.get('password')
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id_usuario, nombre, rol, password_hash FROM USUARIOS WHERE rut = %s", (rut,))
            user_data = cursor.fetchone()
            
            if user_data:
                user = User(user_data['id_usuario'], user_data['nombre'], user_data['rol'], user_data['password_hash'])
                
                # Criterio de Aceptación: Uso de hashes
                if user.check_password(password): 
                    login_user(user)
                    return jsonify({'message': 'Inicio de sesión exitoso.', 'user': user.nombre, 'rol': user.rol}), 200
                else:
                    return jsonify({'error': 'Credenciales inválidas.'}), 401
            
            return jsonify({'error': 'Usuario no encontrado.'}), 404
            
        except Exception as e:
            print(f"Error en login: {e}")
            return jsonify({'error': 'Error en el proceso de autenticación.'}), 500
    
    # Renderizar la vista de login (si la tuvieras)
    return render_template('login.html') 


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Sesión cerrada correctamente.'}), 200

# HU-ADMIN02 (Parte: Obtener Usuario por ID para Edición)
@app.route('/api/admin/usuario/obtener/<int:usuario_id>', methods=['GET'])
@login_required
@admin_required
def obtener_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    sql = """
    SELECT 
        id_usuario, nombre, rut, correo, telefono, rol, estado_activo 
    FROM USUARIOS 
    WHERE id_usuario = %s
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (usuario_id,))
        usuario = cursor.fetchone()
        
        if usuario:
            return jsonify(usuario), 200
        else:
            return jsonify({'error': 'Usuario no encontrado.'}), 404

    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        return jsonify({'error': 'Error en la consulta SQL de obtención de usuario.'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN02 (Parte: Listar Usuarios)
# HU-ADMIN02 (Parte: Listar Usuarios)
@app.route('/api/admin/usuarios', methods=['GET'])
@login_required
@admin_required # Solo el Admin debe ver la lista completa de usuarios del sistema
def listar_usuarios():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    sql = """
    SELECT 
        id_usuario, nombre, rut, correo, telefono, rol, estado_activo  /* <--- COLUMNA AÑADIDA */
    FROM USUARIOS 
    ORDER BY rol DESC, nombre ASC
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        usuarios = cursor.fetchall()
        
        return jsonify(usuarios), 200

    except Exception as e:
        print(f"Error al listar usuarios: {e}")
        return jsonify({'error': 'Error en la consulta SQL de listado de usuarios'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN02 (Parte: Editar Usuario - UPDATE)
@app.route('/api/admin/usuario/editar/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required # Solo el Admin puede editar los datos de otros usuarios
def editar_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    # Parámetros que esperamos de la interfaz
    nombre = data.get('nombre')
    correo = data.get('correo')
    telefono = data.get('telefono')
    rol = data.get('rol') 
    
    # Validación básica de datos
    if not all([nombre, correo, telefono, rol]):
         return jsonify({'error': 'Faltan campos obligatorios para actualizar el usuario.'}), 400

    sql = """
    UPDATE USUARIOS SET 
        nombre = %s, 
        correo = %s, 
        telefono = %s, 
        rol = %s 
    WHERE id_usuario = %s
    """
    values = (nombre, correo, telefono, rol, usuario_id)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado o no se realizaron cambios.'}), 404
        
        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': f'Usuario {usuario_id} ({nombre}) actualizado correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al editar usuario: {err}")
        # Error 1062 es duplicidad de entrada (ej: RUT o correo ya existe)
        if err.errno == 1062: 
            return jsonify({'error': 'El correo o RUT ingresado ya está registrado.'}), 400
        return jsonify({'error': f'Error al actualizar en BD: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN02 (Parte: Bloquear/Desactivar Usuario - DELETE LÓGICO)
# Usamos PUT para actualizar el estado, no DELETE físico.
@app.route('/api/admin/usuario/bloquear/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required # Solo el Admin puede bloquear cuentas
def bloquear_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()

        # 1. REGLA DE NEGOCIO: Prohibir al Admin bloquearse a sí mismo
        if current_user.id == usuario_id:
            return jsonify({'error': 'No puedes bloquear tu propia cuenta de administrador mientras estás logueado.'}), 400

        # 2. Desactivar la cuenta
        # Cambiamos estado_activo a FALSE
        sql = "UPDATE USUARIOS SET estado_activo = FALSE WHERE id_usuario = %s"
        cursor.execute(sql, (usuario_id,))

        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado.'}), 404

        conn.commit()
        if 'db' in g:
            g.db.close() # Cierra la conexión antigua
            g.pop('db', None) # Remueve la conexión del objeto g
        return jsonify({'message': f'Usuario {usuario_id} desactivado correctamente. Ya no podrá iniciar sesión.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al bloquear usuario: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN02 (Parte: Reactivar Cuenta)
@app.route('/api/admin/usuario/reactivar/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required 
def reactivar_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
        # Cambiamos estado_activo a TRUE
        sql = "UPDATE USUARIOS SET estado_activo = TRUE WHERE id_usuario = %s"
        cursor.execute(sql, (usuario_id,))

        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado.'}), 404

        conn.commit()
        if 'db' in g: g.db.close(); g.pop('db', None)
        
        return jsonify({'message': f'Usuario {usuario_id} reactivado correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al reactivar usuario: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN04: Reporte de Uso - 10 Materiales Más Prestados
@app.route('/api/admin/reportes/uso', methods=['GET'])
@login_required
@role_required('Bibliotecario') # El bibliotecario necesita esta información para gestión
def reporte_materiales_uso():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    sql = """
    SELECT 
        M.titulo AS titulo_material,
        M.isbn,
        A.nombre_autor,
        COUNT(P.id_prestamo) AS total_prestamos_historico
    FROM 
        PRESTAMOS P
    JOIN 
        MATERIALES M ON P.MATERIALES_id_material = M.id_material
    JOIN
        AUTOR A ON M.AUTOR_id_autor = A.id_autor
    GROUP BY 
        M.id_material, M.titulo, M.isbn, A.nombre_autor
    ORDER BY 
        total_prestamos_historico DESC
    LIMIT 10
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        reporte = cursor.fetchall()
        
        return jsonify(reporte), 200

    except Exception as e:
        print(f"Error al generar Reporte de Uso: {e}")
        return jsonify({'error': 'Error en la consulta SQL para el reporte de uso.'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-ADMIN05: Reporte de Mora - Usuarios con Préstamos Vencidos y Multas
@app.route('/api/admin/reportes/mora', methods=['GET'])
@login_required
@role_required('Bibliotecario')
def reporte_usuarios_mora():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    sql = """
    SELECT 
        U.nombre AS nombre_usuario,
        U.rut,
        M.titulo AS titulo_material,
        P.fecha_devolucion AS fecha_esperada,
        DATEDIFF(CURDATE(), P.fecha_devolucion) AS dias_mora,
        (DATEDIFF(CURDATE(), P.fecha_devolucion) * 500) AS multa_estimada
    FROM 
        PRESTAMOS P
    JOIN 
        USUARIOS U ON P.USUARIOS_id_usuario = U.id_usuario
    JOIN 
        MATERIALES M ON P.MATERIALES_id_material = M.id_material
    WHERE 
        P.estado_prestamo = 'Activo' 
        AND P.fecha_devolucion < CURDATE()
    ORDER BY 
        dias_mora DESC
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        reporte = cursor.fetchall()
        
        return jsonify(reporte), 200

    except Exception as e:
        print(f"Error al generar Reporte de Mora: {e}")
        return jsonify({'error': 'Error en la consulta SQL para el reporte de mora.'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()



# **********************************************************
# 9. INICIO DE LA APLICACIÓN
# **********************************************************

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    # Asegúrate de que tu entorno virtual esté activo y Flask esté instalado.
    app.run(debug=True)
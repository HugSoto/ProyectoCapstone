import mysql.connector
from flask import redirect, url_for, Flask, render_template, request, jsonify, g
from configuracion import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
app = Flask(__name__)
app.secret_key = 'tonecaps' 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, nombre, rol, password_hash):
        self.id = id
        self.nombre = nombre
        self.rol = rol
        self.password_hash = password_hash
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
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

def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Acceso denegado. Se requiere iniciar sesión.'}), 401
            
            if current_user.rol == 'Admin' or current_user.rol == role_name:
                return f(*args, **kwargs)
            
            return jsonify({'error': f'Acceso denegado. Se requiere el rol: {role_name}.'}), 403
            
        return decorated_function
    return decorator

def admin_required(f):
    return role_required('Admin')(f)

## Conexión a Base de Datos

db_config = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASSWORD,
    'database': MYSQL_DATABASE
}

def get_db_connection():
    """Establece la conexión a la base de datos."""
    try:
        if 'db' not in g:
            g.db = mysql.connector.connect(**db_config)
        return g.db
    except mysql.connector.Error as err:
        print(f"Error de conexión a MySQL. Por favor, verifica el archivo 'configuracion.py' y que MySQL esté activo: {err}")
        return None

@app.teardown_appcontext
def close_db_connection(exception):
    """Cierra la conexión a la base de datos."""
    db = g.pop('db', None)
    if db is not None and db.is_connected():
        db.close()

## Rutas HTML (Vistas)
@app.route('/')
def index():

    if current_user.is_authenticated:
        return redirect(url_for('main')) 
    return render_template('login.html')

@app.route('/catalogacion')
def catalogacion():
    return render_template('catalogacion.html')

@app.route('/circulacion')
def circulacion():
    return render_template('circulacion.html')

@app.route('/opac')
def opac():
    return render_template('opac.html')

@app.route('/admin/usuarios')
@login_required
@role_required('Admin')
def admin_usuarios():
    return render_template('admin_usuarios.html')

@app.route('/admin/reportes')
@login_required
@role_required('Bibliotecario')
def admin_reportes():
    return render_template('admin_reportes.html')

@app.route('/admin/catalogos')
@login_required
@role_required('Bibliotecario')
def admin_catalogos():
    return render_template('admin_tablas_apoyo.html')

@app.route('/dashboard')
@login_required 
def main():
    """Muestra la vista principal (dashboard)."""
    return render_template('main.html')

## Rutas de API 

@app.route('/api/catalogacion/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
def guardar_material():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    sql_material = """
    INSERT INTO MATERIALES (
        titulo, anio_publicacion, isbn, ejemplares_totales, ejemplares_disponibles, 
        tipo, disponible, EDITORIAL_id_editorial, AUTOR_id_autor
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        ejemplares_input = data.get('ejemplares', 1) 
        ejemplares = int(ejemplares_input)
        
        anio = int(data.get('anio'))
        editorial_id = int(data.get('editorial_id'))
        autor_id = int(data.get('autor_id'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Error de formato: Los valores de stock, año e IDs deben ser números enteros.'}), 400
    values_material = (
        data.get('titulo'),
        data.get('anio'),
        data.get('isbn'),
        ejemplares, 
        ejemplares, 
        'Libro', 
        'S', 
        data.get('editorial_id'), 
        data.get('autor_id') 
    )
    categorias_ids = data.get('categorias_ids', [])
    if not isinstance(categorias_ids, list):
        categorias_ids = [categorias_ids] if categorias_ids else []

    try:
        cursor = conn.cursor()
        cursor.execute(sql_material, values_material)
        material_id = cursor.lastrowid
        if categorias_ids:
            sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
            for cat_id in categorias_ids:
                cursor.execute(sql_cat, (material_id, cat_id))
        
        conn.commit()
        if 'db' in g:
            g.db.close()
            g.pop('db', None)

        return jsonify({'message': 'Material catalogado y vinculado a categorías correctamente.', 'id': material_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al guardar material: {err}")
        return jsonify({'error': f'Error al guardar en BD: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()
    pass

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

@app.route('/api/catalogacion/obtener/<int:material_id>', methods=['GET'])
@login_required
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
        GROUP_CONCAT(MC.CATEGORIAS_id_categoria) AS categorias_ids
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
        
        if not ejemplares_totales_input or not ejemplares_disponibles_input:
            return jsonify({'error': 'El stock total y disponible son obligatorios.'}), 400
            
        ejemplares_totales = int(ejemplares_totales_input)
        ejemplares_disponibles = int(ejemplares_disponibles_input)
        
        anio = int(data.get('anio'))
        editorial_id = int(data.get('editorial_id'))
        autor_id = int(data.get('autor_id'))

    except (ValueError, TypeError):
        return jsonify({'error': 'Error de formato: Stock, año e IDs deben ser números enteros válidos.'}), 400 
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
        
        cursor.execute(sql_material, values_material)
        
        cursor.execute("DELETE FROM MATERIALES_CATEGORIAS WHERE MATERIALES_id_material = %s", (material_id,))
        
        if categorias_ids:
            sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
            for cat_id in categorias_ids:
                cursor.execute(sql_cat, (material_id, cat_id))
        
        conn.commit()
        if 'db' in g: g.db.close(); g.pop('db', None)
        
        return jsonify({'message': f'Material {material_id} actualizado y categorías vinculadas correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al actualizar material: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/catalogacion/eliminar/<int:material_id>', methods=['DELETE'])
@login_required
@role_required('Bibliotecario')
def eliminar_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ejemplares_totales, ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", (material_id,))
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404
            
        if material['ejemplares_totales'] != material['ejemplares_disponibles']:
            prestados = material['ejemplares_totales'] - material['ejemplares_disponibles']
            return jsonify({'error': f'Imposible eliminar. Aún hay {prestados} ejemplares prestados o en circulación.'}), 400

        sql = "DELETE FROM MATERIALES WHERE id_material = %s"
        cursor.execute(sql, (material_id,))
        conn.commit()
        
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

@app.route('/api/autor/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
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
            g.db.close()
            g.pop('db', None)
        return jsonify({'message': 'Autor registrado con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/autor/eliminar/<int:autor_id>', methods=['DELETE'])
@login_required
@role_required('Bibliotecario')
def eliminar_autor(autor_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
        sql = "DELETE FROM AUTOR WHERE id_autor = %s"
        cursor.execute(sql, (autor_id,))
        conn.commit()
        if 'db' in g:
            g.db.close()
            g.pop('db', None)
        if cursor.rowcount > 0:
            return jsonify({'message': f'Autor {autor_id} eliminado correctamente.'}), 200
        else:
            return jsonify({'error': 'Autor no encontrado o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar el autor: tiene materiales bibliográficos asociados.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/editorial/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
def guardar_editorial():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    nombre = data.get('nombre_editorial') 
    
    if not nombre:
        return jsonify({'error': 'El nombre de la editorial es obligatorio.'}), 400

    sql = "INSERT INTO EDITORIAL (nombre_editorial) VALUES (%s)"
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (nombre,))
        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': 'Editorial registrada con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

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
            g.db.close() 
            g.pop('db', None) 
        if cursor.rowcount > 0:
            return jsonify({'message': f'Editorial {editorial_id} eliminada correctamente.'}), 200
        else:
            return jsonify({'error': 'Editorial no encontrada o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar la editorial: tiene materiales bibliográficos asociados.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/categoria/guardar', methods=['POST'])
@login_required
@role_required('Bibliotecario')
def guardar_categoria():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    nombre = data.get('nombre_categoria') 
    descripcion = data.get('descripcion', 'Sin descripción proporcionada.') 
    
    if not nombre:
        return jsonify({'error': 'El nombre de la categoría es obligatorio.'}), 400

    sql = "INSERT INTO CATEGORIAS (nombre_categoria, descripcion) VALUES (%s, %s)"
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (nombre, descripcion))
        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': 'Categoría registrada con éxito.', 'id': cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

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
            g.db.close() 
            g.pop('db', None) 
        if cursor.rowcount > 0:
            return jsonify({'message': f'Categoría {categoria_id} eliminada correctamente.'}), 200
        else:
            return jsonify({'error': 'Categoría no encontrada o no se pudo eliminar.'}), 404

    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1451: 
             return jsonify({'error': 'No se puede eliminar la categoría: está asignada a uno o más materiales.'}), 400
        return jsonify({'error': f'Error SQL al eliminar: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/usuario/registrar', methods=['POST'])
@login_required
@admin_required 
def registrar_usuario():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    required_fields = ['nombre', 'rut', 'correo', 'telefono', 'rol', 'password'] 
    if not all(data.get(field) for field in required_fields):
        return jsonify({'error': 'Faltan campos obligatorios para el registro del usuario.'}), 400
    
    from werkzeug.security import generate_password_hash
    password_claro = data.get('password')
    hashed_password = generate_password_hash(password_claro, method='pbkdf2:sha256') 

    sql = """
    INSERT INTO USUARIOS (nombre, rut, correo, telefono, rol, password_hash)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (
        data.get('nombre'), data.get('rut'), data.get('correo'),
        data.get('telefono'), data.get('rol'), 
        hashed_password
    )
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()
        if 'db' in g: g.db.close(); g.pop('db', None) 
        return jsonify({'message': 'Usuario registrado con éxito.'}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062: 
            return jsonify({'error': 'Error: El RUT o Correo ya está registrado en el sistema.'}), 400
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/listas_catalogacion', methods=['GET'])
def cargar_listas_catalogacion():
    if 'listas_cache' in g:
        return jsonify(g.listas_cache), 200

    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    data = {}
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id_autor, nombre_autor FROM AUTOR")
        data['autores'] = cursor.fetchall() 

        cursor.execute("SELECT id_editorial, nombre_editorial FROM EDITORIAL")
        data['editoriales'] = cursor.fetchall() 
        
        cursor.execute("SELECT id_categoria, nombre_categoria FROM CATEGORIAS")
        data['categorias'] = cursor.fetchall() 
        
        g.listas_cache = data 
        
        return jsonify(data), 200

    except Exception as e:
        print(f"Error al cargar listas de apoyo: {e}")
        return jsonify({'error': 'Error en la consulta SQL'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

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

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_usuario FROM USUARIOS WHERE rut = %s", (rut_usuario,))
        usuario = cursor.fetchone()
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado o RUT inválido.'}), 404
        id_usuario = usuario['id_usuario']
        
        cursor.execute(
            "SELECT ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", 
            (material_id,)
        )
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404

        if material['ejemplares_disponibles'] < 1:
            return jsonify({'error': 'No hay ejemplares disponibles para préstamo.'}), 400
            
        sql_prestamo = """
        INSERT INTO PRESTAMOS (fecha_prestamo, fecha_devolucion, estado_prestamo, USUARIOS_id_usuario, MATERIALES_id_material)
        VALUES (NOW(), DATE_ADD(CURDATE(), INTERVAL 14 DAY), 'Activo', %s, %s)
        """
        cursor.execute(sql_prestamo, (id_usuario, material_id))
        
        sql_stock_update = """
        UPDATE MATERIALES SET ejemplares_disponibles = ejemplares_disponibles - 1
        WHERE id_material = %s
        """
        cursor.execute(sql_stock_update, (material_id,))

        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': 'Préstamo registrado con éxito. Stock actualizado.', 'id_prestamo': cursor.lastrowid}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al registrar préstamo: {err}")
        return jsonify({'error': f'Error transaccional al registrar préstamo: {err.msg}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

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
        
        sql_multa = """
        SELECT GREATEST(0, DATEDIFF(CURDATE(), %s)) AS dias_retraso
        """
        cursor.execute(sql_multa, (prestamo['fecha_devolucion'],))
        dias_retraso = cursor.fetchone()['dias_retraso']
        
        monto_multa = dias_retraso * 500 
        
        sql_prestamo_update = """
        UPDATE PRESTAMOS SET 
            estado_prestamo = 'Devuelto', 
            fecha_devolucion_real = CURDATE(),
            monto_multa = %s
        WHERE id_prestamo = %s
        """
        cursor.execute(sql_prestamo_update, (monto_multa, id_prestamo))
        
        sql_stock_update = """
        UPDATE MATERIALES SET ejemplares_disponibles = ejemplares_disponibles + 1
        WHERE id_material = %s
        """
        cursor.execute(sql_stock_update, (material_id,))

        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
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


@app.route('/api/circulacion/prestamos_activos', methods=['GET'])
def listar_prestamos_activos():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
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
        
        return jsonify(prestamos), 200

    except Exception as e:
        print(f"Error al listar préstamos activos: {e}")
        return jsonify({'error': 'Error en la consulta SQL de listado de préstamos'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/opac/buscar', methods=['GET'])
def buscar_materiales():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
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
    
    if query_text:
        base_sql += " AND (M.titulo LIKE %s OR A.nombre_autor LIKE %s)"
        params.extend([f'%{query_text}%', f'%{query_text}%'])
    
    if categoria_id:
        base_sql += " AND M.id_material IN (SELECT MATERIALES_id_material FROM MATERIALES_CATEGORIAS WHERE CATEGORIAS_id_categoria = %s)"
        params.append(categoria_id)

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

@app.route('/api/opac/reservar', methods=['POST'])
@login_required 
def registrar_reserva():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    material_id = data.get('material_id')
    id_usuario = current_user.id 

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT titulo, ejemplares_disponibles FROM MATERIALES WHERE id_material = %s", 
            (material_id,)
        )
        material = cursor.fetchone()
        
        if not material:
            return jsonify({'error': 'Material no encontrado.'}), 404

        if material['ejemplares_disponibles'] > 0:
            return jsonify({'error': 'El material está disponible actualmente. No necesita reserva.'}), 400

        cursor.execute(
            "SELECT id_reserva FROM RESERVAS WHERE USUARIOS_id_usuario = %s AND MATERIALES_id_material = %s AND estado_reserva = 'Pendiente'", 
            (id_usuario, material_id)
        )
        if cursor.fetchone():
            return jsonify({'error': 'Ya tienes una reserva activa para este material.'}), 400
            
        sql_reserva = """
        INSERT INTO RESERVAS (fecha_reserva, estado_reserva, USUARIOS_id_usuario, MATERIALES_id_material)
        VALUES (CURDATE(), 'Pendiente', %s, %s)
        """
        cursor.execute(sql_reserva, (id_usuario, material_id))

        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': f'Reserva registrada con éxito para el material: {material["titulo"]}. Recibirás una notificación cuando esté disponible.'}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al registrar reserva: {err}")
        return jsonify({'error': f'Error transaccional al registrar reserva: {err.msg}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

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
                
                if user.check_password(password): 
                    login_user(user)
                    return jsonify({'message': 'Inicio de sesión exitoso.', 'user': user.nombre, 'rol': user.rol}), 200
                else:
                    return jsonify({'error': 'Credenciales inválidas.'}), 401
            
            return jsonify({'error': 'Usuario no encontrado.'}), 404
            
        except Exception as e:
            print(f"Error en login: {e}")
            return jsonify({'error': 'Error en el proceso de autenticación.'}), 500
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

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

@app.route('/api/admin/usuarios', methods=['GET'])
@login_required
@admin_required 
def listar_usuarios():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    sql = """
    SELECT 
        id_usuario, nombre, rut, correo, telefono, rol, estado_activo 
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

@app.route('/api/admin/usuario/editar/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required 
def editar_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    nombre = data.get('nombre')
    correo = data.get('correo')
    telefono = data.get('telefono')
    rol = data.get('rol') 
    
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
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': f'Usuario {usuario_id} ({nombre}) actualizado correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al editar usuario: {err}")
        if err.errno == 1062: 
            return jsonify({'error': 'El correo o RUT ingresado ya está registrado.'}), 400
        return jsonify({'error': f'Error al actualizar en BD: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/admin/usuario/bloquear/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required 
def bloquear_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()

        if current_user.id == usuario_id:
            return jsonify({'error': 'No puedes bloquear tu propia cuenta de administrador mientras estás logueado.'}), 400

        sql = "UPDATE USUARIOS SET estado_activo = FALSE WHERE id_usuario = %s"
        cursor.execute(sql, (usuario_id,))

        if cursor.rowcount == 0:
            return jsonify({'error': 'Usuario no encontrado.'}), 404

        conn.commit()
        if 'db' in g:
            g.db.close() 
            g.pop('db', None) 
        return jsonify({'message': f'Usuario {usuario_id} desactivado correctamente. Ya no podrá iniciar sesión.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al bloquear usuario: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/admin/usuario/reactivar/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_required 
def reactivar_usuario(usuario_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor()
        
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

@app.route('/api/admin/reportes/uso', methods=['GET'])
@login_required
@role_required('Bibliotecario') 
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

@app.route('/api/admin/metrics', methods=['GET'])
@login_required
def obtener_metricas_dashboard():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(id_material) AS total_materiales FROM MATERIALES")
        total_materiales = cursor.fetchone()['total_materiales']
        
        cursor.execute("SELECT COUNT(id_prestamo) AS prestamos_activos FROM PRESTAMOS WHERE estado_prestamo = 'Activo'")
        prestamos_activos = cursor.fetchone()['prestamos_activos']
        
        sql_ultimos = """
        SELECT titulo, id_material AS fecha_ingreso
        FROM MATERIALES
        ORDER BY id_material DESC
        LIMIT 5
        """
        cursor.execute(sql_ultimos)
        ultimos_materiales = cursor.fetchall()
    
        user_name = current_user.nombre if current_user.is_authenticated and hasattr(current_user, 'nombre') else 'Usuario Desconocido'
        user_role = current_user.rol if current_user.is_authenticated and hasattr(current_user, 'rol') else 'N/A'
        
        return jsonify({
            'total_materiales': total_materiales,
            'prestamos_activos': prestamos_activos,
            'ultimos_materiales': ultimos_materiales,
            'user_role': user_role,
            'user_name': user_name
        }), 200
    
    except Exception as e:
        print(f"Error al obtener métricas del dashboard: {e}")
        return jsonify({'error': f'Error en la consulta SQL para métricas: {e}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

@app.route('/api/registro/estudiante', methods=['POST'])
def registrar_estudiante():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    required_fields = ['nombre', 'rut', 'correo', 'password', 'telefono']
    if not all(data.get(field) for field in required_fields):
        return jsonify({'error': 'Faltan campos obligatorios.'}), 400

    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256') 

    sql = """
    INSERT INTO USUARIOS (nombre, rut, correo, telefono, rol, password_hash, estado_activo)
    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
    """
    values = (
        data['nombre'], data['rut'], data['correo'], data['telefono'], 
        'Estudiante',
        hashed_password
    )
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit()

        return jsonify({'message': '¡Registro exitoso! Ya puedes iniciar sesión.'}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062: 
            return jsonify({'error': 'Error: El RUT o Correo ya está registrado.'}), 400
        print(f"Error SQL al registrar estudiante: {err}")
        return jsonify({'error': f'Error SQL: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

## Inicio de la Aplicación

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    app.run(debug=True)
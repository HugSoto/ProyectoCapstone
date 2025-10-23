import mysql.connector
from flask import Flask, render_template, request, jsonify, g
# 🚨 IMPORTACIÓN DE CONFIGURACIÓN EXTERNA
from configuracion import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE 

app = Flask(__name__)

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

# **********************************************************
# 3. RUTAS DE API (Módulo de Catalogación - CRUD COMPLETO)
# **********************************************************

# HU-CAT01: Carga de listas de apoyo (Autores, Editoriales, Categorías)
@app.route('/api/listas_catalogacion', methods=['GET'])
def cargar_listas_catalogacion():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500
    
    data = {}
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Consulta para Autores
        cursor.execute("SELECT id_autor, nombre_autor FROM AUTOR")
        data['autores'] = cursor.fetchall()

        # Consulta para Editoriales
        cursor.execute("SELECT id_editorial, nombre_editorial FROM EDITORIAL")
        data['editoriales'] = cursor.fetchall()
        
        # Consulta para Categorías
        cursor.execute("SELECT id_categoria, nombre_categoria FROM CATEGORIAS")
        data['categorias'] = cursor.fetchall()
        
        return jsonify(data), 200

    except Exception as e:
        print(f"Error al cargar listas de apoyo: {e}")
        return jsonify({'error': 'Error en la consulta SQL'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CAT02: Guardar un nuevo material (CREATE)
@app.route('/api/catalogacion/guardar', methods=['POST'])
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
    
    ejemplares = int(data.get('ejemplares', 1))
    
    values_material = (
        data.get('titulo'),
        data.get('anio'),
        data.get('isbn'),
        ejemplares,           # ejemplares_totales
        ejemplares,           # ejemplares_disponibles
        'Libro',              # tipo (Valor por defecto si no se especifica)
        'S',                  # disponible (Valor por defecto)
        data.get('editorial_id'), # FK EDITORIAL
        data.get('autor_id')      # FK AUTOR
    )
    
    categoria_id = data.get('categoria_id')

    try:
        cursor = conn.cursor()
        
        # 1. Insertar el Material
        cursor.execute(sql_material, values_material)
        material_id = cursor.lastrowid # Obtener el ID generado
        
        # 2. Insertar la Categoría en la tabla N:M
        sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
        cursor.execute(sql_cat, (material_id, categoria_id))
        
        conn.commit()
        return jsonify({'message': 'Material catalogado y vinculado correctamente.', 'id': material_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error SQL al guardar material: {err}")
        return jsonify({'error': f'Error al guardar en BD: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()


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

# HU-CAT04 (Parte 1): Obtener material por ID (para edición)
@app.route('/api/catalogacion/obtener/<int:material_id>', methods=['GET'])
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
        MC.CATEGORIAS_id_categoria AS categoria_id 
    FROM MATERIALES M
    LEFT JOIN MATERIALES_CATEGORIAS MC ON M.id_material = MC.MATERIALES_id_material
    WHERE M.id_material = %s
    """
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (material_id,))
        material = cursor.fetchone()
        
        if material:
            return jsonify(material), 200
        else:
            return jsonify({'error': 'Material no encontrado'}), 404
            
    except Exception as e:
        print(f"Error al obtener material: {e}")
        return jsonify({'error': 'Error en la consulta'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()


# HU-CAT04 (Parte 2): Guardar los cambios de un material (UPDATE)
@app.route('/api/catalogacion/editar/<int:material_id>', methods=['PUT'])
def editar_material(material_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    ejemplares_totales = int(data.get('ejemplares_totales'))
    ejemplares_disponibles = int(data.get('ejemplares_disponibles'))

    # Validación de Regla de Negocio
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
        data.get('titulo'), 
        data.get('anio'), 
        data.get('isbn'), 
        ejemplares_totales,
        ejemplares_disponibles,
        data.get('editorial_id'), 
        data.get('autor_id'),
        material_id
    )
    
    categoria_id = data.get('categoria_id')

    try:
        cursor = conn.cursor()
        
        # 1. Actualizar el Material
        cursor.execute(sql_material, values_material)
        
        # 2. Actualizar la Categoría N:M (borrar y re-insertar la principal)
        cursor.execute("DELETE FROM MATERIALES_CATEGORIAS WHERE MATERIALES_id_material = %s", (material_id,))
        if categoria_id:
            sql_cat = "INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES (%s, %s)"
            cursor.execute(sql_cat, (material_id, categoria_id))
        
        conn.commit()
        
        return jsonify({'message': f'Material {material_id} actualizado correctamente.'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': f'Error al actualizar material: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()

# HU-CAT05: Eliminar un material (DELETE)
@app.route('/api/catalogacion/eliminar/<int:material_id>', methods=['DELETE'])
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
# 4. INICIO DE LA APLICACIÓN
# **********************************************************

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    # Asegúrate de que tu entorno virtual esté activo y Flask esté instalado.
    app.run(debug=True)

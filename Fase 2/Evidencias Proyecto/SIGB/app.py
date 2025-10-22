from flask import Flask, render_template, request, jsonify
import mysql.connector
from configuracion import *

app = Flask(__name__)

# Función para establecer la conexión a la BD
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None

# **********************************************
# RUTAS DE VISUALIZACIÓN (FRONTEND)
# **********************************************

# Ruta de la página principal (para probar que Flask funciona)
@app.route('/')
def index():
    return "¡Servidor de Gestión de Biblioteca Funcionando! Visita /catalogacion para el módulo."

# Ruta para el Módulo de Catalogación (devuelve la vista HTML)
# NOTA: Debes crear una carpeta 'templates' y poner allí 'catalogacion.html'
@app.route('/catalogacion')
def catalogacion_view():
    return render_template('catalogacion.html')


# **********************************************
# RUTAS DE API (BACKEND / DATOS) - Fase III.2
# **********************************************

# API para obtener las listas de apoyo (Autores, Editoriales, Categorías)
@app.route('/api/listas_catalogacion', methods=['GET'])
def get_listas_catalogacion():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500

    try:
        cursor = conn.cursor(dictionary=True) 
        
        # Consultas SQL para Autores, Editoriales y Categorías
        cursor.execute("SELECT id_autor, nombre_autor FROM AUTORES ORDER BY nombre_autor")
        autores = cursor.fetchall()
        
        cursor.execute("SELECT id_editorial, nombre_editorial FROM EDITORIALES ORDER BY nombre_editorial")
        editoriales = cursor.fetchall()
        
        cursor.execute("SELECT id_categoria, nombre_categoria FROM CATEGORIAS ORDER BY nombre_categoria")
        categorias = cursor.fetchall()

        return jsonify({
            'autores': autores,
            'editoriales': editoriales,
            'categorias': categorias
        })

    except Exception as e:
        print(f"Error en la consulta SQL: {e}")
        return jsonify({'error': f'Error al obtener listas: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# **********************************************
# FUNCIÓN MAIN
# **********************************************

if __name__ == '__main__':
    # Cuando debug=True, Flask reinicia automáticamente al guardar cambios
    app.run(debug=True)

@app.route('/api/catalogacion/guardar', methods=['POST'])
def guardar_material():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión a la base de datos'}), 500

    data = request.get_json()
    
    # ⚠️ Nota: Flask convierte los datos JSON del frontend en un diccionario Python
    # Extraemos los datos del material:
    titulo = data.get('titulo')
    isbn = data.get('isbn')
    anio = data.get('anio')
    ejemplares = data.get('ejemplares')
    
    # Claves Foráneas (IDs seleccionados del HTML)
    autor_id = data.get('autor_id')
    editorial_id = data.get('editorial_id')
    categoria_id = data.get('categoria_id')

    sql = """
    INSERT INTO MATERIALES 
    (titulo, anio_publicacion, isbn, ejemplares_totales, ejemplares_disponibles, fk_id_autor, fk_id_editorial, fk_id_categoria)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Usamos ejemplares_totales y ejemplares_disponibles con el mismo valor inicial
    values = (titulo, anio, isbn, ejemplares, ejemplares, autor_id, editorial_id, categoria_id)
    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        conn.commit() # Confirma la transacción en la BD
        
        return jsonify({'message': 'Material catalogado correctamente', 'id': cursor.lastrowid}), 201

    except mysql.connector.Error as err:
        conn.rollback() # Revierte la operación si hay un error (ej: ISBN duplicado)
        return jsonify({'error': f'Error al insertar material: {err.msg}'}), 400
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
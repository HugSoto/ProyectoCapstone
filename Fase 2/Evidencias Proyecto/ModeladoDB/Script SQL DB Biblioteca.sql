DROP DATABASE IF EXISTS db_biblioteca;
CREATE DATABASE db_biblioteca;

USE db_biblioteca;

CREATE TABLE AUTOR (
    id_autor INT PRIMARY KEY AUTO_INCREMENT,
    nombre_autor VARCHAR(150) NOT NULL
);

CREATE TABLE EDITORIAL (
    id_editorial INT PRIMARY KEY AUTO_INCREMENT,
    nombre_editorial VARCHAR(150) NOT NULL
);

CREATE TABLE CATEGORIAS (
    id_categoria INT PRIMARY KEY AUTO_INCREMENT,
    nombre_categoria VARCHAR(50) NOT NULL,
    descripcion TEXT NOT NULL
);

CREATE TABLE USUARIOS (
    id_usuario INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    rut VARCHAR(15) UNIQUE NOT NULL,
    correo VARCHAR(60) UNIQUE NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    rol VARCHAR(25) NOT NULL
);

CREATE TABLE MATERIALES (
    id_material INT PRIMARY KEY AUTO_INCREMENT,
    titulo VARCHAR(100) NOT NULL,
    isbn VARCHAR(20) UNIQUE NOT NULL, 
    anio_publicacion INT NOT NULL,
    ejemplares_totales INT DEFAULT 1 NOT NULL,
    ejemplares_disponibles INT DEFAULT 1 NOT NULL, 
    tipo VARCHAR(50) NOT NULL,
    disponible CHAR(1) NOT NULL, 
    
    EDITORIAL_id_editorial INT NOT NULL,
    AUTOR_id_autor INT NOT NULL,
    
    CONSTRAINT fk_materiales_editorial FOREIGN KEY (EDITORIAL_id_editorial) 
        REFERENCES EDITORIAL(id_editorial) ON DELETE RESTRICT,
    CONSTRAINT fk_materiales_autor FOREIGN KEY (AUTOR_id_autor) 
        REFERENCES AUTOR(id_autor) ON DELETE RESTRICT
);

CREATE TABLE MATERIALES_CATEGORIAS ( 
    MATERIALES_id_material INT NOT NULL,
    CATEGORIAS_id_categoria INT NOT NULL,
    
    PRIMARY KEY (MATERIALES_id_material, CATEGORIAS_id_categoria),
    
    CONSTRAINT fk_mc_materiales FOREIGN KEY (MATERIALES_id_material) 
        REFERENCES MATERIALES(id_material) ON DELETE CASCADE,
    CONSTRAINT fk_mc_categorias FOREIGN KEY (CATEGORIAS_id_categoria) 
        REFERENCES CATEGORIAS(id_categoria) ON DELETE RESTRICT
);

CREATE TABLE PRESTAMOS (
    id_prestamo INT PRIMARY KEY AUTO_INCREMENT,
    fecha_prestamo DATE NOT NULL, -- Modificada a DATETIME en el paso 5
    fecha_devolucion DATE NOT NULL,
    estado_prestamo VARCHAR(80) NOT NULL,
    
    USUARIOS_id_usuario INT NOT NULL,
    MATERIALES_id_material INT NOT NULL,
    
    CONSTRAINT fk_prestamos_usuarios FOREIGN KEY (USUARIOS_id_usuario) 
        REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT,
    CONSTRAINT fk_prestamos_materiales FOREIGN KEY (MATERIALES_id_material) 
        REFERENCES MATERIALES(id_material) ON DELETE RESTRICT
);

CREATE TABLE RESERVAS (
    id_reserva INT PRIMARY KEY AUTO_INCREMENT,
    fecha_reserva DATE NOT NULL,
    estado_reserva VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
    
    USUARIOS_id_usuario INT NOT NULL,
    MATERIALES_id_material INT NOT NULL,
    
    UNIQUE KEY uk_reserva_activa (USUARIOS_id_usuario, MATERIALES_id_material, estado_reserva),
    
    CONSTRAINT fk_reservas_usuarios FOREIGN KEY (USUARIOS_id_usuario) 
        REFERENCES USUARIOS(id_usuario) ON DELETE RESTRICT,
    CONSTRAINT fk_reservas_materiales FOREIGN KEY (MATERIALES_id_material) 
        REFERENCES MATERIALES(id_material) ON DELETE RESTRICT
);

CREATE TABLE HISTORIAL_MATERIAL (
    id_historial INT PRIMARY KEY AUTO_INCREMENT,
    tipo_evento VARCHAR(200) NOT NULL,
    fecha_evento DATE NOT NULL,
    
    MATERIALES_id_material INT NOT NULL,
    
    CONSTRAINT fk_historial_materiales FOREIGN KEY (MATERIALES_id_material) 
        REFERENCES MATERIALES(id_material) ON DELETE CASCADE
);

CREATE TABLE ADMINISTRACION (
    id_rol INT PRIMARY KEY AUTO_INCREMENT,
    nombre_rol VARCHAR(30) NOT NULL,
    permisos TEXT NOT NULL, 
    USUARIOS_id_usuario INT NOT NULL,
    
    CONSTRAINT fk_admin_usuarios FOREIGN KEY (USUARIOS_id_usuario) 
        REFERENCES USUARIOS(id_usuario) ON DELETE CASCADE
);

ALTER TABLE USUARIOS ADD COLUMN password_hash VARCHAR(128) NOT NULL;
ALTER TABLE USUARIOS ADD COLUMN estado_activo BOOLEAN DEFAULT TRUE NOT NULL;

ALTER TABLE PRESTAMOS ADD COLUMN fecha_devolucion_real DATE NULL;
ALTER TABLE PRESTAMOS ADD COLUMN monto_multa DECIMAL(10, 2) DEFAULT 0;

ALTER TABLE PRESTAMOS MODIFY COLUMN fecha_prestamo DATETIME NOT NULL;

SET @PasswordHash = 'pbkdf2:sha256:1000000$GpBsCX36BAJbYaHW$cf2ce2bafb48407892910dee44a859dde43f4c434113ee22dc2c13e67101e989';

INSERT INTO AUTOR (nombre_autor) VALUES 
('Gabriel García Márquez'), ('Stephen King'), ('Isabel Allende'), 
('Mario Vargas Llosa'), ('Yuval Noah Harari');

INSERT INTO EDITORIAL (nombre_editorial) VALUES 
('Planeta'), ('Anagrama'), ('Fondo de Cultura Económica'), 
('Penguin Random House'), ('HarperCollins');

INSERT INTO CATEGORIAS (nombre_categoria, descripcion) VALUES 
('Ficción', 'Obras de imaginación y creatividad, incluyendo novelas y cuentos.'),
('Informática', 'Materiales sobre programación, redes y bases de datos.'),
('Historia', 'Libros sobre eventos pasados, civilizaciones y biografías históricas.'),
('Ciencia', 'Textos de física, química, biología y matemáticas.'),
('Ingeniería', 'Material técnico y aplicado a distintas ramas de la ingeniería.');

INSERT INTO USUARIOS (nombre, rut, correo, telefono, rol, password_hash, estado_activo) VALUES
('Hugo Soto Salgado', '20594886-4', 'admin@biblioteca.cl', '987654321', 'Admin', @PasswordHash, TRUE),
('Juan Perez', '17123456-7', 'juan.perez@biblioteca.cl', '912345678', 'Bibliotecario', @PasswordHash, TRUE),
('Maria Lopez', '22555666-K', 'maria.lopez@estudiante.cl', '955554444', 'Estudiante', @PasswordHash, TRUE);

INSERT INTO MATERIALES 
    (titulo, anio_publicacion, isbn, ejemplares_totales, ejemplares_disponibles, tipo, disponible, EDITORIAL_id_editorial, AUTOR_id_autor) 
VALUES
('Cien Años de Soledad', 1967, '978-9584218679', 10, 10, 'Novela', 'S', 4, 1),
('Misery', 1987, '978-84-97592211', 5, 5, 'Terror', 'S', 5, 2),
('La Casa de los Espíritus', 1982, '978-84-97592228', 8, 8, 'Novela', 'S', 1, 3);

INSERT INTO MATERIALES_CATEGORIAS (MATERIALES_id_material, CATEGORIAS_id_categoria) VALUES
(1, 1), (1, 3), (2, 1), (3, 1), (3, 3);

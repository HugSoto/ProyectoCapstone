from werkzeug.security import generate_password_hash

# La contraseña base que usaremos para todos los usuarios de prueba
test_password = 'password'

# 🚨 CÓDIGO CORREGIDO: Usando 'pbkdf2:sha256' para asegurar compatibilidad.
password_hash = generate_password_hash(test_password, method='pbkdf2:sha256')

# Imprimir el hash generado. ¡Cópialo!
print(password_hash)
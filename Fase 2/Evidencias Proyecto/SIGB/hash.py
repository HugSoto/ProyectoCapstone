from werkzeug.security import generate_password_hash

test_password = 'password'
password_hash = generate_password_hash(test_password, method='pbkdf2:sha256')
print(password_hash)
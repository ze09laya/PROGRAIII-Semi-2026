import mysql.connector

def obtener_conexion():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_academica"
    )

def crud_usuarios_USSS003725(accion, id_usuario=None, usuario=None, clave=None, nombre=None, direccion=None, telefono=None):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    try:
        if accion == 'crear':
            sql = "INSERT INTO usuarios_USSS003725 (usuario, clave, nombre, dirección, teléfono) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (usuario, clave, nombre, direccion, telefono))
            
        elif accion == 'actualizar':
            if clave:
                sql = "UPDATE usuarios_USSS003725 SET usuario = %s, clave = %s, nombre = %s, dirección = %s, teléfono = %s WHERE idUsuario = %s"
                cursor.execute(sql, (usuario, clave, nombre, direccion, telefono, id_usuario))
            else:
                sql = "UPDATE usuarios_USSS003725 SET usuario = %s, nombre = %s, dirección = %s, teléfono = %s WHERE idUsuario = %s"
                cursor.execute(sql, (usuario, nombre, direccion, telefono, id_usuario))
                
        elif accion == 'eliminar':
            sql = "DELETE FROM usuarios_USSS003725 WHERE idUsuario = %s"
            cursor.execute(sql, (id_usuario,))
            
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        print(f"Error en el CRUD: {e}")
    finally:
        cursor.close()
        conexion.close()

def obtener_usuarios_USSS003725(busqueda=""):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    if busqueda:
        sql = "SELECT * FROM usuarios_USSS003725 WHERE nombre LIKE %s OR usuario LIKE %s"
        cursor.execute(sql, (f"%{busqueda}%", f"%{busqueda}%"))
    else:
        sql = "SELECT * FROM usuarios_USSS003725"
        cursor.execute(sql)
    resultados = cursor.fetchall()
    cursor.close()
    conexion.close()
    return resultados

def validar_login_USSS003725(user_input, clave_input):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios_USSS003725 WHERE usuario = %s AND clave = %s", (user_input, clave_input))
    usuario = cursor.fetchone()
    cursor.close()
    conexion.close()
    return usuario
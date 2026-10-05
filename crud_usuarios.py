from conexion import Conexion


class crud_usuarios:

    def login(self, usuario, contrasena):

        conexion = Conexion().conectar()

        cursor = conexion.cursor(dictionary=True)

        sql = """
        SELECT
            usuarios.id_usuario,
            usuarios.nombre,
            usuarios.usuario,
            usuarios.id_rol,
            roles.nombre AS rol
        FROM usuarios
        INNER JOIN roles
            ON usuarios.id_rol = roles.id_rol
        WHERE usuarios.usuario = %s
        AND usuarios.contrasena = %s
        AND usuarios.activo = TRUE
        """

        valores = (usuario, contrasena)

        cursor.execute(sql, valores)

        resultado = cursor.fetchone()

        cursor.close()
        conexion.close()

        return resultado
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

        cursor.execute(sql, (usuario, contrasena))

        resultado = cursor.fetchone()

        cursor.close()
        conexion.close()

        return resultado


    def registrar(self, nombre, usuario, contrasena):

        conexion = Conexion().conectar()

        cursor = conexion.cursor()

    

        sql_buscar = """
        SELECT id_usuario
        FROM usuarios
        WHERE usuario = %s
        """

        cursor.execute(sql_buscar, (usuario,))

        existe = cursor.fetchone()

        if existe:

            cursor.close()
            conexion.close()

            return False, "El usuario ya existe."


     

        sql = """
        INSERT INTO usuarios
        (
            id_rol,
            nombre,
            usuario,
            contrasena,
            activo
        )
        VALUES
        (
            2,
            %s,
            %s,
            %s,
            TRUE
        )
        """

        cursor.execute(
            sql,
            (nombre, usuario, contrasena)
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        return True, "Usuario registrado correctamente."
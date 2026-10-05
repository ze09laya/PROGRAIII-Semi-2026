import mysql.connector


class Conexion:

    def conectar(self):

        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="akari_store"
        )

        return conexion
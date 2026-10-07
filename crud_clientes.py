from mysql.connector.errors import Error
import conexion

db = conexion.Conexion()

class crud_clientes:
    def consultar(self, buscar):
        # Parametrizado para evitar Inyección SQL
        sql = "SELECT * FROM clientes WHERE nombre LIKE %s"
        valores = (f"%{buscar}%",)
        return db.consultar(sql, valores)

    def administrar(self, datos):
        try:
            accion = datos.get('accion')
            
            if accion == 'nuevo':
                sql = """
                    INSERT INTO clientes (codigo, nombre, direccion, telefono, email, tipo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                valores = (
                    datos['codigo'], 
                    datos['nombre'], 
                    datos['direccion'], 
                    datos['telefono'], 
                    datos['email'], 
                    datos['tipo']
                )
                
            elif accion == 'modificar':
                sql = """
                    UPDATE clientes 
                    SET codigo=%s, nombre=%s, direccion=%s, telefono=%s, email=%s, tipo=%s
                    WHERE idCliente=%s
                """
                valores = (
                    datos['codigo'], 
                    datos['nombre'], 
                    datos['direccion'], 
                    datos['telefono'], 
                    datos['email'], 
                    datos['tipo'], 
                    datos['idCliente']
                )
                
            elif accion == 'eliminar':
                sql = "DELETE FROM clientes WHERE idCliente=%s"
                valores = (datos['idCliente'],)
                
            else:
                return "Acción no válida"

            return db.ejecutar(sql, valores)

        except Error as e:
            return f"Error al administrar la base de datos: {e}"
        except KeyError as e:
            return f"Falta el campo obligatorio en los datos: {e}"
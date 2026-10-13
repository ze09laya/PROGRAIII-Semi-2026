from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import mysql.connector
import json
import os
import uuid


# ============================================================
# CONFIGURACIÓN
# ============================================================

PORT = 3000

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "akari_store"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CARPETA_IMAGENES = os.path.join(
    BASE_DIR,
    "img",
    "productos"
)

os.makedirs(CARPETA_IMAGENES, exist_ok=True)


# ============================================================
# CONEXIÓN A MYSQL
# ============================================================

def conectar_bd():
    return mysql.connector.connect(**DB_CONFIG)


# ============================================================
# RESPUESTAS JSON
# ============================================================

def responder_json(handler, datos, codigo=200):
    respuesta = json.dumps(
        datos,
        ensure_ascii=False,
        default=str
    ).encode("utf-8")

    handler.send_response(codigo)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )
    handler.send_header("Content-Length", str(len(respuesta)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(respuesta)


# ============================================================
# LEER JSON
# ============================================================

def leer_json(handler):
    longitud = int(handler.headers.get("Content-Length", 0))

    if longitud <= 0:
        return {}

    cuerpo = handler.rfile.read(longitud)
    return json.loads(cuerpo.decode("utf-8"))


# ============================================================
# LEER FORMULARIOS MULTIPART
# ============================================================

def leer_multipart(handler):
    content_type = handler.headers.get("Content-Type", "")

    if "multipart/form-data" not in content_type:
        return None

    partes_boundary = content_type.split("boundary=", 1)

    if len(partes_boundary) != 2:
        return None

    boundary = partes_boundary[1].strip().strip('"').encode("utf-8")
    longitud = int(handler.headers.get("Content-Length", 0))

    if longitud <= 0:
        return None

    cuerpo = handler.rfile.read(longitud)
    datos = {}

    for parte in cuerpo.split(b"--" + boundary):
        if not parte or parte.strip(b"\r\n-") == b"":
            continue

        parte = parte.strip(b"\r\n")

        if b"\r\n\r\n" not in parte:
            continue

        encabezados, contenido = parte.split(b"\r\n\r\n", 1)
        contenido = contenido.rstrip(b"\r\n")

        encabezados_texto = encabezados.decode(
            "utf-8",
            errors="ignore"
        )

        nombre = None
        nombre_archivo = None

        for linea in encabezados_texto.split("\r\n"):
            if "Content-Disposition:" in linea:
                if 'name="' in linea:
                    nombre = linea.split('name="', 1)[1].split('"', 1)[0]

                if 'filename="' in linea:
                    nombre_archivo = linea.split(
                        'filename="', 1
                    )[1].split('"', 1)[0]

        if not nombre:
            continue

        if nombre_archivo is not None:
            datos[nombre] = {
                "filename": nombre_archivo,
                "data": contenido
            }
        else:
            datos[nombre] = contenido.decode(
                "utf-8",
                errors="replace"
            )

    return datos


# ============================================================
# GUARDAR IMAGEN
# ============================================================

def guardar_imagen(imagen):
    if not imagen or not imagen.get("filename"):
        return None

    nombre_original = os.path.basename(imagen["filename"])
    extension = os.path.splitext(nombre_original)[1].lower()

    extensiones_permitidas = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    )

    if extension not in extensiones_permitidas:
        raise ValueError(
            "Formato de imagen no permitido. Use JPG, JPEG, PNG o WEBP."
        )

    contenido = imagen.get("data", b"")

    if not contenido:
        raise ValueError("La imagen está vacía.")

    # Límite de 5 MB
    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError("La imagen no puede superar los 5 MB.")

    nombre_archivo = str(uuid.uuid4()) + extension

    ruta = os.path.join(
        CARPETA_IMAGENES,
        nombre_archivo
    )

    with open(ruta, "wb") as archivo:
        archivo.write(contenido)

    return "/img/productos/" + nombre_archivo, ruta


# ============================================================
# SERVIDOR
# ============================================================

class MiServidor(SimpleHTTPRequestHandler):

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):
        url = urlparse(self.path)

        # Obtener productos de MySQL
        if url.path == "/productos":
            conexion = None
            cursor = None

            try:
                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                cursor.execute("""
                    SELECT
                        id_producto,
                        nombre,
                        descripcion,
                        precio,
                        imagen,
                        activo
                    FROM productos
                    ORDER BY id_producto DESC
                """)

                productos = cursor.fetchall()

                responder_json(
                    self,
                    {
                        "estado": True,
                        "productos": productos
                    }
                )

            except Exception as error:
                print("ERROR PRODUCTOS:", error)

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "No se pudieron cargar los productos."
                    },
                    500
                )

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        # Página principal
        if url.path == "/":
            self.path = "/index.html"

        return SimpleHTTPRequestHandler.do_GET(self)

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def do_POST(self):
        url = urlparse(self.path)

        # ====================================================
        # REGISTRO DE USUARIOS
        # ====================================================

        if url.path == "/registro":
            try:
                datos = leer_json(self)

                nombre = str(datos.get("nombre", "")).strip()
                usuario = str(datos.get("usuario", "")).strip()
                contrasena = str(datos.get("contrasena", ""))

                if not nombre or not usuario or not contrasena:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Complete todos los campos."
                        },
                        400
                    )
                    return

                from crud_usuarios import crud_usuarios

                crud = crud_usuarios()
                estado, mensaje = crud.registrar(
                    nombre,
                    usuario,
                    contrasena
                )

                responder_json(
                    self,
                    {
                        "estado": bool(estado),
                        "mensaje": mensaje
                    },
                    200 if estado else 400
                )

            except Exception as error:
                print("ERROR REGISTRO:", error)

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "No se pudo registrar el usuario."
                    },
                    500
                )

            return

        # ====================================================
        # INICIO DE SESIÓN
        # ====================================================

        if url.path == "/login":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                usuario = str(datos.get("usuario", "")).strip()
                contrasena = str(datos.get("contrasena", ""))

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                cursor.execute("""
                    SELECT
                        u.id_usuario,
                        u.nombre,
                        u.usuario,
                        u.contrasena,
                        r.id_rol,
                        r.nombre AS rol
                    FROM usuarios u
                    INNER JOIN roles r
                        ON u.id_rol = r.id_rol
                    WHERE
                        u.usuario = %s
                        AND u.contrasena = %s
                        AND u.activo = TRUE
                """, (usuario, contrasena))

                resultado = cursor.fetchone()

                if resultado:
                    responder_json(
                        self,
                        {
                            "estado": True,
                            "mensaje": "Bienvenido a Akari Store.",
                            "id_usuario": resultado["id_usuario"],
                            "usuario": resultado["usuario"],
                            "nombre": resultado["nombre"],
                            "id_rol": resultado["id_rol"],
                            "rol": resultado["rol"]
                        }
                    )
                else:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Usuario o contraseña incorrectos."
                        },
                        401
                    )

            except Exception as error:
                print("ERROR LOGIN:", error)

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "Ocurrió un error al iniciar sesión."
                    },
                    500
                )

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        # ====================================================
        # ELIMINAR PRODUCTO (Ruta aislada que recibe JSON puro)
        # ====================================================

        if url.path == "/productos/eliminar":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                try:
                    id_producto = int(datos.get("id_producto", 0))
                except (ValueError, TypeError):
                    id_producto = 0

                if id_producto <= 0:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "ID de producto no válido."
                        },
                        400
                    )
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor()

                cursor.execute(
                    "SELECT imagen FROM productos WHERE id_producto = %s",
                    (id_producto,)
                )
                producto = cursor.fetchone()

                if producto is None:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "El producto no existe."
                        },
                        404
                    )
                    return

                cursor.execute(
                    "DELETE FROM productos WHERE id_producto = %s",
                    (id_producto,)
                )

                conexion.commit()

                # Eliminar imagen local si existe
                imagen = producto[0]

                if imagen:
                    nombre_imagen = os.path.basename(imagen)
                    ruta_imagen = os.path.join(
                        CARPETA_IMAGENES,
                        nombre_imagen
                    )

                    if os.path.isfile(ruta_imagen):
                        try:
                            os.remove(ruta_imagen)
                        except OSError as error:
                            print("Error al eliminar imagen:", error)

                responder_json(
                    self,
                    {
                        "estado": True,
                        "mensaje": "Producto eliminado correctamente."
                    }
                )

            except Exception as error:
                if conexion:
                    conexion.rollback()
                print("ERROR ELIMINAR:", error)
                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "No se pudo eliminar el producto."
                    },
                    500
                )
            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        # ====================================================
        # CAMBIAR ESTADO DE PRODUCTOS
        # ====================================================

        if url.path == "/productos/estado":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                id_producto = int(datos.get("id_producto", 0))
                activo = int(datos.get("activo", -1))

                if id_producto <= 0 or activo not in (0, 1):
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Los datos enviados no son válidos."
                        },
                        400
                    )
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor()

                cursor.execute("""
                    UPDATE productos
                    SET activo = %s
                    WHERE id_producto = %s
                """, (activo, id_producto))

                if cursor.rowcount == 0:
                    conexion.rollback()
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Producto no encontrado o sin cambios."
                        },
                        404
                    )
                    return

                conexion.commit()

                responder_json(
                    self,
                    {
                        "estado": True,
                        "mensaje": "Estado actualizado correctamente."
                    }
                )

            except Exception as error:
                if conexion:
                    conexion.rollback()
                print("ERROR ESTADO:", error)
                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "Ocurrió un error al cambiar el estado."
                    },
                    500
                )
            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        # ====================================================
        # AGREGAR O EDITAR PRODUCTOS (Multipart / Form-data)
        # ====================================================

        if url.path in ("/productos", "/productos/editar"):
            conexion = None
            cursor = None
            ruta_archivo_nuevo = None

            try:
                datos = leer_multipart(self)

                if datos is None:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "El formulario debe enviarse como multipart/form-data."
                        },
                        400
                    )
                    return

                nombre = datos.get("nombre", "").strip()
                descripcion = datos.get("descripcion", "").strip()
                precio_texto = datos.get("precio", "")
                activo_texto = datos.get("activo", "1")
                id_producto_texto = datos.get("id_producto", "0")

                if not nombre:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Ingrese el nombre del producto."
                        },
                        400
                    )
                    return

                try:
                    precio = float(precio_texto)
                    activo = int(activo_texto)
                    id_producto = int(id_producto_texto or 0)
                except (ValueError, TypeError):
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "El precio o el identificador no son válidos."
                        },
                        400
                    )
                    return

                if precio <= 0 or activo not in (0, 1):
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "El precio debe ser mayor que cero."
                        },
                        400
                    )
                    return

                if url.path == "/productos/editar" and id_producto <= 0:
                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje": "Falta el ID del producto."
                        },
                        400
                    )
                    return

                imagen = datos.get("imagen")
                ruta_imagen = None

                if imagen and imagen.get("filename"):
                    resultado_imagen = guardar_imagen(imagen)
                    ruta_imagen, ruta_archivo_nuevo = resultado_imagen

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                if url.path == "/productos":
                    if ruta_imagen is None:
                        ruta_imagen = ""

                    cursor.execute("""
                        INSERT INTO productos
                            (nombre, descripcion, precio, imagen, activo)
                        VALUES
                            (%s, %s, %s, %s, %s)
                    """, (
                        nombre,
                        descripcion,
                        precio,
                        ruta_imagen,
                        activo
                    ))

                    mensaje = "Producto agregado correctamente."

                else:
                    cursor.execute("""
                        SELECT imagen
                        FROM productos
                        WHERE id_producto = %s
                    """, (id_producto,))

                    producto = cursor.fetchone()

                    if not producto:
                        conexion.rollback()
                        responder_json(
                            self,
                            {
                                "estado": False,
                                "mensaje": "El producto no existe."
                            },
                            404
                        )
                        return

                    if ruta_imagen is None:
                        ruta_imagen = producto["imagen"] or ""

                    cursor.execute("""
                        UPDATE productos
                        SET
                            nombre = %s,
                            descripcion = %s,
                            precio = %s,
                            imagen = %s,
                            activo = %s
                        WHERE id_producto = %s
                    """, (
                        nombre,
                        descripcion,
                        precio,
                        ruta_imagen,
                        activo,
                        id_producto
                    ))

                    mensaje = "Producto actualizado correctamente."

                conexion.commit()

                responder_json(
                    self,
                    {
                        "estado": True,
                        "mensaje": mensaje
                    }
                )

            except ValueError as error:
                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": str(error)
                    },
                    400
                )

            except Exception as error:
                if conexion:
                    conexion.rollback()

                if ruta_archivo_nuevo and os.path.exists(ruta_archivo_nuevo):
                    try:
                        os.remove(ruta_archivo_nuevo)
                    except OSError:
                        pass

                print("ERROR PRODUCTOS:", error)

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": "Ocurrió un error al procesar el producto."
                    },
                    500
                )

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        # ====================================================
        # RUTA NO ENCONTRADA
        # ====================================================

        responder_json(
            self,
            {
                "estado": False,
                "mensaje": "Ruta no encontrada."
            },
            404
        )


# ============================================================
# INICIAR SERVIDOR
# ============================================================

if __name__ == "__main__":
    print("==========================================")
    print("     AKARI STORE - SERVIDOR")
    print("==========================================")
    print("Servidor corriendo en:")
    print("http://localhost:" + str(PORT))
    print("==========================================")

    servidor = HTTPServer(
        ("localhost", PORT),
        MiServidor
    )

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        servidor.server_close()
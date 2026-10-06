from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mysql.connector
import json
import os
import uuid
import mimetypes


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


# ============================================================
# CARPETA PARA IMÁGENES
# ============================================================

CARPETA_IMAGENES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "img",
    "productos"
)

os.makedirs(CARPETA_IMAGENES, exist_ok=True)


# ============================================================
# CONEXIÓN A MYSQL
# ============================================================

def conectar_bd():

    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"]
    )


# ============================================================
# RESPUESTA JSON
# ============================================================

def responder_json(handler, datos, codigo=200):

    respuesta = json.dumps(
        datos,
        ensure_ascii=False
    ).encode("utf-8")

    handler.send_response(codigo)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Content-Length",
        str(len(respuesta))
    )

    handler.end_headers()

    handler.wfile.write(respuesta)


# ============================================================
# LEER MULTIPART/FORM-DATA
# ============================================================

def leer_multipart(handler):

    content_type = handler.headers.get("Content-Type", "")

    if "multipart/form-data" not in content_type:

        return None

    # Obtener boundary
    partes = content_type.split("boundary=")

    if len(partes) < 2:
        return None

    boundary = partes[1].encode("utf-8")

    content_length = int(
        handler.headers.get("Content-Length", 0)
    )

    cuerpo = handler.rfile.read(content_length)

    limite = b"--" + boundary

    partes = cuerpo.split(limite)

    datos = {}

    for parte in partes:

        if not parte or parte in (b"--\r\n", b"--"):
            continue

        if b"\r\n\r\n" not in parte:
            continue

        encabezados, contenido = parte.split(
            b"\r\n\r\n",
            1
        )

        contenido = contenido.rstrip(b"\r\n-")

        encabezados_texto = encabezados.decode(
            "utf-8",
            errors="ignore"
        )

        nombre = None
        nombre_archivo = None

        for linea in encabezados_texto.split("\r\n"):

            if "Content-Disposition" in linea:

                if 'name="' in linea:

                    nombre = linea.split(
                        'name="'
                    )[1].split('"')[0]

                if 'filename="' in linea:

                    nombre_archivo = linea.split(
                        'filename="'
                    )[1].split('"')[0]

        if not nombre:
            continue

        # ----------------------------------------------------
        # ARCHIVO
        # ----------------------------------------------------

        if nombre_archivo:

            datos[nombre] = {
                "filename": nombre_archivo,
                "data": contenido
            }

        # ----------------------------------------------------
        # CAMPO NORMAL
        # ----------------------------------------------------

        else:

            datos[nombre] = contenido.decode(
                "utf-8",
                errors="ignore"
            )

    return datos


# ============================================================
# SERVIDOR
# ============================================================

class MiServidor(SimpleHTTPRequestHandler):


    # ========================================================
    # GET
    # ========================================================

    def do_GET(self):

        url = urlparse(self.path)

        # ----------------------------------------------------
        # OBTENER CATEGORÍAS
        # ----------------------------------------------------

        if url.path == "/categorias":

            try:

                conexion = conectar_bd()

                cursor = conexion.cursor(
                    dictionary=True
                )

                cursor.execute("""
                    SELECT
                        id_categoria,
                        nombre
                    FROM categorias
                    WHERE activo = TRUE
                    ORDER BY nombre
                """)

                categorias = cursor.fetchall()

                cursor.close()
                conexion.close()

                responder_json(
                    self,
                    {
                        "estado": True,
                        "categorias": categorias
                    }
                )

            except Exception as error:

                print("ERROR CATEGORIAS:", error)

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje": str(error)
                    },
                    500
                )

            return


        # ----------------------------------------------------
        # OBTENER PRODUCTOS
        # ----------------------------------------------------

        if url.path == "/productos":

            try:

                conexion = conectar_bd()

                cursor = conexion.cursor(
                    dictionary=True
                )

                cursor.execute("""
                    SELECT
                        p.id_producto,
                        p.nombre,
                        p.id_categoria,
                        c.nombre AS categoria,
                        p.precio,
                        p.existencias,
                        p.imagen,
                        p.descripcion,
                        p.activo
                    FROM productos p
                    LEFT JOIN categorias c
                        ON p.id_categoria = c.id_categoria
                    WHERE p.activo = TRUE
                    ORDER BY p.id_producto DESC
                """)

                productos = cursor.fetchall()

                cursor.close()
                conexion.close()

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
                        "mensaje": str(error)
                    },
                    500
                )

            return


        # ----------------------------------------------------
        # PÁGINA PRINCIPAL
        # ----------------------------------------------------

        if url.path == "/":

            self.path = "/index.html"

        return SimpleHTTPRequestHandler.do_GET(self)


    # ========================================================
    # POST
    # ========================================================

    def do_POST(self):

        url = urlparse(self.path)


        # ====================================================
        # AGREGAR PRODUCTO
        # ====================================================

        if url.path == "/productos":

            try:

                datos = leer_multipart(self)

                if datos is None:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Los datos no fueron enviados correctamente."
                        },
                        400
                    )

                    return


                nombre = datos.get(
                    "nombre",
                    ""
                ).strip()

                id_categoria = datos.get(
                    "categoria",
                    ""
                )

                precio = datos.get(
                    "precio",
                    "0"
                )

                existencias = datos.get(
                    "existencias",
                    "0"
                )

                descripcion = datos.get(
                    "descripcion",
                    ""
                ).strip()


                # ------------------------------------------------
                # VALIDACIONES
                # ------------------------------------------------

                if not nombre:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Ingrese el nombre del producto."
                        },
                        400
                    )

                    return


                if not id_categoria:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Seleccione una categoría."
                        },
                        400
                    )

                    return


                try:

                    precio = float(precio)
                    existencias = int(existencias)

                except:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Precio o existencias inválidos."
                        },
                        400
                    )

                    return


                if precio < 0:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "El precio no puede ser negativo."
                        },
                        400
                    )

                    return


                if existencias < 0:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Las existencias no pueden ser negativas."
                        },
                        400
                    )

                    return


                # =================================================
                # GUARDAR IMAGEN
                # =================================================

                imagen = datos.get("imagen")

                ruta_imagen = ""


                if imagen:

                    nombre_original = imagen["filename"]

                    extension = os.path.splitext(
                        nombre_original
                    )[1].lower()


                    extensiones_permitidas = [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp"
                    ]


                    if extension not in extensiones_permitidas:

                        responder_json(
                            self,
                            {
                                "estado": False,
                                "mensaje":
                                "Formato de imagen no permitido. "
                                "Use JPG, JPEG, PNG o WEBP."
                            },
                            400
                        )

                        return


                    # Nombre único para evitar que
                    # dos imágenes tengan el mismo nombre

                    nombre_archivo = (
                        str(uuid.uuid4())
                        + extension
                    )


                    ruta_archivo = os.path.join(
                        CARPETA_IMAGENES,
                        nombre_archivo
                    )


                    with open(
                        ruta_archivo,
                        "wb"
                    ) as archivo:

                        archivo.write(
                            imagen["data"]
                        )


                    ruta_imagen = (
                        "/img/productos/"
                        + nombre_archivo
                    )


                # =================================================
                # GUARDAR PRODUCTO EN MYSQL
                # =================================================

                conexion = conectar_bd()

                cursor = conexion.cursor()


                sql = """
                    INSERT INTO productos
                    (
                        id_categoria,
                        nombre,
                        precio,
                        existencias,
                        imagen,
                        descripcion,
                        activo
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        TRUE
                    )
                """


                valores = (
                    int(id_categoria),
                    nombre,
                    precio,
                    existencias,
                    ruta_imagen,
                    descripcion
                )


                cursor.execute(
                    sql,
                    valores
                )


                conexion.commit()


                id_producto = cursor.lastrowid


                cursor.close()
                conexion.close()


                print(
                    "Producto guardado:",
                    id_producto
                )


                responder_json(
                    self,
                    {
                        "estado": True,
                        "mensaje":
                        "Producto agregado correctamente.",
                        "id_producto":
                        id_producto,
                        "imagen":
                        ruta_imagen
                    }
                )

                return


            except Exception as error:

                print(
                    "ERROR AL GUARDAR PRODUCTO:",
                    error
                )

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje":
                        "Error al guardar el producto: "
                        + str(error)
                    },
                    500
                )

                return


        # ====================================================
        # LOGIN
        # ====================================================

        if url.path == "/login":

            try:

                longitud = int(
                    self.headers.get(
                        "Content-Length",
                        0
                    )
                )

                cuerpo = self.rfile.read(longitud)

                datos = json.loads(
                    cuerpo.decode("utf-8")
                )

                usuario = datos.get(
                    "usuario",
                    ""
                )

                contrasena = datos.get(
                    "contrasena",
                    ""
                )


                conexion = conectar_bd()

                cursor = conexion.cursor(
                    dictionary=True
                )


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
                """, (
                    usuario,
                    contrasena
                ))


                resultado = cursor.fetchone()


                cursor.close()
                conexion.close()


                if resultado:

                    responder_json(
                        self,
                        {
                            "estado": True,
                            "mensaje":
                            "Bienvenido a Akari Store.",
                            "usuario":
                            resultado["usuario"],
                            "nombre":
                            resultado["nombre"],
                            "rol":
                            resultado["rol"]
                        }
                    )

                else:

                    responder_json(
                        self,
                        {
                            "estado": False,
                            "mensaje":
                            "Usuario o contraseña incorrectos."
                        }
                    )

            except Exception as error:

                print(
                    "ERROR LOGIN:",
                    error
                )

                responder_json(
                    self,
                    {
                        "estado": False,
                        "mensaje":
                        "Error del servidor: "
                        + str(error)
                    },
                    500
                )

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

print(
    "=========================================="
)

print(
    "       AKARI STORE - SERVIDOR"
)

print(
    "=========================================="
)

print(
    "Servidor corriendo en:"
)

print(
    "http://localhost:" + str(PORT)
)

print(
    "=========================================="
)


servidor = HTTPServer(
    ("localhost", PORT),
    MiServidor
)

servidor.serve_forever()
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import mysql.connector
import json
import os
import uuid
import secrets
import traceback
from http.cookies import SimpleCookie
from google import genai

PORT = 3000

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.8-flash"


ESTADOS_PEDIDO_VALIDOS = {
    "pendiente": "Pendiente",
    "en proceso": "En proceso",
    "listo": "Listo",
    "entregado": "Entregado",
    "cancelado": "Cancelado"
}


def resolver_estado_pedido(valor):
    limpio = " ".join(str(valor or "").strip().split()).lower()
    return ESTADOS_PEDIDO_VALIDOS.get(limpio)


def mostrar_restricciones_pedidos():
    conexion = None
    cursor = None
    try:
        conexion = mysql.connector.connect(**DB_CONFIG)
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""
            SELECT CONSTRAINT_NAME, CHECK_CLAUSE
            FROM information_schema.CHECK_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = %s
              AND TABLE_NAME = 'pedidos'
        """, (DB_CONFIG["database"],))
        filas = cursor.fetchall()
        if filas:
            print("RESTRICCIONES CHECK EN PEDIDOS:")
            for fila in filas:
                print(" -", fila.get("CONSTRAINT_NAME"), "->", fila.get("CHECK_CLAUSE"))
    except Exception:
        pass
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()


def responder_con_gemini(pregunta, productos):
    if not GEMINI_API_KEY:
        raise RuntimeError("Falta configurar GEMINI_API_KEY.")

    cliente = genai.Client(api_key=GEMINI_API_KEY)

    catalogo = json.dumps(
        productos,
        ensure_ascii=False,
        default=str
    )

    instrucciones = f"""
Eres el asistente virtual de Akari Store, una tienda de El Salvador
que vende camisas estampadas, urbanas y oversize.

Responde siempre en español, con amabilidad, claridad y mensajes
relativamente breves.

Ayuda a los clientes a conocer los productos y encontrar opciones.
Utiliza los productos del catálogo que se te proporciona.

No inventes precios, existencias, descuentos ni características.
Si no encuentras un dato en el catálogo, indica que el cliente debe
consultarlo con la tienda.

Por ahora no proceses pedidos ni confirmes compras.
No solicites contraseñas ni datos bancarios.

CATÁLOGO ACTUAL:
{catalogo}

PREGUNTA DEL CLIENTE:
{pregunta}
"""

    respuesta = cliente.models.generate_content(
        model=GEMINI_MODEL,
        contents=instrucciones
    )

    texto = (respuesta.text or "").strip()

    if not texto:
        raise RuntimeError("Gemini no devolvió una respuesta.")

    return texto


SESIONES = {}

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "akari_store"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CARPETA_IMAGENES = os.path.join(
    BASE_DIR, "img", "productos"
)

os.makedirs(CARPETA_IMAGENES, exist_ok=True)


def conectar_bd():
    return mysql.connector.connect(**DB_CONFIG)


def obtener_sesion(handler):
    cookies = SimpleCookie(handler.headers.get("Cookie", ""))
    cookie = cookies.get("akari_session")

    if not cookie:
        return None

    return SESIONES.get(cookie.value)


def puede_administrar(handler):
    sesion = obtener_sesion(handler)

    if not sesion:
        return False

    rol = str(sesion.get("rol", "")).strip().lower()

    return rol in ("administrador", "empleado")


def responder_json(handler, datos, codigo=200, headers_extra=None):
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

    if headers_extra:
        for nombre, valor in headers_extra.items():
            handler.send_header(nombre, valor)

    handler.end_headers()
    handler.wfile.write(respuesta)


def leer_json(handler):
    longitud = int(handler.headers.get("Content-Length", 0))

    if longitud <= 0:
        return {}

    cuerpo = handler.rfile.read(longitud)

    codificacion = handler.headers.get_content_charset() or "utf-8"

    try:
        texto = cuerpo.decode(codificacion)
        return json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(
            "El cuerpo de la solicitud no contiene JSON válido en UTF-8."
        )


def leer_multipart(handler):
    content_type = handler.headers.get("Content-Type", "")

    if "multipart/form-data" not in content_type:
        return None

    partes_boundary = content_type.split("boundary=", 1)

    if len(partes_boundary) != 2:
        return None

    boundary = (
        partes_boundary[1].strip().strip('"').encode("utf-8")
    )

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

        encabezados, contenido = parte.split(
            b"\r\n\r\n", 1
        )

        contenido = contenido.rstrip(b"\r\n")

        encabezados_texto = encabezados.decode(
            "utf-8", errors="ignore"
        )

        nombre = None
        nombre_archivo = None

        for linea in encabezados_texto.split("\r\n"):
            if "Content-Disposition:" not in linea:
                continue

            if 'name="' in linea:
                nombre = linea.split(
                    'name="', 1
                )[1].split('"', 1)[0]

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
                "utf-8", errors="replace"
            )

    return datos


def guardar_imagen(imagen):
    if not imagen or not imagen.get("filename"):
        return None

    nombre_original = os.path.basename(
        imagen["filename"]
    )

    extension = os.path.splitext(
        nombre_original
    )[1].lower()

    extensiones_permitidas = (
        ".jpg", ".jpeg", ".png", ".webp"
    )

    if extension not in extensiones_permitidas:
        raise ValueError(
            "Formato no permitido. Use JPG, JPEG, PNG o WEBP."
        )

    contenido = imagen.get("data", b"")

    if not contenido:
        raise ValueError("La imagen está vacía.")

    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError("La imagen no puede superar los 5 MB.")

    nombre_archivo = str(uuid.uuid4()) + extension

    ruta = os.path.join(
        CARPETA_IMAGENES, nombre_archivo
    )

    with open(ruta, "wb") as archivo:
        archivo.write(contenido)

    return "/img/productos/" + nombre_archivo, ruta


class MiServidor(SimpleHTTPRequestHandler):

    def do_GET(self):
        url = urlparse(self.path)

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
                        activo,
                        tipo_producto,
                        categoria
                    FROM productos
                    ORDER BY id_producto DESC
                """)

                productos = cursor.fetchall()

                responder_json(self, {
                    "estado": True,
                    "productos": productos
                })

            except Exception as error:
                print("ERROR AL CARGAR PRODUCTOS:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "No se pudieron cargar los productos."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path in ("/pedidos/admin", "/pedidos"):
            conexion = None
            cursor = None

            try:
                if not obtener_sesion(self):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Debe iniciar sesión."
                    }, 401)
                    return

                if not puede_administrar(self):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "No tiene permiso para ver los pedidos."
                    }, 403)
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                cursor.execute("""
                    SELECT
                        p.id_pedido,
                        p.fecha,
                        p.estado,
                        c.id_cliente,
                        c.nombre AS cliente,
                        c.telefono,
                        c.correo,
                        c.direccion,
                        COALESCE(SUM(dp.cantidad), 0) AS total_unidades,
                        COALESCE(SUM(dp.cantidad * dp.precio_aplicado), 0) AS total
                    FROM pedidos p
                    INNER JOIN clientes c
                        ON p.id_cliente = c.id_cliente
                    LEFT JOIN detalle_pedido dp
                        ON p.id_pedido = dp.id_pedido
                    GROUP BY
                        p.id_pedido,
                        p.fecha,
                        p.estado,
                        c.id_cliente,
                        c.nombre,
                        c.telefono,
                        c.correo,
                        c.direccion
                    ORDER BY p.id_pedido DESC
                """)

                pedidos = cursor.fetchall()

                for pedido in pedidos:
                    cursor.execute("""
                        SELECT
                            dp.id_detalle,
                            dp.id_producto,
                            pr.nombre AS producto,
                            t.nombre AS talla,
                            col.nombre AS color,
                            d.texto_personalizado AS personalizacion,
                            dp.cantidad,
                            dp.precio_aplicado,
                            (dp.cantidad * dp.precio_aplicado) AS subtotal
                        FROM detalle_pedido dp
                        INNER JOIN productos pr
                            ON dp.id_producto = pr.id_producto
                        INNER JOIN tallas t
                            ON dp.id_talla = t.id_talla
                        INNER JOIN colores col
                            ON dp.id_color = col.id_color
                        LEFT JOIN disenos d
                            ON dp.id_diseno = d.id_diseno
                        WHERE dp.id_pedido = %s
                        ORDER BY dp.id_detalle ASC
                    """, (pedido["id_pedido"],))
                    pedido["detalles"] = cursor.fetchall()

                responder_json(self, {
                    "estado": True,
                    "pedidos": pedidos
                })

            except Exception as error:
                print("ERROR PEDIDOS ADMIN:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "No se pudieron cargar los pedidos."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        sesion = obtener_sesion(self)

        paginas_privadas = (
            "/index.html",
            "/catalogo.html",
            "/personalizar.html",
            "/pedidos.html"
        )

        if url.path == "/":
            self.path = (
                "/index.html" if sesion else "/login.html"
            )
            return SimpleHTTPRequestHandler.do_GET(self)

        if url.path in paginas_privadas and not sesion:
            self.send_response(302)
            self.send_header("Location", "/login.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        url = urlparse(self.path)

        
        if url.path == "/chat-ia":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                pregunta = str(
                    datos.get("mensaje", "")
                ).strip()

                if not pregunta:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Escribe una pregunta."
                    }, 400)
                    return

                if len(pregunta) > 1200:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "La pregunta es demasiado larga."
                    }, 400)
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                cursor.execute("""
                    SELECT
                        nombre,
                        descripcion,
                        precio,
                        tipo_producto,
                        categoria
                    FROM productos
                    WHERE activo = 1
                    ORDER BY id_producto DESC
                    LIMIT 100
                """)

                productos = cursor.fetchall()

                respuesta = responder_con_gemini(
                    pregunta,
                    productos
                )

                responder_json(self, {
                    "estado": True,
                    "respuesta": respuesta
                })

            except Exception as error:
                print("ERROR CHAT IA:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": (
                        "No pudimos responder en este momento. "
                        "Inténtalo nuevamente."
                    )
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path == "/pedidos/crear":
            conexion = None
            cursor = None

            try:
                if not obtener_sesion(self):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Debe iniciar sesión."
                    }, 401)
                    return

                datos = leer_json(self)

                cliente_obj = datos.get("cliente") if isinstance(datos.get("cliente"), dict) else {}

                nombre_cliente = str(
                    datos.get("nombre")
                    or datos.get("clienteNombre")
                    or datos.get("nombre_cliente")
                    or datos.get("cliente_nombre")
                    or cliente_obj.get("nombre")
                    or ""
                ).strip()

                telefono = str(
                    datos.get("telefono")
                    or datos.get("tel")
                    or datos.get("whatsapp")
                    or datos.get("telefono_whatsapp")
                    or cliente_obj.get("telefono")
                    or ""
                ).strip()

                correo = (
                    str(
                        datos.get("correo")
                        or datos.get("email")
                        or cliente_obj.get("correo")
                        or ""
                    ).strip()
                    or None
                )

                direccion = (
                    str(
                        datos.get("direccion")
                        or datos.get("direccion_entrega")
                        or cliente_obj.get("direccion")
                        or ""
                    ).strip()
                    or None
                )

                items = (
                    datos.get("items")
                    or datos.get("productos")
                    or datos.get("carrito")
                    or datos.get("detalle")
                    or []
                )

                if not nombre_cliente or not telefono:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Complete nombre y teléfono del cliente."
                    }, 400)
                    return

                if not isinstance(items, list) or len(items) == 0:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Agrega al menos un producto al pedido."
                    }, 400)
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                cursor.execute(
                    "SELECT id_cliente FROM clientes WHERE telefono = %s LIMIT 1",
                    (telefono,)
                )
                cliente_existente = cursor.fetchone()

                if cliente_existente:
                    id_cliente = cliente_existente["id_cliente"]
                    cursor.execute("""
                        UPDATE clientes
                        SET
                            nombre = %s,
                            correo = COALESCE(%s, correo),
                            direccion = COALESCE(%s, direccion)
                        WHERE id_cliente = %s
                    """, (nombre_cliente, correo, direccion, id_cliente))
                else:
                    cursor.execute("""
                        INSERT INTO clientes (
                            nombre,
                            telefono,
                            correo,
                            direccion
                        )
                        VALUES (%s, %s, %s, %s)
                    """, (nombre_cliente, telefono, correo, direccion))
                    id_cliente = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO pedidos (id_cliente, estado)
                    VALUES (%s, 'Pendiente')
                """, (id_cliente,))
                id_pedido = cursor.lastrowid

                cursor.execute("SELECT id_talla, nombre FROM tallas")
                tallas_map = {
                    str(fila["nombre"]).strip().upper(): fila["id_talla"]
                    for fila in cursor.fetchall()
                }

                cursor.execute("SELECT id_color, nombre FROM colores")
                colores_map = {
                    str(fila["nombre"]).strip().lower(): fila["id_color"]
                    for fila in cursor.fetchall()
                }

                if not tallas_map or not colores_map:
                    raise ValueError(
                        "Faltan registros en las tablas tallas o colores."
                    )

                id_talla_default = tallas_map.get("M") or next(iter(tallas_map.values()))
                id_color_default = colores_map.get("negro") or next(iter(colores_map.values()))

                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError("Formato de producto inválido en el pedido.")

                    try:
                        id_producto = int(
                            item.get("id_producto")
                            or item.get("producto_id")
                            or item.get("id")
                            or 0
                        )
                        cantidad = int(item.get("cantidad", 0))
                    except (ValueError, TypeError):
                        raise ValueError("ID de producto o cantidad no válidos.")

                    if id_producto <= 0 or cantidad <= 0 or cantidad > 100:
                        raise ValueError("Producto o cantidad fuera de rango.")

                    cursor.execute("""
                        SELECT nombre, precio, activo
                        FROM productos
                        WHERE id_producto = %s
                    """, (id_producto,))
                    producto = cursor.fetchone()

                    if not producto:
                        raise ValueError(f"El producto #{id_producto} no existe.")

                    if not producto["activo"]:
                        raise ValueError(
                            f"El producto '{producto['nombre']}' no está disponible."
                        )

                    talla_texto = str(item.get("talla", "")).strip().upper()
                    id_talla = tallas_map.get(talla_texto, id_talla_default)

                    color_texto = str(item.get("color", "")).strip().lower()
                    id_color = colores_map.get(color_texto, id_color_default)

                    personalizacion = str(
                        item.get("personalizacion")
                        or item.get("texto_personalizado")
                        or ""
                    ).strip()

                    id_diseno = None
                    if personalizacion:
                        cursor.execute("""
                            INSERT INTO disenos (
                                nombre,
                                texto_personalizado
                            )
                            VALUES (%s, %s)
                        """, ("Personalización pedido", personalizacion))
                        id_diseno = cursor.lastrowid

                    cursor.execute("""
                        INSERT INTO detalle_pedido (
                            id_pedido,
                            id_producto,
                            id_talla,
                            id_color,
                            id_diseno,
                            cantidad,
                            precio_aplicado
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_pedido,
                        id_producto,
                        id_talla,
                        id_color,
                        id_diseno,
                        cantidad,
                        producto["precio"]
                    ))

                conexion.commit()

                responder_json(self, {
                    "estado": True,
                    "mensaje": "Pedido creado correctamente.",
                    "id_pedido": id_pedido
                })

            except ValueError as error:
                if conexion:
                    conexion.rollback()

                responder_json(self, {
                    "estado": False,
                    "mensaje": str(error)
                }, 400)

            except Exception as error:
                if conexion:
                    conexion.rollback()

                print("ERROR PEDIDOS CREAR:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "Ocurrió un error al crear el pedido."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path in (
            "/pedidos/admin",
            "/pedidos/estado",
            "/pedidos/actualizar",
            "/pedidos/cambiar-estado"
        ):
            conexion = None
            cursor = None

            try:
                if not obtener_sesion(self):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Debe iniciar sesión."
                    }, 401)
                    return

                if not puede_administrar(self):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "No tiene permiso para actualizar pedidos."
                    }, 403)
                    return

                datos = leer_json(self)

                try:
                    id_pedido = int(
                        datos.get("id_pedido")
                        or datos.get("pedido_id")
                        or datos.get("id")
                        or 0
                    )
                except (ValueError, TypeError):
                    id_pedido = 0

                estado_crudo = (
                    datos.get("estado")
                    or datos.get("nuevo_estado")
                    or ""
                )
                nuevo_estado = resolver_estado_pedido(estado_crudo)

                if id_pedido <= 0 or not nuevo_estado:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": (
                            f"ID de pedido o estado no válidos ('{estado_crudo}'). "
                            f"Permitidos: {', '.join(ESTADOS_PEDIDO_VALIDOS.values())}."
                        )
                    }, 400)
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor()

                cursor.execute("""
                    UPDATE pedidos
                    SET estado = %s
                    WHERE id_pedido = %s
                """, (nuevo_estado, id_pedido))

                if cursor.rowcount == 0:
                    conexion.rollback()
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "El pedido no existe."
                    }, 404)
                    return

                conexion.commit()

                responder_json(self, {
                    "estado": True,
                    "mensaje": "Estado del pedido actualizado."
                })

            except ValueError as error:
                responder_json(self, {
                    "estado": False,
                    "mensaje": str(error)
                }, 400)

            except Exception as error:
                if conexion:
                    conexion.rollback()

                print("ERROR PEDIDOS ADMIN POST:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": f"No se pudo actualizar el pedido: {error}"
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path == "/logout":
            cookies = SimpleCookie(
                self.headers.get("Cookie", "")
            )

            cookie = cookies.get("akari_session")

            if cookie:
                SESIONES.pop(cookie.value, None)

            responder_json(
                self,
                {
                    "estado": True,
                    "mensaje": "Sesión cerrada correctamente."
                },
                headers_extra={
                    "Set-Cookie":
                    "akari_session=; Path=/; HttpOnly; "
                    "SameSite=Lax; Max-Age=0"
                }
            )
            return

        
        if url.path == "/registro":
            try:
                datos = leer_json(self)

                nombre = str(
                    datos.get("nombre", "")
                ).strip()

                usuario = str(
                    datos.get("usuario", "")
                ).strip()

                contrasena = str(
                    datos.get("contrasena", "")
                )

                if not nombre or not usuario or not contrasena:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Complete todos los campos."
                    }, 400)
                    return

                from crud_usuarios import crud_usuarios

                crud = crud_usuarios()

                estado, mensaje = crud.registrar(
                    nombre, usuario, contrasena
                )

                responder_json(self, {
                    "estado": bool(estado),
                    "mensaje": mensaje
                }, 200 if estado else 400)

            except Exception as error:
                print("ERROR REGISTRO:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "No se pudo registrar el usuario."
                }, 500)

            return

        
        if url.path == "/login":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                usuario = str(
                    datos.get("usuario", "")
                ).strip()

                contrasena = str(
                    datos.get("contrasena", "")
                )

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

                if not resultado:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Usuario o contraseña incorrectos."
                    }, 401)
                    return

                token = secrets.token_urlsafe(32)

                SESIONES[token] = {
                    "id_usuario": resultado["id_usuario"],
                    "usuario": resultado["usuario"],
                    "nombre": resultado["nombre"],
                    "id_rol": resultado["id_rol"],
                    "rol": resultado["rol"]
                }

                responder_json(
                    self,
                    {
                        "estado": True,
                        "mensaje": "Bienvenido a Akari Store.",
                        **SESIONES[token]
                    },
                    headers_extra={
                        "Set-Cookie":
                        "akari_session=" + token +
                        "; Path=/; HttpOnly; SameSite=Lax"
                    }
                )

            except Exception as error:
                print("ERROR LOGIN:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "Ocurrió un error al iniciar sesión."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        rutas_protegidas = (
            "/productos",
            "/productos/editar",
            "/productos/eliminar",
            "/productos/estado"
        )

        if url.path in rutas_protegidas:
            if not obtener_sesion(self):
                responder_json(self, {
                    "estado": False,
                    "mensaje": "Debe iniciar sesión."
                }, 401)
                return

            if not puede_administrar(self):
                responder_json(self, {
                    "estado": False,
                    "mensaje": "No tiene permiso para modificar productos."
                }, 403)
                return

        
        if url.path == "/productos/eliminar":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                try:
                    id_producto = int(
                        datos.get("id_producto", 0)
                    )
                except (ValueError, TypeError):
                    id_producto = 0

                if id_producto <= 0:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "ID de producto no válido."
                    }, 400)
                    return

                conexion = conectar_bd()
                cursor = conexion.cursor()

                cursor.execute(
                    "SELECT imagen FROM productos WHERE id_producto = %s",
                    (id_producto,)
                )

                producto = cursor.fetchone()

                if not producto:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "El producto no existe."
                    }, 404)
                    return

                cursor.execute(
                    "DELETE FROM productos WHERE id_producto = %s",
                    (id_producto,)
                )

                conexion.commit()

                imagen = producto[0]

                if imagen:
                    ruta = os.path.join(
                        CARPETA_IMAGENES,
                        os.path.basename(imagen)
                    )

                    if os.path.isfile(ruta):
                        try:
                            os.remove(ruta)
                        except OSError as error:
                            print("ERROR AL BORRAR IMAGEN:", error)

                responder_json(self, {
                    "estado": True,
                    "mensaje": "Producto eliminado correctamente."
                })

            except Exception as error:
                if conexion:
                    conexion.rollback()

                print("ERROR ELIMINAR:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "No se pudo eliminar el producto."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path == "/productos/estado":
            conexion = None
            cursor = None

            try:
                datos = leer_json(self)

                id_producto = int(
                    datos.get("id_producto", 0)
                )

                activo = int(datos.get("activo", -1))

                if id_producto <= 0 or activo not in (0, 1):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Los datos enviados no son válidos."
                    }, 400)
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

                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Producto no encontrado o sin cambios."
                    }, 404)
                    return

                conexion.commit()

                responder_json(self, {
                    "estado": True,
                    "mensaje": "Estado actualizado correctamente."
                })

            except Exception as error:
                if conexion:
                    conexion.rollback()

                print("ERROR ESTADO:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "No se pudo cambiar el estado."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        
        if url.path in ("/productos", "/productos/editar"):
            conexion = None
            cursor = None
            ruta_archivo_nuevo = None

            try:
                datos = leer_multipart(self)

                if datos is None:
                    responder_json(self, {
                        "estado": False,
                        "mensaje":
                        "El formulario debe enviarse como multipart/form-data."
                    }, 400)
                    return

                nombre = datos.get("nombre", "").strip()
                descripcion = datos.get("descripcion", "").strip()

                tipo_producto = (
                    datos.get("tipo_producto", "Camisas").strip()
                    or "Camisas"
                )

                categoria = (
                    datos.get("categoria", "Otros").strip()
                    or "Otros"
                )

                precio_texto = datos.get("precio", "")
                activo_texto = datos.get("activo", "1")
                id_producto_texto = datos.get("id_producto", "0")

                if not nombre:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Ingrese el nombre del producto."
                    }, 400)
                    return

                try:
                    precio = float(precio_texto)
                    activo = int(activo_texto)
                    id_producto = int(id_producto_texto or 0)
                except (ValueError, TypeError):
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Precio o identificador no válidos."
                    }, 400)
                    return

                if precio <= 0 or activo not in (0, 1):
                    responder_json(self, {
                        "estado": False,
                        "mensaje":
                        "El precio debe ser mayor que cero y el estado válido."
                    }, 400)
                    return

                es_edicion = url.path == "/productos/editar"

                if es_edicion and id_producto <= 0:
                    responder_json(self, {
                        "estado": False,
                        "mensaje": "Falta el ID del producto."
                    }, 400)
                    return

                imagen = datos.get("imagen")
                ruta_imagen = None

                if imagen and imagen.get("filename"):
                    resultado = guardar_imagen(imagen)
                    ruta_imagen, ruta_archivo_nuevo = resultado

                conexion = conectar_bd()
                cursor = conexion.cursor(dictionary=True)

                if not es_edicion:
                    if ruta_imagen is None:
                        ruta_imagen = ""

                    cursor.execute("""
                        INSERT INTO productos (
                            nombre,
                            descripcion,
                            precio,
                            imagen,
                            activo,
                            tipo_producto,
                            categoria
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        nombre,
                        descripcion,
                        precio,
                        ruta_imagen,
                        activo,
                        tipo_producto,
                        categoria
                    ))

                    id_nuevo = cursor.lastrowid
                    mensaje = "Producto agregado correctamente."

                    print("PRODUCTO INSERTADO. ID:", id_nuevo)

                else:
                    cursor.execute("""
                        SELECT imagen
                        FROM productos
                        WHERE id_producto = %s
                    """, (id_producto,))

                    producto = cursor.fetchone()

                    if not producto:
                        conexion.rollback()

                        responder_json(self, {
                            "estado": False,
                            "mensaje": "El producto no existe."
                        }, 404)
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
                            activo = %s,
                            tipo_producto = %s,
                            categoria = %s
                        WHERE id_producto = %s
                    """, (
                        nombre,
                        descripcion,
                        precio,
                        ruta_imagen,
                        activo,
                        tipo_producto,
                        categoria,
                        id_producto
                    ))

                    mensaje = "Producto actualizado correctamente."

                conexion.commit()

                responder_json(self, {
                    "estado": True,
                    "mensaje": mensaje
                })

            except ValueError as error:
                responder_json(self, {
                    "estado": False,
                    "mensaje": str(error)
                }, 400)

            except Exception as error:
                if conexion:
                    conexion.rollback()

                if ruta_archivo_nuevo and os.path.exists(
                    ruta_archivo_nuevo
                ):
                    try:
                        os.remove(ruta_archivo_nuevo)
                    except OSError:
                        pass

                print("ERROR AL GUARDAR PRODUCTO:", repr(error))
                traceback.print_exc()

                responder_json(self, {
                    "estado": False,
                    "mensaje": "Ocurrió un error al guardar el producto."
                }, 500)

            finally:
                if cursor:
                    cursor.close()
                if conexion:
                    conexion.close()

            return

        responder_json(self, {
            "estado": False,
            "mensaje": "Ruta no encontrada."
        }, 404)


if __name__ == "__main__":
    print("==========================================")
    print("       AKARI STORE - SERVIDOR")
    print("==========================================")
    print("Base de datos:", DB_CONFIG["database"])
    print("Servidor: http://localhost:" + str(PORT))
    print("==========================================")
    mostrar_restricciones_pedidos()

    servidor = HTTPServer(
        ("localhost", PORT),
        MiServidor
    )

    try:
        servidor.serve_forever()

    except KeyboardInterrupt:
        print("\nServidor detenido.")

    finally:
        servidor.server_close()
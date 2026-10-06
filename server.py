from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import json

import crud_usuarios


port = 3000

crudUsuarios = crud_usuarios.crud_usuarios()


class miServidor(SimpleHTTPRequestHandler):


    def do_POST(self):

        longitud = int(
            self.headers['Content-Length']
        )

        datos = self.rfile.read(longitud)

        datos = datos.decode("utf-8")

        datos = json.loads(datos)


        # ==========================
        # LOGIN
        # ==========================

        if self.path == "/login":

            usuario = datos.get("usuario")

            contrasena = datos.get("contrasena")


            resultado = crudUsuarios.login(
                usuario,
                contrasena
            )


            if resultado:

                respuesta = {

                    "estado": True,

                    "mensaje":
                        "Inicio de sesión exitoso.",

                    "usuario":
                        resultado["usuario"],

                    "rol":
                        resultado["rol"]

                }

            else:

                respuesta = {

                    "estado": False,

                    "mensaje":
                        "Usuario o contraseña incorrectos."

                }


            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()


            self.wfile.write(
                json.dumps(respuesta).encode("utf-8")
            )

            return


        # ==========================
        # REGISTRO
        # ==========================

        if self.path == "/registro":

            nombre = datos.get("nombre")

            usuario = datos.get("usuario")

            contrasena = datos.get("contrasena")


            if not nombre or not usuario or not contrasena:

                respuesta = {

                    "estado": False,

                    "mensaje":
                        "Todos los campos son obligatorios."

                }

            else:

                estado, mensaje = crudUsuarios.registrar(
                    nombre,
                    usuario,
                    contrasena
                )


                respuesta = {

                    "estado": estado,

                    "mensaje": mensaje

                }


            self.send_response(200)

            self.send_header(
                "Content-Type",
                "application/json"
            )

            self.end_headers()


            self.wfile.write(
                json.dumps(respuesta).encode("utf-8")
            )

            return


    def do_GET(self):

        urlParse = urlparse(self.path)


        # Página principal

        if urlParse.path == "/":

            self.path = "/login.html"

            return SimpleHTTPRequestHandler.do_GET(
                self
            )


        return SimpleHTTPRequestHandler.do_GET(
            self
        )


print(
    "Servidor corriendo en el puerto",
    port
)


server = HTTPServer(
    ("localhost", port),
    miServidor
)


server.serve_forever()
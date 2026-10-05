from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import json
import crud_usuarios


port = 3000

crudUsuarios = crud_usuarios.crud_usuarios()


class miServidor(SimpleHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/":
            self.path = "/login.html"

        return SimpleHTTPRequestHandler.do_GET(self)


    def do_POST(self):

        if self.path == "/login":

            longitud = int(self.headers["Content-Length"])

            datos = self.rfile.read(longitud)

            datos = datos.decode("utf-8")

            datos = json.loads(datos)

            usuario = datos["usuario"]
            contrasena = datos["contrasena"]

            resultado = crudUsuarios.login(usuario, contrasena)

            if resultado:

                respuesta = {
                    "estado": True,
                    "mensaje": "Login correcto",
                    "usuario": resultado["nombre"],
                    "rol": resultado["rol"]
                }

            else:

                respuesta = {
                    "estado": False,
                    "mensaje": "Usuario o contraseña incorrectos"
                }

            self.send_response(200)
            self.send_header(
                "Content-type",
                "application/json"
            )
            self.end_headers()

            self.wfile.write(
                json.dumps(respuesta).encode("utf-8")
            )

            return


print(f"Servidor corriendo en el puerto {port}")

server = HTTPServer(
    ("localhost", port),
    miServidor
)

server.serve_forever()
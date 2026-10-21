import http.server
import urllib.parse
import os
from crud_usuarios_USSS003725 import (
    crud_usuarios_USSS003725,
    obtener_usuarios_USSS003725,
    validar_login_USSS003725
)

class MiServidorHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if path == "/" or path == "/index.html":
            self.enviar_html("index.html", {"error": ""})
            
        elif path == "/usuarios":
            busqueda = query_params.get("q", [""])[0]
            usuarios = obtener_usuarios_USSS003725(busqueda)
            self.enviar_vista_usuarios(usuarios, busqueda)
            
        elif path == "/eliminar":
            id_usuario = query_params.get("id", [None])[0]
            if id_usuario:
                crud_usuarios_USSS003725('eliminar', id_usuario=id_usuario)
            self.send_response(303)
            self.send_header('Location', '/usuarios')
            self.end_headers()
            
        elif path == "/logout":
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        if self.path == "/login":
            usuario = params.get("usuario", [""])[0]
            clave = params.get("clave", [""])[0]
            user_db = validar_login_USSS003725(usuario, clave)
            if user_db:
                self.send_response(303)
                self.send_header('Location', '/usuarios')
                self.end_headers()
            else:
                self.enviar_html("index.html", {"error": "Usuario o clave incorrectos"})

        elif self.path == "/guardar":
            id_usuario = params.get("idUsuario", [None])[0]
            usuario = params.get("usuario", [""])[0]
            clave = params.get("clave", [""])[0]
            nombre = params.get("nombre", [""])[0]
            direccion = params.get("dirección", [""])[0]
            telefono = params.get("teléfono", [""])[0]

            if id_usuario:
                crud_usuarios_USSS003725('actualizar', id_usuario=id_usuario, usuario=usuario, clave=clave, nombre=nombre, direccion=direccion, telefono=telefono)
            else:
                crud_usuarios_USSS003725('crear', usuario=usuario, clave=clave, nombre=nombre, direccion=direccion, telefono=telefono)

            self.send_response(303)
            self.send_header('Location', '/usuarios')
            self.end_headers()

    def enviar_html(self, filename, contexto):
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Obtener el error del contexto
            error_msg = contexto.get("error", "")
            if error_msg:
                alerta_html = f'<div class="alert alert-danger py-2 mb-3 text-center small" role="alert">{error_msg}</div>'
            else:
                alerta_html = ""  
                
          
            content = content.replace("{{alerta_error}}", alerta_html)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404, "Archivo no encontrado")

    def enviar_vista_usuarios(self, usuarios, query):
        if os.path.exists("usuarios.html"):
            with open("usuarios.html", "r", encoding="utf-8") as f:
                content = f.read()
            
            filas_html = ""
            for u in usuarios:
                filas_html += f"""
                <tr>
                    <td><span class="fw-bold text-secondary">#{u['idUsuario']}</span></td>
                    <td><span class="fw-semibold">{u['usuario']}</span></td>
                    <td>{u['nombre']}</td>
                    <td><span class="text-muted">{u.get('dirección') or '-'}</span></td>
                    <td><span class="text-muted">{u.get('teléfono') or '-'}</span></td>
                    <td class="text-center">
                        <button class="btn btn-warning btn-sm px-3 me-1 text-dark fw-semibold" onclick="editarUsuario('{u['idUsuario']}', '{u['usuario']}', '{u['nombre']}', '{u.get('dirección') or ''}', '{u.get('teléfono') or ''}')" data-bs-toggle="modal" data-bs-target="#modalUsuario">Editar</button>
                        <a href="/eliminar?id={u['idUsuario']}" class="btn btn-danger btn-sm px-3" onclick="return confirm('¿Estás seguro de eliminar este usuario?')">Eliminar</a>
                    </td>
                </tr>
                """
            if not usuarios:
                filas_html = '<tr><td colspan="6" class="text-center text-muted py-4">No se encontraron registros de usuarios.</td></tr>'

            content = content.replace("{{query}}", query)
            content = content.replace("{{filas_usuarios}}", filas_html)

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404, "Falta el archivo usuarios.html")

if __name__ == "__main__":
    puerto = 8000
    server = http.server.HTTPServer(("localhost", puerto), MiServidorHandler)
    print(f"Servidor nativo corriendo en http://localhost:{puerto}")
    server.serve_forever()
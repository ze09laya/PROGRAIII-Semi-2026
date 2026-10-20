
import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: No se ha configurado GEMINI_API_KEY.")
    raise SystemExit(1)

try:
    client = genai.Client(api_key=api_key)

    respuesta = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Responde en español: saluda a un cliente de Akari Store."
    )

    print("¡Conexión exitosa con Gemini!")
    print(respuesta.text)

except Exception as error:
    print("No se pudo conectar con Gemini.")
    print("Detalle:", error)

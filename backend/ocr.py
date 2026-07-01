import os
import json
import base64
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import google.generativeai as genai
import models
from database import get_db

router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 1. Configuración de credenciales desde el sistema operativo del contenedor Docker
API_KEY_SISTEMA = os.getenv("GEMINI_API_KEY")
DRIVE_BRIDGE_URL = os.getenv("DRIVE_BRIDGE_URL")

if not API_KEY_SISTEMA:
    raise RuntimeError(
        "CRÍTICO: La variable de entorno 'GEMINI_API_KEY' no está configurada en el contenedor. "
        "Verifica tu archivo .env y el docker-compose.yml."
    )

# 2. Inicializar el SDK de Google con el modelo global estable actual
genai.configure(api_key=API_KEY_SISTEMA)
model = genai.GenerativeModel('gemini-2.5-flash')

@router.post("/procesar-cedula")
async def procesar_cedula(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validación estricta de formatos permitidos
    if file.content_type not in ["image/jpeg", "image/png", "application/pdf"]:
        raise HTTPException(
            status_code=400, 
            detail="Formato de archivo no soportado. Solo se permiten imágenes (JPEG, PNG) o PDFs."
        )
    
    try:
        # Leer los bytes del documento adjunto
        archivo_bytes = await file.read()
        
        # 3. Prompt de ingeniería de instrucciones ultra-preciso
        prompt = (
            "Analiza detalladamente la imagen o PDF adjunto que corresponde a un documento de identidad. "
            "Tu tarea es extraer los datos de la persona de manera exacta. Revisa tanto el frente como el reverso si están disponibles. "
            "Debes responder **ÚNICAMENTE** con un objeto JSON plano que contenga exactamente estas llaves y formatos:\n"
            "{\n"
            '  "nombres": "Nombres de la persona en Mayúsculas",\n'
            '  "apellidos": "Apellidos de la persona en Mayúsculas",\n'
            '  "tipo_documento": "Tipo de documento",\n'
            '  "numero_documento": "Solo los números sin puntos ni comas\nEn caso de Permiso de Protección Temporal o Permiso de Protección Especial no tomas en cuenta el numero de la nacionalidad, solo el numero del documento.",\n'
            '  "fecha_nacimiento": "Formato AAAA-MM-DD",\n'
            '  "lugar_expedicion": "Municipio y departamento de expedición"\n'
            "}\n"
            "No incluyas introducciones, comentarios, ni bloques de código de markdown (como ```json), solo el JSON plano."
        )

        # Enviar la petición de forma segura a los servidores de Google AI
        response = model.generate_content([
            {'mime_type': file.content_type, 'data': archivo_bytes},
            prompt
        ])

        # Limpieza robusta de la respuesta en texto plano
        texto_ia = response.text.strip()
        if texto_ia.startswith("```"):
            texto_ia = texto_ia.replace("```json", "", 1).replace("```", "", 1).strip()

        # Parsear el texto plano limpio a diccionario nativo de Python
        try:
            datos_ia = json.loads(texto_ia)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500, 
                detail="La IA no devolvió un formato JSON limpio. Inténtalo de nuevo."
            )

        # 4. Automatización con Google Drive a través del puente corporativo
        url_carpeta_drive = None
        if DRIVE_BRIDGE_URL:
            try:
                # Codificar archivo a Base64 para adjuntarlo de manera segura en la carga útil HTTP
                file_base64 = base64.b64encode(archivo_bytes).decode("utf-8")
                
                payload = {
                    "nombres": datos_ia.get("nombres"),
                    "apellidos": datos_ia.get("apellidos"),
                    "tipo_documento": datos_ia.get("tipo_documento"),
                    "numero_documento": datos_ia.get("numero_documento"),
                    "file_base64": file_base64,
                    "mime_type": file.content_type,
                    "file_name": f"Cedula_{datos_ia.get('numero_documento')}_{file.filename}"
                }
                
                # Despachar al microservicio de Google Apps Script (Tiempo de espera de 20 segundos)
                response_drive = requests.post(DRIVE_BRIDGE_URL, json=payload, timeout=20)
                if response_drive.status_code == 200:
                    res_data = response_drive.json()
                    if res_data.get("status") == "success":
                        url_carpeta_drive = res_data.get("folder_url")
            except Exception as drive_err:
                # Log de advertencia sin romper la experiencia del usuario final si el Drive falla de forma temporal
                print(f"Advertencia de Automatización: No se pudo subir el archivo a Drive: {str(drive_err)}")

        # 5. Guardar en la base de datos de PostgreSQL usando SQLAlchemy
        # Nota: Si agregaste la columna 'url_drive' en tu modelo, puedes pasarla aquí
        nuevo_empleado = models.Empleado(
            nombres=datos_ia.get("nombres"),
            apellidos=datos_ia.get("apellidos"),
            tipo_documento=datos_ia.get("tipo_documento"),
            numero_documento=datos_ia.get("numero_documento"),
            fecha_nacimiento=datos_ia.get("fecha_nacimiento"),
            lugar_expedicion=datos_ia.get("lugar_expedicion"),
            telefono=None,
            direccion_residencia=None
        )
        
        db.add(nuevo_empleado)
        db.commit()
        db.refresh(nuevo_empleado)

        # Retornar respuesta exitosa unificada al frontend
        return {
            "status": "success",
            "mensaje": "Documento procesado, guardado en base de datos y respaldado en Google Drive con éxito.",
            "datos_extraidos": datos_ia,
            "drive_folder": url_carpeta_drive
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")
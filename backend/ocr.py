import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import google.generativeai as genai
import models
from database import get_db

# 1. Creamos el Router para agrupar nuestras rutas de IA
router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 2. Configuramos la API Key de Gemini desde las variables de entorno
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

@router.post("/procesar-cedula")
async def procesar_cedula(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Validación: Solo permitir imágenes o PDFs
    if not file.content_type.startswith("image/") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Formato de archivo no válido. Sube una imagen o un PDF.")

    try:
        # A) Leer el archivo directamente en la memoria RAM en formato de bytes
        archivo_bytes = await file.read()

        # B) Inicializar el modelo pro de Gemini ideal para visión y análisis documental
        model = genai.GenerativeModel('gemini-2.5-flash')

        # C) Prompt Estructurado: Instrucciones estrictas para forzar una respuesta JSON
        prompt = (
            "Analiza detalladamente la imagen o PDF adjunto que corresponde a una cédula de ciudadanía de Colombia. "
            "Tu tarea es extraer los datos del ciudadano de manera exacta. Revisa tanto el frente como el reverso si están disponibles. "
            "Debes responder **ÚNICAMENTE** con un objeto JSON plano que contenga exactamente estas llaves y formatos:\n"
            "{\n"
            '  "nombres": "Nombres del ciudadano en Mayúsculas",\n'
            '  "apellidos": "Apellidos del ciudadano en Mayúsculas",\n'
            '  "tipo_documento": "C.C.",\n'
            '  "numero_documento": "Solo los números sin puntos ni comas",\n'
            '  "fecha_nacimiento": "Formato AAAA-MM-DD",\n'
            '  "lugar_expedicion": "Municipio y departamento de expedición"\n'
            "}\n"
            "No incluyas introducciones, comentarios, ni bloques de código de markdown (como ```json), solo el JSON plano."
        )

        # D) Enviar los bytes del archivo y las instrucciones a la API de Google
        response = model.generate_content([
            {'mime_type': file.content_type, 'data': archivo_bytes},
            prompt
        ])

        # E) Convertir la respuesta de texto de Gemini a un Diccionario de Python
        datos_ia = json.loads(response.text.strip())

        # F) Persistencia en Postgres: Verificar si el ciudadano ya existe mediante su cédula
        empleado_existente = db.query(models.Empleado).filter(
            models.Empleado.numero_documento == datos_ia["numero_documento"]
        ).first()

        if not empleado_existente:
            # Si no existe, creamos el registro con los campos limpios de la IA
            nuevo_empleado = models.Empleado(
                nombres=datos_ia["nombres"],
                apellidos=datos_ia["apellidos"],
                tipo_documento=datos_ia["tipo_documento"],
                numero_documento=datos_ia["numero_documento"],
                fecha_nacimiento=datos_ia["fecha_nacimiento"] if datos_ia["fecha_nacimiento"] else None,
                lugar_expedicion=datos_ia["lugar_expedicion"]
            )
            db.add(nuevo_empleado)
            db.commit()      # Guardar físicamente en la base de datos
            db.refresh(nuevo_empleado) # Traer el ID generado por la base de datos
            return {"status": "creado_y_guardado", "data": nuevo_empleado}
        
        return {"status": "ya_existia_en_sistema", "data": empleado_existente}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="La IA no devolvió un formato JSON limpio. Inténtalo de nuevo.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")
import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
import google.generativeai as genai
import models
from database import get_db

# 1. Creamos el Router de FastAPI para agrupar los endpoints de IA
router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 2. Inicialización automática sugerida por la documentación oficial de Google.
# El SDK buscará por sí solo la variable de entorno 'GEMINI_API_KEY' que Docker
# inyecta de forma segura desde tu archivo local .env
genai.configure()

@router.post("/procesar-cedula")
async def procesar_cedula(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Validación estricta del tipo de archivo (Imágenes o PDFs)
    if not file.content_type.startswith("image/") and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Formato de archivo no válido. Sube una imagen o un PDF."
        )

    try:
        # A) Leer los bytes del documento directamente en la memoria RAM
        archivo_bytes = await file.read()

        # B) Inicializar el modelo recomendado para el nivel gratuito (Free Tier de Costo $0)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # C) Prompt de ingeniería de instrucciones para asegurar la extracción exacta del formato colombiano
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

        # D) Enviar la petición de forma segura a los servidores de Google utilizando la Auth Key invisible
        response = model.generate_content([
            {'mime_type': file.content_type, 'data': archivo_bytes},
            prompt
        ])

        # E) Parsear el texto plano devuelto por la IA a un diccionario nativo de Python
        datos_ia = json.loads(response.text.strip())

        # F) Capa de persistencia (PostgreSQL): Evitar duplicados mediante el número de documento
        empleado_existente = db.query(models.Empleado).filter(
            models.Empleado.numero_documento == datos_ia["numero_documento"]
        ).first()

        if not empleado_existente:
            # Si el ciudadano es nuevo, lo creamos y lo guardamos en la base de datos
            nuevo_empleado = models.Empleado(
                nombres=datos_ia["nombres"],
                apellidos=datos_ia["apellidos"],
                tipo_documento=datos_ia["tipo_documento"],
                numero_documento=datos_ia["numero_documento"],
                fecha_nacimiento=datos_ia["fecha_nacimiento"] if datos_ia["fecha_nacimiento"] else None,
                lugar_expedicion=datos_ia["lugar_expedicion"]
            )
            db.add(nuevo_empleado)
            db.commit()                # Confirmar cambios físicos en Postgres
            db.refresh(nuevo_empleado) # Capturar el ID autogenerado
            return {"status": "creado_y_guardado", "data": nuevo_empleado}
        
        # Si ya existía, retornamos los datos existentes para no duplicar llaves en la BD
        return {"status": "ya_existia_en_sistema", "data": empleado_existente}

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="La IA no devolvió un formato JSON limpio. Inténtalo de nuevo."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error en el servidor: {str(e)}"
        )
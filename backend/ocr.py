import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import google.generativeai as genai
import models
from database import get_db

router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 1. Leemos la variable directamente del sistema operativo del contenedor
API_KEY_SISTEMA = os.getenv("GEMINI_API_KEY")

# 2. Si viene vacía, lanzamos un error claro antes de que Google falle por el ADC
if not API_KEY_SISTEMA:
    raise RuntimeError(
        "CRÍTICO: La variable de entorno 'GEMINI_API_KEY' no está configurada en el contenedor. "
        "Verifica tu archivo .env y el docker-compose.yml."
    )

# 3. Configuramos el SDK con la llave del entorno
genai.configure(api_key=API_KEY_SISTEMA)

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
        model = genai.GenerativeModel('gemini-2.5-flash')

        # C) Prompt de ingeniería de instrucciones para asegurar la extracción exacta del formato colombiano
        prompt = (
            "Analiza detalladamente la imagen o PDF adjunto que corresponde a un documento de identidad. "
            "Tu tarea es extraer los datos de la persona de manera exacta. Revisa tanto el frente como el reverso si están disponibles. "
            "Debes responder **ÚNICAMENTE** con un objeto JSON plano que contenga exactamente estas llaves y formatos:\n"
            "{\n"
            '  "nombres": "Nombres de la persona en Mayúsculas",\n'
            '  "apellidos": "Apellidos de la persona en Mayúsculas",\n'
            '  "tipo_documento": "Tipo de documento",\n'
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

        texto_ia = response.text.strip()
        
        # Si la IA ignora las instrucciones y mete bloques de código Markdown, los eliminamos a la fuerza
        if texto_ia.startswith("```"):
            # Quita el inicio ```json o ``` y el final ```
            texto_ia = texto_ia.replace("```json", "", 1).replace("```", "", 1)
            # Volvemos a limpiar espacios o saltos de línea restantes
            texto_ia = texto_ia.strip()

        # E) Parsear el texto plano devuelto por la IA a un diccionario nativo de Python
        datos_ia = json.loads(texto_ia)

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
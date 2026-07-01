import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import google.generativeai as genai
import models
from database import get_db

router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# BYPASS DE ADC: Nos aseguramos de configurar la API key usando la variable nativa del entorno
# El SDK de Google revisa automáticamente os.environ["GEMINI_API_KEY"] de forma prioritaria
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

@router.post("/procesar-cedula")
async def procesar_cedula(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    if not file.content_type.startswith("image/") and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Formato de archivo no válido. Sube una imagen o un PDF."
        )

    try:
        archivo_bytes = await file.read()

        # Inicializamos el modelo de forma limpia. Al estar configurada la API key globalmente,
        # el SDK dejará de buscar archivos de cuentas de servicio (ADC).
        model = genai.GenerativeModel('gemini-2.0-flash')

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

        response = model.generate_content([
            {'mime_type': file.content_type, 'data': archivo_bytes},
            prompt
        ])

        datos_ia = json.loads(response.text.strip())

        empleado_existente = db.query(models.Empleado).filter(
            models.Empleado.numero_documento == datos_ia["numero_documento"]
        ).first()

        if not empleado_existente:
            nuevo_empleado = models.Empleado(
                nombres=datos_ia["nombres"],
                apellidos=datos_ia["apellidos"],
                tipo_documento=datos_ia["tipo_documento"],
                numero_documento=datos_ia["numero_documento"],
                fecha_nacimiento=datos_ia["fecha_nacimiento"] if datos_ia["fecha_nacimiento"] else None,
                lugar_expedicion=datos_ia["lugar_expedicion"]
            )
            db.add(nuevo_empleado)
            db.commit()
            db.refresh(nuevo_empleado)
            return {"status": "creado_y_guardado", "data": nuevo_empleado}
        
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
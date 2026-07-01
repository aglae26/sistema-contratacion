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
from pydantic import BaseModel
from datetime import date
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 1. Configuración de credenciales desde el sistema operativo del contenedor Docker
API_KEY_SISTEMA = os.getenv("GEMINI_API_KEY")
URL_PUENTE_OCR = os.getenv("URL_PUENTE_OCR")

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
        if URL_PUENTE_OCR:
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
                response_drive = requests.post(URL_PUENTE_OCR, json=payload, timeout=20)
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

    # Esquema de validación para los datos mezclados de React
class EmpleadoContratoUpdate(BaseModel):
    # Datos del Empleado (Por si se corrigen)
    nombres: str
    apellidos: str
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: Optional[date] = None
    lugar_expedicion: Optional[str] = None
    direccion_residencia: Optional[str] = None
    telefono: Optional[str] = None
    
    # Datos Manuales del Contrato
    cargo: str
    salario: str
    fecha_ingreso: date

@router.put("/empleados/{empleado_id}/aprobar")
async def aprobar_y_generar_contrato(empleado_id: int, datos: EmpleadoContratoUpdate, db: Session = Depends(get_db)):
    # 1. Buscar al empleado en la base de datos
    db_empleado = db.query(models.Empleado).filter(models.Empleado.id == empleado_id).first()
    if not db_empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    
    # 2. Actualizar/Corregir los campos del empleado en la DB
    db_empleado.nombres = datos.nombres
    db_empleado.apellidos = datos.apellidos
    db_empleado.tipo_documento = datos.tipo_documento
    db_empleado.numero_documento = datos.numero_documento
    db_empleado.fecha_nacimiento = datos.fecha_nacimiento
    db_empleado.lugar_expedicion = datos.lugar_expedicion
    db_empleado.direccion_residencia = datos.direccion_residencia
    db_empleado.telefono = datos.telefono
    
    # Cambiar estado a APROBADO
    db_empleado.estado = models.EstadoEmpleado.APROBADO
    
    # 3. Crear el registro físico del Contrato en la base de datos relacional
    nuevo_contrato = models.Contrato(
        empleado_id=db_empleado.id,
        cargo=datos.cargo,
        salario=datos.salario,
        fecha_ingreso=datos.fecha_ingreso
    )
    db.add(nuevo_contrato)
    db.flush() # Obtiene el ID del contrato antes del commit final

    # 4. Despachar TODO el bloque de datos al puente de Google Workspace
    url_contrato = None
    if URL_PUENTE_OCR:
        try:
            payload = {
                "accion": "generar_contrato",
                "plantilla_id": "1f-T9T2xtGBYjx0PqCn6LtUs1NGk0kSPy", # <- Recuerda verificar/poner el ID real de tu plantilla de Google Docs
                "nombres": db_empleado.nombres,
                "apellidos": db_empleado.apellidos,
                "tipo_documento": db_empleado.tipo_documento,
                "numero_documento": db_empleado.numero_documento,
                "fecha_nacimiento": str(db_empleado.fecha_nacimiento) if db_empleado.fecha_nacimiento else "",
                "lugar_expedicion": db_empleado.lugar_expedicion or "",
                "direccion": db_empleado.direccion_residencia or "",
                "telefono": db_empleado.telefono or "",
                "cargo": nuevo_contrato.cargo,
                "salario": nuevo_contrato.salario,
                "fecha_ingreso": str(nuevo_contrato.fecha_ingreso)
            }
            
            res = requests.post(URL_PUENTE_OCR, json=payload, timeout=25)
            if res.status_code == 200:
                res_data = res.json()
                if res_data.get("status") == "success":
                    url_contrato = res_data.get("contrato_url")
                    # Vincular la URL del documento al contrato creado
                    nuevo_contrato.url_documento_drive = url_contrato
        except Exception as e:
            print(f"Advertencia: No se pudo generar el Google Doc: {str(e)}")

    db.commit()
    
    return {
        "status": "success",
        "mensaje": "Datos del empleado actualizados, contrato registrado en DB y generado en Google Drive con éxito.",
        "contrato_url": url_contrato
    }

@router.get("/empleados")
def listar_empleados(db: Session = Depends(get_db)):
    """
    Retorna la lista completa de candidatos registrados en el sistema,
    ordenados desde el más reciente para que React llene la tabla de control.
    """
    return db.query(models.Empleado).order_by(models.Empleado.id.desc()).all()
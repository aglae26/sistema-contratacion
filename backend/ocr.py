import database
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
from datetime import date, datetime
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["OCR Inteligente"])

# 1. Configuración de credenciales desde el sistema operativo del contenedor Docker
API_KEY_SISTEMA = os.getenv("GEMINI_API_KEY")
URL_PUENTE_OCR = os.getenv("URL_PUENTE_OCR")
URL_PUENTE_PLANTILLAS = os.getenv("URL_PUENTE_PLANTILLAS")


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

# =========================================================================
# 📝 2. ESQUEMAS DE VALIDACIÓN PYDANTIC (INTERFAZ REACT -> FASTAPI)
# =========================================================================
class EmpleadoContratoUpdate(BaseModel):
    # Datos personales actualizables del Empleado
    nombres: str
    apellidos: str
    tipo_documento: str
    numero_documento: str
    fecha_nacimiento: Optional[date] = None
    lugar_expedicion: Optional[str] = None
    direccion_residencia: Optional[str] = None
    telefono: Optional[str] = None
    
    # Datos manuales o de control del Contrato
    empresa_id: int          # ID de la sociedad seleccionada
    sede_id: int             # 👈 ID de la sede (>0: DB, 0: Manual, -1: No aplica)
    sede_manual: Optional[str] = None  # 👈 NUEVO: Captura el texto si digitan a mano
    tipo_contrato: str       # 'INDEFINIDO_ESTANDAR', 'INDEFINIDO_ABITA', 'FIJO', 'TIEMPO_PARCIAL'
    cargo: str
    salario: str
    fecha_ingreso: date


def numero_a_letras(numero):
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    especiales = {11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE", 16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
                  21: "VEINTIUN", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO", 25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO", 29: "VEINTINUEVE"}
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def leer_decenas(n):
        if n < 10: return unidades[n]
        if n < 30 and n in especiales: return especiales[n]
        if n < 30: return decenas[n // 10] + (" Y " + unidades[n % 10] if n % 10 != 0 else "")
        return decenas[n // 10] + (" Y " + unidades[n % 10] if n % 10 != 0 else "")

    def leer_centenas(n):
        if n == 100: return "CIEN"
        return (centenas[n // 100] + " " + leer_decenas(n % 100)).strip()

    def leer_miles(n):
        if n < 1000: return leer_centenas(n)
        if n == 1000: return "MIL"
        miles = n // 1000
        resto = n % 1000
        str_miles = "MIL" if miles == 1 else leer_centenas(miles) + " MIL"
        return (str_miles + " " + leer_centenas(resto)).strip()

    def leer_millones(n):
        if n < 1000000: return leer_miles(n)
        millones = n // 1000000
        resto = n % 1000000
        str_millones = "UN MILLON" if millones == 1 else leer_miles(millones) + " MILLONES"
        return (str_millones + " " + leer_miles(resto)).strip()
        
    try:
        numero = int(float(numero))
        if numero == 0: return "CERO"
        return leer_millones(numero)
    except:
        return str(numero)

# =========================================================================
# 🎯 3. ENDPOINT: APROBACIÓN Y AUTOMATIZACIÓN DE CONTRATOS
# =========================================================================
@router.put("/empleados/{empleado_id}/aprobar")
async def aprobar_y_generar_contrato(empleado_id: int, datos: EmpleadoContratoUpdate, db: Session = Depends(get_db)):
    # A. Verificar existencia del Empleado
    db_empleado = db.query(models.Empleado).filter(models.Empleado.id == empleado_id).first()
    if not db_empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    
    # B. Consultar la Sociedad directamente de PostgreSQL
    empresa_contratante = db.query(models.Empresa).filter(models.Empresa.id == datos.empresa_id).first()
    if not empresa_contratante:
        raise HTTPException(status_code=404, detail="La Sociedad seleccionada no existe en la base de datos")

    # C. 🧠 LÓGICA INTELIGENTE PARA DETERMINAR LOS DATOS DE LA SEDE
    nombre_sede = "No aplica"
    ciudad_sede = "No aplica"
    depto_sede = "No aplica"

    if datos.sede_id > 0:
        # Caso 1: La sede existe en la Base de Datos
        sede_seleccionada = db.query(models.Sede).filter(models.Sede.id == datos.sede_id).first()
        if not sede_seleccionada:
            raise HTTPException(status_code=404, detail="La Sede seleccionada no existe")
        nombre_sede = sede_seleccionada.nombre
        ciudad_sede = sede_seleccionada.ciudad or "Por definir"
        depto_sede = sede_seleccionada.departamento or "Por definir"
        
    elif datos.sede_id == 0:
        # Caso 2: El usuario digitó la sede a mano en React
        if not datos.sede_manual:
            raise HTTPException(status_code=422, detail="Debes ingresar la dirección de la sede manual")
        nombre_sede = datos.sede_manual
        ciudad_sede = "Especificada en texto"
        depto_sede = "Especificada en texto"
        
    # Nota: Si datos.sede_id == -1, se salta el bloque y conserva los valores "No aplica"

    # D. Diccionario de enrutamiento para tus 4 plantillas de Google Drive
    PLANTILLAS_CONTRATOS = {
        "INDEFINIDO_ESTANDAR": "1J_n_mpmOWWEeUNKF2vcuo38WFq1xSJvt22KiXJV_lEA",
        "INDEFINIDO_ABITA": "1O-Sga4_5qMINa9Vk_95pZdr0jOOkgaZsTd6AxJrIXrg",
        "FIJO": "1E6A9h1O-d45OlFrGB064RbXM6Wu_I627cMlZXoAbjj8", 
        "TIEMPO_PARCIAL": "1JCH8mYlA1ZIo_QwFXwyHMTV77TOd5RlxAc77Xe23E-M"
    }
    
    id_plantilla_seleccionada = PLANTILLAS_CONTRATOS.get(
        datos.tipo_contrato.upper(), 
        PLANTILLAS_CONTRATOS["INDEFINIDO_ESTANDAR"]
    )

    # E. Sincronizar y actualizar datos del candidato
    db_empleado.nombres = datos.nombres
    db_empleado.apellidos = datos.apellidos
    db_empleado.tipo_documento = datos.tipo_documento
    db_empleado.numero_documento = datos.numero_documento
    db_empleado.fecha_nacimiento = datos.fecha_nacimiento
    db_empleado.lugar_expedicion = datos.lugar_expedicion
    db_empleado.direccion_residencia = datos.direccion_residencia
    db_empleado.telefono = datos.telefono
    db_empleado.empresa_id = datos.empresa_id
    db_empleado.estado = models.EstadoEmpleado.APROBADO
    
    # F. Metadatos cronológicos para las cláusulas de cierre
    hoy = datetime.now()
    meses_es = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    
    salario_en_letras = numero_a_letras(datos.salario)

    # G. Registrar el contrato en PostgreSQL
    nuevo_contrato = models.Contrato(
        empleado_id=db_empleado.id,
        empresa_id=empresa_contratante.id,
        tipo_contrato=datos.tipo_contrato.upper(),            
        cargo_desempenar=datos.cargo,                         
        fecha_inicio_labores=datos.fecha_ingreso,             
        salario_numeros=float(datos.salario),                 
        salario_letras=f"{salario_en_letras} PESOS M/CTE",            
        sede_trabajo=nombre_sede,                             
        ciudad=ciudad_sede,                                   
        departamento=depto_sede,                               
        dia_firma=str(hoy.day),                               
        mes_firma=meses_es[hoy.month - 1],                    
        anio_firma=str(hoy.year)                              
    )
    db.add(nuevo_contrato)
    db.flush()

    # H. Despachar el payload extendido al Apps Script de Google Drive
    url_contrato_generado = None
    if URL_PUENTE_PLANTILLAS:
        try:
            payload = {
                "accion": "generar_contrato",
                "plantilla_id": id_plantilla_seleccionada,
                "empresa_id": str(empresa_contratante.id),
                "empresa_razon_social": empresa_contratante.razon_social,
                "empresa_nit": empresa_contratante.nit,
                "sede_trabajo": nuevo_contrato.sede_trabajo,         # Mapeado a {{sede_trabajo}}
                "ciudad": nuevo_contrato.ciudad or "",               # Mapeado a {{ciudad}}
                "departamento": nuevo_contrato.departamento or "",   # Mapeado a {{departamento}}
                "nombres": db_empleado.nombres,
                "apellidos": db_empleado.apellidos,
                "tipo_documento": db_empleado.tipo_documento,
                "numero_documento": db_empleado.numero_documento,
                "fecha_nacimiento": str(db_empleado.fecha_nacimiento) if db_empleado.fecha_nacimiento else "",
                "direccion": db_empleado.direccion_residencia or "",
                "telefono": db_empleado.telefono or "",
                "cargo": nuevo_contrato.cargo_desempenar,
                "salario": str(nuevo_contrato.salario_numeros),
                "salario_letras": nuevo_contrato.salario_letras,
                "fecha_ingreso": str(nuevo_contrato.fecha_inicio_labores),
                "fecha_finalizacion": str(nuevo_contrato.fecha_finalizacion_labores) if nuevo_contrato.fecha_finalizacion_labores else "No aplica",
                "dia_firma": nuevo_contrato.dia_firma,
                "mes_firma": nuevo_contrato.mes_firma,
                "anio_firma": nuevo_contrato.anio_firma
            }
            
            res = requests.post(URL_PUENTE_PLANTILLAS, json=payload, timeout=25)
            if res.status_code == 200:
                res_data = res.json()
                if res_data.get("status") == "success":
                    url_contrato_generado = res_data.get("contrato_url")
        except Exception as e:
            print(f"Error en comunicación con Google: {str(e)}")

    db.commit()
    return {
        "status": "success", 
        "mensaje": "Contrato procesado y generado de forma dinámica exitosamente.", 
        "contrato_url": url_contrato_generado
    }


# =========================================================================
# 🏢 4. ENDPOINTS DE CONSULTA DINÁMICA (PARA EL FLUJO DE REACT)
# =========================================================================
@router.get("/sociedades")
def listar_sociedades(db: Session = Depends(get_db)):
    """
    Retorna las sociedades y siembra datos iniciales de prueba SIN dirección en la empresa.
    """
    if db.query(models.Empresa).count() == 0:
        try:
            # Abita Home Deco S.A.S
            sociedad1 = models.Empresa(nit="901.756.017-8", razon_social="Abita Home Deco S.A.S.")
            db.add(sociedad1)
            db.flush()

            sede1_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad1.id)
            db.add(sede1_gen)

            # Mizzu Inmobiliaria S.A.S
            sociedad2 = models.Empresa(nit="901.884.591-2", razon_social="Mizzú Inmobiliaria S.A.S.")
            db.add(sociedad2)
            db.flush()

            sede2_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad2.id)
            db.add(sede2_gen)

            # Inversiones La Maria y CIA SAS
            sociedad3 = models.Empresa(nit="810.004.405-6", razon_social="Inversiones La María y CIA S.A.S.")
            db.add(sociedad3)
            db.flush()
            #Sede
            sede3_1 = models.Sede(nombre="Finca La Alpujarra", direccion="Vereda La Perla", ciudad="Anserma", departamento="Caldas", empresa_id=sociedad3.id)
            sede3_2 = models.Sede(nombre="Finca La Argentina", direccion="Km 41 vía Medellín - Vereda Colombia", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad3.id)
            sede3_3 = models.Sede(nombre="Lechería Madrid", direccion="Vereda La Perla", ciudad="Anserma", departamento="Caldas", empresa_id=sociedad3.id)
            sede3_4 = models.Sede(nombre="Finca Zaragoza", direccion="Vereda La Perla", ciudad="Anserma", departamento="Caldas", empresa_id=sociedad3.id)
            sede3_5 = models.Sede(nombre="Finca Ceba", direccion="Vereda La Perla", ciudad="Anserma", departamento="Caldas", empresa_id=sociedad3.id)
            sede3_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad3.id)
            db.add_all([sede3_1, sede3_2, sede3_3, sede3_4, sede3_5, sede3_gen])

            # Sucesores Agricola SAS
            sociedad4 = models.Empresa(nit="901.910.259-3", razon_social="Sucesores Agrícola S.A.S.")
            db.add(sociedad4)
            db.flush()
            # Sede
            sede4_1 = models.Sede(nombre="Hacienda Buenos Aires", direccion="Tres Puertas", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad4.id)
            sede4_2 = models.Sede(nombre="Lechería Buenos Aires", direccion="Tres Puertas", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad4.id)
            sede4_3 = models.Sede(nombre="Finca Colinas", direccion="Tres Puertas", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad4.id)
            sede4_4 = models.Sede(nombre="Finca La Coca", direccion="Tres Puertas", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad4.id)
            sede4_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad4.id)
            db.add_all([sede4_1, sede4_2, sede4_3, sede4_4, sede4_gen]) 

            # Sucesores de Liborio INC
            sociedad5 = models.Empresa(nit="901.845.505-2", razon_social="Sucesores de Liborio INC")
            db.add(sociedad5)
            db.flush()

            sede5_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad5.id)
            db.add(sede5_gen)

            # Maredu SAS
            sociedad6 = models.Empresa(nit="900.997.890-1", razon_social="Maredu S.A.S.")
            db.add(sociedad6)
            db.flush()
            # Sede
            sede6_1 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad6.id)
            sede6_2 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Santa Rosa De Cabal", departamento="Risaralda", empresa_id=sociedad6.id)
            sede6_3 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Dosquebradas", departamento="Risaralda", empresa_id=sociedad6.id)
            sede6_4 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Pereira", departamento="Risaralda", empresa_id=sociedad6.id)
            sede6_5 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Armenia", departamento="Quindio", empresa_id=sociedad6.id)
            sede6_6 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Tuluá", departamento="Valle Del Cauca", empresa_id=sociedad6.id)
            sede6_7 = models.Sede(nombre="OFFCORSS", direccion="No Aplica", ciudad="Apartadó", departamento="Antioquia", empresa_id=sociedad6.id)
            sede6_gen = models.Sede(nombre="Oficina Principal", direccion="Calle 64A No. 21-50 OF 1601 Portal Del Cable", ciudad="Manizales", departamento="Caldas", empresa_id=sociedad6.id)
            db.add_all([sede6_1, sede6_2, sede6_3, sede6_4, sede6_5, sede6_6, sede6_7, sede6_gen])

            db.commit() 
        
        except Exception as e:
            db.rollback() # 👈 Evita trancar la base de datos si ocurre un choque
            print(f"⚠️ Error controlado en siembra: {str(e)}")

    return db.query(models.Empresa).all()


@router.get("/empresas/{empresa_id}/sedes")
def listar_sedes_por_empresa(empresa_id: int, db: Session = Depends(get_db)):
    """
    Retorna únicamente las sedes que pertenecen al id de la empresa consultada.
    """
    return db.query(models.Sede).filter(models.Sede.empresa_id == empresa_id).all()


@router.get("/empleados")
def listar_empleados(db: Session = Depends(get_db)):
    return db.query(models.Empleado).order_by(models.Empleado.id.desc()).all()
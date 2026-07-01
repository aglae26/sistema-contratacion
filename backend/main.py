from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <-- 1. Importamos el middleware
from database import engine
import models
from ocr import router as ocr_router

# Creamos las tablas en la base de datos al arrancar
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sistema de Contratación - API",
    description="Backend para la gestión documental y extracción de datos con IA",
    version="1.0.0"
)

# 2. Configurar la lista de orígenes permitidos (Tu Frontend de React)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# 3. Añadir el escudo de confianza CORS a la aplicación
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Permite que React le hable al Backend
    allow_credentials=True,
    allow_methods=["*"],              # Permite GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],              # Permite todos los encabezados estándar
)

# Ruta base de prueba de salud del sistema
@app.get("/")
def home():
    return {"mensaje": "Backend, Base de Datos e IA listos"}

# Registrar el enrutador del módulo OCR
app.include_router(ocr_router)
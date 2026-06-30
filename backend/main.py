from fastapi import FastAPI
import models
import ocr  # <-- Importar tu nuevo archivo de IA
from database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Contratación - MVP")

# Registrar las rutas del OCR en la aplicación principal
app.include_router(ocr.router)

@app.get("/")
def inicio():
    return {"mensaje": "Backend, Base de Datos e IA listos"}
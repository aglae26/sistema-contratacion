from fastapi import FastAPI

app = FastAPI(title="Sistema de Contratación - MVP")

@app.get("/")
def inicio():
    return {"mensaje": "Backend funcionando perfectamente"} 
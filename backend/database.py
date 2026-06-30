from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 1. Traemos la ruta de la base de datos desde las variables de entorno de Docker
DATABASE_URL = os.getenv("DATABASE_URL")

# 2. El 'engine' es el motor encargado de gestionar las conexiones físicas a Postgres
engine = create_engine(DATABASE_URL)

# 3. Cada vez que hagamos una consulta, usaremos un objeto Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 'Base' será la clase madre de la cual nacerán todas nuestras tablas
Base = declarative_base()

# 5. Función auxiliar para abrir y cerrar la base de datos de forma segura en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
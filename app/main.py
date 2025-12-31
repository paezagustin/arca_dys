from fastapi import FastAPI
from app.core.database import engine, Base
from app.api import mp

app = FastAPI()

# Crear tablas
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(mp.router)

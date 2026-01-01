from fastapi import FastAPI
from app.core.database import engine, Base
from app.api import mp
from app.api import pagina
app = FastAPI()

# Crear tablas
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(mp.router)
app.include_router(pagina.router)

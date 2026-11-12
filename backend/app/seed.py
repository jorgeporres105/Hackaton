from .database import engine, SessionLocal, Base
from . import models

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(models.Usuario).first():
        db.add_all([
            models.Usuario(nombre="Admin Sistema", email="admin@exb.org.bo", password_hash="admin123", rol="admin"),
            models.Usuario(nombre="Técnico Finanzas", email="tecnico@exb.org.bo", password_hash="tecnico123", rol="tecnico"),
            models.Usuario(nombre="Auditor Consulta", email="consulta@exb.org.bo", password_hash="consulta123", rol="consulta"),
        ])
    if not db.query(models.TipoCambio).first():
        db.add_all([models.TipoCambio(gestion=g, mes=m, tasa=6.96) for g in (2025, 2026) for m in range(1, 13)])
    db.commit()
    db.close()
    print("Tablas creadas correctamente en Neon.")

if __name__ == "__main__":
    init_db()

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import get_db
from . import models, etl_excel, reports

app = FastAPI(title="Sistema de Control Presupuestario - EXB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: str
    password: str

class TipoCambioUpdate(BaseModel):
    gestion: int
    tasa: float
    usuario_id: int

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "conectada correctamente"}

# 0. LOGIN CON CONTRASEÑA
@app.post("/api/login")
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(
        models.Usuario.email == creds.email,
        models.Usuario.password_hash == creds.password,
        models.Usuario.activo == True
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")

    db.add(models.Auditoria(
        usuario_id=user.id,
        accion="INICIO_SESION",
        detalle=f"Ingreso al sistema con rol {user.rol.upper()}"
    ))
    db.commit()

    return {
        "id": user.id,
        "nombre": user.nombre,
        "email": user.email,
        "rol": user.rol
    }

# 1. IMPORTAR EXCEL (SOLO ADMIN)
@app.post("/api/importar")
async def importar_archivo(
    file: UploadFile = File(...),
    gestion: int = Form(2026),
    usuario_id: int = Form(...),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario or usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: Solo un Administrador puede importar datos.")

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")

    contenido = await file.read()
    resultado = etl_excel.procesar_excel_exb(contenido, file.filename, gestion, usuario_id, db)
    return {"mensaje": "Importación completada con éxito", "detalle": resultado}

# 1.5 ACTUALIZAR TIPO DE CAMBIO (SOLO ADMIN)
@app.get("/api/tipos-cambio")
def listar_tipos_cambio(db: Session = Depends(get_db)):
    tcs = db.query(models.TipoCambio).filter(models.TipoCambio.mes == 1).all()
    return [{"gestion": t.gestion, "tasa": t.tasa} for t in tcs]

@app.put("/api/tipos-cambio")
def actualizar_tipo_cambio(data: TipoCambioUpdate, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == data.usuario_id).first()
    if not usuario or usuario.rol != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: Solo el Administrador puede modificar el tipo de cambio.")

    registros = db.query(models.TipoCambio).filter(models.TipoCambio.gestion == data.gestion).all()
    if not registros:
        for m in range(1, 13):
            db.add(models.TipoCambio(gestion=data.gestion, mes=m, tasa=data.tasa))
    else:
        for r in registros:
            r.tasa = data.tasa

    db.add(models.Auditoria(
        usuario_id=usuario.id,
        accion="MODIFICACION_TC",
        detalle=f"Tipo de cambio Gestión {data.gestion} actualizado a {data.tasa} Bs/USD"
    ))
    db.commit()
    return {"mensaje": f"Tipo de cambio {data.gestion} actualizado a {data.tasa}"}

# 2. CATÁLOGOS PARA FILTROS COMBINADOS
@app.get("/api/filtros")
def obtener_filtros(db: Session = Depends(get_db)):
    gestiones = [r[0] for r in db.query(models.Presupuesto.gestion).distinct().all()]
    if not gestiones:
        gestiones = [2026, 2025]
    return {
        "gestiones": sorted(gestiones, reverse=True),
        "financiadores": [{"id": f.id, "nombre": f.nombre} for f in db.query(models.Financiador).all()],
        "regiones": [{"id": r.id, "nombre": r.nombre} for r in db.query(models.Region).all()],
        "areas": [{"id": a.id, "nombre": a.nombre} for a in db.query(models.Area).all()],
        "rubros": [{"id": r.id, "nombre": r.nombre} for r in db.query(models.Rubro).all()],
    }

# 3. MOTOR DE LOS 7 REPORTES + DASHBOARD
@app.get("/api/reportes/{tipo_reporte}")
def consultar_reporte(
    tipo_reporte: str,
    gestion: int = 2026,
    financiador_id: int | None = None,
    region_id: int | None = None,
    area_id: int | None = None,
    rubro_id: int | None = None,
    mes_hasta: int | None = None,
    moneda: str = "BOB",
    comparar_anterior: bool = False,
    db: Session = Depends(get_db)
):
    return reports.generar_reporte(
        db, tipo_reporte, gestion, financiador_id, region_id, area_id, rubro_id, mes_hasta, moneda, comparar_anterior
    )

# 4. DESCARGA EN EXCEL DE CUALQUIER REPORTE FILTRADO
@app.get("/api/reportes/{tipo_reporte}/excel")
def descargar_excel(
    tipo_reporte: str,
    gestion: int = 2026,
    financiador_id: int | None = None,
    region_id: int | None = None,
    area_id: int | None = None,
    rubro_id: int | None = None,
    mes_hasta: int | None = None,
    moneda: str = "BOB",
    usuario_id: int = 1,
    db: Session = Depends(get_db)
):
    data = reports.generar_reporte(
        db, tipo_reporte, gestion, financiador_id, region_id, area_id, rubro_id, mes_hasta, moneda, False
    )
    excel_stream = reports.exportar_reporte_excel(data["filas"], nombre_hoja=tipo_reporte)

    db.add(models.Auditoria(
        usuario_id=usuario_id,
        accion="EXPORTACION_EXCEL",
        detalle=f"Descarga reporte '{tipo_reporte}' Gestión {gestion} ({moneda})"
    ))
    db.commit()

    headers = {"Content-Disposition": f"attachment; filename=reporte_{tipo_reporte}_{gestion}.xlsx"}
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

# 5. HISTORIAL DE IMPORTACIONES Y AUDITORÍA
@app.get("/api/auditoria")
def ver_auditoria(db: Session = Depends(get_db)):
    usuarios = {u.id: u.nombre for u in db.query(models.Usuario).all()}
    importaciones = db.query(models.Importacion).order_by(models.Importacion.fecha_carga.desc()).all()
    logs = db.query(models.Auditoria).order_by(models.Auditoria.fecha.desc()).limit(50).all()

    return {
        "importaciones": [
            {
                "id": i.id,
                "archivo": i.nombre_archivo,
                "gestion": i.gestion,
                "registros": i.registros_procesados,
                "fecha": i.fecha_carga.strftime("%Y-%m-%d %H:%M"),
                "usuario": usuarios.get(i.usuario_id, "Sistema")
            } for i in importaciones
        ],
        "auditoria": [
            {
                "id": l.id,
                "accion": l.accion,
                "detalle": l.detalle,
                "fecha": l.fecha.strftime("%Y-%m-%d %H:%M"),
                "usuario": usuarios.get(l.usuario_id, "Sistema")
            } for l in logs
        ]
    }

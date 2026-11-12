from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "conectada correctamente"}

# 1. IMPORTAR EXCEL (Con control de rol y auditoría)
@app.post("/api/importar")
async def importar_archivo(
    file: UploadFile = File(...),
    gestion: int = Form(2026),
    usuario_id: int = Form(1),
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if usuario and usuario.rol == "consulta":
        raise HTTPException(status_code=403, detail="El rol Consulta no tiene permisos para importar datos.")

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")

    contenido = await file.read()
    resultado = etl_excel.procesar_excel_exb(contenido, file.filename, gestion, usuario_id, db)
    return {"mensaje": "Importación completada con éxito", "detalle": resultado}

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
        "usuarios": [{"id": u.id, "nombre": u.nombre, "rol": u.rol} for u in db.query(models.Usuario).all()],
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

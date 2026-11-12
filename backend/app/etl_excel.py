import io
import pandas as pd
from sqlalchemy.orm import Session
from . import models

MESES_MAP = {
    "1": 1, "ene": 1, "enero": 1,
    "2": 2, "feb": 2, "febrero": 2,
    "3": 3, "mar": 3, "marzo": 3,
    "4": 4, "abr": 4, "abril": 4,
    "5": 5, "may": 5, "mayo": 5,
    "6": 6, "jun": 6, "junio": 6,
    "7": 7, "jul": 7, "julio": 7,
    "8": 8, "ago": 8, "agosto": 8,
    "9": 9, "sep": 9, "septiembre": 9,
    "10": 10, "oct": 10, "octubre": 10,
    "11": 11, "nov": 11, "noviembre": 11,
    "12": 12, "dic": 12, "diciembre": 12,
}

def limpiar_texto(val, default="SIN DEFINIR"):
    if pd.isna(val) or str(val).strip() in ("", "nan", "None", "NaT"):
        return default
    return str(val).strip()

def limpiar_numero(val, default=0.0):
    num = pd.to_numeric(val, errors="coerce")
    return float(num) if pd.notna(num) else default

def procesar_excel_exb(file_bytes: bytes, filename: str, gestion: int, usuario_id: int, db: Session):
    excel_buffer = io.BytesIO(file_bytes)
    df = pd.read_excel(excel_buffer, sheet_name="BD", header=1)
    df.columns = [str(c).strip() for c in df.columns]

    financiadores = {f.nombre: f for f in db.query(models.Financiador).all()}
    regiones = {r.nombre: r for r in db.query(models.Region).all()}
    areas = {a.nombre: a for a in db.query(models.Area).all()}
    rubros = {r.nombre: r for r in db.query(models.Rubro).all()}
    cuentas = {c.nombre: c for c in db.query(models.Cuenta).all()}

    importacion = models.Importacion(
        nombre_archivo=filename,
        gestion=gestion,
        usuario_id=usuario_id
    )
    db.add(importacion)
    db.flush()

    presupuestos_batch = []
    modificaciones_batch = []
    movimientos_batch = []

    for idx, row in df.iterrows():
        mes_raw = limpiar_texto(row.get("mes"), "")
        if not mes_raw or mes_raw.lower() in ("mes", "total", "subtotal"):
            continue

        fondo_nom = limpiar_texto(row.get("fondo"), "SIN FONDO")
        region_nom = limpiar_texto(row.get("region"), "SIN REGION")
        area_nom = limpiar_texto(row.get("area"), "SIN AREA")
        rubro_nom = limpiar_texto(row.get("rubro"), "SIN RUBRO")
        cuenta_nom = limpiar_texto(row.get("Cuenta"), "SIN CUENTA")

        if fondo_nom not in financiadores:
            obj = models.Financiador(codigo=f"FIN-{len(financiadores)+1}", nombre=fondo_nom)
            db.add(obj); db.flush()
            financiadores[fondo_nom] = obj
        fin_id = financiadores[fondo_nom].id

        if region_nom not in regiones:
            obj = models.Region(codigo=f"REG-{len(regiones)+1}", nombre=region_nom)
            db.add(obj); db.flush()
            regiones[region_nom] = obj
        reg_id = regiones[region_nom].id

        if area_nom not in areas:
            obj = models.Area(codigo=f"AREA-{len(areas)+1}", nombre=area_nom)
            db.add(obj); db.flush()
            areas[area_nom] = obj
        area_id = areas[area_nom].id

        if rubro_nom not in rubros:
            obj = models.Rubro(codigo=f"RUB-{len(rubros)+1}", nombre=rubro_nom)
            db.add(obj); db.flush()
            rubros[rubro_nom] = obj
        rubro_id = rubros[rubro_nom].id

        if cuenta_nom not in cuentas:
            obj = models.Cuenta(codigo=f"CTA-{len(cuentas)+1}", nombre=cuenta_nom, rubro_id=rubro_id)
            db.add(obj); db.flush()
            cuentas[cuenta_nom] = obj
        cuenta_id = cuentas[cuenta_nom].id

        ref_val = limpiar_texto(row.get("ref"), "").upper()
        ptto_monto = limpiar_numero(row.get("presupuesto Bs"), 0.0)
        ejec_monto = limpiar_numero(row.get("Ejecución"), 0.0)

        fecha_val = None
        if pd.notna(row.get("cfecha")):
            try:
                fecha_val = pd.to_datetime(row.get("cfecha")).date()
            except Exception:
                fecha_val = None

        if mes_raw.upper() == "PTTO" or ref_val == "PRESUPUESTO":
            presupuestos_batch.append(models.Presupuesto(
                gestion=gestion,
                monto_inicial=ptto_monto,
                financiador_id=fin_id,
                region_id=reg_id,
                area_id=area_id,
                cuenta_id=cuenta_id,
                importacion_id=importacion.id
            ))
        elif "MOD" in mes_raw.upper() or "MOD" in ref_val:
            modificaciones_batch.append(models.Modificacion(
                gestion=gestion,
                mes=fecha_val.month if fecha_val else 1,
                fecha=fecha_val,
                descripcion=ref_val,
                monto=ptto_monto if ptto_monto != 0 else ejec_monto,
                financiador_id=fin_id,
                region_id=reg_id,
                area_id=area_id,
                cuenta_id=cuenta_id,
                importacion_id=importacion.id
            ))
        else:
            mes_clean = mes_raw.lower().replace(".0", "")
            mes_num = MESES_MAP.get(mes_clean, fecha_val.month if fecha_val else 1)
            dsus = limpiar_numero(row.get("dsus"), 0.0)
            hsus = limpiar_numero(row.get("hsus"), 0.0)
            tasa = limpiar_numero(row.get("tasa"), 6.96)

            movimientos_batch.append(models.Movimiento(
                gestion=gestion,
                mes=mes_num,
                fecha=fecha_val,
                codigo_contable=limpiar_texto(row.get("codigo"), ""),
                nombre_contable=limpiar_texto(row.get("nombre"), ""),
                tipo_comprobante=limpiar_texto(row.get("tipo"), ""),
                numero=limpiar_texto(row.get("numero"), ""),
                no_cheque=limpiar_texto(row.get("no_cheque"), ""),
                glosa=limpiar_texto(row.get("ref"), ""),
                monto_ejecutado=ejec_monto,
                monto_usd=dsus - hsus,
                tasa_cambio=tasa if tasa > 0 else 6.96,
                financiador_id=fin_id,
                region_id=reg_id,
                area_id=area_id,
                cuenta_id=cuenta_id,
                importacion_id=importacion.id
            ))

    db.bulk_save_objects(presupuestos_batch)
    db.bulk_save_objects(modificaciones_batch)
    db.bulk_save_objects(movimientos_batch)

    total = len(presupuestos_batch) + len(modificaciones_batch) + len(movimientos_batch)
    importacion.registros_procesados = total

    db.add(models.Auditoria(
        usuario_id=usuario_id,
        accion="IMPORTACION_EXCEL",
        detalle=f"Archivo '{filename}' (Gestión {gestion}): {len(presupuestos_batch)} ptto, {len(movimientos_batch)} movs."
    ))
    db.commit()

    return {
        "importacion_id": importacion.id,
        "gestion": gestion,
        "presupuestos_cargados": len(presupuestos_batch),
        "modificaciones_cargadas": len(modificaciones_batch),
        "movimientos_cargados": len(movimientos_batch),
        "total_registros": total
    }

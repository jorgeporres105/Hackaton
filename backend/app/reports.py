import io
import pandas as pd
from sqlalchemy.orm import Session
from . import models

NOMBRES_MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def _obtener_dataframes_filtrados(
    db: Session,
    gestion: int,
    financiador_id: int | None = None,
    region_id: int | None = None,
    area_id: int | None = None,
    rubro_id: int | None = None,
    mes_hasta: int | None = None,
    moneda: str = "BOB"
):
    # Catálogos en diccionarios
    fin_map = {f.id: f.nombre for f in db.query(models.Financiador).all()}
    reg_map = {r.id: r.nombre for r in db.query(models.Region).all()}
    area_map = {a.id: a.nombre for a in db.query(models.Area).all()}
    rubro_map = {r.id: r.nombre for r in db.query(models.Rubro).all()}
    cuentas_db = db.query(models.Cuenta).all()
    cuenta_map = {c.id: c.nombre for c in cuentas_db}
    cuenta_rubro_map = {c.id: c.rubro_id for c in cuentas_db}

    # Tasa promedio de cambio si piden USD
    tc = 1.0
    if moneda.upper() == "USD":
        tc_row = db.query(models.TipoCambio).filter(models.TipoCambio.gestion == gestion).first()
        tc = tc_row.tasa if tc_row and tc_row.tasa > 0 else 6.96

    def filtrar_query(query, model, tiene_mes=True):
        q = query.filter(model.gestion == gestion)
        if financiador_id:
            q = q.filter(model.financiador_id == financiador_id)
        if region_id:
            q = q.filter(model.region_id == region_id)
        if area_id:
            q = q.filter(model.area_id == area_id)
        if tiene_mes and mes_hasta:
            q = q.filter(model.mes <= mes_hasta)
        return q.all()

    pttos = filtrar_query(db.query(models.Presupuesto), models.Presupuesto, tiene_mes=False)
    mods = filtrar_query(db.query(models.Modificacion), models.Modificacion, tiene_mes=True)
    movs = filtrar_query(db.query(models.Movimiento), models.Movimiento, tiene_mes=True)

    registros = []

    for p in pttos:
        r_id = cuenta_rubro_map.get(p.cuenta_id)
        if rubro_id and r_id != rubro_id:
            continue
        registros.append({
            "financiador": fin_map.get(p.financiador_id, "N/A"),
            "region": reg_map.get(p.region_id, "N/A"),
            "area": area_map.get(p.area_id, "N/A"),
            "rubro": rubro_map.get(r_id, "N/A"),
            "cuenta": cuenta_map.get(p.cuenta_id, "N/A"),
            "mes": 0,
            "inicial": (p.monto_inicial or 0.0) / tc,
            "modificado": 0.0,
            "ejecutado": 0.0,
        })

    for m in mods:
        r_id = cuenta_rubro_map.get(m.cuenta_id)
        if rubro_id and r_id != rubro_id:
            continue
        registros.append({
            "financiador": fin_map.get(m.financiador_id, "N/A"),
            "region": reg_map.get(m.region_id, "N/A"),
            "area": area_map.get(m.area_id, "N/A"),
            "rubro": rubro_map.get(r_id, "N/A"),
            "cuenta": cuenta_map.get(m.cuenta_id, "N/A"),
            "mes": m.mes or 1,
            "inicial": 0.0,
            "modificado": (m.monto or 0.0) / tc,
            "ejecutado": 0.0,
        })

    movs_detalle = []
    for mv in movs:
        r_id = cuenta_rubro_map.get(mv.cuenta_id)
        if rubro_id and r_id != rubro_id:
            continue
        monto_val = (mv.monto_ejecutado or 0.0) / tc
        registros.append({
            "financiador": fin_map.get(mv.financiador_id, "N/A"),
            "region": reg_map.get(mv.region_id, "N/A"),
            "area": area_map.get(mv.area_id, "N/A"),
            "rubro": rubro_map.get(r_id, "N/A"),
            "cuenta": cuenta_map.get(mv.cuenta_id, "N/A"),
            "mes": mv.mes or 1,
            "inicial": 0.0,
            "modificado": 0.0,
            "ejecutado": monto_val,
        })
        movs_detalle.append({
            "id": mv.id,
            "mes": NOMBRES_MESES.get(mv.mes, str(mv.mes)),
            "fecha": str(mv.fecha) if mv.fecha else "",
            "comprobante": f"{mv.tipo_comprobante or ''} {mv.numero or ''}".strip(),
            "no_cheque": mv.no_cheque or "",
            "glosa": mv.glosa or "",
            "financiador": fin_map.get(mv.financiador_id, "N/A"),
            "region": reg_map.get(mv.region_id, "N/A"),
            "area": area_map.get(mv.area_id, "N/A"),
            "rubro": rubro_map.get(r_id, "N/A"),
            "cuenta": cuenta_map.get(mv.cuenta_id, "N/A"),
            "monto_ejecutado": round(monto_val, 2),
        })

    cols = ["financiador", "region", "area", "rubro", "cuenta", "mes", "inicial", "modificado", "ejecutado"]
    df = pd.DataFrame(registros, columns=cols) if registros else pd.DataFrame(columns=cols)
    return df, movs_detalle

def _agrupar_y_calcular(df: pd.DataFrame, group_cols: list[str]):
    if df.empty:
        return []
    grouped = df.groupby(group_cols, as_index=False)[["inicial", "modificado", "ejecutado"]].sum()
    grouped["vigente"] = grouped["inicial"] + grouped["modificado"]
    grouped["saldo"] = grouped["vigente"] - grouped["ejecutado"]
    grouped["porcentaje_ejecucion"] = grouped.apply(
        lambda r: round((r["ejecutado"] / r["vigente"] * 100), 2) if r["vigente"] > 0 else 0.0, axis=1
    )
    for col in ["inicial", "modificado", "vigente", "ejecutado", "saldo"]:
        grouped[col] = grouped[col].round(2)
    return grouped.to_dict(orient="records")

def generar_reporte(
    db: Session,
    tipo_reporte: str,
    gestion: int,
    financiador_id: int | None = None,
    region_id: int | None = None,
    area_id: int | None = None,
    rubro_id: int | None = None,
    mes_hasta: int | None = None,
    moneda: str = "BOB",
    comparar_anterior: bool = False
):
    df, movs_detalle = _obtener_dataframes_filtrados(
        db, gestion, financiador_id, region_id, area_id, rubro_id, mes_hasta, moneda
    )

    # Totales consolidados (Reporte 7 y KPIs del Dashboard)
    inicial_tot = round(float(df["inicial"].sum()), 2) if not df.empty else 0.0
    mod_tot = round(float(df["modificado"].sum()), 2) if not df.empty else 0.0
    vigente_tot = round(inicial_tot + mod_tot, 2)
    ejec_tot = round(float(df["ejecutado"].sum()), 2) if not df.empty else 0.0
    saldo_tot = round(vigente_tot - ejec_tot, 2)
    pct_tot = round((ejec_tot / vigente_tot * 100), 2) if vigente_tot > 0 else 0.0

    resumen = {
        "gestion": gestion,
        "moneda": moneda,
        "presupuesto_inicial": inicial_tot,
        "modificaciones": mod_tot,
        "presupuesto_vigente": vigente_tot,
        "ejecutado": ejec_tot,
        "saldo": saldo_tot,
        "porcentaje_ejecucion": pct_tot,
    }

    # Comparativo interanual opcional
    if comparar_anterior:
        df_prev, _ = _obtener_dataframes_filtrados(
            db, gestion - 1, financiador_id, region_id, area_id, rubro_id, mes_hasta, moneda
        )
        ejec_prev = round(float(df_prev["ejecutado"].sum()), 2) if not df_prev.empty else 0.0
        var_pct = round(((ejec_tot - ejec_prev) / ejec_prev * 100), 2) if ejec_prev > 0 else 0.0
        resumen["comparativo_anterior"] = {
            "gestion_anterior": gestion - 1,
            "ejecutado_anterior": ejec_prev,
            "variacion_porcentual": var_pct
        }

    # Selección de los 7 reportes
    if tipo_reporte == "rubro_cuenta":
        filas = _agrupar_y_calcular(df, ["rubro", "cuenta"])
    elif tipo_reporte == "financiador":
        filas = _agrupar_y_calcular(df, ["financiador"])
    elif tipo_reporte == "area_financiador":
        filas = _agrupar_y_calcular(df, ["area", "financiador"])
    elif tipo_reporte == "region":
        filas = _agrupar_y_calcular(df, ["region", "area"])
    elif tipo_reporte == "mes":
        if df.empty:
            filas = []
        else:
            df_mes = df[df["mes"] > 0].groupby("mes", as_index=False)[["ejecutado"]].sum()
            df_mes["mes_nombre"] = df_mes["mes"].map(NOMBRES_MESES)
            df_mes["acumulado"] = df_mes["ejecutado"].cumsum().round(2)
            df_mes["ejecutado"] = df_mes["ejecutado"].round(2)
            filas = df_mes.sort_values("mes").to_dict(orient="records")
    elif tipo_reporte == "detalle_movimientos":
        filas = movs_detalle
    else:  # "consolidado"
        filas = [resumen]

    return {"resumen": resumen, "filas": filas}

def exportar_reporte_excel(filas: list[dict], nombre_hoja: str = "Reporte") -> io.BytesIO:
    output = io.BytesIO()
    df_out = pd.DataFrame(filas)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name=nombre_hoja[:30])
    output.seek(0)
    return output

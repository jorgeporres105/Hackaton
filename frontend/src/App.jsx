import React, { useState, useEffect } from "react";
import {
  BarChart3, FileSpreadsheet, Upload, ShieldCheck, Download,
  Printer, RefreshCw, AlertCircle, CheckCircle2, Layers, Lock, LogOut, Settings
} from "lucide-react";

const API_URL = "https://exb-presupuesto-api.onrender.com/api";

const REPORTES_LISTA = [
  { id: "consolidado", nombre: "7. Resumen Consolidado" },
  { id: "rubro_cuenta", nombre: "1. Por Rubro y Cuenta" },
  { id: "financiador", nombre: "2. Por Financiador" },
  { id: "area_financiador", nombre: "3. Por Área y Financiador" },
  { id: "region", nombre: "4. Por Región y Área" },
  { id: "mes", nombre: "5. Ejecución Mensual" },
  { id: "detalle_movimientos", nombre: "6. Detalle Movimientos" },
];

export default function App() {
  // Sesión autenticada
  const [usuarioActivo, setUsuarioActivo] = useState(() => {
    const saved = localStorage.getItem("exb_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [loginForm, setLoginForm] = useState({ email: "admin@exb.org.bo", password: "" });
  const [loginError, setLoginError] = useState("");

  const [vista, setVista] = useState("dashboard");
  const [catalogos, setCatalogos] = useState({
    gestiones: [2026, 2025], financiadores: [], regiones: [], areas: [], rubros: []
  });

  const [filtros, setFiltros] = useState({
    gestion: 2026, financiador_id: "", region_id: "", area_id: "",
    rubro_id: "", mes_hasta: "", moneda: "BOB", comparar_anterior: true,
  });

  const [tipoReporte, setTipoReporte] = useState("rubro_cuenta");
  const [dataReporte, setDataReporte] = useState({ resumen: {}, filas: [] });
  const [dataDashboard, setDataDashboard] = useState({ resumen: {}, porFinanciador: [], porMes: [] });
  const [auditoriaData, setAuditoriaData] = useState({ importaciones: [], auditoria: [] });
  const [cargando, setCargando] = useState(false);

  // Admin: Importar Excel y Tipo de Cambio
  const [archivoExcel, setArchivoExcel] = useState(null);
  const [gestionImportar, setGestionImportar] = useState(2026);
  const [msgImport, setMsgImport] = useState(null);
  const [tcGestion, setTcGestion] = useState(2026);
  const [tcValor, setTcValor] = useState(6.96);
  const [msgTc, setMsgTc] = useState("");

  const manejarLogin = async (e) => {
    e.preventDefault();
    setLoginError("");
    try {
      const res = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm),
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(data.detail || "Credenciales inválidas");
      } else {
        setUsuarioActivo(data);
        localStorage.setItem("exb_user", JSON.stringify(data));
      }
    } catch {
      setLoginError("No se pudo conectar con el servidor.");
    }
  };

  const cerrarSesion = () => {
    setUsuarioActivo(null);
    localStorage.removeItem("exb_user");
    setVista("dashboard");
  };

  const construirQuery = (extra = {}) => {
    const params = new URLSearchParams();
    const merged = { ...filtros, ...extra };
    Object.entries(merged).forEach(([k, v]) => {
      if (v !== "" && v !== null && v !== undefined) params.append(k, v);
    });
    return params.toString();
  };

  const cargarCatalogos = async () => {
    try {
      const res = await fetch(`${API_URL}/filtros`);
      setCatalogos(await res.json());
    } catch (e) { console.error(e); }
  };

  const cargarDatos = async () => {
    if (!usuarioActivo) return;
    setCargando(true);
    try {
      const qs = construirQuery();
      const [resRep, resFin, resMes] = await Promise.all([
        fetch(`${API_URL}/reportes/${tipoReporte}?${qs}`).then(r => r.json()),
        fetch(`${API_URL}/reportes/financiador?${qs}`).then(r => r.json()),
        fetch(`${API_URL}/reportes/mes?${qs}`).then(r => r.json()),
      ]);
      setDataReporte(resRep);
      setDataDashboard({
        resumen: resRep.resumen || {},
        porFinanciador: resFin.filas || [],
        porMes: resMes.filas || [],
      });
    } catch (e) { console.error(e); }
    setCargando(false);
  };

  const cargarAuditoria = async () => {
    const res = await fetch(`${API_URL}/auditoria`);
    setAuditoriaData(await res.json());
  };

  useEffect(() => { if (usuarioActivo) cargarCatalogos(); }, [usuarioActivo]);
  useEffect(() => { cargarDatos(); }, [filtros, tipoReporte, usuarioActivo]);
  useEffect(() => { if (vista === "auditoria") cargarAuditoria(); }, [vista]);

  const manejarImportacion = async (e) => {
    e.preventDefault();
    if (!archivoExcel) return;
    setMsgImport(null);
    const formData = new FormData();
    formData.append("file", archivoExcel);
    formData.append("gestion", gestionImportar);
    formData.append("usuario_id", usuarioActivo.id);

    try {
      const res = await fetch(`${API_URL}/importar`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        setMsgImport({ tipo: "error", texto: data.detail || "Error al importar" });
      } else {
        setMsgImport({
          tipo: "ok",
          texto: `Importado: ${data.detalle.presupuestos_cargados} presupuestos y ${data.detalle.movimientos_cargados} movimientos.`
        });
        cargarCatalogos();
        cargarDatos();
      }
    } catch {
      setMsgImport({ tipo: "error", texto: "Error de conexión." });
    }
  };

  const actualizarTipoCambio = async (e) => {
    e.preventDefault();
    setMsgTc("");
    const res = await fetch(`${API_URL}/tipos-cambio`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gestion: Number(tcGestion), tasa: Number(tcValor), usuario_id: usuarioActivo.id })
    });
    const data = await res.json();
    setMsgTc(res.ok ? data.mensaje : data.detail);
    cargarDatos();
  };

  const descargarExcel = () => {
    const qs = construirQuery({ usuario_id: usuarioActivo.id });
    window.open(`${API_URL}/reportes/${tipoReporte}/excel?${qs}`, "_blank");
  };

  const fmt = (num) =>
    new Intl.NumberFormat("es-BO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num || 0);

  const colorSemaforo = (pct) => {
    if (pct > 95) return "bg-red-100 text-red-800 border-red-300";
    if (pct >= 50) return "bg-emerald-100 text-emerald-800 border-emerald-300";
    return "bg-amber-100 text-amber-800 border-amber-300";
  };

  // ==================== PANTALLA DE LOGIN ====================
  if (!usuarioActivo) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-emerald-600 p-2.5 rounded-xl">
              <Lock className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-slate-900">Control Presupuestario</h1>
              <p className="text-xs text-slate-500">Enseña por Bolivia — Acceso Institucional</p>
            </div>
          </div>

          <form onSubmit={manejarLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Correo Institucional</label>
              <input
                type="email"
                value={loginForm.email}
                onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                className="w-full border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Contraseña</label>
              <input
                type="password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                placeholder="••••••••"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>

            {loginError && (
              <p className="text-xs text-red-600 bg-red-50 p-2.5 rounded-lg border border-red-200">{loginError}</p>
            )}

            <button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-lg text-sm transition"
            >
              Iniciar Sesión
            </button>
          </form>

          {/* Credenciales de prueba visibles para facilitar evaluación */}
          <div className="mt-6 pt-4 border-t border-slate-100">
            <p className="text-[11px] font-bold text-slate-400 uppercase mb-2">Cuentas de Prueba (Clic para rellenar):</p>
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              <button
                type="button"
                onClick={() => setLoginForm({ email: "admin@exb.org.bo", password: "admin123" })}
                className="p-2 rounded bg-slate-100 hover:bg-emerald-50 text-left border"
              >
                <span className="font-bold block text-slate-800">Admin</span>
                <span className="text-slate-500">Sube y edita</span>
              </button>
              <button
                type="button"
                onClick={() => setLoginForm({ email: "tecnico@exb.org.bo", password: "tecnico123" })}
                className="p-2 rounded bg-slate-100 hover:bg-emerald-50 text-left border"
              >
                <span className="font-bold block text-slate-800">Técnico</span>
                <span className="text-slate-500">Solo lectura</span>
              </button>
              <button
                type="button"
                onClick={() => setLoginForm({ email: "consulta@exb.org.bo", password: "consulta123" })}
                className="p-2 rounded bg-slate-100 hover:bg-emerald-50 text-left border"
              >
                <span className="font-bold block text-slate-800">Consulta</span>
                <span className="text-slate-500">Solo lectura</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const res = dataDashboard.resumen;
  const esAdmin = usuarioActivo.rol === "admin";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* NAVBAR SUPERIOR */}
      <header className="bg-slate-900 text-white px-6 py-3 flex flex-wrap items-center justify-between gap-4 no-print">
        <div className="flex items-center gap-3">
          <div className="bg-emerald-500 p-2 rounded-lg">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight">Enseña por Bolivia — Control Presupuestario</h1>
            <p className="text-xs text-slate-400">Sistema de Ejecución Financiera y Reportes Automatizados</p>
          </div>
        </div>

        <nav className="flex items-center gap-2">
          {[
            { id: "dashboard", label: "Dashboard", icon: BarChart3 },
            { id: "reportes", label: "7 Reportes", icon: FileSpreadsheet },
            { id: "admin", label: "Administración", icon: Settings },
            { id: "auditoria", label: "Auditoría", icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setVista(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                  vista === tab.id ? "bg-emerald-600 text-white" : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <div className="text-right text-xs">
            <p className="font-bold text-white">{usuarioActivo.nombre}</p>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
              esAdmin ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
            }`}>
              Rol: {usuarioActivo.rol}
            </span>
          </div>
          <button
            onClick={cerrarSesion}
            className="p-2 bg-slate-800 hover:bg-red-600 rounded-lg text-slate-300 hover:text-white transition"
            title="Cerrar Sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* BARRA DE FILTROS COMBINADOS */}
      {(vista === "dashboard" || vista === "reportes") && (
        <section className="bg-white border-b border-slate-200 px-6 py-3 flex flex-wrap items-center gap-3 no-print">
          <select
            className="border rounded-md px-2.5 py-1.5 text-sm font-semibold bg-slate-50"
            value={filtros.gestion}
            onChange={(e) => setFiltros({ ...filtros, gestion: Number(e.target.value) })}
          >
            {catalogos.gestiones.map((g) => <option key={g} value={g}>Gestión {g}</option>)}
          </select>

          <select
            className="border rounded-md px-2.5 py-1.5 text-sm max-w-[180px]"
            value={filtros.financiador_id}
            onChange={(e) => setFiltros({ ...filtros, financiador_id: e.target.value })}
          >
            <option value="">Todos los Financiadores</option>
            {catalogos.financiadores.map((f) => <option key={f.id} value={f.id}>{f.nombre}</option>)}
          </select>

          <select
            className="border rounded-md px-2.5 py-1.5 text-sm max-w-[180px]"
            value={filtros.area_id}
            onChange={(e) => setFiltros({ ...filtros, area_id: e.target.value })}
          >
            <option value="">Todas las Áreas</option>
            {catalogos.areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </select>

          <select
            className="border rounded-md px-2.5 py-1.5 text-sm max-w-[150px]"
            value={filtros.region_id}
            onChange={(e) => setFiltros({ ...filtros, region_id: e.target.value })}
          >
            <option value="">Todas las Regiones</option>
            {catalogos.regiones.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select>

          <select
            className="border rounded-md px-2.5 py-1.5 text-sm max-w-[180px]"
            value={filtros.rubro_id}
            onChange={(e) => setFiltros({ ...filtros, rubro_id: e.target.value })}
          >
            <option value="">Todos los Rubros</option>
            {catalogos.rubros.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select>

          <select
            className="border rounded-md px-2.5 py-1.5 text-sm"
            value={filtros.mes_hasta}
            onChange={(e) => setFiltros({ ...filtros, mes_hasta: e.target.value })}
          >
            <option value="">Acumulado Anual</option>
            {[...Array(12)].map((_, i) => <option key={i + 1} value={i + 1}>Hasta Mes {i + 1}</option>)}
          </select>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setFiltros({ ...filtros, moneda: filtros.moneda === "BOB" ? "USD" : "BOB" })}
              className="px-3 py-1.5 rounded-md text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100"
            >
              Moneda: {filtros.moneda}
            </button>
            <button
              onClick={() => setFiltros({
                gestion: 2026, financiador_id: "", region_id: "", area_id: "",
                rubro_id: "", mes_hasta: "", moneda: "BOB", comparar_anterior: true
              })}
              className="p-1.5 text-slate-500 hover:text-slate-800"
              title="Limpiar filtros"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </section>
      )}

      <main className="max-w-7xl mx-auto p-6">
        {/* ==================== VISTA 1: DASHBOARD ==================== */}
        {vista === "dashboard" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase">Presupuesto Vigente ({filtros.moneda})</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{fmt(res.presupuesto_vigente)}</p>
                <p className="text-xs text-slate-400 mt-1">Inicial: {fmt(res.presupuesto_inicial)}</p>
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase">Ejecutado Acumulado ({filtros.moneda})</p>
                <p className="text-2xl font-bold text-emerald-600 mt-1">{fmt(res.ejecutado)}</p>
                {res.comparativo_anterior && (
                  <p className="text-xs text-slate-500 mt-1">
                    vs {res.comparativo_anterior.gestion_anterior}:{" "}
                    <span className="font-semibold">
                      {res.comparativo_anterior.variacion_porcentual > 0 ? "+" : ""}
                      {res.comparativo_anterior.variacion_porcentual}%
                    </span>
                  </p>
                )}
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase">Saldo Disponible ({filtros.moneda})</p>
                <p className="text-2xl font-bold text-blue-600 mt-1">{fmt(res.saldo)}</p>
                <p className="text-xs text-slate-400 mt-1">Por comprometer / ejecutar</p>
              </div>
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <p className="text-xs font-semibold text-slate-500 uppercase">% Avance de Ejecución</p>
                <div className="flex items-center gap-3 mt-1">
                  <p className="text-2xl font-bold text-slate-900">{res.porcentaje_ejecucion || 0}%</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${colorSemaforo(res.porcentaje_ejecucion || 0)}`}>
                    {(res.porcentaje_ejecucion || 0) > 95 ? "Alerta Límite" : (res.porcentaje_ejecucion || 0) >= 50 ? "Óptimo" : "En curso"}
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full mt-3 overflow-hidden">
                  <div className="bg-emerald-500 h-full" style={{ width: `${Math.min(res.porcentaje_ejecucion || 0, 100)}%` }} />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-4">Ejecución por Financiador ({filtros.moneda})</h3>
                <div className="space-y-3">
                  {dataDashboard.porFinanciador.map((f, i) => (
                    <div key={i}>
                      <div className="flex justify-between text-xs font-medium mb-1">
                        <span className="truncate max-w-[220px]">{f.financiador}</span>
                        <span>{fmt(f.ejecutado)} / {fmt(f.vigente)} ({f.porcentaje_ejecucion}%)</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                        <div className="bg-indigo-600 h-full rounded-full" style={{ width: `${Math.min(f.porcentaje_ejecucion, 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-4">Evolución Mensual ({filtros.moneda})</h3>
                <div className="space-y-2">
                  {dataDashboard.porMes.map((m, i) => {
                    const maxMes = Math.max(...dataDashboard.porMes.map((x) => x.ejecutado), 1);
                    return (
                      <div key={i} className="flex items-center gap-3 text-xs">
                        <span className="w-20 font-medium text-slate-600">{m.mes_nombre}</span>
                        <div className="flex-1 bg-slate-100 h-4 rounded overflow-hidden">
                          <div className="bg-emerald-500 h-full" style={{ width: `${(m.ejecutado / maxMes) * 100}%` }} />
                        </div>
                        <span className="w-24 text-right font-semibold">{fmt(m.ejecutado)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ==================== VISTA 2: 7 REPORTES ==================== */}
        {vista === "reportes" && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 no-print">
              <div className="flex flex-wrap gap-1.5">
                {REPORTES_LISTA.map((rep) => (
                  <button
                    key={rep.id}
                    onClick={() => setTipoReporte(rep.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                      tipoReporte === rep.id ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                    }`}
                  >
                    {rep.nombre}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={descargarExcel} className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">
                  <Download className="w-4 h-4" /> Excel (.xlsx)
                </button>
                <button onClick={() => window.print()} className="flex items-center gap-1.5 bg-slate-700 hover:bg-slate-800 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">
                  <Printer className="w-4 h-4" /> PDF / Imprimir
                </button>
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
              <div className="mb-4 border-b pb-3">
                <h2 className="text-lg font-bold text-slate-900">
                  {REPORTES_LISTA.find((r) => r.id === tipoReporte)?.nombre} — Gestión {filtros.gestion}
                </h2>
                <p className="text-xs text-slate-500">
                  Moneda: {filtros.moneda} | Total Ejecutado: <strong>{fmt(dataReporte.resumen?.ejecutado)}</strong>
                </p>
              </div>

              {cargando ? (
                <p className="text-sm text-slate-500 py-8 text-center">Calculando cifras...</p>
              ) : dataReporte.filas?.length === 0 ? (
                <p className="text-sm text-slate-500 py-8 text-center">No hay registros para los filtros seleccionados.</p>
              ) : (
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 uppercase border-b border-slate-300">
                      {Object.keys(dataReporte.filas[0]).map((col) => (
                        <th key={col} className="py-2.5 px-3 font-bold">{col.replace("_", " ")}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {dataReporte.filas.map((fila, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        {Object.entries(fila).map(([k, val], i) => (
                          <td key={i} className="py-2 px-3">
                            {k === "porcentaje_ejecucion" ? (
                              <span className={`px-2 py-0.5 rounded-full border font-semibold ${colorSemaforo(val)}`}>{val}%</span>
                            ) : typeof val === "number" && k !== "id" && k !== "mes" && k !== "gestion" ? (
                              <span className="font-mono font-medium">{fmt(val)}</span>
                            ) : val}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ==================== VISTA 3: ADMINISTRACIÓN (SOLO ADMIN) ==================== */}
        {vista === "admin" && (
          <div className="max-w-3xl mx-auto">
            {!esAdmin ? (
              <div className="bg-white p-8 rounded-xl border border-amber-200 shadow-sm text-center space-y-3">
                <div className="w-12 h-12 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto">
                  <Lock className="w-6 h-6" />
                </div>
                <h2 className="text-lg font-bold text-slate-900">Módulo Restringido (Solo Administradores)</h2>
                <p className="text-sm text-slate-600">
                  Has iniciado sesión como <strong>{usuarioActivo.nombre}</strong> con rol <strong>{usuarioActivo.rol.toUpperCase()}</strong>.
                  Tu perfil solo tiene permisos de consulta y descarga de reportes, pero no puede cargar archivos ni modificar parámetros financieros.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 1. CARGA DE EXCEL */}
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
                    <Upload className="w-4 h-4 text-emerald-600" /> Importar Excel Contable
                  </h2>
                  <p className="text-xs text-slate-500 mb-4">
                    Sube la hoja <strong>BD</strong> para cargar presupuestos y ejecución de una gestión.
                  </p>
                  <form onSubmit={manejarImportacion} className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Gestión (Año)</label>
                      <input
                        type="number"
                        value={gestionImportar}
                        onChange={(e) => setGestionImportar(Number(e.target.value))}
                        className="w-full border rounded-lg px-3 py-2 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Archivo Excel (.xlsx)</label>
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={(e) => setArchivoExcel(e.target.files[0])}
                        className="w-full border rounded-lg px-3 py-2 text-xs bg-slate-50"
                        required
                      />
                    </div>
                    <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-lg text-sm">
                      Importar Datos
                    </button>
                  </form>
                  {msgImport && (
                    <div className={`mt-4 p-3 rounded-lg text-xs flex items-center gap-2 ${
                      msgImport.tipo === "ok" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-red-50 text-red-800 border border-red-200"
                    }`}>
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>{msgImport.texto}</span>
                    </div>
                  )}
                </div>

                {/* 2. CONFIGURACIÓN DE TIPO DE CAMBIO */}
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                  <h2 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
                    <Settings className="w-4 h-4 text-indigo-600" /> Tipo de Cambio Oficial (BOB/USD)
                  </h2>
                  <p className="text-xs text-slate-500 mb-4">
                    Ajusta la tasa de conversión para los reportes expresados en dólares (USD).
                  </p>
                  <form onSubmit={actualizarTipoCambio} className="space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Gestión</label>
                      <input
                        type="number"
                        value={tcGestion}
                        onChange={(e) => setTcGestion(e.target.value)}
                        className="w-full border rounded-lg px-3 py-2 text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Tasa de Cambio (Bs por 1 USD)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={tcValor}
                        onChange={(e) => setTcValor(e.target.value)}
                        className="w-full border rounded-lg px-3 py-2 text-sm"
                        required
                      />
                    </div>
                    <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 rounded-lg text-sm">
                      Guardar Tipo de Cambio
                    </button>
                  </form>
                  {msgTc && (
                    <p className="mt-4 p-3 rounded-lg text-xs bg-indigo-50 text-indigo-800 border border-indigo-200">{msgTc}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ==================== VISTA 4: AUDITORÍA ==================== */}
        {vista === "auditoria" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-800 mb-3">Historial de Importaciones</h3>
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b text-slate-500">
                    <th className="py-2">Archivo</th>
                    <th className="py-2">Gestión</th>
                    <th className="py-2">Registros</th>
                    <th className="py-2">Usuario</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {auditoriaData.importaciones.map((imp) => (
                    <tr key={imp.id}>
                      <td className="py-2 font-medium">{imp.archivo}</td>
                      <td className="py-2">{imp.gestion}</td>
                      <td className="py-2">{imp.registros}</td>
                      <td className="py-2">{imp.usuario}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-800 mb-3">Bitácora de Auditoría</h3>
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b text-slate-500">
                    <th className="py-2">Acción</th>
                    <th className="py-2">Detalle</th>
                    <th className="py-2">Usuario</th>
                    <th className="py-2">Fecha</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {auditoriaData.auditoria.map((log) => (
                    <tr key={log.id}>
                      <td className="py-2 font-bold text-indigo-600">{log.accion}</td>
                      <td className="py-2">{log.detalle}</td>
                      <td className="py-2">{log.usuario}</td>
                      <td className="py-2 text-slate-400">{log.fecha}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

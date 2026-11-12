from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base

# 1. USUARIOS
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(String, default="tecnico")  # admin, tecnico, consulta
    activo = Column(Boolean, default=True)

# 2. FINANCIADORES (Columna 'fondo' en Excel: ej. CATALYST 18)
class Financiador(Base):
    __tablename__ = "financiadores"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)

# 3. REGIONES (Columna 'region' en Excel: ej. LP, SC, CB)
class Region(Base):
    __tablename__ = "regiones"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)

# 4. ÁREAS (Columna 'area' en Excel: ej. CAMBIO SISTEMICO)
class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)

# 5. RUBROS (Columna 'rubro' en Excel: ej. 4. Consultoria)
class Rubro(Base):
    __tablename__ = "rubros"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    cuentas = relationship("Cuenta", back_populates="rubro")

# 6. CUENTAS (Columna 'Cuenta' en Excel: ej. 4.1 Videos)
class Cuenta(Base):
    __tablename__ = "cuentas"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    rubro_id = Column(Integer, ForeignKey("rubros.id"), nullable=False)
    rubro = relationship("Rubro", back_populates="cuentas")

# 7. TIPOS DE CAMBIO (Columna 'tasa' en Excel)
class TipoCambio(Base):
    __tablename__ = "tipos_cambio"
    id = Column(Integer, primary_key=True, index=True)
    gestion = Column(Integer, index=True, nullable=False)
    mes = Column(Integer, nullable=False)
    moneda_origen = Column(String, default="USD")
    moneda_destino = Column(String, default="BOB")
    tasa = Column(Float, nullable=False)

# 8. IMPORTACIONES
class Importacion(Base):
    __tablename__ = "importaciones"
    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String, nullable=False)
    gestion = Column(Integer, nullable=False)
    registros_procesados = Column(Integer, default=0)
    fecha_carga = Column(DateTime, default=datetime.utcnow)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))

# 9. PRESUPUESTOS (Filas donde mes == 'PTTO')
class Presupuesto(Base):
    __tablename__ = "presupuestos"
    id = Column(Integer, primary_key=True, index=True)
    gestion = Column(Integer, index=True, nullable=False)
    monto_inicial = Column(Float, default=0.0)
    financiador_id = Column(Integer, ForeignKey("financiadores.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regiones.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    cuenta_id = Column(Integer, ForeignKey("cuentas.id"), nullable=False)
    importacion_id = Column(Integer, ForeignKey("importaciones.id"))

# 10. MODIFICACIONES
class Modificacion(Base):
    __tablename__ = "modificaciones"
    id = Column(Integer, primary_key=True, index=True)
    gestion = Column(Integer, index=True, nullable=False)
    mes = Column(Integer, nullable=False)
    fecha = Column(Date, nullable=True)
    tipo = Column(String, default="traspaso")
    descripcion = Column(String, nullable=True)
    monto = Column(Float, default=0.0)
    financiador_id = Column(Integer, ForeignKey("financiadores.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regiones.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    cuenta_id = Column(Integer, ForeignKey("cuentas.id"), nullable=False)
    importacion_id = Column(Integer, ForeignKey("importaciones.id"))

# 11. MOVIMIENTOS (Filas de ejecución mensual)
class Movimiento(Base):
    __tablename__ = "movimientos"
    id = Column(Integer, primary_key=True, index=True)
    gestion = Column(Integer, index=True, nullable=False)
    mes = Column(Integer, index=True, nullable=False)
    fecha = Column(Date, nullable=True)
    codigo_contable = Column(String, nullable=True)
    nombre_contable = Column(String, nullable=True)
    tipo_comprobante = Column(String, nullable=True)
    numero = Column(String, nullable=True)
    no_cheque = Column(String, nullable=True)
    glosa = Column(String, nullable=True)
    monto_ejecutado = Column(Float, default=0.0) # En Bs
    monto_usd = Column(Float, default=0.0)       # En USD (dsus - hsus)
    tasa_cambio = Column(Float, default=6.96)
    financiador_id = Column(Integer, ForeignKey("financiadores.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regiones.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    cuenta_id = Column(Integer, ForeignKey("cuentas.id"), nullable=False)
    importacion_id = Column(Integer, ForeignKey("importaciones.id"))

# AUDITORÍA
class Auditoria(Base):
    __tablename__ = "auditoria"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    accion = Column(String, nullable=False)
    detalle = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

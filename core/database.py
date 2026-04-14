from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import db_cfg

Base = declarative_base()

class Auditoria(Base):
    """Representa una sesión de auditoría para un cliente (CUIT) y período."""
    __tablename__ = "auditorias"

    id = Column(Integer, primary_key=True, index=True)
    cuit = Column(String(20), index=True)
    periodo = Column(String(20))
    provincia_id = Column(Integer, nullable=True)
    fecha_proceso = Column(DateTime, default=datetime.now)
    estado = Column(String(50), default="PROCESANDO")  # COMPLETADO, ERROR, PROCESANDO
    resumen_ia = Column(Text, nullable=True)
    caso_id = Column(String(20), nullable=True)  # ID en CaseHistory para vincular validaciones
    
    # Relaciones
    resultados = relationship("ResultadoActividad", back_populates="auditoria", cascade="all, delete-orphan")
    archivos = relationship("ArchivoGenerado", back_populates="auditoria", cascade="all, delete-orphan")


class ResultadoActividad(Base):
    """Cada actividad específica auditada dentro de una sesión."""
    __tablename__ = "resultados_actividad"

    id = Column(Integer, primary_key=True, index=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"))

    actividad_desc = Column(String(500))
    naes = Column(String(20))
    alicuota_base = Column(Float)
    alicuota_sugerida = Column(Float)
    alicuota_ia = Column(Float)
    alicuota_anterior = Column(Float, nullable=True)
    justificacion = Column(Text)
    normativa_ref = Column(String(500))

    # Validación humana
    validacion_estado = Column(String(20), default="PENDIENTE")  # PENDIENTE / ACEPTADO / MODIFICADO
    alicuota_validada = Column(Float, nullable=True)
    comentario_validacion = Column(Text, nullable=True)
    fecha_validacion = Column(DateTime, nullable=True)
    validado_por = Column(String(100), nullable=True)   # usuario que validó
    equipo_validacion = Column(String(100), nullable=True)  # equipo/estudio

    auditoria = relationship("Auditoria", back_populates="resultados")


class ActivityLog(Base):
    """Registro de toda actividad del sistema: consultas, validaciones, acciones."""
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    usuario = Column(String(100), index=True)
    equipo = Column(String(100), index=True)
    accion = Column(String(50), index=True)   # CONSULTA_INICIADA | CONSULTA_COMPLETADA | CONSULTA_ERROR
                                               # VALIDACION_ACEPTADA | VALIDACION_MODIFICADA
                                               # REPORTE_DESCARGADO | HISTORIAL_CONSULTADO
    cuit = Column(String(20), nullable=True)
    periodo = Column(String(10), nullable=True)
    jurisdiccion_id = Column(Integer, nullable=True)
    auditoria_id = Column(Integer, nullable=True)
    detalle = Column(Text, nullable=True)      # Info extra en texto libre


class ArchivoGenerado(Base):
    """Metadatos de los archivos Word/Excel generados por el sistema."""
    __tablename__ = "archivos_generados"

    id = Column(Integer, primary_key=True, index=True)
    auditoria_id = Column(Integer, ForeignKey("auditorias.id"))
    
    tipo = Column(String(20))  # 'WORD' o 'EXCEL'
    nombre_archivo = Column(String(255))
    ruta_archivo = Column(String(500))
    fecha_creacion = Column(DateTime, default=datetime.now)
    
    auditoria = relationship("Auditoria", back_populates="archivos")


# Configuración de Engine y Sesión
engine = create_engine(
    db_cfg.uri, 
    connect_args={"check_same_thread": False} if "sqlite" in db_cfg.uri else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Migración automática: agrega columnas nuevas si no existen (safe para SQLite)
    from sqlalchemy import text
    with engine.connect() as conn:
        for ddl in [
            "ALTER TABLE resultados_actividad ADD COLUMN alicuota_anterior REAL",
            "ALTER TABLE resultados_actividad ADD COLUMN validacion_estado TEXT DEFAULT 'PENDIENTE'",
            "ALTER TABLE resultados_actividad ADD COLUMN alicuota_validada REAL",
            "ALTER TABLE resultados_actividad ADD COLUMN comentario_validacion TEXT",
            "ALTER TABLE resultados_actividad ADD COLUMN fecha_validacion DATETIME",
            "ALTER TABLE auditorias ADD COLUMN caso_id TEXT",
            "ALTER TABLE resultados_actividad ADD COLUMN validado_por TEXT",
            "ALTER TABLE resultados_actividad ADD COLUMN equipo_validacion TEXT",
            """CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT, equipo TEXT, accion TEXT,
                cuit TEXT, periodo TEXT, jurisdiccion_id INTEGER,
                auditoria_id INTEGER, detalle TEXT
            )""",
        ]:
            try:
                conn.execute(text(ddl))
                conn.commit()
            except Exception:
                pass  # La columna ya existe
    print(f"Base de datos inicializada en: {db_cfg.uri}")

def log_actividad(
    db,
    accion: str,
    usuario: str = "Especialista",
    equipo: str = "Lisicki Litvin",
    cuit: str = None,
    periodo: str = None,
    jurisdiccion_id: int = None,
    auditoria_id: int = None,
    detalle: str = None,
):
    """Registra una acción en el log de actividad."""
    try:
        entry = ActivityLog(
            usuario=usuario,
            equipo=equipo,
            accion=accion,
            cuit=cuit,
            periodo=periodo,
            jurisdiccion_id=jurisdiccion_id,
            auditoria_id=auditoria_id,
            detalle=detalle,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


def clear_all_audits(db):
    """Borra todos los registros de auditoría y resultados."""
    try:
        db.query(Auditoria).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error al limpiar DB: {e}")
        return False

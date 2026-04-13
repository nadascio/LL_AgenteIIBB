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
    justificacion = Column(Text)
    normativa_ref = Column(String(500))
    
    auditoria = relationship("Auditoria", back_populates="resultados")


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
    print(f"Base de datos inicializada en: {db_cfg.uri}")

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

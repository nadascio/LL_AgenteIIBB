"""
memory/case_history.py — Gestor del historial de casos (SQLAlchemy Version)

Ahora utiliza una base de datos relacional (SQLite por defecto, Azure SQL soportado)
para garantizar escalabilidad, seguridad y concurrencia.
"""

import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy import select, desc

from config import paths_cfg, agent_cfg

# Configuración de Base de Datos
# Azure SQL se configura vía Connection String en el .env (proóximamente)
DB_PATH = f"sqlite:///{paths_cfg.cases_db.with_suffix('.db')}"
Base = declarative_base()

class CaseModel(Base):
    """Modelo relacional para un caso de auditoría fiscal."""
    __tablename__ = "casos_historial"

    id = Column(String(10), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cuit = Column(String(20), index=True)
    provincia_id = Column(String(10), index=True)
    actividades_desc = Column(Text)
    naes_code = Column(String(50))
    volumen_ventas_anual = Column(Float)
    situacion_especial = Column(Text) # Antes tags_condicion (JSON)
    
    alicuota_determinada = Column(Float)
    final_alicuota = Column(Float)
    alicuota_periodo_anterior = Column(Float, nullable=True)
    periodo = Column(String(10))
    
    norma_citada = Column(String(255))
    articulo_citado = Column(String(255))
    razonamiento_resumen = Column(Text)
    analista = Column(String(100))
    
    expert_validated = Column(Boolean, default=False)
    expert_comments = Column(Text, nullable=True)
    timestamp_validacion = Column(DateTime, nullable=True)

class CaseHistory:
    """Implementación de CaseHistory usando SQLAlchemy."""

    def __init__(self, db_url: str = DB_PATH):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def register_case(
        self,
        cuit: str,
        provincia_id: str,
        actividades_desc: str,
        alicuota_determinada: float,
        norma_citada: str | None = None,
        articulo_citado: str | None = None,
        naes_code: str | None = None,
        volumen_ventas_anual: float = 0.0,
        situacion_especial: str | None = None,
        alicuota_periodo_anterior: float | None = None,
        razonamiento_resumen: str | None = None,
        analista: str | None = None,
        periodo: str | None = None,
        expert_validated: bool = False,
        expert_comments: str | None = None
    ) -> str:
        case_id = str(uuid.uuid4())[:8].upper()
        
        with self.SessionLocal() as session:
            db_case = CaseModel(
                id=case_id,
                timestamp=datetime.now(),
                cuit=cuit,
                provincia_id=provincia_id,
                actividades_desc=actividades_desc,
                naes_code=naes_code,
                volumen_ventas_anual=volumen_ventas_anual,
                situacion_especial=situacion_especial,
                alicuota_determinada=alicuota_determinada,
                final_alicuota=alicuota_determinada,
                alicuota_periodo_anterior=alicuota_periodo_anterior,
                periodo=periodo or str(datetime.now().year),
                norma_citada=norma_citada,
                articulo_citado=articulo_citado,
                razonamiento_resumen=razonamiento_resumen,
                analista=analista or "Agente IIBB",
                expert_validated=expert_validated,
                expert_comments=expert_comments
            )
            session.add(db_case)
            session.commit()
            return case_id

    def update_validation(
        self,
        case_id: str,
        expert_validated: bool = True,
        expert_comments: str | None = None,
        final_alicuota: float | None = None,
        manual_norma: str | None = None,
    ) -> bool:
        with self.SessionLocal() as session:
            case = session.get(CaseModel, case_id)
            if not case:
                return False
            
            case.expert_validated = expert_validated
            if expert_comments:
                case.expert_comments = expert_comments
            if final_alicuota is not None:
                case.final_alicuota = final_alicuota
            if manual_norma:
                case.norma_citada = manual_norma
            
            case.timestamp_validacion = datetime.now()
            session.commit()
            return True

    def find_similar(
        self,
        actividades_desc: str,
        provincia_id: str,
        naes_code: str | None = None,
        max_results: int | None = None,
    ) -> list[dict]:
        max_results = max_results or agent_cfg.max_history_references
        
        with self.SessionLocal() as session:
            # Priorizar match exacto por NAES y Provincia
            stmt = select(CaseModel).where(CaseModel.provincia_id == provincia_id)
            if naes_code:
                stmt = stmt.where(CaseModel.naes_code == naes_code)
            
            # Validados por experto primero, luego por fecha descendente
            stmt = stmt.order_by(desc(CaseModel.expert_validated), desc(CaseModel.timestamp)).limit(max_results)
            results = session.execute(stmt).scalars().all()
            
            # Convertir a dict para compatibilidad con el resto del sistema
            return [self._to_dict(r) for r in results]

    def _to_dict(self, model: CaseModel) -> dict:
        """Convierte un modelo SQLAlchemy a diccionario."""
        return {c.name: getattr(model, c.name) for c in model.__table__.columns}

    def format_as_context(self, casos: list[dict]) -> str:
        """Mantiene la lógica de formateo para el LLM."""
        if not casos:
            return "No se encontraron casos previos similares en el historial del equipo."

        lines = [f"Se encontraron {len(casos)} caso(s) previo(s) similar(es):\n"]
        for caso in casos:
            validado_str = " [SELLO: VALIDADO POR EXPERTO]" if caso.get("expert_validated") else " [Sugerencia IA]"
            expert_comm = f"\n    Comentarios experto: {caso['expert_comments']}" if caso.get("expert_comments") else ""
            
            lines.append(
                f"── Caso ID #{caso['id']}{validado_str} ──\n"
                f"  CUIT: {caso['cuit']} | Provincia: {caso['provincia_id'].upper()} | Período: {caso['periodo']}\n"
                f"  Actividad: {caso['actividades_desc']}\n"
                f"  NAES: {caso.get('naes_code', 'N/A')}\n"
                f"  Alícuota Aplicada: {caso.get('final_alicuota')}%\n"
                f"  Norma: {caso['norma_citada']} | {caso['articulo_citado']}\n"
                f"  Analista: {caso['analista']} | Fecha: {str(caso['timestamp'])[:10]}{expert_comm}"
            )
        return "\n\n".join(lines)

    def count(self) -> int:
        with self.SessionLocal() as session:
            from sqlalchemy import func
            return session.query(func.count(CaseModel.id)).scalar()

import pandas as pd
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import re
from core.agent import IIBBAgent, AgentInput, ActividadInput
from core.database import Auditoria, ResultadoActividad, ArchivoGenerado
from output.word_generator import generar_informe_word
import os

class AuditorProcessor:
    def __init__(self, db: Session, output_base_dir: str = "resultados"):
        self.db = db
        self.agent = IIBBAgent()
        self.agent.initialize()
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

    def process_dataframe(self, df: pd.DataFrame, progress_callback=None):
        """Procesa un DataFrame con el contrato definitivo de 10 columnas de LL"""
        from core.constants import JURISDICCIONES
        
        processed_count = 0
        total_rows = len(df)
        
        for index, row in df.iterrows():
            cuit = str(row.get('Cuit', ''))
            periodo_raw = str(row.get('Periodo', ''))
            # Normalizar periodo a Año únicamente (ANUAL)
            periodo = re.sub(r"\D", "", periodo_raw)[:4] if periodo_raw else datetime.now().strftime("%Y")
            if not periodo: periodo = datetime.now().strftime("%Y")
            
            juris_code = int(row.get('Codigo_Jurisdiccion', 0))
            provincia = JURISDICCIONES.get(juris_code, f"Jurisdiccion_{juris_code}")
            
            # Log progress
            if progress_callback:
                progress_callback(f"Analizando CUIT {cuit} - {provincia}...", (index + 1) / total_rows)
            
            # 1. Crear registro de Auditoría
            nueva_auditoria = Auditoria(
                cuit=cuit,
                periodo=periodo,
                provincia_id=juris_code,
                estado="PROCESANDO",
                fecha_proceso=datetime.now()
            )
            self.db.add(nueva_auditoria)
            self.db.commit()
            self.db.refresh(nueva_auditoria)
            
            try:
                # 2. Extraer datos del contrato de 10 puntos
                volumen = float(row.get('Volumen de Venta', 0))
                desc_naes = str(row.get('Desc_Actividad_NAES', ''))
                code_naes = str(row.get('Codigo_NAES', ''))
                desc_real = str(row.get('Des_Actividad_Real', ''))
                cond_iva = str(row.get('Condicion_IVA', ''))
                ali_ant = float(row.get('Alicuota_Anterior', 0)) if pd.notna(row.get('Alicuota_Anterior')) else None
                sit_esp = str(row.get('Situacion_Especial', ''))
                
                # 3. Mapear para la IA (Unificamos las actividades para el agente)
                act_input = ActividadInput(
                    desc=f"{desc_naes} | REAL: {desc_real}",
                    naes=code_naes
                )
                
                in_data = AgentInput(
                    cuit=cuit,
                    periodo=periodo,
                    volumen_ventas_anual=volumen,
                    actividades=[act_input],
                    provincia_id=provincia,
                    alicuota_periodo_anterior=ali_ant,
                    analista="Portal Auditor LL",
                    situacion_especial=f"Condición IVA: {cond_iva}. {sit_esp}"
                )
                
                # 4. Llamar a la IA
                resultado_ia = self.agent.analizar(in_data)
                
                # 5. Guardar resultados detallados
                db_results_data = [] # Para el generador de Excel
                for res_act in resultado_ia.resultados_por_actividad:
                    ia_rate = getattr(res_act, 'alicuota_ia', 0.0)
                    db_res = ResultadoActividad(
                        auditoria_id=nueva_auditoria.id,
                        actividad_desc=getattr(res_act, 'actividad_desc_norma', "Actividad no identificada"),
                        naes=getattr(res_act, 'naes_encontrado', "000000"),
                        alicuota_base=getattr(res_act, 'alicuota_base', 0.0),
                        alicuota_sugerida=getattr(res_act, 'alicuota_final', 0.0),
                        alicuota_ia=ia_rate,
                        justificacion=getattr(res_act, 'justificacion', ""),
                        normativa_ref=f"{getattr(res_act, 'norma_ref_actividad', 'N/A')} - Art. {getattr(res_act, 'articulo_actividad', 'N/A')}"
                    )
                    self.db.add(db_res)
                    
                    db_results_data.append({
                        'actividad_desc': db_res.actividad_desc,
                        'naes': db_res.naes,
                        'alicuota_base': db_res.alicuota_base,
                        'alicuota_sugerida': db_res.alicuota_sugerida,
                        'alicuota_ia': db_res.alicuota_ia,
                        'normativa_ref': db_res.normativa_ref
                    })
                
                # 6. Generar Informe Word
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                client_dir = self.output_base_dir / cuit.replace('-', '')
                client_dir.mkdir(parents=True, exist_ok=True)
                
                word_path = client_dir / f"Informe_{cuit}_{timestamp}.docx"
                generar_informe_word(
                    cuit=in_data.cuit,
                    periodo=in_data.periodo,
                    provincia_id=in_data.provincia_id,
                    volumen_ventas_anual=in_data.volumen_ventas_anual,
                    resultados_calc=resultado_ia.resultados_por_actividad,
                    justificacion_llm=resultado_ia.justificacion_llm,
                    situacion_especial=in_data.situacion_especial,
                    output_path=str(word_path)
                )
                
                # Excel
                from output.excel_generator import generate_excel_report
                excel_path = client_dir / f"Informe_{cuit}_{timestamp}.xlsx"
                generate_excel_report(
                    audit_data={
                        'cuit': cuit,
                        'provincia': provincia,
                        'volumen': volumen,
                        'resumen_ia': resultado_ia.resumen_ejecutivo
                    },
                    results=db_results_data,
                    output_path=str(excel_path)
                )
                
                # 7. Registrar archivos y finalizar
                for path, tipo in [(word_path, "WORD"), (excel_path, "EXCEL")]:
                    nuevo_archivo = ArchivoGenerado(
                        auditoria_id=nueva_auditoria.id,
                        nombre_archivo=path.name,
                        ruta_archivo=str(path),
                        tipo=tipo
                    )
                    self.db.add(nuevo_archivo)
                
                nueva_auditoria.estado = "COMPLETADO"
                nueva_auditoria.resumen_ia = resultado_ia.resumen_ejecutivo
                processed_count += 1
                
            except Exception as e:
                nueva_auditoria.estado = "ERROR"
                nueva_auditoria.resumen_ia = f"Error: {str(e)}"
            
            self.db.commit()
            
        return processed_count

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

# ============================================================================
# 1. ESQUEMA ESTRICTO DE SALIDA (GARANTIZA CERO ALUCINACIONES DE FORMATO)
# ============================================================================

class CitedEvidence(BaseModel):
    chunk_id: UUID = Field(..., description="UUID exacto del fragmento en la tabla literature_chunks")
    book_title: str = Field(..., description="Título del libro o guía clínica citada")
    branch: str = Field(..., description="Rama: convencional_alopatica, natural_fitoterapia, protocolo_enfermeria, etc.")
    page_and_section: str = Field(..., description="Página y sección exacta de donde proviene el respaldo")
    clinical_relevance: str = Field(..., description="Explicación breve de cómo este texto respalda el diagnóstico o curación")

class DifferentialDiagnosisItem(BaseModel):
    pathology_name: str = Field(..., description="Nombre de la patología o condición sospechada")
    cie11_code_estimate: str = Field(..., description="Código CIE-11 estimado")
    probability_level: str = Field(..., description="Alta, Media o Baja")
    supporting_biomarkers: List[str] = Field(..., description="Valores de máquinas de laboratorio (HL7/DICOM) que sustentan esta hipótesis")
    reasoning: str = Field(..., description="Razonamiento fisiopatológico detallado")

class SuggestedTreatmentAndCuration(BaseModel):
    conventional_approach: List[str] = Field(..., description="Opciones farmacológicas o clínicas convencionales basadas en la evidencia")
    natural_complementary_approach: List[str] = Field(..., description="Opciones de medicina natural/fitoterapia validadas y seguras para el caso")
    nursing_curation_protocol: List[str] = Field(..., description="Pasos técnicos de monitoreo, curación de heridas o cuidados de enfermería")
    recommended_capital_equipment_studies: List[str] = Field(..., description="Estudios adicionales sugeridos en máquinas de laboratorio o imagenología de capitales")

class InteractionAlert(BaseModel):
    compounds_involved: str = Field(..., description="Fármaco sintético y compuesto natural en conflicto")
    severity: str = Field(..., description="Gravedad: leve, moderada, grave o contraindicado")
    action_required: str = Field(..., description="Medida preventiva recomendada al médico")

class AIClinicalOutputSchema(BaseModel):
    clinical_summary: str = Field(..., description="Síntesis ejecutiva del estado del paciente y hallazgos críticos de laboratorio")
    differential_diagnoses: List[DifferentialDiagnosisItem]
    treatment_and_curation_plan: SuggestedTreatmentAndCuration
    pharmacological_warnings: List[InteractionAlert]
    cited_literature: List[CitedEvidence]
    human_governance_disclaimer: str = Field(
        default="ADVERTENCIA LEGAL Y CLÍNICA: Este análisis ha sido generado por un sistema de Inteligencia Artificial de soporte diagnóstico. NO constituye una orden médica ni reemplaza el juicio clínico. La decisión final y la responsabilidad recaen exclusivamente en el médico o enfermero firmante."
    )


# ============================================================================
# 2. SYSTEM PROMPT DE ALTA CAPACIDAD CON CANDADO HUMANO
# ============================================================================

CLINICAL_SYSTEM_PROMPT = """Eres una Inteligencia Artificial de Soporte a la Decisión Clínica (CDSS) de alta capacidad, diseñada para asistir a médicos generales, enfermeros, especialistas e investigadores.

TUS REGLAS OPERATIVAS Y ÉTICAS INQUEBRANTABLES SON:

1. ROL DE ASISTENTE (NUNCA DECISOR):
   - Eres una herramienta de análisis y consulta bibliográfica. JAMÁS emitas órdenes médicas definitivas ni te dirijas al paciente como si fueras el médico tratante.
   - Toda sugerencia debe redactarse en tono técnico-consultivo para el profesional de la salud (ej. "Se sugiere al facultativo valorar...", "El protocolo de enfermería indica considerar...").

2. RIGOR CIENTÍFICO Y TRAZABILIDAD BIBLIOGRÁFICA (CERO INVENCIÓN):
   - Solo puedes fundamentar diagnósticos, tratamientos convencionales, terapias de medicina natural y procesos de curación utilizando los fragmentos provistos en el bloque [EVIDENCIA_BIBLIOGRAFICA_RECUPERADA].
   - Es OBLIGATORIO incluir el `chunk_id`, el título del libro y el número de página exacto de cada fragmento utilizado dentro de la lista `cited_literature`. Si un dato no está respaldado en la evidencia provista, indícalo explícitamente.

3. INTEGRACIÓN DE MEDICINA CONVENCIONAL Y NATURAL:
   - Analiza tanto las guías alopáticas convencionales como la evidencia de fitoterapia y medicina natural disponible en el contexto.
   - Revisa rigurosamente el bloque [ALERTAS_INTERACCION_FARMACOLOGICA]. Si existe una interacción entre un remedio natural que toma el paciente y un fármaco sintético, debes resaltarlo con máxima prioridad en `pharmacological_warnings` y abstenerte de sugerir combinaciones contraindicadas.

4. ANÁLISIS DE MÁQUINAS DE LABORATORIO Y EQUIPOS DE CAPITALES (HL7 / DICOM):
   - Examina los biomarcadores, signos vitales y reportes de imagenología en [CONTEXTO_CLINICO_Y_LABORATORIO].
   - Correlaciona cada valor fuera de rango (banderas anormales o alertas críticas) con los síntomas descritos por el médico o enfermero. Si el caso requiere equipamiento especializado de un hospital en la capital (ej. resonancia magnética, citometría de flujo, gases arteriales avanzados), inclúyelo en `recommended_capital_equipment_studies`.

5. FORMATO DE SALIDA:
   - Responde ÚNICAMENTE con un objeto JSON válido que cumpla de forma estricta con el esquema solicitado, sin texto adicional fuera del JSON.
"""

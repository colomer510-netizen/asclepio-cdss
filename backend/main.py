import os
import hashlib
import json
from contextlib import asynccontextmanager
from typing import List, Optional
from uuid import UUID

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pgvector.asyncpg import register_vector
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from clinical_prompt_spec import AIClinicalOutputSchema, CLINICAL_SYSTEM_PROMPT
from clinical_guardrails import MedicalAIGuardrail, ClinicalSafetyViolationError

# Configuración de entorno
DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/asclepio_cdss")
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434/api/chat")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "llama3.2:latest")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-mpnet-base-v2")

# Recursos globales del servidor
db_pool: Optional[asyncpg.Pool] = None
embedder: Optional[SentenceTransformer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, embedder
    try:
        print(f"[*] Cargando modelo de embeddings: {EMBEDDING_MODEL_NAME}...")
        embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as e:
        print(f"[!] Advertencia al inicializar embedder: {e}")

    try:
        print(f"[*] Conectando a PostgreSQL ({DB_DSN})...")
        db_pool = await asyncpg.create_pool(DB_DSN, init=register_vector, min_size=2, max_size=10)
    except Exception as e:
        print(f"[!] Error de conexión PostgreSQL (modo offline/arranque sin DB): {e}")

    yield

    if db_pool:
        await db_pool.close()


app = FastAPI(
    title="Plataforma CDSS de IA Médica y Monitoreo Hospitalario",
    description="Asistente clínico conectado a pgvector y máquinas HL7/DICOM bajo supervisión humana estricta.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend estático si existe
frontend_candidates = [
    os.path.join(os.path.dirname(__file__), "frontend"),
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
    "/app/frontend",
]
for candidate in frontend_candidates:
    if os.path.exists(candidate):
        app.mount("/static", StaticFiles(directory=candidate, html=True), name="static")
        print(f"[*] Frontend montado en /static desde: {candidate}")
        break


# ============================================================================
# MODELOS DE ENTRADA DE LA API (REQUEST PAYLOADS)
# ============================================================================

class ConsultationRequest(BaseModel):
    patient_id: UUID
    requesting_staff_id: UUID
    symptoms_and_clinical_notes: str = Field(..., min_length=10)
    proposed_synthetic_drugs: List[str] = Field(default_factory=list)
    proposed_natural_remedies: List[str] = Field(default_factory=list)
    lab_window_hours: int = Field(default=72, ge=1, le=720)
    similarity_threshold: float = Field(default=0.68, ge=0.5, le=0.95)
    chunks_per_branch: int = Field(default=3, ge=1, le=10)


class HumanDecisionRequest(BaseModel):
    consultation_id: UUID
    patient_id: UUID
    deciding_staff_id: UUID
    resolution_status: str = Field(
        ...,
        pattern="^(aprobado_sin_cambios|aprobado_con_modificaciones|rechazado_criterio_medico|escalado_a_especialista_capital)$",
    )
    final_clinical_diagnosis: str = Field(..., min_length=5)
    final_treatment_and_curation_plan: str = Field(..., min_length=10)
    clinical_justification: str = Field(..., min_length=10)
    staff_passphrase_or_token: str = Field(..., description="Clave privada o token del profesional para sellar su firma digital")


# ============================================================================
# CONSULTAS SQL INTEGRADAS
# ============================================================================

SQL_BALANCED_RAG = """
SELECT 
    b.branch::text AS rama_medica,
    q.chunk_id,
    q.title AS libro_o_guia,
    q.publication_year AS anio,
    q.evidence_level AS nivel_evidencia,
    q.chapter_title AS capitulo,
    q.page_number AS pagina,
    q.section_reference AS seccion,
    q.content_text AS fragmento_evidencia,
    ROUND(q.similitud::numeric, 4) AS score_similitud
FROM (SELECT unnest(ENUM_RANGE(NULL::medicine_branch)) AS branch) b
CROSS JOIN LATERAL (
    SELECT 
        lc.chunk_id, ml.title, ml.publication_year, ml.evidence_level,
        lc.chapter_title, lc.page_number, lc.section_reference, lc.content_text,
        1 - (lc.embedding <=> $1::vector) AS similitud
    FROM literature_chunks lc
    INNER JOIN medical_literature ml ON lc.document_id = ml.document_id
    WHERE ml.branch = b.branch
      AND (1 - (lc.embedding <=> $1::vector)) >= $2
    ORDER BY lc.embedding <=> $1::vector ASC
    LIMIT $3
) q
ORDER BY q.similitud DESC;
"""

SQL_PHARMA_INTERACTIONS = """
WITH patient_active_regimen AS (
    SELECT 
        ARRAY(
            SELECT jsonb_array_elements_text(active_conventional_meds)
            UNION SELECT unnest(COALESCE($2::text[], ARRAY[]::text[]))
        ) AS all_synthetic_drugs,
        ARRAY(
            SELECT jsonb_array_elements_text(active_natural_remedies)
            UNION SELECT unnest(COALESCE($3::text[], ARRAY[]::text[]))
        ) AS all_natural_compounds
    FROM patients WHERE patient_id = $1
)
SELECT 
    pi.natural_compound, pi.synthetic_drug, pi.severity_level,
    pi.clinical_effect, pi.mechanism_description, ml.title AS fuente
FROM pharmacological_interactions pi
CROSS JOIN patient_active_regimen par
LEFT JOIN medical_literature ml ON pi.reference_document_id = ml.document_id
WHERE EXISTS (
    SELECT 1 FROM unnest(par.all_natural_compounds) nc WHERE pi.natural_compound ILIKE '%' || nc || '%'
) AND EXISTS (
    SELECT 1 FROM unnest(par.all_synthetic_drugs) sd WHERE pi.synthetic_drug ILIKE '%' || sd || '%'
)
ORDER BY CASE pi.severity_level
    WHEN 'contraindicado' THEN 1 WHEN 'grave' THEN 2 WHEN 'moderada' THEN 3 WHEN 'leve' THEN 4
END ASC;
"""

SQL_PATIENT_AND_MACHINES_CONTEXT = """
SELECT jsonb_build_object(
    'paciente', jsonb_build_object(
        'expediente', p.medical_record_number,
        'nombre', p.full_name,
        'edad_anios', EXTRACT(YEAR FROM age(CURRENT_DATE, p.birth_date)),
        'tipo_sangre', p.blood_type,
        'alergias', p.known_allergies,
        'condiciones_cronicas', p.chronic_conditions,
        'medicacion_convencional_activa', p.active_conventional_meds,
        'medicina_natural_activa', p.active_natural_remedies
    ),
    'resultados_maquinas_recientes', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'result_id', mdr.result_id,
                'fecha_captura', mdr.captured_at,
                'estudio', mdr.study_type,
                'alerta_critica', mdr.critical_alert,
                'equipo_nombre', me.equipment_name,
                'hospital_origen', me.location_hospital,
                'banderas_anormales', mdr.abnormal_flags,
                'valores_hl7_fhir', mdr.raw_machine_payload,
                'uri_imagen_dicom', mdr.dicom_storage_uri
            ) ORDER BY mdr.critical_alert DESC, mdr.captured_at DESC
        )
        FROM machine_diagnostic_results mdr
        INNER JOIN medical_equipment me ON mdr.equipment_id = me.equipment_id
        WHERE mdr.patient_id = p.patient_id
          AND mdr.captured_at >= NOW() - ($2 || ' hours')::interval
    ), '[]'::jsonb)
) AS contexto_clinico_completo
FROM patients p WHERE p.patient_id = $1;
"""


# ============================================================================
# ENDPOINT 1: ANÁLISIS CLÍNICO ASISTIDO POR IA (NO VINCULANTE)
# ============================================================================

@app.post("/api/v1/consultations/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_clinical_case(req: ConsultationRequest):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")

    # 1. Vectorizar los síntomas
    query_vector = embedder.encode(req.symptoms_and_clinical_notes, normalize_embeddings=True).tolist()

    async with db_pool.acquire() as conn:
        # 2. Contexto de paciente y máquinas
        raw_context = await conn.fetchval(SQL_PATIENT_AND_MACHINES_CONTEXT, req.patient_id, req.lab_window_hours)
        if not raw_context:
            raise HTTPException(status_code=404, detail="Paciente no encontrado en la base de datos.")
        patient_context = json.loads(raw_context)

        # 3. RAG balanceado en pgvector
        rag_rows = await conn.fetch(
            SQL_BALANCED_RAG, query_vector, req.similarity_threshold, req.chunks_per_branch
        )
        literature_evidence = [dict(row) for row in rag_rows]
        for item in literature_evidence:
            item["chunk_id"] = str(item["chunk_id"])
            item["score_similitud"] = float(item["score_similitud"])

        # 4. Alertas farmacológicas cruzadas
        interaction_rows = await conn.fetch(
            SQL_PHARMA_INTERACTIONS,
            req.patient_id,
            req.proposed_synthetic_drugs,
            req.proposed_natural_remedies,
        )
        interactions_detected = [dict(row) for row in interaction_rows]

        # 5. Inferencia LLM
        user_prompt = f"""
[CUADRO_CLINICO_INGRESADO_POR_PROFESIONAL]
{req.symptoms_and_clinical_notes}

[CONTEXTO_CLINICO_Y_LABORATORIO]
{json.dumps(patient_context, ensure_ascii=False, indent=2)}

[ALERTAS_INTERACCION_FARMACOLOGICA]
{json.dumps(interactions_detected, ensure_ascii=False, indent=2)}

[EVIDENCIA_BIBLIOGRAFICA_RECUPERADA]
{json.dumps(literature_evidence, ensure_ascii=False, indent=2)}
"""

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                llm_response = await client.post(
                    LLM_API_URL,
                    json={
                        "model": LLM_MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": CLINICAL_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "format": AIClinicalOutputSchema.model_json_schema(),
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                if llm_response.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"Error del motor LLM ({llm_response.status_code}): {llm_response.text}")
                
                ai_raw_content = llm_response.json()["message"]["content"]
                validated_ai_output = AIClinicalOutputSchema.model_validate_json(ai_raw_content)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Falla en la inferencia clínica: {str(e)}")

        # 6. Cortafuegos de seguridad
        valid_chunk_uuids = {UUID(item["chunk_id"]) for item in literature_evidence}
        try:
            validated_ai_output = MedicalAIGuardrail.validate_ai_output(
                ai_output=validated_ai_output,
                retrieved_chunk_ids=valid_chunk_uuids,
                db_detected_interactions=interactions_detected,
            )
        except ClinicalSafetyViolationError as safety_err:
            raise HTTPException(
                status_code=422,
                detail=f"Filtro de Seguridad Clínica activado: {str(safety_err)}",
            )

        # 7. Guardar en ai_clinical_consultations
        machine_ids = [
            UUID(m["result_id"]) for m in patient_context.get("resultados_maquinas_recientes", [])
        ]
        cited_chunk_ids = [item.chunk_id for item in validated_ai_output.cited_literature]

        consultation_id = await conn.fetchval(
            """
            INSERT INTO ai_clinical_consultations (
                patient_id, requesting_staff_id, input_symptoms_and_notes,
                analyzed_machine_results, cited_literature_chunks, ai_model_version,
                ai_suggested_diagnosis, ai_suggested_treatment_plan, interaction_warnings
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb)
            RETURNING consultation_id;
            """,
            req.patient_id,
            req.requesting_staff_id,
            req.symptoms_and_clinical_notes,
            machine_ids,
            cited_chunk_ids,
            LLM_MODEL_NAME,
            json.dumps([d.model_dump(mode="json") for d in validated_ai_output.differential_diagnoses]),
            validated_ai_output.treatment_and_curation_plan.model_dump_json(),
            json.dumps([w.model_dump(mode="json") for w in validated_ai_output.pharmacological_warnings]),
        )

    return {
        "consultation_id": consultation_id,
        "status": "PENDIENTE_VALIDACION_HUMANA",
        "ai_assistance_report": validated_ai_output.model_dump(mode="json"),
    }


# ============================================================================
# ENDPOINT 2: VALIDACIÓN Y FIRMA DEL MÉDICO O ENFERMERO (FACTOR HUMANO)
# ============================================================================

@app.post("/api/v1/decisions/validate", status_code=status.HTTP_201_CREATED)
async def register_human_medical_decision(req: HumanDecisionRequest):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Base de datos no disponible.")

    payload_to_sign = (
        f"{req.consultation_id}|{req.patient_id}|{req.deciding_staff_id}|"
        f"{req.final_clinical_diagnosis}|{req.final_treatment_and_curation_plan}|{req.staff_passphrase_or_token}"
    )
    signature_hash = hashlib.sha256(payload_to_sign.encode("utf-8")).hexdigest()

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH staff_verification AS (
                SELECT staff_id
                FROM clinical_staff
                WHERE staff_id = $3
                  AND is_active = TRUE
                  AND role IN ('medico_general', 'especialista', 'enfermero')
            )
            INSERT INTO human_medical_decisions (
                consultation_id, patient_id, deciding_staff_id,
                resolution_status, final_clinical_diagnosis,
                final_treatment_and_curation_plan, clinical_justification,
                digital_signature_hash
            )
            SELECT $1, $2, sv.staff_id, $4::human_resolution_status, $5, $6, $7, $8
            FROM staff_verification sv
            RETURNING decision_id, decided_at;
            """,
            req.consultation_id,
            req.patient_id,
            req.deciding_staff_id,
            req.resolution_status,
            req.final_clinical_diagnosis,
            req.final_treatment_and_curation_plan,
            req.clinical_justification,
            signature_hash,
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Autorización denegada: El profesional no existe, está inactivo o no posee rol clínico habilitado para firmar decisiones.",
            )

    return {
        "decision_id": row["decision_id"],
        "decided_at": row["decided_at"],
        "digital_signature_hash": signature_hash,
        "legal_status": "DECISIÓN MÉDICA HUMANA REGISTRADA Y FIRMADA EN EXPEDIENTE",
    }

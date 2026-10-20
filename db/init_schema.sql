-- ============================================================================
-- PLATAFORMA CDSS - SISTEMA DE SOPORTE A LA DECISIÓN CLÍNICA
-- Esquema DDL en PostgreSQL con soporte para pgvector y auditoría inmutable
-- ============================================================================

-- 0. EXTENSIONES NECESARIAS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector"; -- pgvector para búsqueda semántica en literatura médica

-- ============================================================================
-- 1. PERSONAL DE SALUD Y PACIENTES (CORE CLÍNICO)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE staff_role AS ENUM (
        'enfermero', 
        'medico_general', 
        'especialista', 
        'investigador', 
        'tecnico_laboratorio'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS clinical_staff (
    staff_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(150) NOT NULL,
    license_number VARCHAR(50) UNIQUE NOT NULL, -- Código sanitario / MINSA
    role staff_role NOT NULL,
    specialty VARCHAR(100),
    hospital_center VARCHAR(150) NOT NULL,
    public_key_hash TEXT NOT NULL, -- Para firma digital de decisiones médicas
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medical_record_number VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    birth_date DATE NOT NULL,
    blood_type VARCHAR(5),
    known_allergies TEXT[],
    active_conventional_meds JSONB DEFAULT '[]'::jsonb, -- Fármacos actuales
    active_natural_remedies JSONB DEFAULT '[]'::jsonb,  -- Plantas/tratamientos naturales actuales
    chronic_conditions TEXT[],
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. BIBLIOTECA MÉDICA HÍBRIDA (CONVENCIONAL Y NATURAL) + PGVECTOR
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE medicine_branch AS ENUM (
        'convencional_alopatica', 
        'natural_fitoterapia', 
        'protocolo_enfermeria', 
        'investigacion_clinica'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS medical_literature (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(300) NOT NULL,
    authors TEXT[],
    publication_year INT,
    branch medicine_branch NOT NULL,
    isbn_or_doi VARCHAR(100) UNIQUE,
    evidence_level VARCHAR(50), -- Ej: Nivel IA, Guía Clínica, Farmacopea Vegetal
    source_institution VARCHAR(150),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Tabla vectorial para RAG (Búsqueda Semántica en Libros y Guías)
CREATE TABLE IF NOT EXISTS literature_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES medical_literature(document_id) ON DELETE CASCADE,
    chapter_title VARCHAR(200),
    page_number INT NOT NULL,
    section_reference VARCHAR(100),
    content_text TEXT NOT NULL,
    -- Vector de 768 dimensiones (SentenceTransformer paraphrase-multilingual-mpnet-base-v2)
    embedding vector(768) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Índice HNSW para búsqueda vectorial ultrarrápida mediante similitud coseno
CREATE INDEX IF NOT EXISTS idx_literature_chunks_embedding 
ON literature_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Tabla para cruce de interacciones: Medicina Natural vs. Fármacos Sintéticos
CREATE TABLE IF NOT EXISTS pharmacological_interactions (
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    natural_compound VARCHAR(150) NOT NULL,   -- Ej: Hypericum perforatum (Hierba de San Juan)
    synthetic_drug VARCHAR(150) NOT NULL,     -- Ej: Warfarina / Anticoagulantes
    severity_level VARCHAR(30) NOT NULL CHECK (severity_level IN ('leve', 'moderada', 'grave', 'contraindicado')),
    clinical_effect TEXT NOT NULL,
    mechanism_description TEXT NOT NULL,
    reference_document_id UUID REFERENCES medical_literature(document_id)
);

-- ============================================================================
-- 3. MÁQUINAS DE LABORATORIO Y EQUIPOS DE CAPITALES (IoMT / HL7 / DICOM)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE equipment_category AS ENUM (
        'analizador_hematologico',
        'analizador_bioquimico',
        'monitor_signos_vitales',
        'imagenologia_dicom',
        'microbiologia'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS medical_equipment (
    equipment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    equipment_name VARCHAR(150) NOT NULL,
    category equipment_category NOT NULL,
    location_hospital VARCHAR(150) NOT NULL, -- Ej: Hospital Central en Capital o Clínica Local
    protocol_standard VARCHAR(50) NOT NULL,  -- Ej: HL7_FHIR, DICOM, MQTT
    ip_endpoint INET,
    is_online BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS machine_diagnostic_results (
    result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(patient_id),
    equipment_id UUID NOT NULL REFERENCES medical_equipment(equipment_id),
    ordered_by_staff UUID REFERENCES clinical_staff(staff_id),
    study_type VARCHAR(120) NOT NULL,
    -- Almacena la trama cruda HL7 FHIR Observation o cabeceras DICOM
    raw_machine_payload JSONB NOT NULL,
    -- Biomarcadores o hallazgos fuera de rango detectados automáticamente
    abnormal_flags JSONB DEFAULT '[]'::jsonb,
    dicom_storage_uri TEXT, -- Ruta al servidor PACS/NAS si es radiografía o tomografía
    critical_alert BOOLEAN DEFAULT FALSE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_machine_results_patient ON machine_diagnostic_results(patient_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_machine_results_jsonb ON machine_diagnostic_results USING gin (raw_machine_payload);

-- ============================================================================
-- 4. ASISTENCIA DE IA Y AUDITORÍA DEL FACTOR HUMANO (GOBERNANZA)
-- ============================================================================

-- Registro de lo que la IA analiza y sugiere (NUNCA es una orden médica directa)
CREATE TABLE IF NOT EXISTS ai_clinical_consultations (
    consultation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID NOT NULL REFERENCES patients(patient_id),
    requesting_staff_id UUID NOT NULL REFERENCES clinical_staff(staff_id),
    input_symptoms_and_notes TEXT NOT NULL,
    analyzed_machine_results UUID[] NOT NULL,
    cited_literature_chunks UUID[] NOT NULL,
    ai_model_version VARCHAR(80) NOT NULL,
    ai_suggested_diagnosis JSONB NOT NULL,
    ai_suggested_treatment_plan JSONB NOT NULL,
    interaction_warnings JSONB DEFAULT '[]'::jsonb,
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

DO $$ BEGIN
    CREATE TYPE human_resolution_status AS ENUM (
        'aprobado_sin_cambios',
        'aprobado_con_modificaciones',
        'rechazado_criterio_medico',
        'escalado_a_especialista_capital'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Tabla donde recae la responsabilidad y decisión final del humano
CREATE TABLE IF NOT EXISTS human_medical_decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    consultation_id UUID UNIQUE NOT NULL REFERENCES ai_clinical_consultations(consultation_id),
    patient_id UUID NOT NULL REFERENCES patients(patient_id),
    deciding_staff_id UUID NOT NULL REFERENCES clinical_staff(staff_id),
    resolution_status human_resolution_status NOT NULL,
    final_clinical_diagnosis TEXT NOT NULL,
    final_treatment_and_curation_plan TEXT NOT NULL,
    clinical_justification TEXT NOT NULL,
    digital_signature_hash TEXT NOT NULL,
    decided_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. CANDADO DE SEGURIDAD: INMUTABILIDAD DE LA AUDITORÍA MÉDICA
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Operación bloqueada: Los registros de sugerencias de IA y decisiones médicas humanas son inmutables por auditoría legal.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lock_ai_consultations ON ai_clinical_consultations;
CREATE TRIGGER trg_lock_ai_consultations
BEFORE UPDATE OR DELETE ON ai_clinical_consultations
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

DROP TRIGGER IF EXISTS trg_lock_human_decisions ON human_medical_decisions;
CREATE TRIGGER trg_lock_human_decisions
BEFORE UPDATE OR DELETE ON human_medical_decisions
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

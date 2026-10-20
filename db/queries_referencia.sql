-- ============================================================================
-- CONSULTAS SQL AVANZADAS PARA CDSS Y REGLAS DE DECISIÓN
-- ============================================================================

-- 1. Búsqueda Semántica Balanceada por Rama Médica (pgvector + Lateral Join)
-- $1: vector(768) -> Embedding generado por el modelo
-- $2: float       -> Umbral mínimo de similitud (ej. 0.68)
-- $3: int         -> Cantidad máxima de citas por rama médica (ej. 3)

SELECT 
    b.branch::text AS rama_medica,
    q.chunk_id,
    q.title AS libro_o_guia,
    q.authors AS autores,
    q.publication_year AS anio,
    q.evidence_level AS nivel_evidencia,
    q.chapter_title AS capitulo,
    q.page_number AS pagina,
    q.section_reference AS seccion,
    q.content_text AS fragmento_evidencia,
    ROUND(q.similitud::numeric, 4) AS score_similitud
FROM (
    SELECT unnest(ENUM_RANGE(NULL::medicine_branch)) AS branch
) b
CROSS JOIN LATERAL (
    SELECT 
        lc.chunk_id,
        ml.title,
        ml.authors,
        ml.publication_year,
        ml.evidence_level,
        lc.chapter_title,
        lc.page_number,
        lc.section_reference,
        lc.content_text,
        1 - (lc.embedding <=> $1::vector) AS similitud
    FROM literature_chunks lc
    INNER JOIN medical_literature ml ON lc.document_id = ml.document_id
    WHERE ml.branch = b.branch
      AND (1 - (lc.embedding <=> $1::vector)) >= $2
    ORDER BY lc.embedding <=> $1::vector ASC
    LIMIT $3
) q
ORDER BY q.similitud DESC;

-- 2. Detector de Interacciones Farmacológicas (Medicina Natural vs. Convencional)
-- $1: uuid   -> patient_id
-- $2: text[] -> Nuevos fármacos sintéticos propuestos (ARRAY['Warfarina'])
-- $3: text[] -> Nuevos compuestos naturales propuestos (ARRAY['Ginkgo biloba'])

WITH patient_active_regimen AS (
    SELECT 
        ARRAY(
            SELECT jsonb_array_elements_text(active_conventional_meds)
            UNION
            SELECT unnest(COALESCE($2::text[], ARRAY[]::text[]))
        ) AS all_synthetic_drugs,
        ARRAY(
            SELECT jsonb_array_elements_text(active_natural_remedies)
            UNION
            SELECT unnest(COALESCE($3::text[], ARRAY[]::text[]))
        ) AS all_natural_compounds
    FROM patients
    WHERE patient_id = $1
)
SELECT 
    pi.interaction_id,
    pi.natural_compound AS compuesto_natural,
    pi.synthetic_drug AS farmaco_sintetico,
    pi.severity_level AS gravedad,
    pi.clinical_effect AS efecto_clinico_adverso,
    pi.mechanism_description AS mecanismo_fisiologico,
    ml.title AS fuente_bibliografica,
    ml.isbn_or_doi AS identificador_fuente
FROM pharmacological_interactions pi
CROSS JOIN patient_active_regimen par
LEFT JOIN medical_literature ml ON pi.reference_document_id = ml.document_id
WHERE 
    EXISTS (
        SELECT 1 FROM unnest(par.all_natural_compounds) nc 
        WHERE pi.natural_compound ILIKE '%' || nc || '%'
    )
    AND EXISTS (
        SELECT 1 FROM unnest(par.all_synthetic_drugs) sd 
        WHERE pi.synthetic_drug ILIKE '%' || sd || '%'
    )
ORDER BY 
    CASE pi.severity_level
        WHEN 'contraindicado' THEN 1
        WHEN 'grave' THEN 2
        WHEN 'moderada' THEN 3
        WHEN 'leve' THEN 4
    END ASC;

-- 3. Consolidación de Telemetría y Laboratorio (HL7 / DICOM) en un solo JSONB
-- $1: uuid -> patient_id
-- $2: int  -> Ventana de horas hacia atrás (ej. 72 horas)

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
                'categoria_equipo', me.category,
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
FROM patients p
WHERE p.patient_id = $1;

import re
from typing import ClassVar
from uuid import UUID

from clinical_prompt_spec import AIClinicalOutputSchema


class ClinicalSafetyViolationError(Exception):
    """Excepción disparada cuando la IA viola las reglas de subordinación humana o evidencia."""


class MedicalAIGuardrail:
    # Expresiones regulares que detectan órdenes imperativas o lenguaje que usurpa al médico
    FORBIDDEN_IMPERATIVE_PATTERNS: ClassVar[list[str]] = [
        r"\b(ordeno|prescribo|diagnostico definitivamente|administre de inmediato sin consultar)\b",
        r"\b(usted tiene|usted padece|tome este medicamento)\b",  # Dirigirse al paciente en 2da persona
        r"\b(no es necesario consultar al médico|reemplaza la valoración)\b",
    ]

    @classmethod
    def validate_ai_output(
        cls,
        ai_output: AIClinicalOutputSchema,
        retrieved_chunk_ids: set[UUID],
        db_detected_interactions: list[dict],
    ) -> AIClinicalOutputSchema:
        """
        Audita rigurosamente la salida del modelo antes de mostrarla al doctor o enfermero.
        """
        # 1. VERIFICACIÓN ANTI-ALUCINACIÓN DE CITAS BIBLIOGRÁFICAS
        # Garantiza que la IA solo cite libros y páginas que realmente vinieron de pgvector en esta consulta
        if not ai_output.cited_literature:
            raise ClinicalSafetyViolationError(
                "Respuesta rechazada: La IA generó sugerencias sin adjuntar ninguna cita bibliográfica de respaldo."
            )

        for citation in ai_output.cited_literature:
            if citation.chunk_id not in retrieved_chunk_ids:
                raise ClinicalSafetyViolationError(
                    f"Alerta de alucinación bloqueada: La IA intentó citar un fragmento inexistente "
                    f"o ajeno al contexto actual ({citation.chunk_id})."
                )

        # 2. VERIFICACIÓN DE BLOQUEO POR INTERACCIONES FARMACOLÓGICAS GRAVES
        # Si PostgreSQL detectó una interacción grave/contraindicada, la IA no puede omitirla
        severe_db_interactions = [
            i for i in db_detected_interactions 
            if i.get("severity_level") in ("grave", "contraindicado")
        ]
        if severe_db_interactions and not ai_output.pharmacological_warnings:
            raise ClinicalSafetyViolationError(
                "Violación de seguridad farmacológica: Existen interacciones graves entre medicina natural "
                "y fármacos sintéticos en la base de datos que la IA omitió reportar."
            )

        # 3. ESCANEO LINGÜÍSTICO DE SUBORDINACIÓN HUMANA
        # Revisa todo el texto generado para asegurar que no existan órdenes imperativas
        full_text_dump = ai_output.model_dump_json()
        for pattern in cls.FORBIDDEN_IMPERATIVE_PATTERNS:
            if re.search(pattern, full_text_dump, re.IGNORECASE):
                raise ClinicalSafetyViolationError(
                    f"Violación de protocolo asistencial: El texto contiene lenguaje prescriptivo directo "
                    f"prohibido por el patrón de seguridad '{pattern}'."
                )

        # 4. IMPOSICIÓN FORZOSA DEL DESCARGO DE RESPONSABILIDAD HUMANA
        ai_output.human_governance_disclaimer = (
            "SOPORTE CLÍNICO ASISTIDO POR IA — NO VINCULANTE: "
            "Toda sugerencia diagnóstica, farmacológica o de curación requiere verificación "
            "y firma digital del médico o enfermero responsable."
        )

        return ai_output

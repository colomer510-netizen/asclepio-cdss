import os
import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import asyncpg
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/hospital_cdss")

iomt_app = FastAPI(
    title="Gateway IoMT - Hospitales y Maquinaria de Laboratorio",
    description="Receptor de tramas HL7 FHIR y DICOM para integración en tiempo real.",
    version="1.0.0",
)

db_pool: Optional[asyncpg.Pool] = None


@iomt_app.on_event("startup")
async def startup_event():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DB_DSN)
    except Exception as e:
        print(f"[!] IoMT Gateway en espera de base de datos: {e}")


@iomt_app.on_event("shutdown")
async def shutdown_event():
    if db_pool:
        await db_pool.close()


# ============================================================================
# ESQUEMAS DE ENTRADA PARA TRAMAS DE MÁQUINAS
# ============================================================================

class HL7ObservationPayload(BaseModel):
    patient_id: UUID
    serial_number_equipment: str = Field(..., description="Número de serie único del analizador o monitor")
    study_type: str = Field(..., description="Ej: Hemograma completo, Gases arteriales, Glucemia, Tomografía")
    raw_fhir_observation: Dict[str, Any] = Field(..., description="Objeto JSON completo del recurso HL7 FHIR Observation")
    abnormal_flags: list[str] = Field(default_factory=list, description="Banderas de alerta detectadas por el equipo (ej. 'CRITICAL_HIGH')")
    dicom_storage_uri: Optional[str] = Field(None, description="Ruta PACS o NAS si la máquina es de imagenología")
    force_critical_alert: bool = Field(False)


# ============================================================================
# ENDPOINT DE INGESTA DE DATOS DE MÁQUINAS
# ============================================================================

@iomt_app.post("/api/v1/iomt/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_machine_payload(payload: HL7ObservationPayload):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")

    async with db_pool.acquire() as conn:
        # 1. Verificar equipo
        equipment = await conn.fetchrow(
            """
            SELECT equipment_id, location_hospital, is_online 
            FROM medical_equipment 
            WHERE serial_number = $1;
            """,
            payload.serial_number_equipment,
        )

        if not equipment:
            raise HTTPException(
                status_code=404,
                detail=f"El equipo con número de serie '{payload.serial_number_equipment}' no está registrado en el sistema.",
            )
        
        if not equipment["is_online"]:
            raise HTTPException(
                status_code=400,
                detail="El equipo receptor se encuentra marcado como fuera de línea en el inventario hospitalario.",
            )

        equipment_id = equipment["equipment_id"]

        # 2. Alerta crítica
        is_critical = payload.force_critical_alert or any(
            flag.upper() in ["CRITICAL_HIGH", "CRITICAL_LOW", "PANIC_VALUE", "SEPSIS_RISK"]
            for flag in payload.abnormal_flags
        )

        # 3. Guardar resultado
        result_id = await conn.fetchval(
            """
            INSERT INTO machine_diagnostic_results (
                patient_id, equipment_id, study_type, 
                raw_machine_payload, abnormal_flags, 
                dicom_storage_uri, critical_alert, captured_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, CURRENT_TIMESTAMP)
            RETURNING result_id;
            """,
            payload.patient_id,
            equipment_id,
            payload.study_type,
            json.dumps(payload.raw_fhir_observation),
            json.dumps(payload.abnormal_flags),
            payload.dicom_storage_uri,
            is_critical,
        )

    return {
        "status": "INGESTA_EXITOSA",
        "result_id": result_id,
        "equipment_id": equipment_id,
        "critical_alert_triggered": is_critical,
        "timestamp": datetime.utcnow().isoformat(),
    }

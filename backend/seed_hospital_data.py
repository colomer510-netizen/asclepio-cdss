import os
import asyncio
import asyncpg

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/asclepio_cdss")

async def seed_database():
    print(f"[*] Conectando a PostgreSQL ({DB_DSN}) para insertar datos iniciales de prueba...")
    conn = await asyncpg.connect(DB_DSN)

    try:
        async with conn.transaction():
            # 1. Personal médico
            staff_id = await conn.fetchval(
                """
                INSERT INTO clinical_staff (full_name, license_number, role, specialty, hospital_center, public_key_hash)
                VALUES ($1, $2, $3::staff_role, $4, $5, $6)
                ON CONFLICT (license_number) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING staff_id;
                """,
                "Dr. Carlos Mendoza", "MINSA-MED-99421", "especialista", "Medicina Interna", "Hospital Central Capital", "sha256_mock_public_key_carlos"
            )
            print(f"[✔] Personal médico registrado con ID: {staff_id}")

            # 2. Paciente de prueba
            patient_id = await conn.fetchval(
                """
                INSERT INTO patients (medical_record_number, full_name, birth_date, blood_type, known_allergies, active_conventional_meds, active_natural_remedies, chronic_conditions)
                VALUES ($1, $2, $3::date, $4, $5, $6::jsonb, $7::jsonb, $8)
                ON CONFLICT (medical_record_number) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING patient_id;
                """,
                "EXP-2026-0089", "María Elena Rostrán", "1978-05-14", "O+", 
                ["Penicilina"], 
                '["Warfarina", "Metformina"]', 
                '["Ginkgo biloba"]', 
                ["Hipertensión Arterial", "Diabetes Mellitus Tipo 2"]
            )
            print(f"[✔] Paciente de prueba registrado con ID: {patient_id}")

            # 3. Equipo de laboratorio (HL7 FHIR)
            equipment_id = await conn.fetchval(
                """
                INSERT INTO medical_equipment (serial_number, equipment_name, category, location_hospital, protocol_standard, ip_endpoint, is_online)
                VALUES ($1, $2, $3::equipment_category, $4, $5, $6::inet, $7)
                ON CONFLICT (serial_number) DO UPDATE SET equipment_name = EXCLUDED.equipment_name
                RETURNING equipment_id;
                """,
                "SYS-LAB-4551I", "Analizador Bioquímico y Hematológico Central", "analizador_bioquimico", "Hospital Central Capital", "HL7_FHIR", "192.168.1.150", True
            )
            print(f"[✔] Equipo de laboratorio registrado con ID: {equipment_id}")

            # 4. Regla de interacción farmacológica crítica (Natural vs Alopática)
            await conn.execute(
                """
                INSERT INTO pharmacological_interactions (natural_compound, synthetic_drug, severity_level, clinical_effect, mechanism_description)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING;
                """,
                "Ginkgo biloba", "Warfarina", "contraindicado", 
                "Riesgo hemorrágico severo por potenciación de la inhibición de la agregación plaquetaria.",
                "El Ginkgo biloba inhibe el factor activador plaquetario (PAF), lo cual sinergiza con los anticoagulantes orales incrementando drásticamente el tiempo de sangrado."
            )
            print("[✔] Regla de interacción (Ginkgo biloba vs Warfarina) inyectada con éxito.")

    finally:
        await conn.close()
        print("[*] Proceso de población de datos finalizado correctamente.")

if __name__ == "__main__":
    asyncio.run(seed_database())

# Plataforma CDSS — Inteligencia Artificial Médica y Monitoreo IoMT

Sistema de Soporte a la Decisión Clínica (CDSS) distribuido de alta capacidad, diseñado para integrar bibliotecas médicas híbridas (medicina convencional alopática y fitoterapia/medicina natural basada en evidencia), telemetría hospitalaria en tiempo real (HL7 FHIR / DICOM) y un estricto protocolo de gobernanza con **factor humano obligatorio (*Human-in-the-Loop*)**.

---

## 🏛️ Arquitectura del Sistema

El ecosistema se organiza en 5 capas tecnológicas para garantizar máxima velocidad diagnóstica, soberanía de datos y seguridad legal del acto médico:

1. **Ingesta e Interoperabilidad (IoMT):** Receptor concurrentemente conectado a analizadores hematológicos, bioquímicos y monitores multiparámetro (estándares HL7 FHIR y DICOM).
2. **Biblioteca Médica Híbrida (RAG Vectorial):** PostgreSQL con extensión `pgvector` e índice HNSW para búsqueda semántica ultrarrápida sobre literatura médica convencional y tratados de medicina natural.
3. **Detector de Interacciones Farmacológicas Cruzadas:** Motor que cruza en tiempo real el consumo de remedios naturales frente a fármacos sintéticos para prevenir efectos adversos graves.
4. **Motor Cognitivo y Cortafuegos de Seguridad (`clinical_guardrails.py`):** Inferencia con modelos de lenguaje locales (vía Ollama: `qwen2.5:14b` o `llama3.2`) con validación forzosa de citas (`chunk_id`, libro y página) y bloqueo determinista de cualquier tono imperativo o directivo.
5. **Gobernanza y Responsabilidad Humana:** Tablas inmutables con *triggers* PostgreSQL donde ninguna sugerencia algorítmica ingresa al expediente sin la resolución y firma digital del médico o enfermero colegiado.

---

## 📂 Estructura del Repositorio

```text
hospital-cdss-platform/
├── backend/
│   ├── main.py                  # Servidor central FastAPI (endpoints de análisis y firma)
│   ├── hospital_iomt_gateway.py # Receptor de tramas de máquinas HL7 FHIR y DICOM
│   ├── clinical_prompt_spec.py  # Contratos Pydantic estrictos y System Prompts clínicos
│   ├── clinical_guardrails.py   # Cortafuegos anti-alucinación y subordinación médica
│   ├── ingest_medical_books.py  # Procesador de libros médicos en PDF hacia pgvector
│   ├── seed_hospital_data.py    # Inyector de datos iniciales para pruebas
│   ├── requirements.txt         # Dependencias Python
│   └── Dockerfile               # Contenedor del backend
├── db/
│   ├── init_schema.sql          # DDL completo con pgvector, tipos ENUM y triggers inmutables
│   └── queries_referencia.sql   # Consultas SQL avanzadas para RAG e interacciones
├── frontend/
│   └── index.html               # Panel web de alta densidad para médicos y enfermeros
├── scripts/
│   └── backup_hospital_db.sh    # Script de respaldo diario con cifrado AES-256 (GPG)
├── docs/
│   └── MANUAL_OPERATIVO_CLINICO.md # Guía para el personal de salud
├── docker-compose.yml           # Orquestación con PostgreSQL (pgvector), Ollama y FastAPI
├── Modelfile                    # Definición de parámetros para el modelo médico en Ollama
├── LICENSE                      # Licencia BUSL 1.1 (Protección contra explotación comercial)
├── DISCLAIMER.md                # Descargo médico-legal estricto ("AS-IS", no vinculante)
└── README.md
```

---

## 🚀 Despliegue Rápido con Docker Compose

### 1. Clonar el repositorio
```bash
git clone https://github.com/encob-business/hospital-cdss-platform.git
cd hospital-cdss-platform
```

### 2. Levantar la infraestructura completa
```bash
docker compose up --build -d
```

### 3. Verificar estado de los contenedores
```bash
docker compose ps
```

### 4. Acceder al Panel Clínico
Abra su navegador web e ingrese a:
- **Panel Web del Personal de Salud:** `http://localhost:8000/static/index.html`
- **Documentación Interactiva Swagger API:** `http://localhost:8000/docs`

---

## 🛡️ Gobernanza Legal y Factor Humano

Este software cumple con el estándar de **Subordinación Total al Criterio Clínico Humano**:
- **La IA no prescribe:** Toda salida se etiqueta como *"Sugerencia de Soporte Clínico - No Vinculante"*.
- **Trazabilidad Forense:** Toda recomendación cita la página y el capítulo del libro de donde provino la información.
- **Firma Criptográfica:** El expediente médico solo se valida cuando el profesional registra su dictamen firmado mediante hash SHA-256.

Consulte [`DISCLAIMER.md`](file:///home/enoc-colomer/dev/work/hospital-cdss-platform/DISCLAIMER.md) para el aviso médico-legal completo.

---

## 📜 Licencia

Este proyecto está publicado bajo los términos de la **Business Source License 1.1 (BUSL)**.
- **Permitido:** Uso académico, investigación, evaluación técnica y contribución de código abierta para desarrolladores.
- **Restringido:** Uso comercial directo, despliegues lucrativos o servicios SaaS en la nube sin una licencia comercial previa otorgada por el autor ([Enoc Colomer](mailto:enoc@colomer.dev)).
- En la fecha límite especificada en el archivo [`LICENSE`](file:///home/enoc-colomer/dev/work/hospital-cdss-platform/LICENSE), este código se convertirá automáticamente en software libre bajo la **GNU AGPLv3**.

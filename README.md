# Asclepio CDSS — Clinical Decision Support Suite & IoMT Gateway

> [!IMPORTANT]
> ### 🔬 Estado del Proyecto: Demostrador Tecnológico / Prueba de Concepto (PoC)
> **Este repositorio constituye un prototipo funcional en fase activa de desarrollo (Technology Demonstration / Proof of Concept - PoC).**
> Ha sido diseñado exclusivamente con propósitos de **investigación biomédica, evaluación de arquitectura técnica y demostración de capacidades** de ingeniería.
> **No está certificado como dispositivo médico (SaMD) ni aprobado para uso en producción clínica diagnóstica o terapéutica con pacientes reales.**

---

[![Licencia: BUSL-1.1](https://img.shields.io/badge/Licencia-BUSL--1.1-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://www.python.org/)
[![FastAPI: 0.115](https://img.shields.io/badge/FastAPI-0.115-teal.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL: 16+pgvector](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-blue.svg)](https://github.com/pgvector/pgvector)
[![Security: Bandit Audited](https://img.shields.io/badge/Security-Bandit%20Clean-success.svg)](https://github.com/PyCQA/bandit)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-black.svg)](https://github.com/astral-sh/ruff)

Sistema de Soporte a la Decisión Clínica (CDSS) distribuido de alta capacidad, diseñado para integrar bibliotecas médicas híbridas (medicina convencional alopática y fitoterapia/medicina natural basada en evidencia), telemetría hospitalaria en tiempo real (HL7 FHIR / DICOM) y un estricto protocolo de gobernanza con **factor humano obligatorio (*Human-in-the-Loop*)**.

---

## 🏛️ Arquitectura del Sistema (Hospital OS)

El ecosistema se organiza en capas tecnológicas modulares para garantizar soberanía de datos, baja latencia diagnóstica y seguridad legal del acto médico:

```
┌────────────────────────────────────────────────────────────────────────┐
│               ASCLEPIO CDSS — SUITE HOSPITALARIA MODULAR               │
└────────────────────────────────────────────────────────────────────────┘
          │                                           │
          ▼                                           ▼
┌─────────────────────────────┐             ┌─────────────────────────────┐
│ 1. Estación Clínica/Triaje  │             │ 5. Vademécum & Fitoterapia  │
│    - Diagnósticos dif. RAG  │             │    - Matriz de interacciones│
│    - Firma médica SHA-256   │             │    - Prevención de riesgos  │
├─────────────────────────────┤             ├─────────────────────────────┤
│ 2. Expedientes y Pacientes  │             │ 6. Consola de IA & Modelos  │
│    - MRN, tipos de sangre   │             │    - Modelos locales Ollama │
│    - Historial de alergias  │             │    - Guardrails y contratos │
├─────────────────────────────┤             ├─────────────────────────────┤
│ 3. IoMT & Laboratorio       │             │ 7. Auditoría & Trazabilidad │
│    - Gateway MLLP / HL7     │             │    - Ledger inmutable DB    │
│    - Telemetría en vivo     │             │    - Verificación forense   │
├─────────────────────────────┤             ├─────────────────────────────┤
│ 4. Biblioteca Vectorial     │             │ 8. Métricas y Configuración │
│    - Tratados indexados     │             │    - Estado de contenedores │
│    - Búsqueda con pgvector  │             │    - Salud de base de datos │
└─────────────────────────────┘             └─────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      NÚCLEO DE INFRAESTRUCTURA                         │
│   FastAPI (Python 3.11) ─── PostgreSQL 16 (pgvector) ─── Ollama Engine  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Principio Ético Fundamental: *Human-in-the-Loop*

1. **Subordinación Total:** Ningún modelo de inteligencia artificial emite órdenes diagnósticas ni recetas de forma autónoma. Todas las salidas se clasifican estrictamente como *Sugerencias No Vinculantes*.
2. **Citas Bibliográficas Obligatorias:** Cada hipótesis clínica generada por el motor RAG debe indicar explícitamente el tratado, edición, capítulo y fragmento de evidencia.
3. **Firma Criptográfica Inmutable:** Toda acción médica requiere la autenticación activa del profesional de la salud con registro criptográfico (SHA-256) no repudiable.
4. **Descargo Médico-Legal:** Consulte [`DISCLAIMER.md`](DISCLAIMER.md) para el marco de delimitación de responsabilidad jurídica.

---

## 📂 Estructura del Repositorio

```text
asclepio-cdss/
├── backend/
│   ├── main.py                  # API REST completa (8 módulos hospitalarios integrados)
│   ├── hospital_iomt_gateway.py # Receptor y simulador de tramas HL7 FHIR y DICOM
│   ├── clinical_prompt_spec.py  # Contratos Pydantic v2 y System Prompts clínicos
│   ├── clinical_guardrails.py   # Cortafuegos anti-alucinaciones y reglas de seguridad
│   ├── ingest_medical_books.py  # Procesador semántico de tratados hacia pgvector
│   ├── seed_hospital_data.py    # Generador de datos clínicos para entornos demo/pruebas
│   ├── requirements.txt         # Dependencias Python
│   └── Dockerfile               # Contenedor optimizado de backend
├── db/
│   ├── init_schema.sql          # DDL completo con pgvector, tipos ENUM y triggers inmutables
│   └── queries_referencia.sql   # Consultas SQL optimizadas para similitud de cosenos
├── frontend/
│   └── index.html               # Panel Web Hospital OS moderno (8 vistas interactivas)
├── scripts/
│   └── backup_hospital_db.sh    # Script de respaldo diario con cifrado AES-256 (GPG)
├── docs/
│   └── MANUAL_OPERATIVO_CLINICO.md # Manual técnico y operativo para personal de salud
├── docker-compose.yml           # Orquestación con PostgreSQL (pgvector), Ollama y FastAPI
├── Modelfile                    # Definición de parámetros para el modelo médico en Ollama
├── LICENSE                      # Licencia BUSL-1.1
├── DISCLAIMER.md                # Descargo médico-legal estricto ("AS-IS", no vinculante)
└── README.md
```

---

## 🚀 Despliegue Rápido (Entorno Local / Demo)

### 1. Requisitos Previos
- Docker Engine 24.0+ y Docker Compose v2+
- Motor local Ollama (opcional para inferencia con `phi4-mini:latest` o `llama3.2:latest`)
- Puerto `5433` (PostgreSQL) y `8080` (FastAPI) disponibles en la máquina anfitriona

### 2. Clonar el repositorio
```bash
git clone https://github.com/colomer510-netizen/asclepio-cdss.git
cd asclepio-cdss
```

### 3. Iniciar los servicios con Docker Compose
```bash
docker compose up -d --build
```

### 4. Acceso a las Interfaces
Una vez levantados los contenedores:
- **Panel Web Hospital OS:** [http://localhost:8080/static/index.html](http://localhost:8080/static/index.html)
- **Documentación Swagger / OpenAPI:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Métricas del Sistema:** [http://localhost:8080/api/v1/system/metrics](http://localhost:8080/api/v1/system/metrics)

---

## 🔍 Auditoría de Calidad y Seguridad Continua

El proyecto se somete a auditorías automáticas de seguridad y calidad estática en cada ciclo de integración:

```bash
# Auditoría de seguridad estática (SAST)
docker exec asclepio_backend_api bandit -r /app -ll

# Análisis estático de código y conformidad de tipos
docker exec asclepio_backend_api ruff check /app
```

**Resultado de la última auditoría:** `0 issues identified` en Bandit y `0 errors` en Ruff.

---

## 📜 Licencia

Este proyecto está publicado bajo los términos de la **Business Source License 1.1 (BUSL-1.1)**.
- **Permitido:** Uso académico, investigación, evaluación técnica y auditorías de código abierto.
- **Restringido:** Explotación comercial, venta directa o provisión de servicios SaaS en la nube sin autorización previa por escrito del autor.
- Cumplido el plazo de transición indicado en [`LICENSE`](LICENSE), el código transicionará automáticamente a licencia **GNU AGPLv3**.

---

<p align="center">
  <b>Desarrollado y mantenido por Enoc Colomer</b><br>
  <i>Investigación y Desarrollo en Sistemas de Decisión Clínica e Inteligencia Artificial Médica</i>
</p>

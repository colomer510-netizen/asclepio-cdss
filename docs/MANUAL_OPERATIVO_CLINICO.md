# MANUAL CLÍNICO DE OPERACIÓN — PLATAFORMA CDSS ASISTIDA POR IA

## 1. Propósito de la Herramienta
Esta plataforma opera estrictamente como un **asistente de consulta y soporte diagnóstico**. Su función es acelerar la revisión bibliográfica de manuales de medicina convencional y natural, cruzar alertas farmacológicas y correlacionar los signos vitales enviados por las máquinas de laboratorio (HL7 FHIR / DICOM).

> ⚠️ **RECORDATORIO ÉTICO Y LEGAL:** La Inteligencia Artificial **NO** emite diagnósticos definitivos ni recetas autónomas. El juicio clínico, la validación y la responsabilidad legal recaen única y exclusivamente en el médico o enfermero que firma el expediente.

---

## 2. Flujo de Trabajo Operativo en el Panel Web

### Paso 1: Ingreso del Caso Clínico
1. Ingrese el **UUID del Paciente** y su **UUID de Profesional** en los campos correspondientes.
2. Redacte en el cuadro de notas los síntomas actuales, hallazgos de exploración física y cualquier duda diagnóstica.
3. Si el paciente consume fármacos sintéticos o remedios naturales (fitoterapia), anótelos en los campos de medicamentos activos para activar el detector de interacciones.
4. Haga clic en **"Consultar Base Híbrida y Generar Asistencia IA"**.

### Paso 2: Revisión del Reporte de Asistencia
El sistema mostrará en segundos:
- **Síntesis Clínica y Diagnósticos Diferenciales:** Ordenados por probabilidad.
- **Evidencia Bibliográfica (RAG):** Citas exactas con el título del libro, capítulo y número de página de donde la IA extrajo el sustento médico (tanto de medicina alopática como natural).
- **Alertas Farmacológicas:** Advertencias en caso de choques químicos graves entre plantas medicinales y fármacos sintéticos.

### Paso 3: Validación, Modificación y Firma Digital (Factor Humano)
Ningún dato ingresa al expediente oficial hasta que usted ejecute el cierre del caso:
1. Seleccione su **Dictamen Profesional** (*Aprobado sin cambios*, *Aprobado con modificaciones*, *Rechazado por criterio médico* o *Escalado a especialista*).
2. Redacte en firme el **Diagnóstico Clínico Definitivo** y el **Plan de Curación/Tratamiento**.
3. Ingrese su **Justificación Clínica** (explicando por qué aceptó o modificó el criterio sugerido por el sistema).
4. Escriba su clave privada o token de credencial en el campo de **Firma Digital**.
5. Presione **"Registrar y Firmar Decisión en Expediente Oficial"**. El sistema generará un sello criptográfico inmutable que sella legalmente la historia clínica del paciente.

#!/bin/bash

# ==============================================================================
# SCRIPT DE RESPALDO Y CIFRADO SEGURO PARA BASE DE DATOS CDSS
# ==============================================================================

DB_CONTAINER="asclepio_postgres_cdss"
DB_NAME="asclepio_cdss"
DB_USER="postgres"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/asclepio_cdss}"
DATE_STAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILENAME="cdss_backup_${DATE_STAMP}.sql.gz"
ENCRYPTED_FILENAME="${BACKUP_FILENAME}.gpg"
PASSPHRASE="${CDSS_BACKUP_PASSPHRASE:-CAMBIE_ESTA_CLAVE_EN_PRODUCCION}"

mkdir -p "${BACKUP_DIR}"

echo "[*] Iniciando respaldo de la base de datos ${DB_NAME}..."

# 1. Extraer el respaldo comprimido
docker exec -t "${DB_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_DIR}/${BACKUP_FILENAME}"

if [ $? -eq 0 ]; then
    echo "[✔] Respaldo SQL comprimido generado con éxito: ${BACKUP_FILENAME}"
else
    echo "[✖] Error crítico al generar el respaldo de PostgreSQL."
    exit 1
fi

# 2. Cifrar el archivo con AES-256 (GPG)
echo "[*] Aplicando cifrado AES-256 al respaldo clínico..."
gpg --symmetric --batch --passphrase "${PASSPHRASE}" --output "${BACKUP_DIR}/${ENCRYPTED_FILENAME}" "${BACKUP_DIR}/${BACKUP_FILENAME}"

# 3. Eliminar el archivo plano sin cifrar
rm -f "${BACKUP_DIR}/${BACKUP_FILENAME}"

if [ $? -eq 0 ]; then
    echo "[✔] Respaldo cifrado correctamente: ${ENCRYPTED_FILENAME}"
else
    echo "[✖] Error al cifrar el archivo de respaldo."
    exit 1
fi

# 4. Política de retención: Eliminar respaldos locales de más de 30 días
find "${BACKUP_DIR}" -name "cdss_backup_*.sql.gz.gpg" -mtime +30 -exec rm {} \;
echo "[*] Limpieza de respaldos antiguos completada. Proceso finalizado con éxito."

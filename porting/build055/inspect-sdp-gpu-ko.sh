#!/usr/bin/env bash
# Offline Samsung GPU module inspection. Never modprobe/insmod, flash, or access TV.
set -euo pipefail

if [[ $# -ne 1 ]]; then
    printf 'Verwendung: bash %s /pfad/zur/sdp_gpu.ko\n' "$0" >&2
    exit 2
fi

gpu_module=$1
if [[ ! -f "$gpu_module" || -L "$gpu_module" ]]; then
    printf 'FEHLER: Bitte eine echte lokale, regulaere .ko-Datei angeben.\n' >&2
    exit 2
fi

for utility in sha256sum file readelf; do
    if ! command -v "$utility" >/dev/null 2>&1; then
        printf 'FEHLER: %s fehlt. Kein Paket wird automatisch installiert.\n' "$utility" >&2
        exit 2
    fi
done

printf '=== Originalmodul / Fingerabdruck ===\n'
sha256sum -- "$gpu_module"
file -- "$gpu_module"

printf '\n=== ELF Architektur / Typ ===\n'
readelf -h -- "$gpu_module" | grep -E 'Class:|Machine:|Type:' || true

printf '\n=== Modulinformationen (falls enthalten) ===\n'
if ! readelf -p .modinfo -- "$gpu_module"; then
    printf 'Keine lesbare .modinfo-Sektion vorhanden.\n'
fi

printf '\n=== modinfo (nur Lesen, falls vorhanden) ===\n'
if command -v modinfo >/dev/null 2>&1; then
    modinfo -- "$gpu_module" || true
fi

printf '\nPruefung abgeschlossen: Modul wurde NICHT geladen oder ausgefuehrt.\n'
printf 'WICHTIG: Modul-Metadaten allein bestaetigen keine Mali-G51/GPU_ID.\n'

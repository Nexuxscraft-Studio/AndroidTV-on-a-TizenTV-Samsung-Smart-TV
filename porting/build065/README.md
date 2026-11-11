# Build 065 – Auswertung der Samsung-GPL-Kernelquellen

Read-only Analyse des bereitgestellten `linux-4.1.10-tizen5.5`-Quellbaums.
**Kein Samsung-Quellcode im Repo** – nur eigene Analyse/Fakten. Vollständiger
Bericht: `../../BUILD065_REPORT.md`. Reale Adressen: `SOC_ADDRESS_MAP.md`.

## Kernbefunde

1. **Display-Controller ist proprietär** (VD-chipdriver-Blob). GPL hat nur
   `drm_tztv_helper.c` (Property/ioctl-Glue) + `panel-sdp.c` („dummy info"). →
   offener Display-Weg = Reverse Engineering **oder** Framebuffer-Handoff über
   das Build-063-`sdp-drm`-Skelett.
2. **Kein offener GPU-Treiber** im Stock (kein Mali/Panfrost in der Defconfig) →
   Panfrost (offen) bleibt richtig.
3. **kexec NICHT im Stock-Kernel** (`# CONFIG_KEXEC is not set`) → löst die
   offene Build-061-Frage; kexec-aus-Stock entfällt.
4. **SMACK statt SELinux** bestätigt.
5. **Reale SoC-Adressen** (Clock `0x10DF0000`, GIC `0x10fa1000`, eMMC
   `0x10000000` mit echter Config, UART/USB/I2C/Ethernet) → SOC_ADDRESS_MAP.md.
6. **GPL-Vorlage ≠ Serienboard** (a7×2/A15 vs. a57×4); Firmware-DTB bleibt
   maßgeblich für Display/GPU-Adressen.

Zusätzlich bereitgestellt (für später): `tztv-bootmode` (Bootmodus-Tool),
`trustzone-ree` (TEE-Client-API-Header, REE-Seite). Sperre und Gates bleiben.

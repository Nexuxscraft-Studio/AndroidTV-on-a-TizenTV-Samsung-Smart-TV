# Build 065 – Auswertung der Samsung-GPL-Kernelquellen (Nike-L)

**Branch:** `claude/build065-gpl-source-analysis` (aus Build 064).
**Status:** Read-only Quellenauswertung. **Kein** Gerätezugriff, **kein** Flash.
Es wird **kein Samsung-Quellcode ins Repo übernommen** (nur eigene Analyse/Fakten).

Der Nutzer hat den echten GPL-Quellbaum `linux-4.1.10-tizen5.5.tgz` (54.173
Einträge) bereitgestellt. Diese Auswertung prüft gezielt Display, GPU, kexec,
Security und die realen SoC-Adressen – und korrigiert/bestätigt damit frühere
Annahmen.

## Befund 1 (zentral): Der Display-Controller ist proprietär

Im GPL-Baum existiert **kein** offener Nike-L-Display-Controller-Treiber. Was da
ist:
- `drivers/gpu/drm/drm_tztv_helper.c` – **nur DRM-Property-/ioctl-Glue**
  (Plane mute/sync, `DRM_IOCTL_TZTV_SET_ONOFF`), die an einen proprietären
  **„chipdriver"** weiterreicht (`..._set_to_chipdriver`). Keine Modeset-,
  CRTC- oder Register-Logik.
- `drivers/gpu/drm/panel/panel-sdp.c` – trägt im Quelltext den Kommentar
  **„this panel-sdp.c contains dummy info"**; Timing (clock/hsync/vsync) ist
  Platzhalter. Real sind nur Panelgröße (678×380 mm) und `samsung,sdp1202-panel`.
- Defconfig: `CONFIG_DRM_SDP=y`, `CONFIG_DRM_PANEL_SDP=y`, `CONFIG_DRM=y` mit
  **CMA**-Helfern (`DRM_GEM_CMA_HELPER`); `CONFIG_VD_KMALLOC_SLAB=y` markiert den
  proprietären **VD-Stack** (Samsung Visual Display).

→ Die eigentliche Display-Hardware-Programmierung liegt in einem **proprietären
Tizen-„VD"-chipdriver-Blob**, analog zum proprietären `sdp_mmc`. **Ein offener
Display-Treiber kann aus diesen Quellen NICHT portiert werden.**

**Konsequenz für die Strategie:** Der offene Display-Weg erfordert eines von:
1. **Reverse Engineering** des VD-Display-IP (groß, wie Panfrost für Mali), oder
2. ein **einfacher Framebuffer-Handoff** (`simple-KMS`/`simplefb`-Stil), falls
   der Bootloader das Panel bereits initialisiert und einen Framebuffer stehen
   lässt – das Build-063-`sdp-drm`-Skelett ist genau die KMS-Hülle dafür, oder
3. headless/limitiert (kein lokales Bild).

Das Build-063-KMS-Skelett bleibt also richtig – aber als **Hülle** für (1)/(2),
nicht als Ziel eines Vendor-Ports.

## Befund 2: Kein offener GPU-Treiber im Stock

Die Defconfig enthält **kein** `MALI`/`PANFROST`/`MIDGARD`/`BIFROST` – nur
`CONFIG_GPU_MEMORY_INFO=y`. Der GPU-Treiber ist proprietär (libmali/kbase-Blob).
→ Bestätigt die Build-063-Entscheidung: **Panfrost (offen)** ist der richtige
Weg, nicht der Vendor-Blob.

## Befund 3: kexec ist im Stock-Kernel NICHT aktiv

```
# CONFIG_KEXEC is not set
# CONFIG_CRASH_DUMP is not set
```
**Löst die offene Build-061-Frage:** Ein kexec aus dem laufenden Stock-Kernel ist
**nicht möglich** (Symbol nicht gebaut). Der „kexec-aus-Stock"-Pfad für einen
eigenen Kernel ist damit zu. (Unser eigener 6.6-Kernel kann kexec aktivieren –
aber der ihn startende signierte Bootweg ist der eigentliche Gate, Build 061.)

## Befund 4: Security-Modell bestätigt

`CONFIG_SECURITY_SMACK=y`, `CONFIG_SECURITY_SFD=y`, `CONFIG_DEFAULT_SECURITY_SMACK=y`,
`# CONFIG_SECURITY_SELINUX is not set`. CPUFreq: `CONFIG_CPU_FREQ_DEFAULT_GOV_INTERACTIVE=y`.
→ Bestätigt Build 015 (Tizen nutzt SMACK; Android braucht SELinux – kommt mit
unserem 6.6-Kernel upstream).

## Befund 5: Reale SoC-Adressen (aus `sdp1412.dtsi`)

Eigene Referenz (Fakten, kein GPL-Code): siehe `porting/build065/SOC_ADDRESS_MAP.md`.
Highlights (ersetzen frühere Platzhalter):
- Clock-Controller **`0x10DF0000`** (`samsung,sdp1412-clock`).
- GIC **`0x10fa1000`** (cortex-a15-gic) – deckt sich mit dem DTB-Fund aus Build 063.
- **eMMC `0x10000000`**, IRQ 43, 8-bit, non-removable, ddr50 + volle Tuning-Regs
  (`0x100000A8`/`0x10000110`) – P0, jetzt mit echter Config statt Platzhalter.
- UART `0x10090A00`/`0x10090A40`; USB EHCI `0x30210000`/`0x30230000`, OHCI
  `0x30218000`/`0x30238000`, xHCI `0x30100000`; I2C `0x10090100`–`0x10090180`;
  Ethernet `0x10020000`; chipid `0x10080000`.

## Befund 6: GPL-Vorlage ≠ Serienboard

`sdp1412.dtsi` nennt **cortex-a7 ×2**, der Boardcode (`board-nike-dt.c`) nutzt
A15-Register (CPUECTLR/CPUACTLR); die **ausgelieferte Firmware-DTB** hat aber
**cortex-a57 ×4** (Build 004/050). Der GPL-Baum ist eine **generische
Mehrvarianten-Basis** („Nike Series", unterstützt `sdp-nikem` **und** `sdp-nikel`),
nicht 1:1 das Q60T-Board. **Für Display/GPU-Adressen bleibt die Firmware-`dtb.bin`
maßgeblich** (die GPL-Basis-DTS enthält diese Knoten ohnehin nicht).

## Zusätzlich bereitgestellt (für später, nicht heute vertieft)

- `tztv-bootmode` (Tool zum Setzen/Lesen des TV-Bootmodus) – relevant für
  Serial-Console/Dev-Boot.
- `trustzone-ree` (GlobalPlatform-TEE-Client-API-Header, REE-Seite) – normale
  Schnittstelle zur Secure World, keine Secrets/Schlüssel.

## Auswirkung auf die Roadmap

- **Display** ist der härteste offene Punkt (proprietär). Realistisch zuerst der
  **Framebuffer-Handoff-Weg** über das `sdp-drm`-Skelett prüfen (hängt davon ab,
  ob der Bootloader das Panel initialisiert).
- **GPU:** Panfrost (offen) bleibt der Weg.
- **kexec-aus-Stock entfällt** → eigener Kernelstart hängt vollständig am
  signierten Bootweg (Build 061).
- **Core-SoC:** eMMC/USB/Clock jetzt mit realen Adressen – konkret für Build 059
  nutzbar.

Keine Datei aus dem GPL-Baum wurde ins Repo übernommen. Sperre und Boot-Gates
bleiben.

# Build 066 – Boot-Zugang, Framebuffer-Handoff, GPL-Clock/Audio/MFC

**Branch:** `claude/build066-boot-fb-media` (aus Build 065). **Status:** read-only
Analyse + Scaffold. Kein Gerätezugriff, kein Flash, kein Samsung-Quellcode im Repo.

Setzt die drei nach Build 065 offenen Richtungen um.

## 1. Boot-Zugang (Richtung 1)

`tztv-bootmode` (GPL) zeigt die **TV-Boot-Modi** (0=TIZEN_BOOTING … 4=RELEASE …
6=HDMI_CAL), vom **Micom** per GPIO oder Register (`& 0x7`) gesetzt, über das
DT-Node `tztv_bootmode` (`communication-mode` gpio|reg, `ew-select`). Das sind
die „S/E"-Modi der Übergabe. `trustzone-ree` = GlobalPlatform-TEE-Client-API
(REE-Header, keine Secrets). **Kein Secure-Boot-Bypass**; Dev-/Serial-Zugang am
Seriengerät bleibt am signierten Bootweg (Build 061). Details: `docs/BOOT_ACCESS.md`.

## 2. Framebuffer-Handoff (Richtung 2) – der praktische Durchbruch

Da der Display-Controller proprietär ist (Build 065), ist der realistische Weg
zum **ersten Bild** nicht ein eigener Modeset-Treiber, sondern die Übernahme
eines **vom Bootloader initialisierten Framebuffers** via Upstream
**`simpledrm`** (`CONFIG_DRM_SIMPLEDRM`, `simple-framebuffer`-DT-Node). Kein
eigener Display-Treiber nötig, solange der Bootloader das Panel anlässt (beim
Stock-Boot sehr wahrscheinlich – Boot-Logo). Scaffold + Grenzen (statisch, kein
Overlay/VSync) in `docs/FRAMEBUFFER_HANDOFF.md`. Das Build-063-`sdp-drm`-Skelett
bleibt die Hülle für den späteren vollen KMS-Treiber (VD-RE).

## 3. GPL-Clock/Audio/MFC (Richtung 3)

- **Clock:** `drivers/clk/clk-sdp.c` ist ein **echter GPL-Treiber** (2692 Zeilen)
  mit PLL0–8-Registermap (`0x000`–`0x020`), mappt den `0x10DF0000`-Controller.
  Für 6.6 portierbar; liefert die realen PLL-Offsets (wichtig für CPU-/Display-
  Clocks). Ersetzt/informiert Build-059-`clk-sdp1804`.
- **Audio:** ASoC-Basis (`sound/soc/samsung/` I2S/S/PDIF) GPL; der **SRP**-Audio-
  DSP ist proprietär → offene ASoC-Karte über I2S/S/PDIF möglich.
- **Video:** nur Upstream `s5p-mfc` vorhanden; der Nike-L-Videodecoder ist Teil
  des proprietären VD-Stacks → offene Decode-HAL unwahrscheinlich ohne RE.

Muster bestätigt: **Kern-Infrastruktur GPL (Clock/I2S/UART/MMC/USB), TV-Media/
Display/GPU proprietär.** Details: `docs/GPL_CLOCK_AUDIO_MFC.md`.

## Roadmap-Auswirkung

- **Erstes Bild** jetzt über `simpledrm`-Handoff greifbar (geräteabhängig), ohne
  das VD-IP zu reversen.
- **Clock** für CPU-DVFS/Display mit realen PLL-Offsets fundiert.
- **Audio** offen über ASoC; **Video-Decode** bleibt proprietär.
- **Boot-Zugang**: UART-Konsole (`0x10090A00`) + Micom-Boot-Modus als nächster
  Schritt am Gerät; Signatur-Gate unverändert.

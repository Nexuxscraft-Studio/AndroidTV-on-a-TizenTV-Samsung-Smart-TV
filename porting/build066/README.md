# Build 066 – Boot-Zugang, Framebuffer-Handoff, GPL-Clock/Audio/MFC

Read-only. Setzt die drei nach Build 065 offenen Richtungen um. **Kein
Samsung-Quellcode im Repo**, kein Flash. Sperre und Gates bleiben.

1. **Boot-Zugang** (`docs/BOOT_ACCESS.md`): TV-Boot-Modi (Micom, GPIO/Register,
   0=Tizen…6) + TEE-Client-API (REE, keine Secrets). Kein Bypass.
2. **Framebuffer-Handoff** (`docs/FRAMEBUFFER_HANDOFF.md`): erstes Bild ohne den
   proprietären VD-Treiber via Upstream **`simpledrm`** über einen vom Bootloader
   hinterlassenen Framebuffer. Scaffold: `configs/nikel-simpledrm.config`,
   `dts/sdp-nikel-simplefb-handoff.dts` (Platzhalter, `disabled`).
3. **GPL-Clock/Audio/MFC** (`docs/GPL_CLOCK_AUDIO_MFC.md`): Clock `clk-sdp.c`
   (GPL, PLL-Map, für 6.6 nutzbar), Audio-ASoC-Basis GPL / SRP-DSP proprietär,
   Video-Decode proprietär (nur Upstream s5p-mfc vorhanden).

CI `build066-dts-check.yml`: `dtc`-Prüfung der simplefb-DTS.

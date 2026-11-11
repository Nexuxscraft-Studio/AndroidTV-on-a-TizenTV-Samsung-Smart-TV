# GPL-Auswertung: Clock, Audio, MFC/Video

Read-only. Muster: **Kern-Infrastruktur GPL, TV-Media proprietär.**

## Clock – `drivers/clk/clk-sdp.c` (GPL, nutzbar)

Echter SDP-Clock-Treiber (2692 Zeilen). Mappt den Clock-Controller
(`0x10DF0000`, Build 065) und definiert die **PLL-Registermap**: `PLL0_PMS`–
`PLL8_PMS` (`0x000`–`0x020`), `PLL2_K`/`PLL3_K` (`0x028`/`0x02C`), separate
AP/MP-Register-Basen. Spinlock-geschützt, DT-getrieben.
→ Für 6.6 portierbar; ersetzt/informiert den Build-059-`clk-sdp1804`. Die realen
PLL-Offsets sind damit bekannt (wichtig für CPU-DVFS/Display-Clocks).

## Audio – ASoC-Basis GPL, SRP-DSP proprietär

- GPL: `sound/soc/samsung/` (I2S `i2s.c`, S/PDIF `spdif.c`, dmaengine) — die
  offene ASoC-Basis.
- Proprietär: der **SRP**-Audio-DSP (`include/uapi/sound/sdp_srp_ioctl.h`) und der
  TV-Audio-Pfad; Register-Header `mach/golfp/sdp_audio_reg.h`.
→ Offener Audio-Weg: ASoC-Karte über I2S/S/PDIF; der SRP-Decoder bleibt außen vor.

## MFC/Video – nur Upstream s5p-mfc, TV-Codec proprietär

- GPL: Upstream `drivers/media/platform/s5p-mfc/` (Samsung MFC V4L2-m2m) ist
  vorhanden, aber ob der Nike-L-Videodecoder damit kompatibel ist, ist
  **unbelegt** — der TV-Codec ist Teil des proprietären VD-Stacks.
- `drivers/media/platform/sdp-dvb/` = Broadcast-Tuner/Demux (GPL), nicht Decode.
→ Offene Video-Decode-HAL unwahrscheinlich ohne RE oder s5p-mfc-Match.

## Fazit

Für die P1-Treiber (Build 064) gilt: Audio (ASoC-Basis) und Clock sind offen
portierbar; **Video-Decode ist wie Display/GPU proprietär**. Kein GPL-Code im
Repo übernommen.

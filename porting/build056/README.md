# Build 056 — Original-Firmwarebefunde für Panfrost (nur Debian)

## Stand

Die vom Nutzer bereitgestellte ZIP `Samsung-Q60T-Tizen-2743-FullOS.zip`
(1.139.943.987 Bytes, 90.395 ZIP-Einträge) wurde **nicht komplett**
heruntergeladen. Stattdessen wurde das ZIP64-Verzeichnis per HTTP-Range gelesen
und drei relevante Einträge aus der ZIP selektiv heruntergeladen und mit CRC32
geprüft. Ein SHA256-Hash der **gesamten** ZIP wurde nicht ermittelt.

Ermittelte Firmware-Dateien:

| Datei in der Original-ZIP | SHA-256 der extrahierten Originalbytes |
|---|---|
| `decrypted/dtb.bin` | `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2` |
| `rootfs-extracted/root/usr/lib/modules/4.1.10/kernel/soc/sdp_gpu.ko` | `115aadc5b2874cc4210f9b6c58bf2b4e09abadfe84fe7ad217f17770b21ecf29` |
| `rootfs-extracted/root/usr/lib/modules/4.1.10/kernel/soc/sdp_drm.ko` | `be8d3e249f813dad1258269dfe074d66668111390b84ed6c7915a310fe4b94ba` |

`sdp_gpu.ko` ist ein ELF32/ARM-Modul und enthält `Mali-G51` und
`r11p0-01rel0 (UK version 11.6)`. Sein ursprünglicher Device-Tree-Match lautet
`arm,mali-midgard` beziehungsweise `arm,malit6xx`.

`dtb.bin` enthält mindestens zwei von uns verifizierte FDT-Bäume:

- Offset `0`: `nikel-2G`;
- Offset `86016`: `nikel-1.5G`.

Beide zeigen `samsung,sdp-nikel` und **vier `arm,cortex-a57`-Knoten**.
Die früher angenommene Cortex-A72-Zuordnung ist damit **nicht** durch diese
Firmware bestätigt. Keine dieser Angaben ist bisher am konkreten TV gemessen.

## Für GPU-Panfrost relevantes DTB-Ergebnis

Der originale Knoten `/soc/sdpgpu@00500000` in **beiden** Varianten enthält:

| Eigenschaft | Wert |
|---|---|
| `compatible` | `arm,mali-midgard` |
| `reg` | `<0x00500000 0x00004000>` |
| `interrupts` | `<0 0x72 0>`, `<0 0x71 0>`, `<0 0x70 0>` |
| `interrupt-names` | `"JOB", "MMU", "GPU"` |
| `clocks` | Nicht im originalen GPU-Knoten vorhanden |
| `power-domains` | Nicht im originalen GPU-Knoten vorhanden |

Der Clock-Controller liegt im selben Device Tree bei `0x00f50000` (Größe
`0x3000`). Die Samsung-GPU-Quellen aus Build 055 nennen GPU-Clock/Reset-Adressen
innerhalb dieses Bereichs, beispielsweise `0x00f5088c` für Nike-L.

Der geplante Linux-6.6-Panfrost-Treiber erkennt die GPU-Generation unter
`arm,mali-bifrost`; Linux 6.6 ordnet `Mali-G51` die Model-ID `0x7000` zu.
**Dies bedeutet keine fertige Hardwareintegration.** Insbesondere sind der
`clock`-Provider, Reset-/Regulator-Steuerung, Interrupt-Trigger und ein realer
`interrupt-parent` für Linux 6.6 noch nicht portiert.

## Sicherer Compile-only-Entwurf

`panfrost-sdp-nikel-disabled.dts` ist ein eigenständiger syntaktischer
**Platzhalter**, absichtlich ohne echte Samsung-Root-Kompatibilität und mit
`status = "disabled"`. Die fehlenden Hardware-Abhängigkeiten verhindern eine
validierte Bindung; erwartet werden gegebenenfalls `dtc`-Warnungen. Der Entwurf
darf **niemals** in den laufenden TV-Kernel oder eine Flash-Datei übernommen
werden.

Nach Installation von `device-tree-compiler` auf einem Debian-Testsystem:

```bash
dtc -I dts -O dtb \
  -o /tmp/build056-panfrost-compile-only.dtb \
  porting/build056/panfrost-sdp-nikel-disabled.dts
```

Dies ist ein **Syntaxkompilat**, kein Linux-6.6-Treiberbuild und kein validierter
Samsung-Device-Tree.

Der Hash-pinnende Bericht ist reproduzierbar, sobald die drei Originaldateien
vorliegen:

```bash
python3 q60t_build056_panfrost_dt_evidence.py \
  --dtb /pfad/zu/dtb.bin \
  --gpu-ko /pfad/zu/sdp_gpu.ko \
  --drm-ko /pfad/zu/sdp_drm.ko \
  --output /tmp/build056-gpu-evidence.json
```

`--output` wird nicht überschrieben. Das Skript liest ausschließlich Dateien;
keine Hardwarezugriffe, Module Loads oder Firmwareänderungen.

# Build 057 — Samsung Nike-L GPU Clock / Reset / Power Forensics

**Status:** `ORIGINAL_POWER_SEQUENCE_CROSSCHECKED_OFFLINE`  
**Ausdrücklich nicht:** funktionsfähiger GPU-Treiber, Clock-Provider, Reset-Provider,
vollständiger Device Tree oder boot-/flashfähiges Image.

Build 057 führt die unveränderten Samsung-Quellen aus Build 055 mit den
SHA256-geprüften Originalfirmware-Funden aus Build 056 zusammen.
Alle Erkenntnisse sind zunächst **Register- und Quellcode-Referenzen**.

## Samsung Original: GPU Power-Control

Quelle:
`tztv-media-nike/sdp_gpu_nike/drivers/gpu/arm/midgard/platform/sdp/mali_kbase_platform_sdp.c`
ab Zeile 470, Funktion `kbase_platform_sdp_gpu_power_control(int state)`.

### Einschaltrichtung (`state == 1`)

| Schritt | Adresse | Maske | Wert des Maskenbits | Beobachtung |
|---:|---|---|---:|---|
| 1 | `0x00f5088c` | `0x00001000` (Bit 12) | 1 | GPU-Clock-Mask aktivieren/freigeben |
| 2 | `0x00f507f8` | `0x01000000` (Bit 24) | 1 | BUSIF-Reset freigeben |
| 3 | `0x00f507f8` | `0x10000000` (Bit 28) | 1 | CORE-Reset freigeben |
| 4 | `0x00f50a10` | `0x00000001` (Bit 0) | 0 | Idle-Anforderung zurücknehmen |

### Ausschaltrichtung (`state == 0`)

| Schritt | Adresse | Maske | Wert des Maskenbits | Beobachtung |
|---:|---|---|---:|---|
| 1 | `0x00f50a10` | `0x00000001` (Bit 0) | 1 | Idle anfordern |
| 2 | `0x00f50a14` | `0x00000001` (Bit 0) | *lesen* | Auf Idle warten |
| 3 | `0x00f507f8` | `0x01000000` (Bit 24) | 0 | BUSIF-Reset aktivieren |
| 4 | `0x00f507f8` | `0x10000000` (Bit 28) | 0 | CORE-Reset aktivieren |
| 5 | `0x00f5088c` | `0x00001000` (Bit 12) | 0 | GPU-Clock deaktivieren |

**Kritisch:** Die Originalfunktion verwendet beim Lesen des Idle-Registers
`&&` statt `&` und besitzt **keinen Timeout** in der `do/while`-Schleife.
Dies kann andere Nichtnull-Bits fälschlich als Idle werten oder die CPU endlos
beschäftigen. Der Ablauf wird daher nur *dokumentiert*, **nicht** in Linux 6.6
kopiert. Eine zukünftige Implementierung benötigt korrekte Registermaskierung,
begrenztes Polling, Fehlerpfad und hardwareverifizierte Bitsemantik.

## Verifikation gegen Build 056

Beide vom Build 056 untersuchten Original-Device-Trees (`nikel-2G` und
`nikel-1.5G`) enthalten:

- Clock-Controller bei `0x00f50000`, Länge `0x3000`;
- Mali GPU MMIO **separat** bei `0x00500000`, Länge `0x4000`;
- JOB/MMU/GPU IRQ-Spezifikationen `<0 0x72 0>`, `<0 0x71 0>`, `<0 0x70 0>`;
- GPU-`compatible = "arm,mali-midgard"` und **keine** `clocks`- oder
  `power-domains`-Eigenschaft am GPU-Knoten.

Alle vier Steuerregister liegen innerhalb des gefundenen Clock-Controller-
Bereichs. BUSIF und CORE teilen sich **dieselbe Adresse** `0x00f507f8`,
nutzen aber unterschiedliche Masken. Eine primitive Registerüberschreibung
wäre folglich besonders gefährlich.

## Lebenszyklus im Samsung-Original

In `mali_kbase_core_linux.c` steht explizit:

- Suspend: erst `kbase_pm_suspend(kbdev)`, dann Samsung `power_control(0)`;
- Resume: erst Samsung `power_control(1)`, dann `kbase_pm_resume(kbdev)`.

Der alte Treiber verwendet außerdem `regulator_get_optional`, `clk_prepare_enable`,
`sdp_runtime_pm_init_and_get` und eine eigene GPU-DVFS-Pfadwahl mit einem
`udelay(20)`. Das ist nicht automatisch mit Linux-6.6-Runtime-PM gleichzusetzen.

## Linux 6.6: vorhandene Verbraucher, fehlende Samsung-Provider

Upstream-Quellcode in
[`drivers/gpu/drm/panfrost/panfrost_device.c` (v6.6)](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panfrost/panfrost_device.c):

| Panfrost-Verbraucher | Bereits vorhandene API | Noch offen bei Samsung |
|---|---|---|
| GPU-Takt | `devm_clk_get`, `clk_prepare_enable` | Common Clock Framework (CCF) Provider und Clock-ID |
| Optionaler Bustakt | `devm_clk_get_optional("bus")` | Prüfung, ob separat nötig |
| Reset | `devm_reset_control_array_get_optional_exclusive` | Reset-Controller mit separaten Bitmasken |
| Versorgung | Regulator/OPP/PM-Domain | Spannung und Power-Domain-Quelle validieren |
| Runtime-PM | `pm_runtime_*` | Sichere Suspend-/Resume-Sequenz und Fehlerpfade |

Linux 6.6 definiert im
[`arm,mali-bifrost.yaml`-Binding](https://github.com/torvalds/linux/blob/v6.6/Documentation/devicetree/bindings/gpu/arm,mali-bifrost.yaml)
unter anderem **`clocks` als Pflichtfeld**. Im Samsung-Original-DT fehlt diese
Eigenschaft. Die Phandle-Nummern, Clock-IDs, IRQ-Trigger und die tatsächliche
Power-Domain sind noch nicht überprüft. Deshalb bleibt der Build-056-DTS
absichtlich **deaktiviert**; Build 057 verändert ihn nicht.

Der Samsung-Clock-Provider muss als eigenständige Linux-6.6-Komponente zunächst
nachvollziehbar aufgebaut werden. Die Implementierung von `sdp_set_clkrst_mux`
ist in den bisher untersuchten OSS-Stellen noch **nicht verifiziert**.

## Reproduzierbarkeit

Benötigt: originale Samsung-OSS-Media-TGZ (mit den Build-055-SHA256-Werten)
und die drei Originalfirmware-Dateien aus Build 056. Beispiel vom Projekt-Root:

```bash
python3 q60t_build057_gpu_power_dependencies.py \
  --media-tgz .build050_vendor/srcarchives/tztv-media-nike.tgz \
  --dtb /pfad/zu/dtb.bin \
  --gpu-ko /pfad/zu/sdp_gpu.ko \
  --drm-ko /pfad/zu/sdp_drm.ko \
  --output /tmp/build057-gpu-power-sequence.json
```

Das Skript liest die gepinnten Quellen, validiert die Originaldateien und
schreibt ausschließlich den Ergebnisbericht. Bereits vorhandene Ausgaben
werden nicht überschrieben. Kein `insmod`, `modprobe`, MMIO, TV- oder
Firmwarezugriff.

**Nächster Entwicklungsblock:** separate CCF-/Reset-Provideranalyse mit
verifizierter Hardware-/Interruptsemantik und begrenzter Idle-Abfrage.
Erst dann kommt die `clocks`-/`resets`-Verknüpfung in einem echten Nike-L-DT
in Betracht.

# Grafikstand: codex/graphics (12.11.2026)

Ziel: Linux **6.6.162 ARM32**, LineageOS **22.2 / Android 15**,
Panfrost (Mali-G51) und sdp-drm. Basis: `claude/build070-drivers` @
`9e02dd326dda46309bfd6073c74ecf0f2a4041ca`.

**Compile-Kandidat, kein funktionierender Grafikstack. Kein TV-Zugriff.**
GPU, GPU-Power-Domain und Display bleiben `disabled`. Keine Module geladen.
Patch 0016 zur Display-Aktivierung ist im Basisbranch nicht vorhanden und
wurde nicht ergänzt: ein grüner Build allein ersetzt die Projektfreigabe nicht.

## Arbeitspakete und tatsächliche Prüfungen

| Paket | Änderung / Ergebnis | Runner-Run-ID |
|---|---|---|
| G1 | In 0019 `ARCH_SAMSUNG_SDP` → `ARCH_SDP`; alle 22 vorhandenen Patches bis 0023 auf sauberem v6.6.162 angewandt. 0019 hatte bereits 19 Zeilen und keinen Repo-Config-Hunk. 0016 fehlt absichtlich. | **43222413774, grün** (zusätzlich lokal) |
| G2 | 0021: disabled `gpu@500000`; reg und alle IRQ-Zellen gegen hashgeprüftes dtb0 verifiziert; beide ARM32-DTBs mit W=1 kompiliert. | **43222413774, grün** (zusätzlich lokal) |
| G3 | 0022: genpd besitzt Gate, Reset und Idle; keine doppelte CCF-/Reset-Steuerung. ARM32-Objekte mit W=1 -Werror kompiliert; Host-MMIO-Modell der tatsächlichen Callbacks bestanden. Parent/Rate/Supply UNBELEGT. | **43222413774, grün** (zusätzlich lokal) |
| G4 | `DRM_PANFROST=y` war vorhanden; `SDP1804_GPU_POWER=y` ergänzt. Alle gesetzten CONFIG-Werte der vier Projektfragmente überleben olddefconfig mit AOSP android-6.6/android-base.config. | **43222413774, grün** (zusätzlich lokal) |
| G5 | 0023: Scanout-Prüfung, FB-Offset, DMA-Adressgrenze, lineare Modifier, IRQ-Initialisierungsreihenfolge und VBlank-Events. ARM32-Objekte mit W=1 -Werror kompiliert. ABGR8888 UNBELEGT; keine Aktivierung. | **43222413774, grün** (zusätzlich lokal) |
| G6 | Kernel-/Mesa-/drm_hwcomposer-Vertrag unten; Userspace weder gebaut noch ausgeführt. | keine |

Lokaler Compiler: Debian GCC **14.2.0**, ARM EABI5, **nicht** der
LineageOS-LLVM-Prebuilt. Das ist ein zusätzlicher Compiletest, kein Ersatz
für den vollständigen Runner-Kernelbuild. Dieser wurde anschließend im Lauf
**43222413774** mit dem LineageOS-LLVM-Prebuilt erfolgreich ausgeführt. Gebaut wurden
`drivers/clk/clk-sdp1804{,-gpu}.o`, `drivers/gpu/drm/{sdp,panfrost}/`
und beide `sdp-nikel-q60t-{1g5,2g}.dtb` mit `W=1 KCFLAGS=-Werror`.
Der erste Android-Configlauf erzeugte die üblichen Kconfig-Choice-Override-
Meldungen (PREEMPT/DEFAULT_SECURITY_SELINUX); keine Projekt-Fragmentwerte
gingen verloren. Die initiale Host-Parser-Generierung meldete vorhandene
Bison-Konflikte in `scripts/genksyms/parse.y`; kein Grafik-C-Warning.
Der vollständige Kernel wurde hier nicht gebaut oder gebootet.

Offline-Tests: Build 059 **17/17**, Build 070 **14/14**, Repository **307 Tests,
0 Fehler, 13 übersprungen** (fehlende optionale Voraussetzungen). Die Quell-
Allowlist wurde ausschließlich um den neuen GPU-MMIO-Test ergänzt.

Die finale Patchwiederholung erzeugt bytegleich dieselben Grafikquellen wie
der Compilekandidat: siehe `local-validation.json`. Firmware-Properties und
SHA-256 der Samsung-Dateien stehen in `source-evidence.json`.

## G2: Firmwarebefund (keine erfundenen IRQ-Flags)

Quelle: `dtb0` (nikel-2G), SHA-256
`0189cc94fe8dd7d016462f22e9f8e965fe328cbc901066c8955f26130f86ab61`.
Direkt geladen aus `https://testpaymenter.noverhost.de/sehrwichtig/dtb.bin`;
Bundle SHA-256 stimmt mit Build 004 überein.

`/soc/sdpgpu@00500000`:

- `reg = <0x00500000 0x4000>`.
- `interrupts = <0 0x72 0>, <0 0x71 0>, <0 0x70 0>`.
- Originalnamen `JOB/MMU/GPU` werden für Panfrost zu `job/mmu/gpu`.
- Original-compatible `arm,mali-midgard`; Zielbinding `arm,mali-bifrost`
  entsprechend dem Projektziel Mali-G51. Live-GPU-ID weiterhin UNBELEGT.
- **Triggertyp im Blob ist 0 / IRQ_TYPE_NONE.** Elektrische Polarität und
  Flanken-/Pegelverhalten sind damit nicht bewiesen. Kein erfundenes
  `IRQ_TYPE_LEVEL_HIGH`. Der Kbase-Test-/Fake-Pfad setzt zwar
  `IORESOURCE_IRQ_HIGHLEVEL`, beschreibt aber nicht Nike-L-Hardware und ist
  daher kein Gegenbeleg. Erst vor Aktivierung aufklären.
- **`mali-supply`: UNBELEGT und nicht ergänzt.** Der Samsung-Kbase-Treiber
  fragt `regulator_get_optional(..., "mali")` ab und fährt bei fehlendem
  Regler ausdrücklich fort
  (`sdp_gpu_nike/.../mali_kbase_core_linux.c:3508–3543`). Das Original-DTB
  enthält zwar die Regler `CPU_PW` und `CORE_PW`, aber keinerlei
  GPU-Knoten-Referenz oder Regler mit Mali-Bezug. Eine Zuordnung von
  `CORE_PW` zu `mali-supply` wäre geraten und bleibt verboten.

## G3: Design 2, ein genpd-Owner

Samsung-Pfade im Archiv `tztv-media-nike.tgz`:

`/sdp_gpu_nike/drivers/gpu/arm/midgard/platform/sdp/`:

- `mali_kbase_platform_sdp.c:470–494`: Clock an → Bus-Reset lösen →
  Core-Reset lösen → Idle-Request löschen; aus: Request → Ack → Bus-/Core-
  Reset setzen → Clock aus.
- `mali_kbase_config_platform.h:101–106`: NIKEL-Register
  `f5088c/f507f8/f50a10/f50a14`; `:128–140,150–162`: Bitmasken.
- Basis und Größe des einzigen MMIO-Mappings aus Firmware
  `/soc/clock-controller@00F50000 reg = <0xf50000 0x3000>`.

`clk-sdp1804-gpu.c` nutzt das bestehende Mapping von `clk-sdp1804.c`.
Die vorhandenen PLL-/Divider-Operationen lesen nur. Nur genpd schreibt die
GPU-Bits; kein `resets`-Eintrag im GPU-Knoten, kein zweiter CCF-Gate-Owner.
Genpd serialisiert die Power-Callbacks. Es werden nur die belegten Bits
verändert; keine separaten IO-Mappings oder Register-Basisadressen erfunden.

Die Domain wird nur registriert, wenn ihr DT-Kind explizit verfügbar ist.
Bei `disabled` erfolgt **kein zusätzlicher GPU-MMIO-Zugriff**. Beim späteren
Registrieren werden nur vollständig an/aus konfigurierte Bootzustände
akzeptiert; ein gemischter Zustand wird ohne Schreibzugriff abgewiesen.
Bei fehlendem Idle-Ack: Fehler zurück an genpd, Request-Bit restaurieren,
Gate und Resets unverändert. Anders als eine `clk_ops.disable`-Funktion kann
`power_off` einen Fehler zurückgeben. Die 2000 µs sind eine Software-
Timeoutgrenze, **keine** gemessene Hardwareanforderung. Samsung nutzt dort
eine unbegrenzte Schleife mit logischem statt bitweisem AND (:479).

**Takt-Parent und Rate: für einen aktivierbaren Panfrost-Knoten weiter
UNBELEGT.** Die echte SDP1804-Tabelle in
`linux-4.1.10/drivers/clk/clk-sdp.c:1505–1545` beschreibt die PLLs und
einige feste Teiler, aber keinen GPU-Ausgang. Das Original-DTB hat unter
`/soc/clock-controller@00F50000` ebenfalls keinen GPU-Clock-Child und der
Vendor-GPU-Knoten hat keine `clocks`-Property. COREPLL0/4-Werte anderer
SoC-Tabellen dürfen nicht übernommen werden.

Die Kbase-DVFS-Implementierung belegt immerhin die folgenden *programmier-
baren* Subpfade. Quelle sind die Kommentare und Zuweisungen in
`mali_kbase_platform_sdp.c:219–285`; die numerischen Muxwerte stehen in
`mali_kbase_config_platform.h:121–154,184–208`. Die Tabelle ist weder eine
Messung am Q60T noch ein gültiger OPP-Satz für Linux 6.6:

| Kbase-Level | Vendor-Kommentar | angewählter PLL-Pfad | Prescaler-Schritt |
|---|---|---|---|
| 1 | 95 MHz, COREPLL1 / 8 | Subpath 2, COREPLL1 | 4 (bei `half_out_sel = 0`) |
| 2 | 190 MHz, COREPLL1 / 4 | Subpath 2, COREPLL1 | 2 |
| 3 | 300 MHz, FRCPLL / 4 | Subpath 1, FRCPLL | 2 |
| 4 | 380 MHz, COREPLL1 / 2 | Subpath 2, COREPLL1 | 1 |
| 5 | 500 MHz, COREPLL0 / 4 | Subpath 1, COREPLL0 | 2 |
| 6 | 600 MHz, FRCPLL / 2 | Subpath 1, FRCPLL | 1 |
| 7 | 702 MHz, PULLPLL1 / 2 | Subpath 1, PULLPLL1 | 1 |
| 8 | 760 MHz, COREPLL1 direkt | keine Programmierung: Funktion gibt `-1` zurück | — |

Die separate Vendor-Frequenztabelle nennt stattdessen 100, 200, 300, 400,
500, 600, 700 und 800 MHz (`mali_kbase_platform_sdp.c:42–52`). Diese
Abweichung und der unimplementierte Level 8 verhindern eine Übernahme als
OPP-Tabelle. Der Umschaltcode setzt erst den Mainpfad, programmiert den
Subpfad, wartet 20 µs und schaltet danach auf Sub um
(`mali_kbase_platform_sdp.c:290–324`). Er beweist weder den Boot-Muxzustand
noch die realen PLL-Raten aus einem laufenden Q60T.

Daher weiterhin kein gefälschter CCF-Clock, kein `clocks = <&fin_pll>` und
keine erfundenen OPPs. Panfrost benötigt vor einer Bindung einen belegten
Clock-Provider und `mali-supply`; genpd allein macht die GPU nicht
lauffähig. Der nächste sichere Nachweis ist ein reiner Register-Readback
eines laufenden Originalsystems für die Mux- und PLL-Register – ohne
Schreibzugriff.

## G5: Displaybefunde und Änderung 0023

Fundstellen unter `tztv-media-nike/`:

| Gegenstand | Fundstelle |
|---|---|
| Registerindizes (REG(x)=x<<2) | `sdp_logo_nike/nikem/inc/sdp_logo_chip.h:164–220` |
| H_OFFSET = width >> 2; Inputgröße | `sdp_logo_nike/nikem/sdp_logo.c:296–301` |
| GP-Basisadresse | dieselbe Datei `:470–472` |
| NIKEL-IRQ read/write-back | dieselbe Datei `:36–53` |
| NIKEL-Unmask 0 | `sdp_logo_nike/nikem/sdp_logo_gfx.c:83–85` |
| VBlank mask/unmask 1/0 | `sdp_drm_nike/gfx/nikel/sdp_mixer.c:108–146` |
| GP-Formate XRGB8888/ARGB8888 | `sdp_drm_nike/sdp_hw_plane.c:13–17` |
| reg-Regionen / IRQ-SPI 0x2f | Firmware dtb0 `/soc/bootlogo` |

Bisher konnte ein IRQ vor CRTC/VBlank-Initialisierung eintreffen. Der
Request kommt jetzt erst danach. Pageflip-Events werden bei verfügbarem
VBlank-Ref für den nächsten Interrupt armiert, statt sofort als fertig
gemeldet. Die üblichen DRM-VBlank-Hooks steuern die belegten Maskwerte.
Ohne Pending-Status liefert der Shared-Handler `IRQ_NONE`.

Die Implementierung programmiert weiter nur den 1920×1080-Bootlogo-Pfad,
übernimmt POST/TMG-Zustand und erfindet keine Pixeltimings. Andere Größen,
Interlace, Double-Scan, nichtlineare Modifier, nicht passende Pitches und
Crop-Offsets werden abgewiesen. FB-Offsets werden in der DMA-Adresse
berücksichtigt. Der portierte BASE_ADDR_LOW-Pfad akzeptiert nur Adressen
innerhalb 32 Bit und begrenzt auch DMA-Allokationen entsprechend.

**Noch UNBELEGT / ungetestet:** genaue Panel-/Refresh-/Blanking-Timings;
GP-Format-/Swizzle-Programmierung für ABGR8888; GP-Adress-Latch bei VSync;
IRQ-Statusbit-Bedeutung im Detail; Scanout-/CMA-/Bootlogo-Speicherübergabe;
Tearing, Farben, PRIME-Import und Display-Power-Sequenz am Gerät.
Die Vendor-GP-Formatliste ist auf XRGB8888 und ARGB8888 begrenzt
(`sdp_drm_nike/sdp_hw_plane.c:13–17`); XRGB8888/ARGB8888 sind damit
Quellbefunde, aber keine Messung korrekter Farben. Weder die G2D-RGBA-Enums
noch Androids Formatwunsch beweisen einen GP-ABGR-Swizzle.

## G6: Mesa-Panfrost / drm_hwcomposer für LineageOS 22.2

| Kernelvertrag | Stand / Konsequenz |
|---|---|
| Panfrost-Render-Node `/dev/dri/renderD*` | `panfrost_drv.c` hat DRIVER_RENDER/GEM/SYNCOBJ; entsteht erst bei erfolgreicher Probe. Kein Beleg durch `=y` allein. |
| KMS-Primary-Node, Atomic/Universal Planes | sdp-drm hat DRIVER_GEM/MODESET/ATOMIC, einen Connector und eine Plane. drm_hwcomposer braucht DRM-Master/SELinux-Rechte und echte Hotplug/VBlank-/Commitfunktion. |
| DMA-BUF / PRIME zwischen zwei Geräten | Panfrost-GEM-shmem-BOs können physisch fragmentiert sein. sdp-drm GEM-DMA benötigt durchgehenden DMA-Adressraum; GPU-MMU ist keine Display-IOMMU. Allocator muss scanoutfähige BOs liefern, die Panfrost importiert. Kompatibilität UNBELEGT. |
| Dumb-Buffer, Patch 0011 | Erlaubt nur die **IOCTL-Berechtigung** auf Render-Nodes. Panfrost hat in v6.6.162 **keinen dumb_create-Callback**; 0011 fügt ihn nicht hinzu und erzeugt keinen Render-Node für sdp-drm. Mesa-Panfrost nutzt CREATE_BO; Scanout-Dumb-Buffers gehören auf den KMS-Pfad. |
| Formate | sdp-drm nur XRGB8888/ARGB8888 linear. Android-RGBA/DRM-ABGR8888 benötigt explizite Composition/Conversion oder belegten Hardware-Swizzle. Keine Format-Alias-Lüge. |
| Modifier | nur DRM_FORMAT_MOD_LINEAR für Scanout, kein AFBC/Tiling. Mesa und Allocator müssen den Schnittmengen-Modifier wählen; AFBC eines Panfrost-Render-BOs ist kein Beweis für Display-AFBC. |
| Fences | Panfrost dma_fence/syncobj und KMS atomic-helper-Fences sind Ausgangspunkt; End-to-End acquire/release/present, VBlank und DMA-BUF-Synchronisierung noch nicht auf Android geprüft. |
| Mesa / HAL | Gallium Panfrost unterstützt Bifrost/G51. kmsro-Zuordnung für `sdp-drm`, ARM32-Build, GBM-Allocator/Mapper, AIDL-Composer3-Version und VINTF für LineageOS 22.2 müssen im Userspace integriert und gebaut werden. Nicht erledigt durch Kernelpatches. |

Kein Vendor-`libmali.so`-/Kbase-ABI wird mit Panfrost gemischt. Das Vorhandensein
von `/dev/mali0` ist kein DRM-Render-Node. MindTheGapps ist kein GPU-/Display-HAL.

## Runnernachweis / nächster Schritt

Workflow `build070-drivers.yml` akzeptiert jetzt auch `codex/graphics`.
Gate erweitert auf `drivers/gpu/drm/panfrost/` und den GPU-Domain-Treiber;
`dtc W=1`-Warnungen sind jetzt ein Fehler statt einer bloßen Zählung.

Ausgeführter Auftrag: MODE=kernel,
`REQUEST_ID=2026-11-12-graphics-g1-g6-01`; genau ein abgestimmter Request.
`LOS_DIR` und `GPL_DIR` unverändert.

**Run [43222413774](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43222413774), 12.11.2026, Ergebnis SUCCESS.**
Getesteter Commit `68f47e940f089168920b539588a057d8bb04fe2d`, Runner `debian`.
LineageOS-Prebuilt `clang-r536225`, Android Clang 19.0.1.
Offline-Tests und vollständiger Kernelbuild `arm android` erfolgreich;
`Image`, `zImage`, beide DTBs erzeugt. Grafik-Gate `W=1 -Werror` erfolgreich,
beide zusätzlichen DT-Rebuilds: **0 Warnungen**. Das heruntergeladene
Actions-Artefakt bestätigt `DRM_PANFROST=y`, `DRM_SDP=y`,
`SDP1804_GPU_POWER=y`, `PM_GENERIC_DOMAINS=y`; alle gesetzten Werte der
vier Projektfragmente sind erhalten. Logauszug:
[runner-43222413774.md](runner-43222413774.md), maschinenlesbarer Beleg:
[runner-validation.json](runner-validation.json).
Artefakt `13947050571`, SHA-256
`7a754e286d75b05148893c5c7a8be7085b9e8c2eaab72ac55fe88e4e750da655`.
Keine Hardware-/Boot-/Userspace-Validierung; `drm@5d0000` bleibt disabled.

Patch 0024 ergänzt eine zweite, softwareseitige Sicherung für den späteren
Displayversuch: Selbst bei `status = "okay"` beendet `sdp-drm` die Probe vor
dem ersten MMIO-Mapping mit `-EPERM`, solange nicht zusätzlich
`samsung,enable-experimental-kms` im selben Knoten steht. Das Property ist
als Projekt-Sicherheitsinterlock im neuen DT-Binding dokumentiert, nicht als
behauptete Hardwarefunktion. GPU und Display sind im ausgelieferten DT weiter
`disabled`; 0024 wurde nur mit `patch --dry-run` auf dem vollständigen
Patchstand 0023 geprüft, noch nicht im Runner gebaut.

Nächste fachliche Arbeit: belegten GPU-Mux-/Parent-Readback erarbeiten;
danach ABGR/Allocator und reale Display-Timings, weiterhin ohne
TV-Aktivierung. Für einen weiteren Kernelauftrag wieder mit dem
Projektleiter abstimmen. Die reinen Ergebnis-Dokuänderungen lösen keinen
neuen Build070-Runnerauftrag aus.

## Vorbereiteter SDB-Readback

`../tools/collect_tizen_graphics_evidence.sh` sammelt für einen bereits
verbundenen Stock-Tizen-SDB-Endpoint ausschließlich lesend `dmesg`,
`/proc/interrupts`, die Live-DT-GPU-Properties, Clock-/Regulator-Debugfs und
DRM-/GPU-Sysfs. Es lädt keine Module, schreibt weder Sysfs noch MMIO und
verändert den Fernseher nicht. Auf dem Rechner mit SDB:

```sh
SDB_SERIAL='HOST:PORT' OUT_DIR=./q60t-stock-evidence \
  porting/build070/tools/collect_tizen_graphics_evidence.sh
```

Das Ergebnisarchiv ist die Eingabe für Clock-Parent/Rate, IRQ-Typ,
`mali-supply` und den echten Display-Bootmodus. Fehlende Debugfs-Dateien
sind ein Befund, kein Fehler des Collectors.

Der Collector prüft vor den Abfragen mit `sdb shell id`, ob der Ziel-Shell
tatsächlich offen ist. Bei einem Fehler wie `closed` wird nur
`connection.txt` geschrieben und der Lauf beendet; ein solches Archiv enthält
keine verwertbaren TV-Daten. Vor einem erneuten Lauf auf dem Mac daher:

```sh
sdb connect 192.168.178.20:26101
sdb devices
sdb -s 192.168.178.20:26101 shell id
```

Erst wenn der letzte Befehl eine `uid=...`-Zeile ausgibt, den Collector
ausführen.

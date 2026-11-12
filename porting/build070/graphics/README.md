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
| G1 | In 0019 `ARCH_SAMSUNG_SDP` → `ARCH_SDP`; alle 22 vorhandenen Patches bis 0023 auf sauberem v6.6.162 angewandt. 0019 hatte bereits 19 Zeilen und keinen Repo-Config-Hunk. 0016 fehlt absichtlich. | keine, lokal |
| G2 | 0021: disabled `gpu@500000`; reg und alle IRQ-Zellen gegen hashgeprüftes dtb0 verifiziert; beide ARM32-DTBs mit W=1 kompiliert. | keine, lokal |
| G3 | 0022: genpd besitzt Gate, Reset und Idle; keine doppelte CCF-/Reset-Steuerung. ARM32-Objekte mit W=1 -Werror kompiliert; Host-MMIO-Modell der tatsächlichen Callbacks bestanden. Parent/Rate/Supply UNBELEGT. | keine, lokal |
| G4 | `DRM_PANFROST=y` war vorhanden; `SDP1804_GPU_POWER=y` ergänzt. Alle gesetzten CONFIG-Werte der vier Projektfragmente überleben olddefconfig mit AOSP android-6.6/android-base.config. | keine, lokal |
| G5 | 0023: Scanout-Prüfung, FB-Offset, DMA-Adressgrenze, lineare Modifier, IRQ-Initialisierungsreihenfolge und VBlank-Events. ARM32-Objekte mit W=1 -Werror kompiliert. ABGR8888 UNBELEGT; keine Aktivierung. | keine, lokal |
| G6 | Kernel-/Mesa-/drm_hwcomposer-Vertrag unten; Userspace weder gebaut noch ausgeführt. | keine |

Lokaler Compiler: Debian GCC **14.2.0**, ARM EABI5, **nicht** der
LineageOS-LLVM-Prebuilt. Das ist ein zusätzlicher Compiletest, kein Ersatz
für den angeforderten vollständigen Runner-Kernelbuild. Gebaut wurden
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
  `IRQ_TYPE_LEVEL_HIGH`. Erst vor Aktivierung aufklären.

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

**Takt-Parent und Rate: UNBELEGT.** Die echte SDP1804-Tabelle in
`linux-4.1.10/drivers/clk/clk-sdp.c:1505–1545` beschreibt PLLs und feste
Teiler, aber keinen GPU-Takt. COREPLL0/4-Werte anderer SoC-Tabellen dürfen
nicht übernommen werden. Kbase `mali_kbase_platform_sdp.c:188–209` wählt
verschiedene Main-/Subpfade; eine Tabelle beweist nicht die aktuelle
Muxstellung. Daher kein gefälschter CCF-Clock, kein `clocks = <&fin_pll>`,
keine erfundenen OPPs. Panfrost benötigt weiterhin einen belegten Clock-
Provider und `mali-supply`, bevor eine Bindung sinnvoll ist. Genpd allein
macht die GPU nicht lauffähig.

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
XRGB8888/ARGB8888 sind Quellbefunde, keine Messung korrekter Farben.

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

## Nächster Runnerauftrag

Workflow `build070-drivers.yml` akzeptiert jetzt auch `codex/graphics`.
Gate erweitert auf `drivers/gpu/drm/panfrost/` und den GPU-Domain-Treiber;
`dtc W=1`-Warnungen sind jetzt ein Fehler statt einer bloßen Zählung.

Einziger geplanter Auftrag: MODE=kernel, neuer REQUEST_ID. `LOS_DIR` und
`GPL_DIR` bleiben unverändert. Vor dem Push wegen der gemeinsam genutzten
Concurrency-Gruppe `build068-selfhosted-v2` mit dem Projektleiter abstimmen.
Solange kein Lauf gestartet wurde: **Runner-Run-ID = keine, Ergebnis = nicht
getestet**. Nach jedem Lauf Run-ID, Ausgang und relevante Logzeilen hier
und im Build-070-README ergänzen. Nächste fachliche Arbeit: belegten
GPU-Mux-/Parent-Readback erarbeiten; danach ABGR/Allocator und reale
Display-Timings, weiterhin ohne TV-Aktivierung.

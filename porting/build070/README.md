# Build 070 – Treiber für den Q60T (Nike-L) auf Linux 6.6.162 ARM32

**Stand 12.11.2026 – Schritt 0 + Infrastruktur, noch kein Runner-Lauf.**
Basis: Branch `claude/build069-android-qemu-boot` (ce5bf49). Am TV wird nichts
getestet, geflasht oder geladen; die Gates aus Build 061/065 bleiben.

## Was in diesem Build „getestet“ heißt

| Prüfung | Wo | Stand |
|---|---|---|
| Offline-Tests (`build059/tests`, `build070/tests`, `tests/`) | lokal (Chat) | ✅ grün, 12.11. |
| Patch-Serie 0001–0012 wendet sich auf v6.6.162 (5139929c) an | lokal (Chat, `patch -p1`) | ✅ |
| Kernel-Konfiguration (jede Fragmentzeile überlebt `olddefconfig`) | Runner, `MODE=kernel` | ⏳ nicht gelaufen |
| `W=1 -Werror`-Gate inkl. `sdp_drm.o` | Runner, `MODE=kernel` | ⏳ nicht gelaufen |
| `dtc` mit `W=1` für `sdp-nikel-q60t-{1g5,2g}.dtb` | Runner, `MODE=kernel` | ⏳ nicht gelaufen |
| Firmware-DTBs + GPL-Quellen auf dem Runner | Runner, `MODE=sources` | ⏳ eingereiht (Runner blockiert) |

Lokal wurde **kein** Kernel konfiguriert oder kompiliert (Chat-Umgebung ohne
`flex`, ohne AOSP-`android-base.config`). Alles in der Spalte „Runner“ gilt erst
nach einem grünen Lauf als geprüft.

## Schritt 0 – ein gemeinsamer Q60T-Kernel

Das Build-059-Profil `android` **ist** jetzt der gemeinsame Kernel:

```
multi_v7_defconfig
 + AOSP android-base.config (6.6)
 + nikel-common.config + nikel-arm.config
 + nikel-android.config      (SELinux-LSM, Security-xattrs – Build 069)
 + nikel-drivers.config      (NEU, Build 070: Treiberset aus Build 063–066)
 + Patches 0001–0012         (0010 BPF-Fallback, 0011 Dumb-ioctls auf Render-Nodes,
                              0012 NEU: sdp-drm-KMS-Skelett in drivers/gpu/drm/sdp/)
```

- `nikel-drivers.config` fasst `nikel-display/-gpu/-cpu/-soc-extra/-peripherals/
  -simpledrm` zusammen. Bewusst entfernt: `CONFIG_COMPILE_TEST` (hier ist
  `ARCH_SDP=y` echt), nur per `select` gesetzte Helfer (`DRM_KMS_HELPER`,
  `DRM_GEM_*_HELPER`, `DRM_SCHED`, `PM_OPP` – würden die Überlebensprüfung von
  `build.sh` scheitern lassen) und `SYSFB`/`SYSFB_SIMPLEFB` (nur X86/EFI;
  simpledrm bindet über einen DT-Knoten `simple-framebuffer`). Alles `=y`, damit
  am TV kein Modul geladen werden muss.
- `build.sh`: Profil `android` mischt `nikel-drivers.config` ein; das
  `W=1 -Werror`-Gate umfasst zusätzlich `drivers/gpu/drm/sdp/sdp_drm.o`.
- Patch 0012 = Build-063-Skelett, ergänzt um `.remove_new`/`.shutdown`
  (6.6-API). Er bindet nur an einen DT-Knoten `samsung,sdp-drm` – den es im
  Q60T-DT noch nicht gibt.
- memfd statt ashmem: `porting/device/samsung/nikel/init.nikel.rc`
  (`sys.use_memfd=true`, wie `init.qemuarm.rc`), eingebunden in `device.mk`.
  Die `$(error)`-Sperre in `BoardConfig.mk` bleibt.
- **Auswirkung auf Build 069:** Ein QEMU-Lauf mit `REBUILD_KERNEL=1` bekommt
  das Treiberset mit. Ohne passende DT-Knoten proben die Treiber nicht; der
  gecachte Boot-10-Kernel (`REBUILD_KERNEL=0`) bleibt unverändert.

### Device-Tree: noch keine neuen Knoten

Die Build-063/064/066-DT-Fixtures enthalten **Platzhalteradressen** (z. B.
`display@c00000`, `framebuffer@0`). Sie werden **nicht** in den Q60T-DT
übernommen. Neue Knoten kommen erst mit Werten aus der Firmware-`dtb.bin`
(Fundstelle: `dtb0 (nikel-2G) /soc/<knoten> <property>`), alle zunächst
`status = "disabled"`.

**Achtung Adressraum:** `porting/build065/SOC_ADDRESS_MAP.md` nennt Adressen der
GPL-Vorlage `sdp1412.dtsi` (z. B. GIC `0x10fa1000`, eMMC `0x10000000`). Die
Firmware-DTBs des Q60T beschreiben dieselben Blöcke anders (GIC `0x431000`,
eMMC `0x100000`, UART `0x190a00`, Clock `samsung,sdp1804-clock`) – der
Build-059-DT folgt der Firmware. Für Build 070 gilt deshalb: **Adressen nur aus
der Firmware-`dtb.bin`**; die GPL-Quelle liefert Registerlayouts und Logik, aber
keine Basisadressen für den Q60T.

## Runner-Aufträge (`runner/request.env`, Workflow `build070-drivers.yml`)

Gleiche Concurrency-Gruppe wie Build 068/069 (`build068-selfhosted-v2`).
Nie zwei `request.env` in einem Push; ein neu eingereihter Lauf verdrängt einen
schon wartenden derselben Gruppe.

| MODE | Tut | Ausgabe im Job-Log |
|---|---|---|
| `sources` | `dtb.bin` per Range-Request aus dem FullOS-ZIP, Aufteilung in dtb0/dtb1, SHA-256 gegen Build 004; GPL-ZIP (743 MB) laden, `linux-4.1.10-tizen5.5.tgz` + `tztv-media-nike.tgz` nach `GPL_DIR`, entpacken | `T>` Knotentabelle, `N>` Treiberknoten mit allen Properties, `X>` Unterschiede 2G/1.5G, `I>` Inventar mit `MODULE_LICENSE` |
| `show` | bis 12 Dateien/Verzeichnisse aus `GPL_DIR/src` oder `GPL_DIR/firmware` | `S>` Zeilen mit Zeilennummern |
| `kernel` | eigener sauberer v6.6.162-Baum, `build059/kernel/build.sh arm android`, `dtc W=1` | Fragment-/Gate-Ergebnis, Treibersymbole, Coverage |

Der Display-Quellcode (`sdp_drm_nike`) liegt **nicht** im Kernel-Tarball,
sondern in `tztv-media-nike.tgz` – deshalb holt `MODE=sources` beide.
Vor jeder Portierung wird die Lizenz geprüft: Dateien mit
`MODULE_LICENSE("Proprietary")` (wie `sdp_mmc.c`) werden nicht übernommen.

## Nächste Schritte (Reihenfolge laut Kickoff)

1. Runner neu registrieren (hängender Run 43095047193) → Boot 10 (Build 069)
   und danach `MODE=sources` laufen von selbst.
2. `MODE=kernel` – gemeinsamer Kernel grün (Fragmente, Gate, dtc).
3. **Display:** `sdp_drm_nike` + `drm_tztv_helper.c` + `panel-sdp.c` lesen
   (`MODE=show`), Lizenz prüfen, Registerprogrammierung in `sdp_drm.c`
   (`pipe_enable/disable/update`, vblank) portieren; DT-Knoten aus `dtb0`
   (`disabled`); simpledrm-Knoten erst mit echten Framebuffer-Parametern.
4. Danach IR (`rc-core`), Ethernet, Audio (ASoC), CEC.

# Build 070 – Treiber für den Q60T (Nike-L) auf Linux 6.6.162 ARM32

**Stand 12.11.2026, 10:35 – gemeinsamer Kernel grün, IR und CEC portiert (compile-only).**
Basis: Branch `claude/build069-android-qemu-boot` (ce5bf49). Am TV wird nichts
getestet, geflasht oder geladen; die Gates aus Build 061/065 bleiben.

## Grafik – codex/graphics (12.11.2026)

Aktueller Grafikstand und G1–G6: [graphics/README.md](graphics/README.md).
Patches 0021 (GPU-DT), 0022 (genpd), 0023 (Scanout/VBlank); GPU, Domain und
Display bleiben disabled. Lokaler ARM32-GCC-Compile mit W=1 -Werror für
sdp-drm/Panfrost/Clock-Domain und beide DTs bestanden; sämtliche gesetzten
Projekt-Fragmentwerte überleben das Android-Profil. **Kein neuer Runnerlauf,
Run-ID: keine; LineageOS-LLVM und vollständiger Kernelbuild noch ausstehend.**
GPU-Parent/Rate/Supply, ABGR8888 und genaue Panel-Timings: **UNBELEGT**.
Andere Subsysteme unverändert, ausgenommen Build-Blocker in Patch 0019:
`CONFIG_ARCH_SAMSUNG_SDP` → `CONFIG_ARCH_SDP`. Hunkgröße/Config-Hunk waren
im übernommenen Basisstand bereits bereinigt. Patch 0016 fehlt und wurde
nicht zur Aktivierung ergänzt.

## Was in diesem Build „getestet“ heißt

| Prüfung | Wo | Stand |
|---|---|---|
| Offline-Tests (`build059/tests`, `build070/tests`, `tests/`) | lokal (Chat) | ✅ grün, 12.11. |
| Patch-Serie 0001–0012 wendet sich auf v6.6.162 (5139929c) an | lokal (Chat, `patch -p1`) | ✅ |
| Kernel-Konfiguration (jede Fragmentzeile überlebt `olddefconfig`) | Runner, Run 43192182923 | ✅ |
| `W=1 -Werror`-Gate (UART, Clock, GPIO, sdp-drm, Micom, IR, CEC) | Runner, Run 43192182923 | ✅ |
| `dtc` mit `W=1` für `sdp-nikel-q60t-{1g5,2g}.dtb` | Runner, Run 43192182923 | ✅ 0 Warnungen |
| Firmware-DTBs (SHA-256 = Build 004) + GPL-Quellen auf dem Runner | Runner, Run 43180001180 | ✅ |
| Am TV / unter QEMU gebootet | – | ❌ nicht gelaufen |

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

## Portierte Treiber (Linux 6.6, aus Samsungs GPL-Paket 20_DTV_NikeL)

| Patch | Treiber | Quelle (4.1.10 / tztv) | DT (Fundstelle Firmware dtb0, nikel-2G) | Stand |
|---|---|---|---|---|
| 0012 | `drm/sdp` Display-KMS **Gerüst** | Build 063 (eigen) | – | kompiliert, kein Modeset |
| 0013 | `soc/sdp/sdp-msgbox` Micom-Mailbox | `drivers/mailbox/sdp_micom_msgbox.c` | `/soc/msgbox` reg 0x9c0400/0x100, IRQ SPI 0x22 | kompiliert, DT disabled |
| 0013 | `soc/sdp/sdp-micom` Micom-Protokoll | `tztv-micom/sdp_micom_messagebox.c` | `/tztv_micom` | kompiliert, DT disabled |
| 0013 | `media/rc/sdp-micom-rc` Fernbedienung | `tztv-micom/rc-wt61p807.c`, `keymap-rc-wt61p807.c` | (Kind von micom) | kompiliert |
| 0014 | `media/cec/platform/sdp/sdp-cecif` HDMI-CEC | `drivers/soc/sdp/sdp_micom_cecif.c` | `/soc/cecif` reg 0x9c0f00/0x48, IRQ SPI 0x27; `/soc/mccmu` 0x9c0300/0x30 | kompiliert, DT disabled |

Hinweise:
- **IR:** `sdp_micom_irb.c` ist ein IR-*Sender*, `sdp_micom_irs.c` ein Roh-Empfänger
  (eigenes `/dev/lirc1`, Polling). Tasten der Fernbedienung dekodiert der Micom und
  meldet sie über die Message-Box – dieser Weg ist portiert. Key-Map: 157 von 163
  Samsung-Codes (6 Hotel-Codes ohne Mainline-Keycode entfallen); Android braucht
  noch eine `.kl`-Datei (Tizen nutzt z. B. KEY_F10 = Lauter).
- **CEC:** Der Controller gehört im Standby dem Micom; der Treiber übernimmt die
  vom Micom gesetzten Timing-Register und verweigert `enable`, solange der Micom
  ihn hält. Offen: Micom-Versionsprüfung (`sdp_mc_ctrl_syscall_get_version`,
  braucht `samsung,sdp-micom-ctrl`), Physikalische Adresse fest 0.0.0.0 (TV).
- **Nicht portiert:** Micom-Poweroff/Restart-Hooks (Ausschalten über Micom),
  Hotel-/HD-Protokoll, ISP, Panel-Tasten-Client.
- **Lizenz:** alle bisher portierten Dateien tragen GPL-Köpfe. Dateien mit
  „confidential and proprietary"-Kopf (v. a. `sdp_drm_nike/dp/`) werden nach
  Absprache vom 12.11. ebenfalls genutzt, nur im privaten Repo, mit Originalkopf,
  in eigenem Unterordner und mit Liste hier; vor einer Veröffentlichung entfernen.

## Nächste Schritte (Reihenfolge laut Kickoff)

1. Runner neu registrieren (hängender Run 43095047193) → Boot 10 (Build 069)
   und danach `MODE=sources` laufen von selbst.
2. `MODE=kernel` – gemeinsamer Kernel grün (Fragmente, Gate, dtc).
3. **Display:** `sdp_drm_nike` + `drm_tztv_helper.c` + `panel-sdp.c` lesen
   (`MODE=show`), Lizenz prüfen, Registerprogrammierung in `sdp_drm.c`
   (`pipe_enable/disable/update`, vblank) portieren; DT-Knoten aus `dtb0`
   (`disabled`); simpledrm-Knoten erst mit echten Framebuffer-Parametern.
4. Danach IR (`rc-core`), Ethernet, Audio (ASoC), CEC.

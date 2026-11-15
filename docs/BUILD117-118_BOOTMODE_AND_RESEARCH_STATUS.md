# Samsung Q60T / Nike-L: BUILD 117–118 – Bootmode und Forschungsstand

**Stand:** 15. November 2026  
**Zielgerät:** Samsung Q60T 50 Zoll (`GQ50Q60TGUXZG`), Firmware T-NKLDEUC 2743.0, Nike-L/SDP1804  
**Evidenzklasse:** GPL-Quellcode, archivierte Firmware-DTBs, Offline-Scans, vorhandene Berichte. **Kein neuer Live-Test eines alternativen Kernels auf dem TV.**

Diese Ergänzung baut auf [BUILD 070–116](BUILD070-116_PROGRESS.md) auf und trennt bewusst neue Erkenntnisse von bereits durchgeführten Analysen.

## BUILD 117 – Was war schon bekannt?

Bereits in **BUILD 066**, dokumentiert unter `porting/build066/docs/BOOT_ACCESS.md` im Debian-Labor, war der generische Samsung-Treibermechanismus `tztv_bootmode` beschrieben: `communication-mode = "gpio"` oder `"reg"`, Parameter `ew-select` und im Registermodus `readl() & 0x7`. Dies ist **kein neuer BUILD-117-Befund**. Auch die frühere `seret.bin`-/`sign.bin`-/`secos.bin`-Analyse, Kernel-Metadaten `0x80008000`, RAM-Bank-Diskussion und U-Boot-`uImage`-Header waren bereits in BUILD 070–116 behandelt worden.

### Tatsächlich verifizierte Zusatzinformationen

Im GPL-Archiv `/opt/samsung-atv-lab/samsung/archives/inner/20_DTV_NikeL.zip` ist `tztv-bootmode.tgz` enthalten, mit `HOW_TO_BUILD.txt`, `Makefile` und `tztv-bootmode.c`. Der Quellcode war bereits in BUILD 117 STEP 4 inspiziert; die Extraktion in STEP 10 FIX war daher eine **Wiederholung**, aber erfolgreich. Der Treiber bildet Werte 0–6 auf Tizen-/Early-Warning-/Upgrade-/DDR-Test-/Release-/Background-/HDMI-Kalibrierungs-Modi ab. Der beobachtete Registerzugriff liest den Bootmode; ein schreibender Bootloader-Unlock-Pfad ist **nicht** nachgewiesen.

**Unterschiedliche Device-Tree-Adressen:**

| DT-Quelle | `communication-mode` | `ew-select` |
|---|---|---|
| Samsung Linux 4.1.10 `arch/arm/boot/dts/sdp1501-tizen.dts` (Zeilen 870–875) | `reg` | `0x00800584` |
| Archivierter Nike-L-DTB, erstes Profil | `reg` | **`0x009c12c4`** |
| Archivierter Nike-L-DTB, zweites Profil | `reg` | **`0x009c12c4`** |

Nike-L-Knoten in beiden extrahierten DTBs:

```dts
tztv_bootmode@B {
    compatible = "tztv-bootmode";
    reg = <0x0b>;
    communication-mode = "reg";
    ew-select = <0x9c12c4>;
};
```

Der `reg = <0x0b>`-Wert ist **nicht** die `ew-select`-MMIO-Adresse. Die Dekompilierung mittels `dtc` zeigte diverse strukturelle Warnungen, darunter `reg_format` zu diesem Knoten; sie verhindern nicht das Ablesen des gezeigten Property-Werts, sind aber keine Laufzeitvalidierung.

**Original-DTB-Provenienz (BUILD 117 STEP 8/9):**

- `/tmp/noverhost-build086-step11/dtb_offset_00000000.dtb` (früher als `nikel-2G` eingeordnet), SHA-256 `0189cc94fe8dd7d016462f22e9f8e965fe328cbc901066c8955f26130f86ab61`.
- `/tmp/noverhost-build086-step11/dtb_offset_00015000.dtb` (zweites Profil), SHA-256 `36e8e77898ce2e253ffd959f96d0fb1d27e3fcf58887325d668b190ac8dcd79e`.

**Einschränkung:** Welcher DTB auf dem tatsächlichen 50-Zoll-TV aktiv ist, wurde nicht live festgestellt. Die Adresse `0x009c12c4` ist für die beiden **archivierten Nike-L-DTBs** belegt, aber weder ein gemessener Registerwert noch ein bestätigter alternativer Bootpfad. `0x00800584` gehört zum **SDP1501**-Quell-DTS und darf nicht als Q60T-Adresse ausgegeben werden.

### BUILD 117 STEP 11 – Negatives Scanergebnis

Ein direkter Scan nach dem 32-Bit-Wert `0x009c12c4` in beiden Byteordnungen zeigte **keinen direkten Treffer** in:

`seret.bin`, `sign.bin`, `secos.bin`, `secos_drv.bin`, `ddr.init`, `uImage`.

Das beweist **nicht**, dass keine Komponente auf die Adresse zugreift. Der Zugriff könnte indirekt oder mit zusammengesetzten Konstanten erfolgen. Keine dieser Dateien wurde durch STEP 11 verändert.

### GPL-/U-Boot-Grenze

Der vorhandene `uImage`-Header ist U-Boot-kompatibel, aber **kein Nachweis für den tatsächlich eingesetzten Bootloader**. Im untersuchten Samsung-GPL-Archiv wurde kein vollständiger U-Boot-Quellbaum bestätigt. `trustzone-ree.zip` enthält REE-/TEE-Clientschnittstellen, ist jedoch kein Nachweis des ausführenden Secure-Boot-Verifiers.

## BUILD 118 – Indexsuche, keine neue Bootketten-Erkenntnis

STEP 1 hat **936 bereits vorhandene Forschungsdateien** durchsucht:

| Suchkategorie | Texttreffer |
|---|---:|
| Kernel-Einsprungadresse | 75 |
| Kernel-Ladevorgang | 9 |
| Bootkette / Bootloader | 80 (Suchlimit erreicht) |
| Secure Boot / Signaturprüfung | 18 |
| Firmwarekomponenten | 78 |

Originaler lokaler Bericht: `/tmp/build118-step1-report.txt`. Diese Zahlen sind **Textsuchtreffer, nicht unabhängige Hardwarebelege**. Es wurde kein neuer Loader, keine konkrete bestätigte Signaturprüfung und kein ausgeführter Kernel-Handoff identifiziert. STEP 2 hätte primär dieselben Treffer erneut angezeigt; der Erkenntnisgewinn ist daher gering.

## Gesamtstatus / Forschungsentscheidung

**Erreicht:** Original-Firmware und DTBs extrahiert; Linux-4.1.10-/Samsung-Gerätearchitektur analysiert; Linux 6.6.162 für ARM32 gebaut, QEMU startet bis eigenem `/init`; mehrere Samsung-Treiber/Module und Offline-/CI-Tests entwickelt.

**Nicht erreicht:** Root auf dem eigenen 50-Zoll-TV bestätigt; Bootloader entsperrt; Kernel-Signaturgrenze überwunden; abgesicherter Kernel-Handoff und physisches RAM-Layout live verifiziert; Linux 6.6 oder Android TV auf dem physischen Q60T gestartet.

**Konsequenz:** Die derzeitige Firmware- und Berichtsanalyse ist weitgehend ausgeschöpft. Weitere Scans ohne neue konkrete Hypothese vermeiden. Das Projekt kann mit dem vorhandenen Offline-Stand konserviert werden. Ein sinnvoller neuer Erkenntnispfad benötigt **unabhängige Live-Evidenz**, etwa lesende UART-Bootlogs an geeigneter Testhardware, einen verifizierten reversiblen Hardware-Diagnosezugang oder einen belastbaren externen Nachweis speziell für diese Bootkette. Vor physischem Experimentieren bleiben Recovery, Rückbaubarkeit, sichere Versorgung und RAM-Adressvalidierung zwingende Voraussetzungen. Keine Roh-Schreibzugriffe auf die eMMC des Alltagsgeräts.

**Wiederholungen vermeiden:** Nicht erneut `seret.bin`/DTBs/Bootdateien extrahieren, `CONFIG_KEXEC` blind prüfen, `0x80008000` ohne neuen Handoff-Beleg als sicher behandeln oder aus QEMU-/CI-Grün einen Hardwareboot ableiten. Keine weitere Build-Nummer nur zur Wiederholung bekannter Arbeit vergeben.

## GitHub-Nachweise

- [Projektstand BUILD 070–116, PR #34](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/34)
- [BUILD 110, PR #31](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/31)
- [BUILD 111, PR #32](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/32)
- [BUILD 112, PR #33](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/33)

Die PRs können auf gestapelten Feature-Branches liegen. Diese Dokumentation behauptet **keinen Merge der Implementierungen nach `main`**.

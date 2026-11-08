# Build 005 – Kernelreproduktion, Mali-Grafikpfad, Rückrollsicherheit

**Datum:** 08.11.2026  
**Auftrag:** Die drei Kernprobleme einer Samsung-Q60T-LineageOS-Portierung
aktiv weiterentwickeln: (1) Originalkernel reproduzieren,
(2) Mali-/Android-Grafik integrieren, (3) sicheren Test-Boot-Rückweg klären.

## Ergebnis in einem Satz

Es gibt jetzt eine **prüfbare Entwicklungs- und Diagnosestrecke für alle
drei Teilgebiete**, neue Referenzbelege und ausführbare Offline-Tests.
**Ein neu gebauter Kernel, lauffähiger Android-Grafiktreiber und der
Nachweis eines reversiblen Bootvorgangs fehlen weiterhin**, weil dafür
Originalquellen, passende Treiber und reale Geräte-/Bootloaderbeweise nötig
sind. Nichts wurde am TV verändert.

## 1. Kernel: erstmals GCC-Version und Buildzeit bestätigt

Der exakt verifizierte Kernel `uImage` der Samsung-Firmware
`T-NKLDEUC-2743.0` (55-Zoll-Referenz `GQ55Q60TGUXZG`) enthält:

| Originalkernel-Eigenschaft | Befund |
| --- | --- |
| Linux | `4.1.10`, ARM32 |
| Compiler | **Tizen/Linaro GCC 6.2.1** (`20161213`) |
| Hersteller-Buildstring | `abuild@B4404DRG` |
| Buildzeit | `Thu Jul 2 08:47:01 UTC 2026` |
| IKCONFIG in Image | **Nicht vorhanden** |
| U-Boot-Header + Payload-CRC | In Build 002 validiert |

Die neuen Metadaten stehen in `reports/kernel_build005.json`.

Mit `q60t_kernel_build.py` kann ein lokal vorliegender Samsung-
Linux-Quellbaum auf Version `4.1.10`, ARM-Kconfig und passende
Cross-Compiler-Version untersucht werden. Das Werkzeug gibt
reproduzierbar parametrisierte `make`-Kommandos für einen separaten
Buildordner aus, **führt sie aber ohne verifizierte Originalquellen nicht
aus**. In der aktuellen Umgebung liegt kein zum Paket `2743.0`
bestätigtes Samsung-GPL-Quellenarchiv und kein GCC-6.2.1-ARM-Cross-
Compiler vor. Ein selbstgebautes `uImage` zu behaupten wäre falsch.

Samsung hat laut ursprünglicher Q60T-Sicherheitsforschung GPL-Quellen
inklusive Kernel/UEP veröffentlicht
([Synacktiv GreHack 2021](https://www.synacktiv.com/sites/default/files/2021-11/GreHack2021_Rooting_Samsung_Q60T_Smart_TV.pdf)),
aber die konkrete Source-Revision muss noch aus dem
[Samsung OSSRC](https://opensource.samsung.com/uploadSearch?searchValue=Q60T)
bezogen und gegen den Referenzkernel geprüft werden.

**Status 1: teilweise vorbereitet – Build selbst blockiert.**

## 2. Mali-GPU: wichtige Modellunsicherheit + erste ABI-Werkzeuge

Die Referenz-DTBs nennen `/soc/sdpgpu@00500000` mit der generischen
Kompatibilitätskennung `arm,mali-midgard`. Das ist **keine zuverlässige
Identifizierung der tatsächlichen GPU-Serie**. Eine separate,
gerätegestützte [Q60T-Firmwareuntersuchung](https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md)
nennt eine **Mali-G51/Bifrost r11p0**. Deren exakte Hardware-/Treiber-
Übereinstimmung haben wir hier nicht selbst anhand eines extrahierten
Mali-Kernelmoduls nachgeprüft.

`q60t_graphics.py` analysiert künftig lokale `libmali.so`- und
`.ko`-Kandidaten **ohne Ausführung**. Es prüft ELF-Header, 32/64-Bit-
Architektur, Hardwareziel, Abhängigkeiten und SHA-256 und stellt diese
Information dem nachgewiesenen ARM32-Referenzkernel gegenüber.
Der Bericht `reports/graphics_build005.json` dokumentiert die GPU-
und Samsung-Display-Knoten beider DTBs und die fehlenden Teile des
Android-Stacks:

- Kbase- bzw. Panfrost-/DRM-Kerneltreiber mit Samsung-Anpassung;
- passende Mali-EGL-/GLES-Userspace-ABI;
- Android-Gralloc-Allocator/Mapper und Buffer-Fences;
- Hardware Composer (für Android 13+ vorzugsweise AIDL Composer3);
- vom Samsung-Panel akzeptierte Modesetting-/Scanout-Pipeline.

Ein ELF32-Match wäre ein **erster notwendiger**, aber kein hinreichender
Kompatibilitätsnachweis. Proprietäre Samsung-/Arm-Binärdateien wurden
weder ins Projekt übernommen noch als Android-HAL ausgegeben.

Google erläutert den [Hardware Composer](https://source.android.com/docs/core/graphics/implement-hwc)
und den [AIDL-Composer3](https://source.android.com/docs/core/graphics/aidl-hwc).

**Status 2: Analysekette vorhanden – Grafiktreiber/HAL noch nicht portiert.**

## 3. Sicherer Boot: Stock-Komponenten verifiziert, Rollback nicht

`q60t_boot_safety.py` hat aus der bereits lokal entschlüsselten
Referenzfirmware folgende statische Komponenten inventarisiert:
`uImage`, `dtb.bin`, `sign.bin`, `seret.bin`, `secos.bin`,
`secos_drv.bin`. Die bekannten Kernel-/DTB-SHA-256 entsprechen den
Veröffentlichungsreferenzen, die U-Boot-CRC-Prüfung ist erfolgreich.

**Das ist keine kryptografische Signaturprüfung.** `sign.bin` und
Trusted-OS-Komponenten belegen allein weder, dass Samsung einen fremden
Kernel akzeptiert, noch, dass ein misslungener Flash rückgängig gemacht
werden kann. Eine modifizierte Firmware darf nicht als authentisch
vorausgesetzt werden.

Der neue Bericht `reports/boot_safety_build005.json` ergibt:

| Prüfung | Resultat |
| --- | --- |
| Referenz-Komponenten-Hashes | `REFERENCE_PRESENT` |
| U-Boot-Header und CRC | Gültig |
| Samsung-Signatur/Trust Chain | **Nicht verifiziert** |
| Nichtpersistenter Alternativstart | **Nicht bewiesen** |
| Recovery inkl. Power-Loss/Watchdog | **Nicht bewiesen** |
| Acht Boot-/Rollback-Gates | **8 offen** |
| Freigabe für TV-Writes/Flash | **Nein** |

Die acht Nachweise sind in `porting/boot-evidence.json` dokumentiert.
Das Tool meldet bewusst `REFUSED_BEFORE_BOOT`: eine lokale Prüfung
**simuliert kein echtes Recovery**. Ein Bootversuch am einzigen
50-Zoll-Fernseher könnte ohne Rückweg einen dauerhaften Defekt bedeuten.

**Status 3: Offline-Sicherheitsprüfung implementiert – reversibler
Start nicht nachgewiesen.**

## Validierung

32 synthetische Tests bestanden. Neue Tests decken ab:

- synthetische Kernel-Makefiles `4.1.10` vs. falsche Version;
- ARM-Basis-Konfiguration und die unverändert offene Source-Provenienz;
- Extraktion von GCC-Version und Buildzeit aus U-Boot-Images;
- synthetische 32-/64-Bit-ELF-Binaries und ungültige ELF-Sections;
- Hash-gebundenen Grafikreport ohne falsche HAL-Behauptung;
- Signaturvorhandensein vs. tatsächliche Authentizitätsprüfung;
- Fail-closed-Rollback-Gates auch bei hypothetischer Vollfreigabe.

Die drei neuen Statusabfragen liefern erwartungsgemäß **Exitcode 1**
(`BLOCKED`), keinen unerwarteten Toolfehler:

```bash
python3 q60t_kernel_build.py
python3 q60t_graphics.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json
python3 q60t_boot_safety.py --evidence porting/boot-evidence.json
python3 -m unittest discover -s tests -v
```

## Was für die tatsächliche Umsetzung fehlt

1. Samsung OSSRC-Sourcepaket mit **nachgewiesener Versionsidentität**
   zur aktuellen Firmware – erst danach kann Kernelkompilierung und
   Binärvergleich beginnen.
2. Gesetzeskonform lokal verfügbare **passende Mali-/Display-Treiber**
   bzw. offener Ersatz, um Gralloc/Composer tatsächlich zu implementieren.
3. **Konkrete Bootloader-/Recovery-Daten** von einem gleichartigen
   Gerät und ein demonstrierter flüchtiger Bootweg; ohne dies kein
   persistenter Bootversuch.
4. Vollständige Modellkennung und RAM-Variante des **50-Zoll-Zielgeräts**;
   die bisherigen Hashes stammen von einer 55-Zoll-Referenz.

Das Projekt kann jetzt methodisch weitermachen, ohne so zu tun, als sei
bereits eine funktionierende ROM vorhanden.

# Build 003 – Samsung Q60T / Nike-L: Hardware- und Portierungsbericht

**Stand:** 08.11.2026  
**Ergebnis:** Offline-Analyse mit zwei identifizierten Hardwareprofilen,
Kernel-Sicherheitsindikatoren und VDFS-Dateireferenzen.
**Kein bootfähiges LineageOS-Image; keine Änderung am Fernseher.**

## 1. Untersuchte Ausgangsbasis

Das geprüfte Originalpaket ist weiterhin die Samsung-Firmware
`T-NKLDEUC-2743.0`, die für das **55-Zoll-Referenzgerät GQ55Q60TGUXZG**
veröffentlicht wurde. Die ZIP-SHA-256
`cb717ed98daf9580eb5b84bccbad5adac82f75dd021ed028f1ee1bb6c4abde32`
stimmt exakt mit dem unabhängigen Forschungsnachweis überein
([tiz0wn](https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md)).
Die vom Nutzer genannte Firmwareversion seines **50-Zoll-Q60T** lautet
ebenfalls `2743.0`, aber der genaue Modellcode, die verwendete
Firmwarefamilie und das tatsächlich ausgewählte RAM-Profil sind damit
**nicht** unabhängig verifiziert.

Build 002 hat neun Firmwareteile entschlüsselt. Build 003 analysiert
vorhandene lokale Dateien **ohne TV-Zugriff, ohne Signaturänderung**.

## 2. Die wichtigste neue Entdeckung: zwei RAM-/Boardprofile

Das 1,56-MB-Paket `dtb.bin` enthält mindestens zwei gültige
*Flattened Device Trees* (FDT). Die neue Strukturprüfung zählt Knoten und
Properties selbstständig und vergleicht die Trees, ohne gefährliche
Rohwerte (z. B. MAC-Adressen, Seriendaten oder Schlüssel) zu exportieren.

| Eigenschaft | Profil A | Profil B |
| --- | --- | --- |
| Offset in `dtb.bin` | `0` Bytes | `86.016` Bytes |
| Firmware-Profiletikett | `nikel-2G` | `nikel-1.5G` |
| Modellkennung | `Samsung DTV based on Nike-L SoC` | gleich |
| Knoten | **365** | **367** |
| Properties | **1.739** | **1.760** |
| CPU-Knoten | 4 × `arm,cortex-a57`, `arm,armv8` | 4 × dito |
| Linux-Root in Bootargumenten | `/dev/mmcblk0p18`, VDFS | gleich |

Die **2 GB** und **1,5 GB** stammen aus den *statischen
`dtsversion`-Bezeichnern* der Firmware – das ist **keine echte RAM-Messung**
am Fernseher. Die Größe der tatsächlichen physischen Speicherausstattung
des Nutzergeräts ist noch unbekannt.

Der strukturierte Vergleich der ersten beiden Trees ergab:

- **130** veränderte Property-Einträge an gemeinsamen Knoten.
- **2** Knoten nur im ersten Profil (`/mem_prevent/dp`, `/mem_prevent/rot`).
- **4** Knoten nur im zweiten, darunter zwei zusätzliche
  `/reserved-memory/cma@*`-Knoten.
- Wesentliche Unterschiede: `reg`, `memory-region`, Phandles,
  Speicherreservierungen, `sdp_mmap` und vereinzelte HDMI-Einstellungen.

**Folgerung:** Ein einzelner blind eingesetzter Device Tree ist für diese
Samsung-Firmware schon auf dem Papier nicht belastbar. Die RAM- und
Speicherreservierungs-Variante muss vor einem Bootversuch zweifelsfrei
bestimmt sein. Die vollen, **wertbereinigten** Daten stehen in
`reports/hardware_2743.0.json`.

## 3. CPU, Kernel und Sicherheitsindikatoren

- Vier **Cortex-A57**-CPU-Knoten (`armv8`-fähig) sind in beiden DTBs deklariert.
- Das ausgelieferte Samsung-`uImage` selbst ist ein **32-Bit-ARM**-Image
  für **Linux 4.1.10**. ARMv8-fähige CPU bedeutet nicht automatisch einen
  eingesetzten 64-Bit-Kernel.
- Die U-Boot-Kernelheader- und Payload-CRC32 waren in Build 002 korrekt.
- Ein eingebetteter `IKCFG_ST`-Konfigurationsblock wurde im realen
  Kernelpayload **nicht gefunden**. Das erlaubt **keine** Aussage darüber,
  welche `CONFIG_*`-Schalter gesetzt sind.
- Im Kernel finden sich unter anderem die Strings
  `SfdUepVerifyExecutableBinary`, `SfdUepVerifyFileSignature`,
  `SfdUepVerifyDynamicLibrary`, `security.SMACK64EXEC` und
  `kernel/seccomp.c`. Das sind **direkt bestätigte Binary-Strings**, aber
  **kein Laufzeitnachweis**, wann und für welche Images UEP greift.

Für moderne Android-Versionen sind ein stark angepasster neuer Kernel,
Android-Binder- und Security-Integration sowie ein lauffähiger Grafikstack
erforderlich. Google veröffentlicht eine
[Android-Kernelkompatibilitätsmatrix](https://source.android.com/docs/core/architecture/kernel/android-common).
Die Samsung-Version 4.1.10 ist deutlich älter als die üblichen
Android-Common-Kernel-Zweige aktueller Releases. Es ist kein formaler Beweis
für Unmöglichkeit, aber ein großer Portierungsaufwand.

## 4. GPU, Display, Audio und Video – was wir jetzt wissen

Die DTBs deklarieren unter anderem:

| Gruppe | Evidenz aus der Firmware | Portierungsaufgabe |
| --- | --- | --- |
| Grafik | `arm,mali-midgard`, `samsung,sdp-drm` | Passender Kernel-GPU-Treiber, GLES/EGL und Android Gralloc/Composer |
| Panel/HDMI | `samsung,sdp-hdmi`, `samsung,sdp1202-panel`, TCON/FRC | Display-Initialisierung, VSync, Videomodi |
| Video | `samsung,sdp-mfc` | Android MediaCodec/Codec2 oder andere HAL-Anbindung |
| Audio | Samsung-spezifische Audioknoten | Audio-HAL, Ausgänge, Lautstärkeregelung |
| TV-Funktionen | Samsung-Micom, Tuner-, HDMI- und Signalpfade | IR/BT-Fernbedienung, CEC, Eingänge, Tuner |

Eine Android-Oberfläche lässt sich erst anzeigen, wenn der
*Hardware-Composer- bzw. Displayweg* funktioniert. Das Android
[Hardware-Composer-Interface](https://source.android.com/docs/core/graphics/implement-hwc)
ist eine andere Softwareschnittstelle als Tizens eigene Grafikdienste.
Ab Android 13 existiert ein
[AIDL-Hardware-Composer-3-Interface](https://source.android.com/docs/core/graphics/aidl-hwc).

**Wichtig:** Ein proprietäres Tizen-`libmali.so` kann nicht einfach als
Android-HAL vorausgesetzt oder ungeprüft umverteilt werden.

## 5. VDFS-Systemabbild: 320 untersuchte Dateipfad-Referenzen

`platform.img` beginnt mit `VDFS2007`, ist **1.328.484.368 Bytes** groß
und hat SHA-256
`dc7cb50fc13966abb678f642cc0c9fd884894c0152b51ffb3fb8e602152566d4`.

Ein neues, nur lesendes Streamingwerkzeug hat in den Rohbytes **320
unterschiedliche plausible Pfadreferenzen** sowie Gerätenamen gefunden,
zum Beispiel:

- `/lib/modules/mali.ko`
- `/lib/modules/sdp_mac.ko`
- `/lib/modules/linux/kernel/soc/sdp-drm.ko` (als Beispiel einer
  Samsung-DRM-Treiberfamilie; die genaue Pfadvariante variiert)
- `/usr/lib/driver/libmali.so`
- `/dev/mali0`, `/dev/dri/card0` und `/dev/dri/card1`
- weitere Pfadstrings für `sdp_hdmi.ko`, `sdp_frc.ko`, `tztv_tuner.ko`,
  `tztv-micom.ko`, USB, ALSA und Netzwerkmodule.

**Evidenzklasse:** Das sind **ASCII-Strings im unverarbeiteten Dateisystem**,
keine entschlüsselten und überprüften Einzeldateien. Sie können in Skripten,
Konfigurationskommentaren oder veralteten Installationsanweisungen stehen.
So gibt es sowohl Pfade unter `3.10.30` als auch unter `4.1.10`, obwohl der
ermittelte Firmwarekernel 4.1.10 ist. Sie dürfen **nicht** als Nachweis
geladener Module oder Android-kompatibler Bibliotheken interpretiert werden.

Der vorhandene historische VDFS-Unpacker konnte aus einer eigenen
lokalen Kopie nach Anpassungen zunächst Verzeichnisstrukturen lesen,
stürzte aber mit Exitcode **139** ab, bevor er verifizierte reguläre
Dateiinhalte ausgeben konnte. Der alternative neuere Quellstand war im
aktuellen Buildkontext nicht ohne weitere Portierung kompilierbar. Wir
beanspruchen **keine** erfolgreiche Voll-Extraktion.
Andere Forscher beschreiben eine vollständig gepatchte Extraktion
([tiz0wn, F10–F12](https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md));
deren Resultat ist **nicht** automatisch durch unsere Analyse reproduziert.

## 6. Offene Hürden vor einer echten LineageOS-ROM

| Gate | Stand | Warum es zwingend ist |
| --- | --- | --- |
| Exakte 50-Zoll-Modellkennung | Offen | Zielvariante und Firmwarefamilie müssen stimmen |
| RAM-/DTB-Profil auf realem Gerät | Offen | 1,5- und 2-GB-Tree sind verschieden |
| GPL-Kernelquellcode exakt passend | Zugangsweg identifiziert | Konfiguration, Boardtreiber und Build reproduzieren |
| Signierter Bootweg / Alternativstart | **Nicht nachgewiesen** | Sonst Gefahr eines dauerhaft nicht startenden Fernsehers |
| Eigene Kernel- und Android-Treiber | **Nicht vorhanden** | Tizen-Modulpfade sind kein Android-HAL |
| Display, MediaCodec, Audio, Fernbedienung | **Nicht portiert** | Ein TV-Boot alleine ist keine nutzbare Android-TV-Version |
| Recovery/Rollback vom Testboot | **Nicht nachgewiesen** | Zwingend vor Hardwareexperiment |

Es gibt daher **kein verantwortbar flashbares Image**. Root unter Tizen
ist nicht gleichbedeutend mit einer Freigabe des Secure-Boot-Pfads.
Auch nach einem denkbaren Android-Start wäre die Funktion von
DRM-Streaming-Apps (z. B. Apple TV/Prime Video) wegen Hardware-DRM,
Gerätezertifizierung und App-Support **nicht garantiert**.

## 7. Konkreter Entwicklungsweg ab Build 003

1. **Board exakt zuordnen:** vollständigen 50-Zoll-Modellcode und
   möglichst read-only Hardwareprofil aus sicherer Quelle verifizieren.
2. **GPL-Quellcode sichern:** Samsung Open Source Release Center:
   <https://opensource.samsung.com/uploadSearch?searchValue=Q60T>.
   Synacktivs Q60T-Studie bestätigt die Veröffentlichung von
   Kernelquellcode und diversen Treibern, einschließlich Samsung-UEP
   ([GreHack 2021, Folie 28](https://www.synacktiv.com/sites/default/files/2021-11/GreHack2021_Rooting_Samsung_Q60T_Smart_TV.pdf)).
   Ein vollständiger, konkret zur Version 2743.0 passender Source-Tarball
   konnte hier **noch nicht heruntergeladen und kompiliert** werden.
3. **Display-Bring-up erforschen:** sdp-drm/Mali und Android Gralloc/
   Composer-Schnittstellen kartieren, ohne Vendorblobs weiterzuverteilen.
4. **Reversiblen Bootpfad nachweisen:** ohne Sicherung und belastbaren
   Recovery-Prozess keine signierten Bootbereiche verändern.
5. **Erst danach** ein minimales eigenes Linux-Startimage im Testmodus;
   darauf aufbauend Android-/LineageOS-Device-Tree, HALs, SELinux und
   schließlich Android-TV-Launcher/-Apps.

## 8. Neue Analysebefehle in diesem Paket

```bash
python3 q60t_lab.py hardware-report /pfad/zu/dtb.bin
python3 q60t_lab.py kernel-report /pfad/zu/uImage
python3 q60t_lab.py rootfs-strings /pfad/zu/platform.img
python3 -m unittest discover -s tests -v
```

Die Ausgaben sind **lokale JSON-Berichte**; keine Befehle wenden sich
an ein Gerät. Beispielberichte aus der echten Referenzfirmware liegen
unter `reports/`, **ohne** Images oder Binärkomponenten.
Alle **14 synthetischen Tests bestanden**.

## Quellen und Begrenzung

- [Samsung, Q60T Support](https://www.samsung.com/de/support/model/QE50Q60TAUXZG/)
- [Samsung, Open Source Release Center](https://opensource.samsung.com/uploadSearch?searchValue=Q60T)
- [Synacktiv, Q60T Firmwareanalyse und Decryptor](https://github.com/synacktiv/samsung-q60t-exploit)
- [Synacktiv, Präsentation zur Q60T-Kernelquellcode-Freigabe](https://www.synacktiv.com/sites/default/files/2021-11/GreHack2021_Rooting_Samsung_Q60T_Smart_TV.pdf)
- [tiz0wn, verifizierte Firmware 2743.0 und VDFS-Forschung](https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md)
- [HinTak/vdfs-tools, quelloffenes VDFS-Werkzeug](https://github.com/HinTak/vdfs-tools)
- [Google, Android Common Kernels](https://source.android.com/docs/core/architecture/kernel/android-common)
- [Google, Android Hardware Composer](https://source.android.com/docs/core/graphics/implement-hwc)

Es wurde ausschließlich mit einer offiziell bezogenen Firmwarekopie
offline gearbeitet. Es gab **keine Verbindung, keine Änderungen und keinen
Exploit** gegen den Fernseher des Nutzers. Proprietäre Firmwarebestandteile,
Ghidra-/REA-Dumps und fremder Quellcode sind diesem Paket nicht beigelegt.

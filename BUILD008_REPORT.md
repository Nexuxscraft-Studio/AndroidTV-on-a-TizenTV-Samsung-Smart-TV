# Build 008 – Recherche nach Nike-L-Quellen, GCC und Mali r11p0

Stand: **08.11.2026**. Zielgerät: Samsung **GQ50Q60TGUXZG**,
Firmware **T-NKLDEUC 2743.0** (Nutzerangabe und bestehende Referenzanalyse).

> **Keine installierbare ROM, kein reproduzierter Samsung-Kernel.**
> Die folgenden Fundstellen belegen Original-/Referenzquellen, **nicht** deren
> Kompatibilität mit exakt diesem TV. Keine fremden Dateien wurden als
> Samsung-Quellbaum ausgegeben; der TV wurde nicht kontaktiert.

## Verifizierte Fundstellen

| Bedarf | Fundort / Artefakt | Recherche-Ergebnis | Grenze |
| --- | --- | --- | --- |
| Samsung-GPL-Kernel | [Samsung OSSRC, Q60T-Suche](https://opensource.samsung.com/uploadSearch?searchValue=Q60T) | Synacktiv dokumentierte 2021 dort ausdrücklich Q60T-Kernelquellen und Samsung-UEP-Patches | Paketkennung, verifizierter Download, exakte Version 2743.0 und Defconfig **nicht gefunden** |
| GCC 6.2.1 **Quellcode** | [Offizieller Tizen-CDN](https://cdn.download.tizen.org/sdk/tizenstudio/tizen_studio_source/source/gcc-6.2.1.tar.gz) | `gcc-6.2.1.tar.gz`, 122.609.288 Bytes laut Tizen-Verzeichnisindex | Keine fertige ARM-Toolchain und keine Samsung-Firmwareidentität |
| GCC 6.2.1 **Cross-Compiler-Kandidat** | [Linaro ARM32, 2016.11](https://releases.linaro.org/components/toolchain/binaries/6.2-2016.11/arm-linux-gnueabi/gcc-linaro-6.2.1-2016.11-x86_64_arm-linux-gnueabi.tar.xz) | Genau dieser ARM32-Cross-Compiler wurde in einem [Samsung-Research-UK-Projekt](https://github.com/SamsungResearchUK-IoT-Meetup/samsung-tf-lite/wiki/3.-Build-%26%26-Run) für ein Tizen/Linaro-6.2.1-Board verwendet | 2016.11 nicht gleich dem nachgewiesenen Samsung-Kernel-Banner `20161213`; kein bitgenauer Match |
| Mali-Bifrost r11p0 **Kerneltreiber** | [Arm Bifrost GPL-Downloads](https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture), Paket `BX301A01B-SW-99002-r11p0-01rel0.tgz` | Arm listet Linux-Ausgabe vom 09.03.2018 mit MD5 `b5dd72297b50e700278adc372fafea94` | Nutzungsbedingungen beachten; kein vollständiger GPU-Userspace, kein Samsung-Display-HAL |

### Dokumentation und unabhängige Referenzen

- [Synacktiv – Rooting Samsung Q60T Smart TV, GreHack 2021](https://www.synacktiv.com/sites/default/files/2021-11/GreHack2021_Rooting_Samsung_Q60T_Smart_TV.pdf), Folie „Downloading Open Source Components“: Historische Q60T-GPL-Verfügbarkeit, nicht die aktuelle Download-ID.
- [Samsung Tizen – Kernel-Portierung](https://github.com/Samsung/tizen-docs/blob/master/docs/platform/porting/kernel.md): Herstellerdokumentation zur ARM-`defconfig` und zum Kernelbau.
- [Samsung Research UK – Toolchain-Anleitung](https://github.com/SamsungResearchUK-IoT-Meetup/samsung-tf-lite/wiki/3.-Build-%26%26-Run): Separates Board/Projekt, keine Behauptung über GQ50Q60TGUXZG.
- [Arm Bifrost – Kernel-GPL-Quellen und DDK-Einschränkung](https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture): User-Space für GLES erfordert zusätzlich eine passende Version des Arm-DDK.
- [Unabhängige Q60T-/2743.0-Untersuchung](https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md): Betrifft das **55-Zoll-Modell GQ55Q60TGUXZG**; Indiz für Mali-G51/Bifrost r11p0, kein Ersatz für unsere 50-Zoll-Live-Hardwareprüfung.

## Was bei der breiten Suche **nicht** verfügbar war

1. Kein frei nachprüfbarer Direktdownload mit Hersteller-Release-ID,
   unabhängig publiziertem SHA-256 und vollständigem **Nike-L**-
   Linux-4.1.10-Quellbaum für `T-NKLDEUC 2743.0`.
2. Keine zur **exakten Firmware** zugeordnete
   `arch/arm/configs/*defconfig` oder originale `.config`.
3. Kein zweifelsfrei identischer, vollständig dokumentierter
   **Tizen/Linaro-GCC-6.2.1-(20161213)-Cross-Compiler** inklusive Patches,
   Binärhash und Buildflags.
4. Kein zusammenhängender, lizenzrechtlich nutzbarer Android-TV-Stack aus
   `mali.ko`, `libmali.so`, Gralloc/Mapper, Composer, Media/DRM und
   Samsung-Panel-/Scanout-Anbindung.
5. Keine nachgewiesene alternative Bootmethode mit unabhängig geprüftem
   **Rollback/Recovery** für diesen TV.

**Wichtig:** Das öffentliche Repository
[`CE1CECL/linux-18_KantS`](https://github.com/CE1CECL/linux-18_KantS)
enthält zwar Linux 4.1.10 und Samsung-Code, gehört aber zu einer
**anderen TV-Boardgeneration (KantS, 2018)**. Es ist für die
Nike-L-Portierung **kein** ersetzender Originalkernel.

## Nächste sinnvolle Beschaffung

1. Samsung OSSRC öffnen, `Q60T`, alternativ `GQ50Q60TGUXZG` und
   `T-NKLDEUC` suchen. Bei angezeigten Quellen **Paketname,
   Versionskennzeichen, Lizenztext, Hersteller-ID und bereitgestellte
   Checksumme** notieren. Bei abweichenden Firmwareständen die Zuordnung
   ausdrücklich beim Open-Source-Support erfragen. Der Zugang zu diesem
   konkreten Paket war in der Rechercheumgebung nicht erfolgreich.
2. Offizielles Samsung-Archiv **lokal** speichern, dann mit
   `python3 q60t_source_provenance.py --archive /pfad/zum/archiv`
   statisch inventarisieren (ohne automatische Extraktion). Vergleich
   mit einer unabhängigen Hersteller-Checksumme nur, falls vorhanden.
3. ARM32-GCC-Kandidaten in einer isolierten Linux-Buildumgebung testen:
   `arm-linux-gnueabi-gcc --version` sowie
   `arm-linux-gnueabi-gcc -dumpmachine`. Ein Versions-/Brandingmatch
   ersetzt weiterhin **keinen** Hersteller-Provenienznachweis.
4. Den Arm-Treiber r11p0 über die offizielle Downloadseite und unter
   Einhaltung ihrer Bedingungen beziehen. Die dort angegebene MD5
   dient nur als Integritäts-Indiz nach dem Herunterladen, **nicht** als
   sicherer Nachweis für Samsung-KABI-Kompatibilität.
5. Erst Samsung-Quellbaum und Defconfig auf Hostseite kontrollieren,
   dann einen reproduzierbaren **Offline-Kernel-Build** versuchen;
   Android-Display und Recovery werden danach separat untersucht.

## Änderung am Prüfwerkzeug

`q60t_kernel_build.py` erfasst nun zusätzlich den ARM32-Target-Triplet und
unterscheidet drei Aussagen strikt:

- `toolchain_version_matches_reference`: Compiler meldet GCC 6.2.1.
- `toolchain_target_is_arm32`: Compiler meldet ein ARM32-Target.
- `matching_tizen_linaro_toolchain`: **bleibt gesperrt**, auch bei
  passendem Banner, solange die genaue Samsung-Toolchain-Herkunft nicht
  unabhängig überprüft wurde.

Alle Kandidaten stehen auch maschinenlesbar in
[`porting/source-candidates-build008.json`](porting/source-candidates-build008.json).
Kein Tool lädt oder flasht automatisch etwas herunter. Keine
Firmware, fremden GPL-Archive oder proprietären Binärdateien werden
dem Projekt hinzugefügt.

**Status nach Build 008:** Recherche wesentlich konkretisiert,
**Kernel-Build blockiert**, **Mali-/Android-HAL blockiert**,
**Boot/Recovery blockiert**.

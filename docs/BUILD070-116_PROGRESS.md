# Samsung Q60T Android TV – Projektstand BUILD 070–116

**Stand:** 15. November 2026  
**Zielgerät:** Samsung Q60T 50 Zoll, `GQ50Q60TGUXZG`, Samsung Nike-L/SDP1804, Firmware `T-NKLDEUC-2743.0` (Tizen 5.5), ARMv7-Userspace; Hardware-Device-Tree mit 4× Cortex-A57 (ARMv8-Kerne).  
**Portierungsziel:** eigener Linux-6.6.162-Kernel mit Samsung-Treibern und später Android TV.  
**WICHTIG:** Ein eigener Kernel wurde **noch nicht auf dem echten 50-Zoll-TV gebootet**. „QEMU PASS“, „kompiliert“, „statische Analyse“ und „TV-Root“ bezeichnen unterschiedliche Nachweisstufen.

## 1. Executive Summary

Das Projekt hat sich von einer allgemeinen Android-TV-Portierung zu einem umfangreichen Samsung-Hardware-, Grafik- und Bootketten-Forensiklabor entwickelt. Auf dem Debian-/Proxmox-Testsystem liegen entschlüsselte Firmware-Komponenten, analysierte Device Trees, Kernel-/Treiber-Prototypen, QEMU-Bootprüfungen, Modul-Builds sowie Bootloader-/RAM-Evidenz vor. Der Samsung-Tizen-Bootloader wurde nicht entsperrt; ein nicht-destruktiver Start von Linux 6.6 auf dem realen Gerät ist weiterhin **nicht nachgewiesen**. Auch ein Root-Zugang auf dem eigenen **50-Zoll-Gerät** ist noch nicht bestätigt.

### Definition der Evidenz

- **Firmware/Offline:** Befund aus entpacktem Image, DTB, Binäranalyse oder Quellcode; kein Laufzeittest auf dem TV.
- **Build/CI:** Code kompiliert, Test oder GitHub Actions besteht; sagt nichts über die konkrete TV-Hardware aus.
- **QEMU:** virtueller ARM32-Gast startet; kein Ersatz für Samsung-SoC-, Display-, RAM- oder Bootloader-Nachweis.
- **Live-TV:** unmittelbar auf `GQ50Q60TGUXZG` gemessen. Bisher vor allem SDB-Verbindungs-/Capability-Daten.
- **Extern berichtet:** auf anderem Fernseher/anderer Bildschirmgröße dokumentiert; keine automatische Übertragbarkeit.

## 2. Zeitliche Entwicklung und Ergebnisse

Die folgenden BUILD-Gruppen sind aus den bisherigen Projektgesprächen und benannten GitHub-Branches rekonstruiert. Nicht jedes einzelne Zwischenergebnis ist hier durch ein dauerhaftes, eigenes Log belegt; **die Tabelle behauptet daher nicht, alle BUILDs seien erfolgreich abgeschlossen**.

| BUILD | Arbeitsgebiet / Ergebnis | Evidenz / Einschränkung |
|---|---|---|
| **070** | SDB-/Grafik-Evidenzsammlung `collect_tizen_graphics_evidence.sh`; Vorprüfung, zunächst ohne TV-Identity, später SDB-Gerätekennung erfolgreich. | Live-SDB-Verbindung, keine Shell-/Root-Freigabe |
| **071** | Bootloader- und Samsung-Bootpfad-Untersuchung für sicheren Alternativstart. | Forschung; kein Bootloader-Unlock |
| **072** | RAM-Boot-Preflight: 7/7 Offline-Prüfungen bestanden; Referenz-Konfiguration mit deaktiviertem `CONFIG_KEXEC`. | **Offline PASS**, kein RAM-Start auf TV |
| **073** | Tizen-Diagnose-App / Evidenzsammlung vorbereitet (PR #16); Signierung/Installation ausstehend. | Entwurf, kein bestätigter Live-Diagnose-Erfolg |
| **074–075** | REA-/CI- und Raw-ARM32-Forensik; Untersuchung extrahierter Boot-/GPU-Binaries. | Statische Analyse; rohe ARM32-Binaries benötigen passendes Format und Basisadresse |
| **076–077** | `seret.bin`, Bootwrapper, Partitionen, Kernel-Handoff und uImage-Kette untersucht. | Firmwareanalyse, keine Änderungen am Flash |
| **078–079** | Firmware-Authentifizierung und SWU-Verifikation als sichere statische Checks behandelt. | Keine nachgewiesene Signaturumgehung |
| **080–085** | SDP1804 Clock-Provider, PLLs, Clock-Gates, Alias-/Divisor-Tabellen; CPU/GPU/DDR-Clock-Kontext. | Quellcode-/Registeranalyse |
| **086–089** | Display-/Framebuffer-Hardware, Testpattern-/Framebuffer-Planung, Speicher-/Plane-Verhältnisse. | Hardwaremodell/Prototypen; kein Bild von Linux 6.6 auf echtem TV |
| **090–095** | DRM/KMS-Integration, Display-Clock/Reset, Full-Driver-Integration und Safe-Boot-Readiness. | Build-/Audit-Arbeit, kein bestätigter Real-TV-Framebuffer |
| **096** | ARM32-QEMU-Test bootet bis eigenem `/init` (**PASS**). | Erfolgreicher virtueller Kernel-/initramfs-Test, kein Hardware-Boot |
| **097** | Neun reproduzierbare `.ko`-Modulartefakte erzeugt. | Reproduzierbarer Build, nicht auf Samsung geladen |
| **098** | Nicht-destruktive RAM-Boot-Readiness; uImage `load/entry 0x80008000` mit dokumentierten RAM-Bänken verglichen, Adresskonflikt/klärungsbedürftige Interpretation. | **Kritischer Blocker**; Ladeadresse nicht als sicher bestätigt |
| **099–103** | `seret.bin`, uImage, DTB, zImage und Handoff weiter untersucht; u. a. `bootargs`-Fund bei `0x24FE`, `booti`-Fund bei `0xB72E`, zImage-Offset `0x8000`. | Statische Fundstellen sind keine belegte ausführbare Bootkette |
| **104** | Teil der fortgesetzten Boot-/Treiber-Untersuchung; separater exakt verifizierter Abschlussnachweis fehlt in dieser Übersicht. | **Nicht als abgeschlossen deklarieren** |
| **105** | Micom-/Peripherie-Integrationszweig (u. a. IRB/IRS-Vorarbeiten). | Branch `feature/build105-micom`; genaue Live-Funktion nicht nachgewiesen |
| **106** | Treiber-/QEMU-Integration. | Branch `feature/build106-driver-qemu`; QEMU ≠ TV |
| **107** | Vorbereitung erster Displaytests. | Branch `feature/build107-first-display-test`; kein nachgewiesenes TV-Bild |
| **108–109** | Im Projektgespräch behandelt; hier liegen keine belastbaren Einzelresultate vor, die eine erfolgreiche Implementierung oder Live-Ausführung belegen. | **Offene Evidenzlücke – vorhandene Debian-Logs/PRs bei Bedarf zuordnen** |
| **110** | Branch für ersten Hardware-Boot-Versuch und entsprechende Vorbereitung. | Branchname `feature/build110-first-hardware-boot` ist **kein Beweis** eines Hardware-Boots |
| **111** | ARM32-Offline-Build/CI grün; reproduzierbare Artefakte, UART-/Bootdiagnosevorbereitung; Draft-PR #32 auf PR #31, Commit `56911d49` im Projektgespräch genannt. | Build/CI; nicht auf dem echten TV gebootet |
| **112** | `seret`-Kernel-Handoff statisch weiterverfolgt. | Branch `feature/build112-seret-handoff-static`; keine Live-Bootbestätigung |
| **113** | Fortsetzung der Boot-/Sicherheits- und Hardware-Evidenzdiskussion; kein eindeutig verifizierter eigener Build-Abschluss im hier verfügbaren Nachweis. | Offen |
| **114** | Samsung-Privileged-Service und Authentisierungsfluss im entschlüsselten Tizen-Rootfs disassembliert. | Konkrete statische ARM32-Funde, Root auf eigenem TV nicht nachgewiesen |
| **115** | Bestehende Firmware/Rootfs-Komponenten überprüft; Schwerpunkt auf vorbereitetem, sicherem Live-Diagnose-/Root-Zugang statt redundanter Boot-/RAM-Extraktion. | Keine destruktiven TV-Schreibzugriffe; Testpfad noch offen |
| **116** | Als nächste Phase **vorgeschlagen**: vorhandene kexec-/RAM-Boot-Ergebnisse nutzen, temporären Root-/Live-Hardwarezugang verifizieren. Wiederholte `CONFIG_KEXEC`-Suche wurde zurecht als bereits erledigt verworfen. | **Planung, kein abgeschlossener neuer Build** |

### Historische Hinweise zu 096–109

Diese Arbeitsphase war Teil derselben fortlaufenden Diskussion, auch wenn nicht jeder Schritt als separate Datei hochgeladen wurde. Die **bestätigten Eckpunkte** sind QEMU `/init` (096), neun Module (097), RAM-Adresskonflikt (098) und die `seret`-/uImage-/DTB-Fundstellen (099–103). Für 104 und 108–109 werden absichtlich **keine erfundenen Resultate** eingetragen.

## 3. RAM, CPU, Device Trees und Bootloader

- Firmware-Device-Trees: Profile **`nikel-2G`** und **`nikel-1.5G`**. **Welches Profil der echte 50-Zoll-TV tatsächlich nutzt, wurde nicht live bestimmt.** Unterschiedliche RAM-Profile dürfen nicht gemischt werden.
- CPU: Samsung SDP1804 / Nike-L, nach DT **vier Cortex-A57**, PSCI 0.2; verfügbare Samsung-Quellen enthalten DVFS-/Thermal-/Clock-Daten. Linux-/Tizen-Userspace ist ARM32; ARM64-CPU-Fähigkeit belegt noch keinen ARM64-Bootweg.
- Im Firmware-/Kernelkontext dokumentierte CPU-Stufen: **1700, 1000, 500, 250, 100 MHz** (L0–L4), Spannungsbereich etwa **870–1020 mV**; nicht als Live-Messung interpretieren.
- Bootartefakte einschließlich `seret.bin`, `uImage`, Payload, DTB und Kernel-Komponenten wurden bereits extrahiert und untersucht. **Erneute Extraktion ist kein sinnvoller nächster Standard-Schritt.**
- `0x80008000` wurde als uImage-Lade-/Entry-Information behandelt; die Übereinstimmung mit tatsächlich nutzbaren RAM-Bänken ist **nicht abschließend bewiesen**. Das darf nicht als freigegebene Zieladresse für Schreib-/Bootversuche gelten.
- `bootargs`, `booti` und zImage-Offsets in Binärdateien sind **statische Hinweise**, kein Nachweis eines frei nutzbaren UART-/USB-/RAM-Boot-Kommandos.
- **Kein öffentlich verifizierter Unlock für genau dieses Zielgerät**, kein bestätigter unsignierter Kernel-Boot; die tatsächliche Kombination aus Signaturprüfung, Boot-Policy und möglicher Verschlüsselung muss sauber getrennt bleiben.
- `CONFIG_KEXEC` war in untersuchten Referenzkonfigurationen deaktiviert. Das allein belegt weder Unmöglichkeit aller RAM-Boot-Wege noch die Existenz einer Alternative.
- Watchdog-Deaktivierung wäre **keine** Umgehung von Signaturprüfungen. Vor einem Test müssen Watchdog-Instanz und Resetursache ermittelt werden.

## 4. GPU, Display, DRM, Clock, Eingaben

### GPU und Panfrost

- Mali-/Midgard- und `mali_kbase`-Quellen sowie Panfrost wurden untersucht; frühere Nutzerangaben zur exakten GPU-Bezeichnung sind **nicht als verifizierte Silicon-ID** zu verwenden.
- GPU-Clock/Reset-Analyse nennt u. a. Register `0x00F50A10`, `0x00F50A14`, `0x00F507F8`, `0x00F5088C`.
- Linux-6.6.162-Panfrost und mehrere Samsung-GPU-Hilfsobjekte kompilierten als ARM32-ELF. Frühere Modpost-/Integrationsfehler sind davon getrennt; **keine echte GPU-Beschleunigung auf dem TV bewiesen**.

### Samsung Display/KMS

- Samsung-spezifischer DRM-/KMS-Entwurf mit OSD/GP/MIXER/QE/GA/POST/TMG, DMA-/Framebufferpfad und VBlank/IRQ-Integration.
- GP-Plane/Firmware-`sdp_mmap`: `0xfb580000` und `0xfd8000` als dokumentierte Grafikadresse/-größe.
- Vsync GIC **SPI 47**; Timing-/Scalerpfad mit 1920×1080 und UHD-/Scaler-Kontext in der Analyse.
- Die in früheren BUILDs entstandene `sdp_drm.c`-Portierung mit `drm_simple_display_pipe` ist ein **Treiberprototyp**, keine nachgewiesene Bildausgabe auf dem echten Q60T.
- IRB/IRS-Device-Tree-Skelette: `mcirb@9c1300` (SPI 110), `mcirs@9c1400` (SPI 111), bewusst `status = "disabled"`; einfache Probe-Skelette ersetzen keine funktionierende Fernbedienung.
- Bereits bearbeitete ALSA-/SDPT-Migrationen betreffen Linux-4.1.10-zu-6.6-Kompatibilität; Modulkompilierung ≠ geprüfter Ton.

## 5. Build, QEMU, CI und Repository

- Testumgebung: Debian-/Proxmox-ARM32-QEMU-Labor; Reproduzierbarkeit, Initramfs, Kernel-Build-Gates, Modultests, GitHub Actions.
- BUILD096: QEMU gelang bis `/init`.
- BUILD097: neun reproduzierbare Kernelmodule.
- BUILD111: ARM32-Offline-Build und CI laut Projektstatus **grün**; Draft-PR #32 baut auf PR #31 auf.
- Sichtbare GitHub-Zweige umfassen `feature/build071-bootloader-research`, `feature/build072-ramboot-preflight`, `feature/build076-seret-bootchain-research`, `feature/build077-seret-deep-analysis`, `research/build-085-clock-controller`, `feature/build096-arm32-qemu-validation`, `feature/build097-module-artifacts`, `feature/build098-safe-ram-boot-readiness`, `feature/build105-micom`, `feature/build106-driver-qemu`, `feature/build107-first-display-test`, `feature/build110-first-hardware-boot`, `feature/build111-arm32-offline` und `feature/build112-seret-handoff-static`.
- **Achtung Git-Struktur:** Fortgeschrittene Builds liegen auf zahlreichen Feature-Branches/PRs; `main` bzw. dessen README bildet möglicherweise einen älteren Stand ab. Diese Zusammenfassung behauptet **nicht**, alle Zweige seien gemergt.

## 6. Tizen-SDB, Root und Sicherheitsgrenzen (BUILD 070 / 113–116)

### Live überprüfte SDB-Fakten

- TV über `sdb connect 192.168.178.20:26101` erreichbar; `sdb devices` zeigte das Zielmodell.
- `cpu_arch:armv7`, `platform_version:5.5`, `product_version:4.0`, `sdbd_version:2.2.31`.
- `secure_protocol:enabled`, `intershell_support:disabled`, `sdbd_rootperm:disabled`, `rootonoff_support:disabled`, `filesync_support:pushpull`.
- SDB-Shellaufrufe gaben teilweise leere Ausgabe oder `closed` zurück. **Kein eigener Root-Erfolg.**

### Statische Privileged-Service-Funde

Bereits entschlüsselte Pfade im Offline-Rootfs:
- `/usr/apps/privileged-service/bin/mount.smb.sh`
- `/usr/apps/privileged-service/bin/ps_agent`
- `/usr/sbin/sdbd`
- `/etc/profile`

`mount.smb.sh` assembliert CIFS-/Mount-Parameter und startet eine Kommandozeile über `/bin/bash -c`. `ps_agent` bindet privilegierte Operationen an D-Bus-/Credential-/SMACK-Prüfungen. In BUILD114 wurde insbesondere der Aufrufpfad `PS_CommunicationServer::CallCommand` → `PS_Executor::Execute` analysiert, mit Caller-PID, Process Path, SMACK-Label, Rule-Matching und indirektem Callback. **Statische Angriffssurface ≠ funktionierender Exploit auf dem 50-Zoll-TV.**

Das Community-Projekt [tiz0wn](https://github.com/sebastianspicker/tiz0wn) berichtet Root und Persistenz auf einem **55-Zoll-Q60T** mit Firmware 2743.0; ein weiteres [Q70T-Root-Forschungsprojekt](https://github.com/cfloinc/samsung-q70t-tizen-root) betrifft verwandte Geräte. **Root/UEP-Bypass ist nicht gleich Bootloader-Unlock oder signaturfreier Linux-Boot.** Die dort berichteten persistenten Roh-Partition-Patches sind **nicht** als übertragbare, sichere Prozedur auf unserem Gerät freigegeben.

## 7. Offene Blocker – explizit

1. **Eigener Linux-Kernel auf echter Q60T-Hardware:** noch kein erfolgreicher Start.
2. **Bootloader-/Signaturbarriere:** kein bestätigter Unlock oder nicht-destruktiver alternativer Bootpfad.
3. **RAM-Layout und Boot-Handoff:** 1.5G/2G-Profile und `0x80008000` ohne ausreichende Live-Verifikation; falsche Adressen können Schaden verursachen.
4. **Live Root/Diagnose:** SDB erreichbar, aber keine Shell; temporärer Root auf genau `GQ50Q60TGUXZG` fehlt.
5. **GPU/DRM/HAL:** Linux-6.6-Objekt-/QEMU-Ergebnisse ersetzen keinen echten GPU-, Display-, Audio- oder Android-TV-End-to-End-Test.
6. **Recovery-/Rollback-Nachweis:** vor jedem risikoreichen Hardwareversuch erforderlich.
7. **Einzel-BUILD-Evidenz:** für 104 und 108–109 (sowie Teile 113) fehlen in dieser Konsolidierung belastbare Abschlusslogs.

## 8. Nächste sinnvolle Schritte – keine Wiederholungen

1. **Nicht wiederholen:** Firmware/DTBs erneut extrahieren, RAM-Bänke blind neu scannen, `CONFIG_KEXEC` ohne neuen Anlass erneut abfragen.
2. **Bereits vorhandene Artefakte konsolidieren:** PR-/Commit-Abgleich für 096–112, vorhandene Debian-Logs zu 104/108/109 als Evidenz nachtragen. Keine „PASS“-Behauptung aus Branch-Namen ableiten.
3. **Nicht-destruktive Live-Tizen-Diagnostik:** vorhandene SDB-/Remote-Access-/SMB-Informationen mit dem konkret dokumentierten Q60T-Pfad vergleichen; nur einen explizit abgesicherten, temporären Root-Nachweis auf dem eigenen Gerät erwägen.
4. **Sicherheitsgrenze:** **keine Roh-Schreibzugriffe auf `/dev/mmcblk*`**, keine Bootloader-/Partitionstabellen-Änderungen, keine `/etc/profile`-, `/etc/passwd`- oder `/etc/shadow`-Persistenzpatches ohne unabhängig geprüften Wiederherstellungsweg.
5. **Boot-Ziel:** nur auf Basis **bestätigter RAM-Topologie, Einstiegsmöglichkeit und Rollback** einen minimalen Linux-6.6-/initramfs-Startversuch spezifizieren.
6. **Erst danach:** Hardwaretreiber nacheinander am realen Gerät prüfen, dann Android-TV-Userspace.

## 9. Referenzzweige und Dokumentation

- Projekt: https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV
- [BUILD 072 RAM-Boot-Preflight](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build072-ramboot-preflight)
- [BUILD 096 QEMU-Validierung](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build096-arm32-qemu-validation)
- [BUILD 097 Modul-Artefakte](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build097-module-artifacts)
- [BUILD 098 RAM-Boot-Readiness](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build098-safe-ram-boot-readiness)
- [BUILD 105 Micom](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build105-micom)
- [BUILD 110 Hardware-Boot-Vorbereitung](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build110-first-hardware-boot)
- [BUILD 111 ARM32 Offline](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build111-arm32-offline)
- [BUILD 112 seret Handoff](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/tree/feature/build112-seret-handoff-static)
- [Draft-PR #32](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/32) laut Projektgespräch.
- [tiz0wn](https://github.com/sebastianspicker/tiz0wn), [SamyGO](https://wiki.samygo.tv/) als **externe** Forschungsquellen.

---

**Status in einem Satz:** Wir haben einen erheblichen ARM32-/Linux-6.6-/Samsung-DRM-/Bootchain-Forschungsstand mit reproduzierbaren Offline- und QEMU-Teilerfolgen; die kritischen nächsten Meilensteine sind **temporärer, verifizierter Live-Zugang und ein sicherer, tatsächlich auf dem Q60T gestarteter eigener Kernel**.

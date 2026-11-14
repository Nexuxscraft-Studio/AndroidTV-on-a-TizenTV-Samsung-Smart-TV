# Teilprojekt 3: Bootkette und Rollback

**Status: statische Referenzinventur und Fail-closed-Gate-Check.**
Ein sicherer alternativer Boot wurde **nicht bewiesen**.

## Bekannte Grenzen

Das referenzierte `2743.0`-Update enthält `uImage`, `dtb.bin`,
`sign.bin`, `seret.bin`, `secos.bin` und `secos_drv.bin`.

- Das uImage trägt einen **gültigen Legacy-U-Boot-Header und CRC32**;
  CRC schützt nur vor zufälliger Korruption, nicht vor absichtlichem
  Austausch.
- Das Vorhandensein von `sign.bin` und TrustZone-Komponenten legt nahe,
  dass verschiedene Signatur-/Verifikationsschritte relevant sind.
  **Die Signatur wurde nicht kryptografisch gegen eine Samsung-Trust-
  Anchor-/Bootrom-Kette validiert.**
- Dass ein Update entschlüsselt werden konnte, bedeutet weder, dass
  ein verändertes Update akzeptiert wird, noch dass ein eigenes Linux-
  oder Android-Image startet.
- Die Samsung-UEP-Strings im Kernel deuten auf zusätzliche Prüfschritte
  hin; deren genaue Bootrelevanz ist nicht nachgewiesen.

## Build 061 – Präzisierung der Komponenten (read-only)

Eine deskriptive Binäranalyse der lokal entschlüsselten Originalkomponenten
(Werkzeug `porting/build061/bootchain_forensics.py`, Report
`reports/bootchain_forensics_build061.json`, Details in `BUILD061_REPORT.md`)
präzisiert die obige Einordnung:

- **`seret.bin` ist ein AArch32-Linux-zImage**, **kein** TrustZone-Monitor:
  Der Einstiegscode ist der PIC-Selbstrelokations-Kopf des ARM-Decompressors
  (`mov r3,pc … and r0,r3,#0xfc000000`) samt Kernel-Decompressor-Strings.
  Der gepackte Payload ist mit Standard-Codecs nicht auspackbar (vermutlich
  verschlüsselt/nicht-standard gepackt).
- **`sign.bin` ist ein OpenSSL-`enc`-Blob** (`Salted__` + Salt + AES,
  salt-abgeleiteter Schlüssel), **kein offener Hash** der Komponenten – geprüft:
  keiner der Komponenten-Hashes steckt roh/hex darin. Ohne den HW-Schlüssel
  **nicht reproduzier- oder fälschbar**.
- **`secos.bin` / `ddr.init` verschlüsselt** (Entropie ~8,0); Schlüssel
  vermutlich in eFuse/OTP.
- Das **entschlüsselte `uImage`** (aus dem FullOS-Container) ist ein
  **unkomprimierter Linux-4.1.10-ARMv7-Kernel** (U-Boot `arch=2`, `comp=0`,
  Load/Entry `0x80008000`, HYP-bewusster `stext`), SoC `SDP1412` / `sdp-nikel`.

**Architektur-Folgerung:** EL3/Secure-Monitor ist AArch32 → `SCR_EL3.RW` nicht
setzbar → niedrigere Exception-Level bleiben AArch32 → ein **arm64-Linux kann
nicht booten**. Die A57-Kerne sind ARMv8-Silizium, aber die Firmware erlaubt nur
AArch32 → Zielarchitektur **ARM 32-Bit**. Das ändert **nichts** an den
Boot-Gates unten: Ein eigener Kernel wird dadurch nicht startfähig.

## Rückroll-Nachweise (alle bisher offen)

`porting/boot-evidence.json` enthält acht vorläufige Prüf-Gates:

1. Exakte Zielhardware einschließlich Board-/RAM-Variante.
2. Bootloader-Signaturprüfung und Herkunft der Trust Anchors geprüft.
3. **Nichtpersistenter**, unabhängiger Testboot möglich.
4. Recovery-Einstieg auf diesem Board nachgewiesen.
5. Vollständige, überprüfte Sicherung der Originalzustände vorhanden.
6. Wiederherstellung tatsächlich an gleichwertiger Ersatzhardware geübt.
7. Watchdog-/Fallback-Pfad für hängende Testboots geprüft.
8. Recovery nach Stromausfall nachgewiesen.

Die neue `q60t_boot_safety.py` kann die lokal entschlüsselten
**Originalkomponenten** anhand ihrer Hashes inventarisieren und die
Gate-Liste maschinell prüfen:

```bash
python3 q60t_boot_safety.py \
  --components-dir /pfad/zu/entschluesselter_firmware \
  --evidence porting/boot-evidence.json
```

Erwartetes Ergebnis für diese Arbeit: `REFERENCE_PRESENT` für die
nachgewiesene 55-Zoll-Originalfirmware, aber **`BLOCKED` mit acht
fehlenden Nachweisen**. Der Rückweg am 50-Zoll-Zielgerät wird nicht
dadurch belegt, dass wir die Originaldateien kennen.

Das Werkzeug gibt **keine** Befehle für Bootloader-Modifikation,
Partitionswrites, Secure-Boot-Umgehung oder Exploit-Nutzung aus.
Selbst bei allen acht grünen Feldern wird lediglich eine menschliche
Sicherheitsüberprüfung angezeigt; `flash_authorized` bleibt immer false.

## Entscheidung für das weitere Projekt

Der erste echte Teststart darf nur **flüchtig und reversibel** erfolgen,
wenn der konkrete Samsung-Bootweg das tatsächlich zulässt. Das ist
gegenwärtig nicht gezeigt. Ohne diesen Nachweis wird weder die
Originalfirmware ersetzt noch eine persistente Android-Bootpartition
angelegt. Ein defekter Secure-Boot-Pfad kann den Fernseher dauerhaft
unbenutzbar machen.

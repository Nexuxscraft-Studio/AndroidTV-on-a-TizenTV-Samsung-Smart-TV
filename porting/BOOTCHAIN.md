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

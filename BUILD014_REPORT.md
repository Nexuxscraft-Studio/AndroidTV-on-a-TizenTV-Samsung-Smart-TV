# Build 014 – Auditierte GitHub-Actions-Quellpakete

Stand: 09.11.2026

## Zweck

Dieses Build automatisiert ausschließlich die **Weitergabe des selbst
erstellten Forschungsquellcodes**. Die CI erstellt **kein** LineageOS-ROM,
keine angepasste Samsung-Firmware und kein bootfähiges Kernelimage.

## Implementierung

- `q60t_package_release.py`: Packt nur Dateien, die der bestehende
  `q60t_release_audit.py` erlaubt. Vor dem Packen werden unerwartete
  Dateitypen, Binärdaten, einige Schlüsselmarker und symbolische Links
  abgelehnt. Diese Heuristik ersetzt **keine umfassende Geheimnisprüfung**.
- ZIP-Inhalt ist alphabetisch sortiert, unter `q60t-lineage-lab/`
  abgelegt und verwendet feste Zeitstempel/Dateimodi, damit gleiche
  Quellbytes zum gleichen Archiv-Hash führen.
- Zu jedem ZIP gehören `.manifest.json` (Einzeldatei-Hashes, Dateizahl,
  Warnung zum Bootrisiko) und `.sha256` (Prüfsumme des ZIPs).
- Ausgaben müssen außerhalb des Projektverzeichnisses liegen. Bestehende
  ZIPs, Manifeste oder Prüfsummen werden nicht überschrieben.
- `.github/workflows/research-release.yml`: Auf `main` und bei manuellem
  Start werden Tests, negative Sicherheits-Gates, Quell-Audit und
  Paketierung ausgeführt; das Ergebnis ist ein 30 Tage vorgehaltenes
  GitHub-Actions-Artefakt. **Nur beim Push eines `v*`-Tags** folgt danach
  ein GitHub-**Prerelease** mit denselben geprüften Dateien.
- Rechte des Paketierungsjobs: ausschließlich `contents: read`.
  Für den gesonderten Tag-Release-Job ist `contents: write` nötig.

## Auslösen

1. **Jeder Push auf `main`**: Testen und paketieren; ZIP unter dem
   jeweiligen GitHub-Actions-Lauf als Artefakt verfügbar.
2. **Actions → Q60T source-only package and release → Run workflow**:
   Manuell erneut testen und paketieren, ohne Release zu veröffentlichen.
3. **Optional später**: Einen Versionstag wie `v0.14.0` bewusst auf den
   geprüften Commit setzen und pushen. Erst dadurch legt die CI ein
   als experimentell markiertes Prerelease an. Ein Tag wird von
   diesem Build nicht eigenständig erzeugt.

## Verifikation

Lokale Projektprüfung:

```bash
python3 -m unittest discover -s tests -q
python3 q60t_release_audit.py .
```

Separater Host-Test:

```bash
mkdir -p /pfad/zu/neuem-dist
python3 q60t_package_release.py --source . \
  --output /pfad/zu/neuem-dist/q60t-source.zip --label build014
cd /pfad/zu/neuem-dist
sha256sum -c q60t-source.sha256
```

Die neuen **acht** Tests prüfen Whitelisting, Archivintegrität,
deterministische Bytes, Dateimanifest/Hashes, existierende Dateien,
Pfadsperre, ungültige Kennungen, Binärdateien und Symlinks.
Insgesamt **88 synthetische Tests** wurden lokal erfolgreich ausgeführt.

## Unveränderte technische Grenzen

- Die Samsung-Quellen aus `20_DTV_NikeL.zip` sind **nicht** im Release.
- Das zuvor auf einem Host testweise erstellte Linux-4.1.10-`zImage`
  ist **nicht bootfähig nachgewiesen** und **nicht** im Release.
- Für den Q60T wurde weder ein sicherer alternativer Bootweg noch
  ein unabhängiger Rollback-Weg belegt.
- Der Android-Produktport bleibt absichtlich gesperrt.

**Nichts aus diesem Projekt auf den Fernseher flashen.**

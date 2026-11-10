# Build 050 – Samsung-Hardware-Referenzprüfung

**Host-only / read-only:** Dieses Verfahren liest ausschließlich bereits
vorhandene JSON-Quell-/Firmware-Reports und optional das originale
Samsung-OSS-ZIP zur SHA-256-Identitätsprüfung. Es schreibt **niemals**
auf den Fernseher, führt keine heruntergeladenen Skripte aus und
entpackt keine Vendor-Binärdateien.

Vom Root des Projekt-Repositories aus:

```bash
python3 q60t_build050_hardware_evidence.py \
  --output /opt/samsung-atv-lab/build050-hardware-evidence.json
```

Wenn das originale äußere `20_DTV_NikeL.zip` zur **rein lesenden**
SHA-256-Prüfung lokal verfügbar ist, optional hinzufügen:

```bash
python3 q60t_build050_hardware_evidence.py \
  --original-oss-archive /pfad/zum/originalen/20_DTV_NikeL.zip \
  --output /opt/samsung-atv-lab/build050-archive-verified.json
```

Hash des bereits inventarisierten **äußeren** 743-MB-OSS-ZIPs:
`3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad`.
Ein abweichender Hash wird abgelehnt; es wird kein Quellcode aus der
ZIP ausgeführt oder entpackt. Für eine echte Linux-6.6-Treiberportierung
brauchen wir danach den vollständigen Samsung-Treiberquellbaum.

```bash
python3 -m unittest tests/test_build050_hardware_evidence.py -v
python3 -m unittest discover -s tests -q
python3 q60t_release_audit.py .
```

Die Datei `reports/hardware_build050_evidence.json` enthält den
verifizierten Stand aus den sieben historischen Referenzreports. Ihr
Status `REFERENCE_IDENTIFIED_LIVE_TV_UNVERIFIED` bedeutet **nicht**,
dass der tatsächliche 50-Zoll-Fernseher untersucht wurde.

Alle nächsten Hardware-Schritte bleiben von einem bestätigten,
flüchtigen Bootweg sowie einem unabhängigen, geprüften Recovery- und
Rollbackweg abhängig. **Keine Flash- oder Bootloaderänderung.**

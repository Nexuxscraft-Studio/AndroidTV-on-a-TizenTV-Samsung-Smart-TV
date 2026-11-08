# Build 006 – Zielgerät und offizielle Firmwarezuordnung bestätigt

**Datum:** 08.11.2026

## Exakte Zielvariante

Der Nutzer hat den vollständigen Samsung-Modellcode mitgeteilt:

- **Modell:** `GQ50Q60TGUXZG`
- **Modellreihe:** Samsung Q60T, 50 Zoll, Modelljahr 2020
- **Firmware am Zielgerät:** `2743.0` (Nutzerangabe)

Das Zielgerät ist auf der
[offiziellen deutschen Samsung-Supportseite](https://www.samsung.com/de/support/model/GQ50Q60TGUXZG/)
gelistet. Die Herstellerseite weist für **genau dieses Modell** aus:

| Offizieller Eintrag | Wert |
| --- | --- |
| Firmware-ZIP | `T-NKLDEUC.zip` |
| Firmwarefamilie | `T-NKLDEUC` |
| Version | `2743.0` |
| Samsung Datei-ID | `7701730` |
| Firmware-Downloadpfad | `FM/202609/20260915171117277/T-NKLDEUC.zip` |

Der Download-Eintrag entspricht dem Paket, das bereits für die
55-Zoll-Referenz `GQ55Q60TGUXZG` analysiert wurde. Damit ist die
**Zuordnung der Firmwarefamilie zum 50-Zoll-Zielgerät jetzt offiziell
abgesichert**. Eine bloße identische Versionsnummer war zuvor kein
ausreichender Beleg.

## Was diese Bestätigung nicht beweist

Die Firmware enthält mindestens zwei unterschiedliche Nike-L-Device-
Trees mit den Namen `nikel-2G` und `nikel-1.5G`.

Es ist **noch nicht ermittelt**, welche Variante beim realen
`GQ50Q60TGUXZG` geladen wird. Auch Bootloader-Signaturen,
Mali-/Display-Treiber und ein reversibler Bootweg wurden nicht
automatisch durch die Handelsmodellnummer bewiesen.

## Änderungen am Projekt

1. `porting/port-state.json` ist jetzt auf `GQ50Q60TGUXZG` festgelegt.
2. `porting/model-evidence.json` dokumentiert Herstellerseite,
   Firmwarefamilie, Version und Referenzbezug.
3. `q60t_portcheck.py` prüft den exakten Modellcode und die gespeicherte
   Herstellerzuordnung. Abweichende Modellcodes werden abgelehnt.
4. Das Modell-Gate ist **bestanden**, neun weitere Portierungs-Gates
   bleiben offen. `flash_authorized` und `image_build_enabled` bleiben
   ausnahmslos `false`.
5. Die Boot-Safety-Gates bleiben gesperrt. Der genaue physische Board-
   und Recoveryzustand wurde noch nicht untersucht.

**Tests:** 33 synthetische Unit-Tests bestanden.

Kein Zugriff auf den Fernseher, kein Flash, kein experimenteller Boot.

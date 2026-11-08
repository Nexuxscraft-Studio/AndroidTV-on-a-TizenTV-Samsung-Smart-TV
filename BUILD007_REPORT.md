# Build 007 – Kernel-Herkunft, Mali-Strategie und integriertes Android-TV-Gate

Stand: 08.11.2026. Ziel: Samsung **GQ50Q60TGUXZG**, T-NKLDEUC **2743.0**.

## Kurzfazit

Build 007 fügt **funktionsfähige Offline-Prüfwerkzeuge, Testfälle und CI** hinzu,
aber kein baubares Android-TV-System und keinen nachgebauten Samsung-Kernel.
Alle Aussagen unten unterscheiden messbare Artefakte von Annahmen.

| Forschungsziel | Was tatsächlich nachgewiesen wurde | Ergebnis |
| --- | --- | --- |
| Originalkernel reproduzieren | ARM32-4.1.10-Banner aus Original-uImage; korrekte, getrennte O=-Konfigurationsschritte entworfen | **Blockiert**: Samsung-Sourcepaket/Defconfig/Cross-Compiler fehlen |
| Mali-Grafik anpassen | Unterscheidung zwischen herstellerspezifischem kbase (`/dev/mali0`) und Panfrost-DRM-Ansatz; referenzierte GPU/Display-DTB-Knoten | **Blockiert**: Kein ABI-/Display-/HAL-Nachweis |
| Reversibler Boot | Build-Guard und Boot-Gates bleiben erzwungen; Host-CI prüft das | **Blockiert**: Kein unabhängiger Boot-/Rollback-Nachweis |
| Android TV bauen | Integrierte Prüfung des experimentellen Lineage-Produktgerüsts | **Blockiert**: bewusst nicht baubar |

## Neue Software

1. `q60t_source_provenance.py`: Hash und ZIP/TAR-Metadaten eines **lokal**
   beschafften Kernelpakets prüfen; verdächtige Archivpfade, Links und zu große
   deklarierte Datenmengen melden. Kein Extrahieren, Ausführen oder Download.
   Die Version eines danebenliegenden Kernel-Quellbaums wird getrennt geprüft.
   Selbst ein übereinstimmender Hash ist keine unabhängige Samsung-Provenienz.
2. `q60t_kernel_build.py`: bestehende Vorprüfung korrigiert. Vor dem
   `O=... olddefconfig` muss die bereitgestellte Originalkonfiguration
   **explizit als `O=.../.config`** kopiert werden. Die erstellten Kommandos
   werden nur angezeigt; sie werden nicht automatisch ausgeführt.
   Ein fremder 4.1.10-Quellbaum gilt nicht als Samsung-GPL-Quelle.
3. `q60t_gpu_strategy.py`: getrennte Voraussetzungen für Samsungs
   legacy-kbase-Stack und den Linux-DRM/Panfrost-Weg; optionaler, rein
   statischer ELF-/Quellpfad-Survey. Kein DRM-Backport oder Android-HAL.
4. `q60t_build007_preflight.py`: integriert die existierenden Firmware-,
   Kernel-, GPU- und Portierungsgates mit der zwingenden
   `$(error ...)`-Sperre des BoardConfig. Eine entfernte Sperre wird
   als Fehler gemeldet und niemals als Flashfreigabe.
5. `.github/workflows/host-only-tests.yml`: Python 3.11/3.12, synthetische
   Tests, Release-Audit und eine Prüfung, dass Android-Build und Flash
   weiterhin gesperrt bleiben. Workflow benötigt **keine Firmware**.

## Offline-Berichte

- `reports/source_candidate_build007.json`: **BLOCKED**, kein offizielles
  Samsung-Quellpaket lokal vorhanden.
- `reports/kernel_plan_build007.json`: **BLOCKED**, kein eigener Kernel-Build.
- `reports/gpu_strategy_build007.json`: **BLOCKED**, beide GPU-Pfade offen.
- `reports/combined_build007.json`: **BLOCKED**, zusammengefasste Nachweise.

Die JSON-Dateien enthalten keine Samsung-Firmwarebytes und keine
Kernel-/GPU-Treiber-Binärdateien.

## Reproduzierbare Befehle

```bash
python3 -m unittest discover -s tests -q
python3 q60t_release_audit.py .

# Ohne Kernelquellen entsteht absichtlich ein gesperrter Kandidatenbericht:
python3 q60t_source_provenance.py

# Wenn das offizielle Samsung-GPL-Archiv selbst heruntergeladen wurde:
python3 q60t_source_provenance.py \
  --archive /pfad/zum/originalen-samsung-source.zip \
  --source /pfad/zum/getrennt-entpackten-linux-tree \
  --expected-sha256 <unabhaengig-bestaetigter-64-stelliger-sha256>

python3 q60t_gpu_strategy.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json

python3 q60t_build007_preflight.py
```

Ein Hash unter `--expected-sha256` muss aus einer **unabhängig geprüften**
Herstellerquelle stammen, nicht nur aus derselben Datei berechnet werden.
Der Toolstatus `MANUAL_REVIEW_REQUIRED` bestätigt lediglich die technische
Konsistenz der Eingaben, niemals die Zugehörigkeit zu Firmware 2743.0.

## Externe Quellen für den nächsten Schritt

- Samsung Open Source Release Center, Q60T-Suche:
  <https://opensource.samsung.com/uploadSearch?searchValue=Q60T>
- Synacktiv, *Rooting Samsung Q60T Smart TV* (Vortrag/Originalforschung):
  <https://www.synacktiv.com/sites/default/files/2022-05/Sthack2022_Rooting_Samsung_Q60T_Smart_TV.pdf>
  – dokumentiert den historischen Samsung-GPL-Quellcode. Eine für **2743.0**
  passende Ausgabe ist damit noch **nicht** verifiziert.
- Arm, Open-Source-Bifrost-Kerneltreiber:
  <https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture>
  – Arm weist ausdrücklich darauf hin, dass diese Quellen **keinen
  vollständigen GLES-Treiberstack** darstellen.
- Android Open Source Project, Composer3-HAL:
  <https://source.android.com/docs/core/graphics/aidl-hwc>
- Mesa/Panfrost-Dokumentation:
  <https://docs.mesa3d.org/drivers/panfrost.html>

## Nächste erforderliche Originalartefakte

1. **Passendes Samsung-GPL-Paket** inklusive exakter Veröffentlichungskennung,
   Lizenz/Hash, Nike-L-Patches und Kernel-Defconfig.
2. **Passende ARM-Cross-Toolchain** samt Build-Anweisungen. Ein
   beliebiges `arm-linux-gnueabihf-gcc` ist nicht gleich GCC 6.2.1 Tizen/Linaro.
3. **Original-Mali-Modul und Userspace-EGL** nur für private lokale
   Kompatibilitätsanalyse, plus dokumentierte `mali_kbase`-Version und
   Display-DRM-Schnittstellen.
4. **Read-only Gerätedaten** zur Unterscheidung `nikel-2G`/`nikel-1.5G`.
5. **Nachweis einer unverändernden Bootmöglichkeit** und unabhängig
   getesteter Wiederherstellung, bevor überhaupt ein fremdes Image auf
   diesem realen TV gestartet wird.

**Nicht erbracht:** Originalkernel-Kompilierung, funktionierendes
SurfaceFlinger/Composer, GPU-Beschleunigung, Android-Boot oder TV-Rollback.

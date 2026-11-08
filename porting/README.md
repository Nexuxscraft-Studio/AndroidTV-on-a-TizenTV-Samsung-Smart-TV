# Experimenteller Android-TV-Geräteport – Samsung Nike-L

**Aktueller Status: Forschungsskelett, absichtlich nicht build- oder flashfähig.**

Dieser Ordner ist der Beginn des LineageOS/Android-TV-Portierungsbaums.
Er führt die nachgewiesene Hardwarefamilie `samsung,sdp-nikel` mit der von
LineageOS für Google-Android-TV-Geräte verwendeten Produktstruktur
zusammen. Die Referenz ist
[`LineageOS/android_device_google_beast`](https://github.com/LineageOS/android_device_google_beast).

## Verzeichnisstruktur

- `device/samsung/nikel/AndroidProducts.mk` – Produktregistrierung.
- `device/samsung/nikel/lineage_nikel.mk` – **experimentelles** ATV-Produkt.
- `device/samsung/nikel/device.mk` – Platzhalter für später verifizierte HALs.
- `device/samsung/nikel/BoardConfig.mk` – explizite Build-Sperre.
- `profiles/*.json` – zwei aus der offiziellen Referenzfirmware
  abgeleitete RAM-/Device-Tree-Profile.
- `port-state.json` – Maschinenstand aller Portierungs-Gates.
- `../q60t_portcheck.py` – prüft Profile, Firmware-Nachweise und Gates.
- `HAL_MATRIX.md` – quellengestützte Android-/Tizen-Hardwarezuordnung.
- `KERNEL_BUILD.md` – reproduzierbare Samsung-Kernel-Source-/Toolchain-Prüfung.
- `GRAPHICS_PORT.md` – Mali-Treiber-KABI, Android EGL/Gralloc/Composer.
- `BOOTCHAIN.md` – statische Bootsignaturgrenzen und Rollback-Gates.
- `boot-evidence.json` – acht noch ungeklärte, sicherheitskritische
  Nachweise für einen späteren Testboot.
- `../q60t_kernel_build.py`, `../q60t_graphics.py`,
  `../q60t_boot_safety.py` – neue Build-005-Prüfwerkzeuge.

## Warum die Build-Sperre notwendig ist

Beim Q60T liegen **zwei unterschiedliche DTBs** mit
`nikel-2G` und `nikel-1.5G` vor. Die exakte Hardwarevariante des Nutzers
ist noch nicht identifiziert. Der vorhandene Samsung-Kernel ist ARM32
Linux 4.1.10; wie er signiert und von der Bootkette geladen wird, ist
nicht sicher reproduziert. Android benötigt zudem einen funktionierenden
Display-Composer/Gralloc-Treiber, Audio-HAL und MediaCodec-Anbindung.

Die `BoardConfig.mk` verweigert deshalb bewusst einen Image-Build.
Es gibt **keine** flaschbaren Images, Partitionstabellen,
`fastboot flash`-Befehle, Vendorblobs oder Sicherheitsumgehungen.

Die zwei JSON-Profile sind _Beschreibungen des Referenzfirmwarepakets_,
nicht automatisch kompatible Boot-Konfigurationen des 50-Zoll-Geräts.
Die exakte Modellkennung `GQ50Q60TGUXZG` und die offizielle
Firmwarezuordnung `T-NKLDEUC 2743.0` sind nun in
`model-evidence.json` dokumentiert. Das aktive RAM-Profil bleibt offen.

## Prüfungen

```bash
python3 q60t_portcheck.py --project porting
python3 q60t_portcheck.py --project porting \
  --hardware-report reports/hardware_2743.0_build004_final.json
python3 -m unittest discover -s tests -v
```

Das erste Kommando zeigt einen maschinenlesbaren `BLOCKED`-Bericht mit
allen offenen Nachweisen. Sobald wir **echte** Belege und einen sicheren
Bootweg haben, können die einzelnen Gates nach nachvollziehbarer Prüfung
schrittweise freigegeben werden. Die Sperre in `BoardConfig.mk` wird
nicht automatisch entfernt.

In Build 005 sind auch die drei neuen Fachprüfungen blockiert:
Matching-Samsung-Kernelquellen fehlen, Android-Displaytreiber/HALs sind
nicht implementiert und ein **reversibler Bootweg ist unbewiesen**.

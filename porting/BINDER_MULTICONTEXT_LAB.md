# Build 016: Drei Binder-Domänen – nur experimentelle Host-Quelle

> **Kein Android-kompatibler Binder-Backport, kein Gerätekernel,
> keine Freigabe für den Fernseher.**

## Warum diese Änderung wichtig ist

Der originale Samsung-Tizen-Kernel 4.1.10 registriert nur eine Miscdevice
`binder` und verwendet einen einzigen globalen
`binder_context_mgr_node` / `binder_context_mgr_uid`.
Damit fehlt die im modernen Android-System übliche Unterscheidung
zwischen drei Dienstkontexten:

| Gerät | Typischer Android-Zweck |
| --- | --- |
| `/dev/binder` | Framework- und App-AIDL |
| `/dev/hwbinder` | HIDL-Schnittstellen von System und Vendor |
| `/dev/vndbinder` | Vendor-interne AIDL-Dienste |

Referenz: [AOSP – Binder IPC in Android](https://source.android.com/docs/core/architecture/hidl/binder-ipc).
Eine bloße Anlage zusätzlicher Gerätedateien mit demselben globalen
Manager wäre **keine** echte Kontexttrennung.

## Experimentelles Quelltext-Overlay

`q60t_binder_lab.py` baut aus dem exakten überprüften
Samsung-`drivers/android/binder.c`-Quellstand eine **ausdrücklich
experimentelle** Treibervariante. Das Werkzeug verweigert einen
unbekannten SHA-256-Quellstand oder mehrfach vorkommende Quellmarker.

Die Änderung enthält:

1. Einen separaten `binder_context` je Miscdevice, der Managerknoten,
   Manager-UID und Gerätenamen enthält.
2. Eine feste Zuordnung jeder geöffneten `binder_proc` zur zugehörigen
   Gerätedomäne über `misc_open()` und `file->private_data`.
3. Managerauflösung, Reference-ID `0` und Manager-Lebenszyklus
   innerhalb der zugehörigen Domäne.
4. Zusätzliche Prüfungen gegen die Übertragung von Binder-Referenzen
   und Transaktionen zwischen unterschiedlichen Domänen.
5. Drei `misc_register()`-Aufrufe mit Fehlerbehandlung und getrennte
   DebugFS-Prozessnamen.

Die Ausgabe ist ein Host-Test-Diff `binder-multicontext-lab.patch` plus
die ausschließlich **im Schattenquellbaum** geänderte Binder-Datei.
Weder der Samsung-Originalquellbaum noch ein Kernel auf dem TV wird
bearbeitet.

## Reproduzieren

```bash
python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build016-binder-lab \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile binder-lab --jobs 4 --timeout 1800
```

Das Profil verwendet zusätzlich die Build-015-Forschungsoptionen
SELinux, Initramfs und IKCONFIG. `--profile tizen` bleibt Standard.
Die generierte `compile-report.json` unterscheidet streng zwischen
Cross-Compile und einem **nie durchgeführten Laufzeittest**.

## Was damit ausdrücklich **nicht** bewiesen wird

- Kein instrumentierter Kernel-Runtime-Test gegen `libbinder`,
  `servicemanager`, `hwservicemanager` und `vndservicemanager`.
- Keine vollständige Upstream-Integration der modernen Binder-ABI,
  BinderFS, Thread-/Allocation-/Security-Hardening oder Android-VTS.
- Keine funktionierende Android-14-Supportmatrix: Linux 4.1.10 bleibt
  ein sehr alter, offiziell nicht unterstützter Kernelstand.
- Keine verifizierte Android-SELinux-Policy, kein Hardware-HAL und keine
  zu diesem Samsung-Modell passend signierte Bootkette.
- Kein Device-Tree-/RAM-Profil des tatsächlich vorhandenen 50-Zoll-TVs.

**Ein bestandener Compilerlauf ist erst der Anfang.** Für die nächste
Stufe ist ein kontrollierter Binder-Runtime-Test in einer isolierten,
vom Samsung-TV unabhängigen Umgebung nötig. Ein Einsatz auf dem
Fernseher bleibt ausdrücklich blockiert.

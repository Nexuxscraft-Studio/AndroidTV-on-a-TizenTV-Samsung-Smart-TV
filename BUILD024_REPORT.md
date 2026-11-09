# Build 024 – LineageOS 21 ARM64 First-Stage Init / QEMU

**Branch:** `feature/build024-lineage21-arm64-init-qemu`  
**Ausgewählter QEMU-Userspace-Kandidat:** offizieller LineageOS-21.0-
Quellbranch (Android 14, API 34, AOSP `android-14.0.0_r67`).  
**Echter Android-Init-Gaststart:** **noch nicht durchgeführt**.  
**Samsung-TV:** vollständig unverändert, kein Flash.

## Implementiert

- Exakte LineageOS-Manifest-/Branch-SHAs zur Reproduzierbarkeit;
  `q60t_lineage_arm64_source.py` verweigert abweichende Quellen.
- Offizieller LineageOS-TV-ARM64-GSI-Target `gsi_tv_arm64` dokumentiert;
  ein TV-Emulator-Target `sdk_tv_arm64` und ein QEMU-`virt`-Product-Target
  werden **nicht** behauptet.
- `q60t_lineage_arm64_initramfs.py` akzeptiert ausschließlich ein
  echtes statisches ARM64-`init` aus einem verifizierten lokalen
  LineageOS-Checkout, prüft ELF-/Kernel-Grundlagen und erzeugt ein
  eigenständiges, unbenutztes QEMU-Initramfs mit SHA-Report.
- `q60t_lineage_arm64_init_result.py` korreliert später echte
  QEMU-Gastlogs mit dem geprüften ARM64-Staging-Artefakt und unterscheidet
  First-Stage-Loghinweise streng von fertigem Android-Boot.
- `q60t_lineage_arm64_sepolicy.py` inventarisiert Android-14-
  Plattform-/Vendor-CIL-Dateien, Labels und Kernel-SELinux-Funktionen;
  **keine** Policy wird stillschweigend als korrekt geladen bestätigt.
- Synthetische Offline-Tests ohne QEMU, Source-Download, Samsung-Zugriff
  oder systemweite Berechtigungen.

## Wesentliche Architekturgrenzen

1. Linux 6.6.162 ist eine aktuelle **Mainline-/Longterm-Testbasis**,
   kein Android-14-GKI-Zweig. Android-Kernel-Patches, SELinux, VINTF,
   Binder und Android-Dateisystem-Anforderungen bleiben zu verifizieren.
2. `gsi_tv_arm64` produziert ein generisches System-Image, **kein
   bootfertiges** QEMU-`virt`-Android-TV-Gerät. Wir benötigen weiterhin
   einen eigenen Device-/Vendor-Port.
3. Android-14-First-Stage kann nur real getestet werden, wenn
   offizielle Quell-Revisionsbasis und echtes Build-`init` vorliegen.
4. Ohne passende `system`-/`vendor`-Mounts und Android-SELinux-Policy
   sind Second-Stage, Property Service und Systemdienste **nicht bereit**.
5. Samsung-SoC-ARM64-Unterstützung, Treiber und Recovery-Boot bleiben
   gesonderte, offene Hardware-Arbeitspakete.

**Vollständige Proxmox-Schrittfolge:** `porting/lineage_arm64/README.md`.

## Host-Checks

```bash
python3 -m unittest discover -s tests -q
python3 q60t_lineage_arm64_source.py
python3 q60t_lineage_arm64_sepolicy.py
```

Der Samsung-Originalkernel 4.1.10 und der erfolgreiche ARM64-Build-023-
QEMU-Labstand bleiben unangetastet. Nächster tatsächlicher Meilenstein ist
ein aus **echtem LineageOS-Source** gebautes ARM64-`/init` mit nachweis-
barem First-Stage-Log unter QEMU, **kein** Hardware-Flash.

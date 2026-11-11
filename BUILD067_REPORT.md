# Build 067 – QEMU-ARM32-Boot-Harness

**Branch:** `claude/build067-qemu-boot-harness` (aus Build 066). **Status:**
CI-Boot-Test in Emulation. **Kein** Gerätezugriff, **kein** Flash.

Bisher war der 6.6.162-ARM32-Kernel nur **compile**-geprüft (Build 059/063).
Build 067 schließt die Lücke zum **Boot**: Es bootet das Build-059-zImage
(multi_v7 + eingebettete `q60t-diag-init`) auf `qemu-system-arm -M virt` und
verifiziert automatisch den Userspace-Einstieg.

## Harness

`run-qemu-boot.sh` nutzt den **bereits CI-grünen** Build-059-Build (`arm`,
`full`) und bootet das Ergebnis:
```
qemu-system-arm -M virt -cpu cortex-a15 -m 512 -nographic \
  -kernel zImage -append "console=ttyAMA0 earlycon panic=-1"
```
Erfolg = der Serial-Log enthält den Init-Banner `q60t-diag-init`. Der QEMU-
Exit 124 (90s-Timeout an der Diag-Shell) ist planmäßig.

## Aussagekraft

- **Beweist:** Der 6.6.162-ARM32-Kernel bootet in Emulation bis in den
  Userspace (PID 1 läuft, Konsole, initramfs).
- **Beweist NICHT:** Boot auf dem realen Q60T — QEMU `virt` ist nicht die
  Nike-L-Hardware, und die signierte Bootkette (Build 061) ist unberührt.

## Einordnung in die Roadmap

Das ist der **Build-060-„Emulator-zuerst"-Meilenstein** auf Kernel-Ebene,
automatisiert. Nächste emulierte Stufe (später, großer Buildhost): der
32-Bit-Android-15-Userspace (LineageOS `TARGET_ARCH=arm`) über denselben
Kernel. Sperre und Gates bleiben.

# Build 067 – QEMU-ARM32-Boot-Harness (Linux 6.6.162)

**Status: CI-Boot-Test in Emulation. NICHT das Samsung-Board, kein Flash.**
Automatisiert, was Builds 018–022 manuell auf der Proxmox-VM taten.

Bootet den **Build-059-Kernel** (6.6.162 ARM32, multi_v7 + eingebettete
`q60t-diag-init`) auf der generischen `qemu-system-arm -M virt`-Maschine und
prüft, ob der **Userspace-Init** erreicht wird (Marker `q60t-diag-init`).

```bash
bash porting/build067/run-qemu-boot.sh /pfad/zu/linux-6.6.162 /pfad/zu/out
```

CI: `.github/workflows/build067-qemu-boot.yml`. Ein grüner Lauf beweist, dass der
6.6.162-ARM32-Kernel **in Emulation bis in den Userspace bootet** — nicht, dass
er auf dem realen Q60T bootet (anderer Machine-Typ, andere Bootkette). Sperre
und Gates bleiben.

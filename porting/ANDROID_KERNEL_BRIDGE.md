# Q60T Build 012 – Reproduzierbarer Host-Ablauf

Dieses Verfahren reproduziert die experimentelle **Kconfig-Konfiguration**
des Samsung-Nike-Kernels unter Linux. Es ist **kein** Bootrezept,
kein ROM-Build, kein Zugang zum Fernseher und kein Freibrief zum Flashen.

## Eingaben

- Entpackter Samsung-Kernelquellbaum aus `linux-4.1.10-tizen5.5.tgz`.
- Ein isoliertes Arbeitsverzeichnis **außerhalb** der Samsung-Quelle.
- Python 3.10+, `make` und ein Host-GCC zum Ausführen von Kconfig.
- Für einen späteren **echten ARM-Kernelbuild** wird zusätzlich ein
  separat überprüfter ARM32-Cross-Compiler benötigt. Der lag bei
  Build 012 **nicht** als ausführbares Werkzeug vor.

## 1. Vorprüfung und fragmentierte Kandidaten-Konfiguration

```bash
python3 q60t_android_kernel.py \
  --source /pfad/zu/linux-4.1.10 \
  --report /neuer/pfad/android_kernel.json \
  --fragment-out /neuer/pfad/android-candidate.cfg
```

Der Prüfer untersucht **neun** Nike-Konfigurationen, ihre ARM-Kconfig-
Deklarationen und die installierten Compilerbefehle (ohne Ausführung).
Die ausgegebene Fragmentdatei besitzt Forschungsstatus; sie verändert
keine Originaldateien.

## 2. Ungeprüfte Konfiguration getrennt vorbereiten

```bash
python3 q60t_kernel_stage.py \
  --source /pfad/zu/linux-4.1.10 \
  --fragment /neuer/pfad/android-candidate.cfg \
  --stage-dir /neuer/pfad/build-output
```

Die neue `build-output/.config` ist **zunächst nur eine Textkopie mit
acht experimentellen Änderungen**. Zusätzlich liegt dort ein Manifest.
Vorhandene Zielordner werden grundsätzlich nicht überschrieben.

## 3. Wichtiger Binder-ABI-Fund

**Nicht blind mit dem unmodifizierten Samsung-Quellbaum weitermachen:**
Dieser setzt in `drivers/android/Kconfig`
`ANDROID_BINDER_IPC_32BIT` ohne Eingabeprompt auf `default y`. Wenn
Binder aktiviert wird, überschreibt `olddefconfig` dadurch das gewünschte
`n`-Flag wieder mit `y`.

Die separat gelieferte Patchdatei
`porting/patches/0001-android-binder32-modern-abi.patch` stellt diesen
Standardwert nur in einer **Kopie** der Kernelquellen auf `n` um.
Dieser Eingriff ist für die **experimentelle Kconfig-Erprobung**
vorgesehen; er beweist noch keine Binder-ABI-Kompatibilität.

Den Patch zunächst an einer **Kopie** prüfen und nach eigener Kontrolle
dort anwenden:

```bash
patch --dry-run --forward -p1 -d /pfad/zu/kernel-schatten \
  -i /pfad/zu/q60t-lineage-lab/porting/patches/0001-android-binder32-modern-abi.patch
```

**Erst nach erfolgreichem Dry-Run und nur im Schattenquellbaum:**

```bash
patch --forward -p1 -d /pfad/zu/kernel-schatten \
  -i /pfad/zu/q60t-lineage-lab/porting/patches/0001-android-binder32-modern-abi.patch
```

Die Archivquellen können schreibgeschützt sein; in diesem Fall
ausschließlich die betroffene Datei der Schattenkopie schreibbar machen.

## 4. Nur Kconfig auf dem Host auflösen

```bash
make -C /pfad/zu/kernel-schatten \
  O=/neuer/pfad/build-output \
  ARCH=arm \
  CROSS_COMPILE=armv7l-tizen-linux-gnueabi- \
  HOSTCC=gcc olddefconfig
```

Dieser Befehl **führt einen Teil des fremden Kernel-Buildsystems aus**.
Nur in einer isolierten, dafür vorgesehenen Entwicklungsumgebung nutzen.
Bei Build 012 lieferte die Phase **Exitcode 0**, aber auch historische
Compiler-/Kconfig-Warnungen. Ein echtes `zImage` wurde **nicht** gebaut.

Für die maschinelle Vergleichsprüfung der originalen und gepatchten
Kconfig-Ergebnisse steht `q60t_kconfig_verify.py` zur Verfügung.
Sie kontrolliert, dass nur der Binder-ABI-Default geändert wurde und
die Samsung-Sicherheitsoptionen gleich geblieben sind.

## Grenzen und offene Entscheidungen

- Das Originalpaket enthält eine `Nike.M`-Defconfig, keine nachgewiesene
  `Nike.L`-Defconfig für exakt den Firmwarekernel 2743.0.
- `CONFIG_SECURITY_SMACK=y` und `CONFIG_SECURITY_SFD=y` bleiben
  bewusst unangetastet. Die Android-SELinux-Migration ist **nicht
  gelöst** und kein Anlass, Herstellersicherheit pauschal abzuschalten.
- Kernel 4.1.10 enthält nicht alle neueren Schnittstellen; der
  Android-Userspace, EGL/Gralloc/Composer und MediaCodec fehlen.
- Die exakte Cross-Toolchain, das echte 50-Zoll-RAM-Profil und ein
  nachgewiesener sicherer Boot-/Rollback-Weg sind noch offen.

Weder dieser Ablauf noch ein später erfolgreiches `zImage` würde
allein das Starten von LineageOS auf dem Q60T belegen.

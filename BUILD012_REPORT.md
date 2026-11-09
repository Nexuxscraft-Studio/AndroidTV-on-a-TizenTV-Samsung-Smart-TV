# Build 012 – Android-Kernel-Konfiguration und echter Kconfig-Test

Stand: **09.11.2026**. Zielgerät: **Samsung GQ50Q60TGUXZG**.
Referenz: **T-NKLDEUC 2743.0**, Kernel **Linux 4.1.10 / ARM32**.

## Ergebnis in einem Satz

Ein reproduzierbarer **Host-Kconfig-Test** des gelieferten Samsung-Kernels
ist gelungen. Dabei wurde ein automatisch aktivierter alter Binder-ABI-Modus
entdeckt, in einer **separaten Kernelkopie** mit einem Ein-Zeilen-Patch
abgestellt und anschließend durch einen zweiten echten `make olddefconfig`
verifiziert. **Kein Kernel kompiliert, kein Android gebootet.**

## 1. Neun Samsung-Konfigurationen analysiert

`q60t_android_kernel.py` liest die ARM-Defconfigs und 1.072 lokale
Kconfig-Quelldateien (3.879.502 Bytes) **ohne fremden Code auszuführen**.
Ein maschinenlesbarer Bericht liegt in
[`reports/android_kernel_build012.json`](reports/android_kernel_build012.json).

| Kennwert | Ergebnis |
| --- | --- |
| Lokale Nike-Profile | **9**, alle heißen `Nike.M-…_defconfig` |
| `Nike.L`-Defconfig | **Nicht** gefunden |
| Untersuchte Konfigurationsziele | **25** |
| Ziel bereits erfüllt | 12 |
| Im Releaseprofil deaktiviert | 7 |
| Kernelinterface nicht deklariert | 2 |
| Abweichendes Sicherheitsziel | 2 |
| Nur als Modul statt fest eingebaut | 1 |
| Nicht explizit gesetzt | 1 (Binder-ABI-Modus) |

Besonders relevant: **Alle neun Konfigurationen** deaktivieren
`CONFIG_ANDROID_BINDER_IPC`, `CONFIG_ASHMEM`, `CONFIG_MEMCG` und
`CONFIG_SECURITY_SELINUX`. `CONFIG_ION` ist im Releaseprofil
deaktiviert. `CONFIG_OVERLAY_FS` ist in den Debug-/Performance-Profilen
bereits aktiv, in den Releaseprofilen jedoch nicht.

Das Linux-4.1.10-Quellpaket enthält Kconfig-Einträge für Binder, Ashmem,
Memcg, ION, SELinux, OverlayFS und Samsung-Displaytreiber. Die in der
Prüfung gesuchten Symbole `ANDROID_BINDERFS` und `DMA_HEAPS` wurden
dagegen **nicht** als ARM-Kconfig-Optionen gefunden. Es handelt sich um
Forschungsziele, **nicht** um eine offiziell verifizierte Android-14-
Kompatibilitätsliste.

## 2. Neuer Konfigurationsentwurf

Der aus dem Original-`Nike.M-Tizen_release_defconfig` abgeleitete
Forschungsentwurf ändert **acht** Einstellungen:

```text
CONFIG_ANDROID_BINDER_IPC=y
CONFIG_ASHMEM=y
CONFIG_MEMCG=y
CONFIG_ION=y
CONFIG_EXT4_FS=y
CONFIG_OVERLAY_FS=y
CONFIG_TUN=y
# CONFIG_ANDROID_BINDER_IPC_32BIT is not set
```

Dieser Vorschlag ist **keine** fertige Android-Konfiguration. Die
Abhängigkeiten werden zunächst durch Kconfig geprüft. Insbesondere wird
`CONFIG_SECURITY_SELINUX` **nicht automatisch aktiviert**, weil das
Samsung-Profil gleichzeitig Smack und SFD benutzt und ein Eingriff in
diese Sicherheitsarchitektur sorgfältig gesondert geprüft werden muss.

Das Hilfsprogramm `q60t_kernel_stage.py` erzeugt eine
Experiment-`.config` **außerhalb** des Originalquellbaums. Es lehnt
unbekannte Optionen, automatische Deaktivierung der Samsung-Sicherheit,
einen fehlenden Binder-ABI-Override und vorhandene Ausgabeverzeichnisse ab.
Das Manifest dokumentiert Input- und Output-Hashes; es startet kein
`make` und keine weiteren Programme.

## 3. Zwei echte `olddefconfig`-Läufe

Für die experimentelle Konfiguration wurde ein isoliertes Kbuild-`O=`-
Verzeichnis erstellt. Beide Male wurde **nur die Konfigurationsphase** mit
`ARCH=arm` und dem verfügbaren Host-GCC ausgeführt; ein Cross-Compiler
war **nicht vorhanden**. Die Ausgaben der Kconfig-Kompilierung enthielten
eine GCC-Warnung zu `symbol.c` und eine Whitespace-Warnung aus
`arch/Kconfig.Csystem`; beide Befehle endeten mit **Exitcode 0**.

**Überraschung im Originalquellbaum:**

- Der erste `olddefconfig`-Durchlauf aktivierte
  `CONFIG_ANDROID_BINDER_IPC_32BIT=y` **wieder**, obwohl das Fragment
  `# CONFIG_ANDROID_BINDER_IPC_32BIT is not set` vorsah.
- Grund: `drivers/android/Kconfig` definiert die Option **ohne
  Benutzer-Prompt** mit `default y`. Die Quelltext-Hilfe warnt selbst,
  dass diese alte Einstellung zu neuerem Android-Userspace inkompatibel
  sein kann.
- Ein Textfragment allein kann diesen Kconfig-Standard nicht überstimmen.

**Experimenteller Patch:** Die Projektdatei
[`porting/patches/0001-android-binder32-modern-abi.patch`](porting/patches/0001-android-binder32-modern-abi.patch)
ändert im Android-Kconfig-Block **nur** `default y` zu `default n`.
Er wurde ausschließlich in einer **lokalen Kopie** der Samsung-Quellen
eingesetzt, nie im Originalbaum oder auf dem TV.

Der zweite `olddefconfig`-Lauf mit dieser Kopie war erfolgreich:

| Option | Ohne Patch | Mit Patch |
| --- | --- | --- |
| `CONFIG_ANDROID_BINDER_IPC` | `y` | `y` |
| `CONFIG_ANDROID_BINDER_IPC_32BIT` | **`y`** | **`n`** |
| `CONFIG_ASHMEM`, `CONFIG_MEMCG`, `CONFIG_ION` | `y` | `y` |
| `CONFIG_EXT4_FS`, `CONFIG_OVERLAY_FS`, `CONFIG_TUN` | `y` | `y` |
| `CONFIG_SECURITY_SMACK`, `CONFIG_SECURITY_SFD` | `y` | `y` |
| `CONFIG_SECURITY_SELINUX` | `n` | `n` |

**Exakt ein Konfigurationssymbol** unterscheidet beide resultierenden
`.config`-Dateien: `CONFIG_ANDROID_BINDER_IPC_32BIT`. Diese Aussage wurde
zusätzlich automatisiert mit `q60t_kconfig_verify.py` geprüft und
im Bericht
[`reports/kconfig_verify_build012.json`](reports/kconfig_verify_build012.json)
gespeichert.

## Hash- und Herkunftsbelege

| Eingabe / Ergebnis | SHA-256 |
| --- | --- |
| Original `Nike.M-Tizen_release_defconfig` | `54dab3e4d55462362d074e6ee11bac7be4d201cb0daa6b18de1454f162f06bc0` |
| Original `drivers/android/Kconfig` | `2e92b1dc5e3dc9f8822488cb4479891932eb419f9ce97d2a81167f361e74f795` |
| Bearbeitete Kconfig-Datei in separater Kopie | `f0fb7d7ec4107f642fdefa623b6e083ce3cfed9331f386b687fbfbeae348c4c3` |
| Resultierende gepatchte `.config` nach `olddefconfig` | `1289a0d2f7ba0e4ae03045edc17c752ebc633f261822ae79be39ddccb08de0d5` |

Das von Samsung bereitgestellte **Nike-L-Quellpaket** stammt aus der
vom Nutzer gelieferten Datei (Details: Build 010). **Ein exakter
Quellpatch-Match zum Firmwarestand 2743.0 ist nicht bewiesen.**

## Tests und Sicherheitsgrenzen

- **72 synthetische Unit-Tests bestanden** (Build 011: 53).
- Neuer Quellprüfer: `q60t_android_kernel.py`.
- Neues, strikt getrenntes Staging: `q60t_kernel_stage.py`.
- Neue Kconfig-Nachprüfung: `q60t_kconfig_verify.py`.
- Patch nur in einer separaten Hostkopie; Samsung-Originalquellen erhalten.
- Kein `zImage`/`uImage`, kein Android-ROM, keine Signaturerzeugung.
- **Der echte Fernseher wurde nicht kontaktiert oder verändert.**

### Noch blockiert

1. Cross-Compiler für ARM32 und Nachweis zur exakten Hersteller-Toolchain.
2. Echte Kernelkompilierung und ABI-/Binder-Userspace-Tests.
3. Samsung-SFD-/Smack- und SELinux-Konzept, **ohne ungeprüft Schutz
   auszuschalten**.
4. Grafik-HAL, Display Composer, Audio-/Media-HAL und Hardware-DRM.
5. Reales Geräteprofil und sicherer Boot-/Rollback-Pfad.

**Fazit:** Wir haben jetzt eine funktionsfähige, testbare
Kconfig-Vorbereitung für den späteren Kernel-Build. Das ist ein
technischer Fortschritt in **Phase 2A**, keine Freigabe für Phase 2B.

# Build 017 – Binder-UAPI-Gapanalyse und ARM32-ABI-Compilerprobe

**09.11.2026 · Forschungsstand · kein Zugriff auf den Samsung-TV.**

## Ergebnis

Der experimentelle Build-016-Dreifach-Binder-Treiber kompiliert. Das
allein genügt jedoch nicht für einen Android-14-Userspace. Build 017
erfasst deshalb systematisch den Unterschied zwischen **UAPI-Header**
und **tatsächlich im Treiber behandelten IOCTLs**. Der Vergleich nutzt
einen *festen offiziellen Android-Common-Kernel-Header-Commit* als
**diagnostische Teilmenge**, nicht als vollständige Android-CDD/VTS-
Konformitätsliste.

Quellen:

- [Android Common Kernel – eingefrorener Binder-UAPI-Referenzheader](https://android.googlesource.com/kernel/common/+/d04d0acdaf98506fca2e6501ed6adcdcc7d31a1f/include/uapi/linux/android/binder.h)
- [Android – Binder-IPC-Domänen](https://source.android.com/docs/core/architecture/hidl/binder-ipc)
- [Android – unterstützte Android Common Kernels](https://source.android.com/docs/core/architecture/kernel/android-common)

## Untersuchte Quellstände

- Samsung: `20_DTV_NikeL.zip` → Linux 4.1.10, ursprünglicher Binder.
- Unser Build-016-Schattenquellbaum mit experimenteller Kontexttrennung.
- Der originalen UAPI-Header ist in **beiden** Varianten identisch:
  SHA-256 `4e1fd815c026c47a227274bb70e5ec4c8a11f1b812e97aa1f1f607c932d1f021`.

`q60t_binder_abi.py` liest diese Quellen rein offline. Es erkennt
deklarierte IOCTL-Namen, `case`-Handler, Binder-Objekttypen und zusätzliche
Protokollstrukturen und erzeugt bewusst **keine** Firmwaredatei.

## Gesicherte statische Findings

| Bereich | Beobachtung im Samsung-Baum |
| --- | --- |
| Bekannte Binder-Protokollwerte | **7 und 8** als alternative Headerwerte, nicht als bestandene Laufzeit-ABI |
| Im Header deklarierte Kern-IOCTLs | 7 |
| Tatsächlich behandelte Kern-IOCTLs | **5** |
| Kern-IOCTLs ohne Handler | `BINDER_SET_IDLE_TIMEOUT`, `BINDER_SET_IDLE_PRIORITY` |
| Fehlende neuere AOSP-IOCTLs | **6** |
| Fehlende neuere Binder-Objekttypen | **2** (`BINDER_TYPE_FDA`, `BINDER_TYPE_PTR`) |
| Fehlende neuere Transaktionsmerkmale | **4** |
| Fehlende neuere UAPI-Strukturen | **4** |
| Summe unterschiedlicher fehlender Referenzmerkmale | **16** |
| Build-016-Kontexttrennung in der Schattenquelle | Statisch erkennbar, **nicht zur Laufzeit bestätigt** |

Die sechs nicht vorhandenen neueren IOCTLs sind:
`BINDER_GET_NODE_DEBUG_INFO`, `BINDER_GET_NODE_INFO_FOR_REF`,
`BINDER_SET_CONTEXT_MGR_EXT`, `BINDER_FREEZE`,
`BINDER_GET_FROZEN_INFO` und `BINDER_ENABLE_ONEWAY_SPAM_DETECTION`.
Ein moderner Userspace kann von einem Teil dieser Funktionen abhängen;
welche Kombination konkret erforderlich ist, müsste gegen einen
bestimmten LineageOS-Build getestet werden. **Kein automatischer
Backport** ist aus einer bloßen Symbolnamensliste sicher ableitbar.

Maschinenlesbare Berichte:

- `reports/binder_abi_build017_vendor.json`
- `reports/binder_abi_build017_lab.json`

Beide berichten `MODERN_BINDER_ABI_INCOMPLETE_AND_RUNTIME_UNVERIFIED`,
`android_userspace_compatible=false`, `flash_authorized=false`.

## Tatsächlich ausgeführter ARM32-Struktur-/ABI-Test

Der neue, komplett selbstgeschriebene C-Test
`porting/probes/binder_uapi_arm32.c` enthält acht überprüfbare
**Compile-Time Assertions** zum aufgelösten Binder-Protokoll,
8-Byte-Wire-Adressen, `binder_write_read`, `flat_binder_object`,
`binder_transaction_data` und zwei IOCTL-Nummern.

Die Schritte erfolgten **nur im Build-016-Schattenbaum**:

1. `make ARCH=arm INSTALL_HDR_PATH=... headers_install` – **Exitcode 0**.
2. `arm-linux-gnueabi-gcc` (GCC 6.2.1) mit `-Werror` und dem installierten
   UAPI-Header – **Exitcode 0**.
3. `file` erkennt das Ergebnis als **32-Bit-ARM-ELF-Objekt, EABI5**.

Die Ausgabe ist kein ausführbares Android-Programm, sondern ein
Cross-Compile-Testobjekt. SHA-256:
`2cabe0c63a8351fdb132c7ee5c03ec3a856749dac99dd31122cc30169d31d6fe`.

Eine direkte Einbindung der unaufbereiteten Samsung-Header scheiterte
zunächst wie zu erwarten an nicht für den Userspace installierten
Kernel-Includes. `make headers_install` hat diese Hürde korrekt gelöst.

## Qualitätssicherung und nächste technische Hürde

- **110 synthetische Python-Tests bestanden.**
- Projektaudit meldet `PASS`; nur **ein expliziter eigener C-ABI-Probe**
  wurde für die Quellcode-Paketierung freigegeben. Proprietäre `.c`-
  Dateien bleiben ausgeschlossen.
- Keine QEMU-Ausführung: Auf dem verwendeten Host war kein
  `qemu-system-arm` oder `qemu-arm` installiert. Keine Runtime-
  oder Gerätevalidierung wird vorgetäuscht.

Der nächste sinnvolle Schritt ist ein **wirklich laufender
Binder-Integrationstest in einer abgeschotteten ARM32-VM** mit passendem
Kernel-Boardprofil, initramfs und den Dienst-Managern. Dazu sind ein
QEMU-kompatibler ARM-Kernel und eine echte Testumgebung notwendig;
Samsungs unveränderte Nike.M-Konfiguration ist kein QEMU-Boardprofil.

**Der reale Q60T bleibt ausdrücklich tabu, solange Bootkette,
Recovery, echter DTB und Android-HALs nicht nachgewiesen sind.**

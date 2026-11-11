# Build 061 – Bootchain- und uImage-Forensik (read-only)

**Zielgerät:** Samsung `GQ50Q60TGUXZG` (50 Zoll), gemeldete Firmware `2743.0`.
**Branch:** `claude/build061-bootchain-uimage-forensics` (aus Build 060).
**Status:** Rein deskriptive, netzwerkfreie Analyse lokal entschlüsselter
Original-Firmwarekomponenten. **Kein** Zugriff auf den realen Fernseher, **kein**
Secure-Boot-Nachweis, **keine** Bootbarkeitsbehauptung, **kein** Flash.

Diese Analyse präzisiert `porting/BOOTCHAIN.md` (dort war `seret` bisher als
„TrustZone-Komponente" eingeordnet) und bestätigt den Stock-Kernel unabhängig
aus dem entschlüsselten `uImage`.

## Quellen (vom Nutzer bereitgestellt)

- `samsung-q60t-bootchain-2743.zip` → `seret.bin`, `secos.bin`, `ddr.init`,
  `sign.bin`.
- `Samsung-Q60T-Tizen-2743-FullOS.zip` (1.139.943.987 Bytes) → daraus gezielt nur
  `decrypted/uImage` (deflate, 7.041.296 B entpackt) und `decrypted/dtb.bin`
  (deflate, 1.564.688 B entpackt) per HTTP-Range-Request extrahiert. Die
  1,14-GB-Datei wurde **nicht** vollständig geladen; keine Samsung-Bytes im Repo.

Maschinenlesbarer Report: `reports/bootchain_forensics_build061.json`.
Reproduktion: `porting/build061/bootchain_forensics.py --components-dir <dir>`.

## 1. `seret.bin` ist ein AArch32-Linux-zImage, kein TrustZone-Monitor

SHA-256 `c97ae1b4db73c2981b13fa9b7121930d77702e8705641225c3a1506064bec728`.

Der Einstiegscode bei Offset 0 ist der positionsunabhängige Selbstrelokations-
Kopf des ARM-Decompressors (`arch/arm/boot/compressed/head.S`-Stil):

```
mov r3, pc          ; e1a0300f
sub r3, r3, #8      ; e2433008
and r0, r3, #0xfc000000   ; e203033f  (64-MB-Align)
```

Dazu die Kernel-Decompressor-Strings im Code-Bereich (`done, booting the
kernel.`, `decompressor returned an error`, `Input is not in the XZ format
(wrong magic bytes)`, `/chosen/bootargs`). Die XZ-Magic bei Offset 0xb743 ist nur
die Vergleichskonstante des `unxz`-Codes, **kein** Stream.

Entropie-Layout: `0x0–0x8000` Code (e≈4,4), `0xc000–0x1a4000` HIGH (e≈8,0),
`0x1a4000–Ende` HIGH/random. Der gepackte Payload ist mit keinem Standard-Codec
(gzip/zlib/xz/lzma/lzma-alone) auspackbar und ohne Container-Magic → konsistent
mit **verschlüsseltem bzw. nicht-standardmäßig gepacktem** Kernel-Payload.
Die exakte eingebettete Kernel-Version ist ohne HW-Schlüssel nicht extrahierbar
(kein Blocker – siehe Abschnitt 4).

## 2. `sign.bin` ist ein OpenSSL-`enc`-Blob, kein offener Hash

SHA-256 `244cbe7ef9ad8fc3f198e5f556968bd18cd0a34f986934b9c5126b6284c4b0b4`,
1040 Bytes. Nicht-Null nur in zwei Bereichen: ein 308-Byte-Kernblob
(`Salted__` + 8-Byte-Salt `cdc64090508afc06` + Chiffrat/Body) und ein
PKCS#7-Voll-Padblock (16× `0x10`).

Geprüft: **keiner** der MD5/SHA1/SHA224/SHA256/SHA384/SHA512-Werte von
`seret.bin`, `secos.bin`, `ddr.init` (oder deren Teilbereiche) kommt – roh oder
hex – in `sign.bin` vor. `sign.bin` ist also **kein Klartext-Hash**, sondern ein
mit OpenSSL (AES, salt-abgeleiteter Schlüssel via `EVP_BytesToKey`)
**verschlüsselter Signatur-/Schlüsselblock**. Ohne den im Signier-Tool / in der
Hardware liegenden Schlüssel **nicht reproduzierbar und nicht fälschbar**.
Das signierte Ziel ist aus diesen Dateien nicht ableitbar.

## 3. `secos.bin` / `ddr.init` verschlüsselt

`secos.bin` (SHA-256 `20e957cf…`, Secure OS / TrustZone) und `ddr.init`
(SHA-256 `128cb3a4…`, DDR-Training) haben Entropie ~8,0 ohne Klartext-Header.
Schlüssel vermutlich in Hardware (eFuse/OTP) → ohne Exploit nicht entschlüsselbar.
Nicht versucht.

## 4. `uImage` = unkomprimierter Stock-Kernel Linux 4.1.10, ARMv7 32-Bit

U-Boot-Legacy-Header gültig (`magic 0x27051956`):

| Feld | Wert |
| --- | --- |
| OS | 5 (Linux) |
| **arch** | **2 (ARM / AArch32)** – nicht 22 (ARM64) |
| type | 2 (kernel) |
| **compression** | **0 (keine)** |
| load / entry | `0x80008000` / `0x80008000` |
| image name | `Linux-4.1.10` |
| payload size | 7.040.960 |

Da unkomprimiert, direkt lesbar: Banner **„Linux version 4.1.10 (abuild@…)
(gcc … Tizen/Linaro GCC 6.2.1 …) #1 SMP PREEMPT"**, SoC-Strings
`SDP1412(Flattened Device Tree)`, `sdp180x_pm_…`, `nikel`. Der Payload-Einstieg
ist der ARM-`stext` mit HYP-Mode-Handling (`eor r9,r9,#0x1a`), passend zu
„CPU(s) started in HYP mode". Damit ist der Stock-Kernel unabhängig als
**AArch32** bestätigt (U-Boot-`arch=2`, 32-Bit-Load, HYP-`stext`).

Hinweis zu kexec: Im unkomprimierten Kernel sind nur Panic-Pfad-Parameternamen
(`crash_kexec_post_notifiers`) als Klartext sichtbar; diese existieren mit **und**
ohne `CONFIG_KEXEC`. Kern-kexec-Funktionsnamen lägen in der komprimierten
kallsyms-Tabelle und sind als Klartext nicht zuverlässig sichtbar; es ist **kein
IKCONFIG** eingebettet (`IKCFG_ST` fehlt) und es liegt **keine** Kernel-`.config`
oder `System.map` im FullOS-ZIP. → `CONFIG_KEXEC` ist aus dem Image allein
**nicht entscheidbar**.

## 5. `dtb.bin` = gültiger Flattened Device Tree v17

FDT-Magic `d00dfeed`, erster Baum `totalsize` 48.770 B, Version 17; die
1,56-MB-Datei ist eine Verkettung mehrerer DTBs. Modell-/SoC-Hinweise:
`samsung,dtv`, `Nike-L SoC`, `sdp-nikel`, GIC `arm,cortex-a15-gic`.

## Architektur-Schlussfolgerung (verschärft gegenüber Build 025/050)

Build 025/050 hielten „ARMv8/AArch64 als SoC-**Kandidat** plausibel" (A57-Knoten)
fest, ließen aber offen, ob die Firmware arm64 erlaubt. Diese Analyse liefert das
Mechanismus-Argument:

**EL3/Secure-Monitor läuft AArch32** (seret ist ein 32-Bit-zImage; der
Stock-Kernel startet in AArch32-HYP). Bei 32-Bit-EL3 kann `SCR_EL3.RW` nicht
gesetzt werden → niedrigere Exception-Level bleiben AArch32 → ein **arm64-Linux
kann auf dieser Firmware nicht booten**. Die A57-Kerne sind ARMv8-**Silizium**,
aber die **Firmware erlaubt nur AArch32**. Das löst den scheinbaren Widerspruch
„A57 = ARMv8" vs. „arm32-Kernel" auf und bestätigt Build 060s **arm32**-Linie;
die Build-023/024-arm64-Experimente sind für das reale Gerät Sackgassen.

## Was dadurch **nicht** gelöst ist

- Das Bootloader-/Signaturproblem bleibt: `sign.bin` ist unfälschbar,
  `secos`/`ddr.init` verschlüsselt. Kein eigener Boot ohne verifizierten Rückweg.
- Kein Zugriff auf den realen 50-Zoll-Fernseher; keine Board-/RAM-Variante
  zugeordnet.
- Die `BoardConfig.mk`-`$(error)`-Sperre bleibt bestehen.

## Tests

`python3 -m unittest discover -s porting/build061/tests -v` → **9** synthetische
Tests grün (nur Kunstdaten, keine Samsung-Bytes).

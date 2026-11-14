# Build 061 – Bootchain- & uImage-Forensik (read-only)

**Status:** Rein deskriptive, netzwerkfreie Analyse der lokal entschlüsselten
Original-Firmwarekomponenten. **Kein** Secure-Boot-Nachweis, **keine**
Bootbarkeitsbehauptung, **kein** Geräte-Flash. Fortsetzung von Build 059/060
für Samsung Q60T (`GQ50Q60TGUXZG`) / Nike-L.

## Quellen (vom Nutzer bereitgestellt, research-only)

- `samsung-q60t-bootchain-2743.zip` – Bootchain-Container mit
  `seret.bin`, `secos.bin`, `ddr.init`, `sign.bin`.
- `Samsung-Q60T-Tizen-2743-FullOS.zip` (1,14 GB) – daraus wurden **ausschließlich**
  `decrypted/uImage` und `decrypted/dtb.bin` per HTTP-Range-Request gezielt
  extrahiert (zwei Zip-Einträge, deflate), ohne die 1,14-GB-Datei vollständig
  zu laden und ohne Samsung-Bytes ins Repo zu schreiben.

## Werkzeug

```bash
# Nur gegen eine lokale Kopie der entschlüsselten Originalkomponenten:
python3 porting/build061/bootchain_forensics.py \
  --components-dir /pfad/zu/entschluesselter_firmware

# Netzwerkfreie Selbsttests (nur Kunstdaten):
python3 -m unittest discover -s porting/build061/tests -v
```

Das Skript nutzt nur die Standardbibliothek, liest keine Netzwerke, führt keine
Firmware aus und gibt keine Binärdaten aus. Es trifft keine Aussage über
Secure-Boot-Akzeptanz oder Bootbarkeit.

## Kernergebnisse (Details in `BUILD061_REPORT.md`)

1. **`seret.bin` = AArch32-Linux-zImage**, kein TrustZone-Monitor. Der
   Einstiegscode ist der PIC-Selbstrelokations-Kopf des ARM-Decompressors
   (`mov r3,pc … and r0,r3,#0xfc000000`) plus die Kernel-Decompressor-Strings.
2. **`sign.bin` = OpenSSL-`enc`-Blob** (`Salted__` + Salt + AES, salt-abgeleiteter
   Schlüssel), **kein** offener Hash der Komponenten. Ohne den HW-Schlüssel nicht
   reproduzier- oder fälschbar.
3. **`secos.bin` / `ddr.init` verschlüsselt** (Entropie ~8,0); Schlüssel
   vermutlich in eFuse/OTP.
4. **`uImage` = unkomprimierter Stock-Kernel Linux 4.1.10, ARMv7 32-Bit**
   (U-Boot `arch=2`, `comp=0`, Load/Entry `0x80008000`, HYP-bewusster `stext`),
   SoC-Hinweis `SDP1412` / `sdp-nikel`.
5. **`dtb.bin` = gültiger FDT v17** (`samsung,dtv` / `Nike-L SoC` / `sdp-nikel`).

## Architektur-Schlussfolgerung

EL3/Secure-Monitor läuft **AArch32** (seret ist ein 32-Bit-zImage, der
Stock-Kernel startet in AArch32-HYP). Bei 32-Bit-EL3 lässt sich `SCR_EL3.RW`
nicht setzen → niedrigere Exception-Level bleiben AArch32 → ein **arm64-Linux
kann nicht booten**. Die A57-Kerne sind ARMv8-Silizium, aber diese Firmware
erlaubt nur AArch32 → **Zielarchitektur ARM 32-Bit**.

Das löst nicht das Bootloader-/Signaturproblem. Die `BoardConfig.mk`-Sperre
bleibt; kein Flash, kein eigener Boot ohne separat verifizierten Rückweg.

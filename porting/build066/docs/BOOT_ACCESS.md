# Boot-Zugang: Boot-Modi und TEE-Schnittstelle (read-only)

Auswertung von `tztv-bootmode` und `trustzone-ree`. **Kein Secure-Boot-Bypass** —
nur Verständnis des Boot-Flows. Dev-/Serial-Zugang am Seriengerät hängt weiter am
signierten Bootweg (Build 061).

## TV-Boot-Modi (vom Micom gesetzt)

`tztv-bootmode` (GPL-Kernelmodul) liest den Boot-Modus, den der **Micom**
(TV-Mikrocontroller) vorgibt. Enum:

| Wert | Modus |
|---|---|
| 0 | TIZEN_BOOTING (normal) |
| 1 | EARLY_WARNING_BOOTING |
| 2 | EARLY_WARNING_UPGRADE |
| 3 | EARLY_WARNING_DDR_TEST |
| 4 | EARLY_WARNING_RELEASE_MODE |
| 5 | EARLY_WARNING_BACKGROUND |
| 6 | EARLY_WARNING_HDMI_CALIBRATION |

Der Modus kommt über das DT-Node `tztv_bootmode`:
- `communication-mode = "gpio"` → GPIO `ew-select` (invertiert), oder
- `communication-mode = "reg"` → Register-Adresse in `ew-select`, Wert `& 0x7`
  (`Soc_BootMode_Tizen=0`, `Soc_BootMode_EW=1`).

Das sind die „S/E"-Modi aus der Übergabe. Praktische Bedeutung: Service-/Factory-
Boot-Pfade existieren und werden per GPIO/Register gewählt. **Das erklärt den
Mechanismus**, umgeht aber keine Signaturprüfung.

## TEE-Schnittstelle (`trustzone-ree`)

GlobalPlatform **TEE Client API** (REE-Seite, nur Header: `tee_client_api.h`,
`teex_client_api.h` + TrustwareOS-private Header). Das ist die normale
Normal-World-Schnittstelle, um mit der Secure World (TrustZone) zu sprechen —
**keine Schlüssel, keine Secrets, kein Bypass**. Relevant nur zum Verständnis,
wie Userspace TEE-Dienste (z. B. Signaturprüfung) aufruft.

## Folgerung

- Boot-Modus-Mechanismus verstanden (Micom-gesteuert, GPIO/Register).
- Für echten Dev-/Serial-Zugang bleibt der signierte Bootweg der Gate.
- Nächster legitimer Schritt am Gerät: UART-Konsole (Build 059 `ttySDP0`,
  `0x10090A00`) physisch anzapfen und den vom Micom gesetzten Modus beobachten.

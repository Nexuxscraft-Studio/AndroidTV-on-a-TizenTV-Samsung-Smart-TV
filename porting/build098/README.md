# Build 098 – Safe RAM Boot Readiness

Ziel ist der Samsung GQ50Q60TGUXZG mit Nike-L/SDP1804 und Referenzfirmware
T-NKLDEUC 2743.0. Das [Manifest](manifest.json) enthält den Befund und
den fehlenden Nachweis je Prüfgebiet. Die Analyse verwendet eingecheckte
Berichte früherer Binär- und DTB-Auswertungen. Die Originaldateien
wurden für diesen Build nicht erneut geprüft. Die historischen Aussagen
zu Verschlüsselung und Secure-Monitor-Zustand bleiben Interpretationen.

| Stock-DTB-Profil | Bundle-Offset | Deklarierte RAM-Bänke (Basis und MiB) |
| --- | --- | --- |
| 2 GiB | 0x0 | 0x40000000 + 320, 0xa2000000 + 988, 0xe4000000 + 152,5 |
| 1,5 GiB | 0x15000 | 0x40000000 + 120, 0x4f000000 + 268, 0xa2000000 + 480, 0xca000000 + 250,25 |

Die Bereiche stammen aus dem [DTB-Bericht](../../reports/hardware_2743.0_build004_final.json).
Die Header-Adresse 0x80008000 fällt in keinem Profil in eine dieser Banken.
Der Widerspruch bleibt offen. Lücken zwischen den Banken und Einträge ohne
vollständig geklärte Semantik sind für die Platzierungsplanung gesperrt.
Der Header und die DTB-Profile erlauben keine Ableitung einer neuen Adresse.

Ein temporärer RAM-Boot bleibt hypothetisch. Voraussetzung sind ein
nachgewiesener authentifizierter Einstieg mit erlaubtem Image, ein
vollständig belegter Handoff mit kollisionsfreien Speicherbereichen und ein
erprobter Wiederherstellungsweg für dieselbe Board-/RAM-Revision. Der
Hosttest überprüft Quellenbindung, beide archivierten Profile, den
Adresswiderspruch und die weiterhin offene Bootentscheidung.

    python3 -m unittest discover -s porting/build098/tests -v

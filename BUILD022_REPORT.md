# Build 022 – Official LineageOS ARM32/QEMU-virt Preflight

**Branch:** `feature/build022-lineage-arm32-preflight`  
**Stand:** Host-only Planungs- und Prüfwerkzeuge; QEMU-LineageOS-Boot **nicht** nachgewiesen.  
**Unverändert:** Build 018, 020, 021 und Samsung-Originalkernel. **Kein TV-Flash.**

## Implementiert

- Vier **existierende offizielle** LineageOS-Manifest-Branches samt
  recherchierter Commit- und Git-Blob-Hashes in
  `porting/lineage_virtual/lineage-source-candidates.json` dokumentiert.
  **Keine** LineageOS-Version als kompatibel ausgewählt.
- `q60t_lineage_preflight.py` verifiziert wahlweise ein *lokal
  bereitgestelltes* offizielles `default.xml` per Git-Blob-Hash und
  untersucht die tatsächliche QEMU-Kernel-`.config` auf elementare
  Android-Treiber-/Kernel-Schalter. Ergebnisse belegen keine vollständige
  Android-Kompatibilität und der Generator verweigert veränderte
  Manifestdateien.
- QEMU-`virt`-ARM32-Hardwareprofil und der schrittweise
  Android-Init-/Service-Anforderungskatalog mit noch offenen Gates.
- `q60t_lineage_init_evidence.py`: liest spätere QEMU-Seriellogs,
  erkennt Hinweise auf Android-Init/Services und unterscheidet diese
  ausdrücklich von einem **verifizierten** LineageOS-Boot.
- Synthetische Tests; **kein** `repo sync`, kein Kernel- oder Android-Build,
  keine Runtime-Binaries im Repository.

## Blocker vor einem ARM32-Android-TV-Build

1. Offizielles LineageOS-Checkout für einen Kandidaten auf separatem
   Build-Volume, inklusive vollständig aufgelöster Projekt-Revisionsbasis.
2. QEMU-`virt`-spezifischer ARM32-Device-Tree plus Android-TV-Product-Target;
   Goldfish/Ranchu-Produkte sind dafür kein Ersatz.
3. Per Kandidat Kernel/Android ABI, SELinux-Policy und Systemdienste prüfen.
4. Danach nachweisbarer echter Android-Init-Start unter QEMU.
5. Echte Samsung-Hardware bleibt eine völlig separate, spätere Aufgabe.

## Tests

```bash
python3 -m unittest discover -s tests -q
python3 q60t_lineage_preflight.py --candidate cm-14.1
python3 q60t_release_audit.py .
```

Details und spätere Proxmox-Kommandos:
`porting/lineage_virtual/README.md`.

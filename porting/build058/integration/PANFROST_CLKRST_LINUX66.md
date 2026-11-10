# Build 058 – Panfrost (Linux 6.6.162) und der Nike-L-GPU-Clock/Reset-Prototyp

Stand: 10.11.2026. Quelle: `drivers/gpu/drm/panfrost/` aus Linux 6.6.162
(Commit `5139929c698c273e07cb0635732f6a918a7b8e78`), direkt gelesen.
**Keine Hardwareaktivierung. Der Prototyp bleibt fail-closed.**

## Was Panfrost 6.6.162 vom Device Tree und den Providern erwartet

| Ressource | Aufruf in Panfrost | Pflicht? |
|---|---|---|
| GPU-Takt | `devm_clk_get(dev, NULL)` – der **erste** `clocks`-Eintrag, dann `clk_get_rate()` + `clk_prepare_enable()` | **ja** |
| Bustakt | `devm_clk_get_optional(dev, "bus")` | nein |
| Resets | `devm_reset_control_array_get_optional_exclusive()` – **alle** `resets`-Einträge als ein Array, gemeinsam deasserted | nein |
| Spannung | `default_supplies = { "mali" }` (Regulator) | über Kompatibilitätsdaten |
| Power-Domain | `num_pm_domains = 1` (optional) | nein |
| OPP-Tabelle | `devm_pm_opp_of_add_table()`; bei `-ENODEV` läuft Panfrost **ohne** devfreq weiter | nein |
| IRQs | `platform_get_irq_byname()` mit `"job"`, `"mmu"`, `"gpu"` | **ja** |
| Kompatibel | generisch `"arm,mali-bifrost"`; Mali-G51 = `GPU_MODEL(g51, 0x7000)` in `panfrost_gpu.c` | — |

Build 056 hat aus Samsungs DT `JOB 0x72`, `MMU 0x71`, `GPU 0x70` abgeleitet.
Ein zukünftiger Knoten bräuchte `interrupt-names = "job", "mmu", "gpu"` in
genau der Reihenfolge der `interrupts`-Einträge. Der Triggertyp ist weiterhin
**unbestätigt**.

## Reihenfolge in Panfrost 6.6.162

`panfrost_device_init()`:

1. `panfrost_clk_init()` → `clk_prepare_enable(gpu_clk)`
2. `panfrost_devfreq_init()`
3. `panfrost_regulator_init()`
4. `panfrost_reset_init()` → `reset_control_deassert(alle)`
5. `panfrost_pm_domain_init()`, ioremap, `panfrost_gpu_init()` …

`panfrost_device_fini()` (Unbind/Fehlerpfad):

1. `… gpu_fini`, `pm_domain_fini`
2. `panfrost_reset_fini()` → `reset_control_assert(alle)`
3. `devfreq_fini`, `regulator_fini`
4. `panfrost_clk_fini()` → `clk_disable_unprepare(gpu_clk)`

`panfrost_device_suspend/resume()` (System- **und** Runtime-PM über
`EXPORT_GPL_RUNTIME_DEV_PM_OPS`) rufen nur devfreq und GPU-Power-Off/On auf.
**Takt und Reset werden in 6.6.162 nicht im Runtime-PM geschaltet.**

## Konflikt mit dem Build-058-Prototyp

`kernel/sdp_nikel_gpu_clkrst.c` bildet Samsungs Sequenz im Takt-Callback ab:

- `.enable`: Clock-Gate an → BUSIF-Reset lösen → CORE-Reset lösen → Idle-Request löschen
- `.disable`: Idle-Request → auf Idle-Ack warten → BUSIF/CORE-Reset setzen → Clock-Gate aus

Mit Panfrost 6.6.162 ergibt das:

| Phase | Panfrost-Schritt | Wirkung im Prototyp | Bewertung |
|---|---|---|---|
| Probe | `clk_prepare_enable` | Takt an **und** beide Resets gelöst | Resets sind schon vor `reset_init` frei |
| Probe | `reset_control_deassert` | Bits erneut auf 1 (idempotent) | unkritisch |
| Unbind | `reset_control_assert` | BUSIF/CORE-Reset gesetzt, **ohne** Idle-Handshake | **weicht von Samsungs Reihenfolge ab** |
| Unbind | `clk_disable_unprepare` | Idle-Request **nach** dem Reset, dann Warten auf Ack | Ack eines GPU-Busses im Reset ist undefiniert; Timeout wahrscheinlich, Takt bleibt an |

Damit gibt es **zwei Eigentümer derselben Reset-Bits**: den Takt-Callback und
den Reset-Controller. Samsungs Ablauf „erst Idle, dann Reset, dann Takt aus“
bleibt mit Upstream-Panfrost nicht erhalten.

## Mögliche Designs (keins ist aktiviert)

1. **Reset nur über den Reset-Controller.** Der Takt-Callback schaltet nur
   Bit 12 (`0x088c`). Der Idle-Handshake käme in `.assert` vor dem Setzen der
   Reset-Bits. Panfrost ruft `assert` vor `clk_disable`, daher stimmt die
   Reihenfolge Idle → Reset → Takt aus wieder.
2. **Ein gemeinsamer Ablauf über eine Power-Domain (genpd).** Samsungs
   Gesamtsequenz liegt im `power_on/power_off` einer PM-Domain. Panfrost
   unterstützt `power-domains` bereits. Dann gibt es keinen `resets`-Eintrag
   im GPU-Knoten.
3. Unverändert lassen: **nicht vertretbar**, siehe Tabelle.

Welche Variante zu Samsungs echter Hardware passt (z. B. ob Idle-Ack bei
gesetztem BUSIF-Reset überhaupt gültig ist), ist **nicht belegt**. Das muss
vor jeder Aktivierung mit Samsungs Kbase-Pfad (`mali_kbase_platform_sdp.c`)
verglichen werden, siehe Build 057.

## Weitere offene Punkte für eine echte GPU-Bindung

- `clk_get_rate()` liefert beim Prototyp 0 (kein Parent, kein `recalc_rate`).
  Panfrost protokolliert nur `clock rate = 0`. devfreq bleibt ohne OPP-Tabelle
  aus. Für eine sinnvolle Frequenz fehlen Parent und Teiler aus Samsungs
  `samsung,sdp1804-clock`.
- GPU-ID-Register (Offset `0x0000` im GPU-MMIO `0x00500000`) des echten
  Fernsehers ist **nicht ausgelesen**. Erwartet wird für G51 `0x7000` in den
  oberen 16 Bit; das ist eine Erwartung, keine Messung.
- Mali-Regulator (`mali`-Supply), Power-Domain und AXI-/Kohärenzanbindung
  sind unbekannt.

# Build 074 — REA Reverse Engineering CI (read-only)

**Target:** Samsung Q60T 50-inch GQ50Q60TGUXZG, offline evidence for
T-NKLDEUC 2743.0. No TV/root/SDB/bootloader interactions.

## Live REA evidence supplied by the project owner (12 November 2026)

The owner executed REA 6.9.0 on an existing server file:

- Source (on server, not checked into Git):
  \`/opt/samsung-atv-lab/samsung/firmware-2743/decrypted/uImage\`
- File SHA-256:
  \`6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2\`
- REA classified it as a valid **legacy uImage** (Linux / ARM / kernel).
- uImage header name: \`Linux-4.1.10\`.
- Declared load and entry: \`0x80008000\` each.
- REA reports header/data CRCs valid.
- uImage file size **7,041,296 bytes**; declared payload **7,040,960 bytes**.
  The 64-byte legacy header leaves **272 bytes beyond the declared payload**.
  Their role is **unknown**; do not infer Samsung signatures or harmless padding.
- Header timestamp: \`2026-07-02T08:47:03Z\` (metadata only; not
  independently authenticated firmware provenance).
- Source digest and measured shape were supplied by user command output;
  **the CI job has not independently validated the bytes yet.**

The observed uImage header alone does NOT prove an actual U-Boot bootloader,
executable load address on the specific 50-inch PCB, firmware authentication
policy, successful \`kexec\`, or a reversible RAM boot. Build 071/072 safety
status remains **BLOCKED / NOT_DEMONSTRATED**.

## Design and security

- **Manual workflow only**: \`.github/workflows/build074-rea-offline.yml\`.
  \`workflow_dispatch\` on the reviewed **main** branch; no \`push\`,
  \`pull_request\`, \`pull_request_target\` or untrusted code on the self-hosted
  runner.
- Runner labels: \`[self-hosted, Linux, X64]\`; uses the same concurrency group
  as Build 068/070 to avoid overloading the single server.
- Node.js **24.22.1** via \`actions/setup-node\`; does **not** change system
  Node.js 20.19.2.
- Installs **rea-agents@6.9.0** under \`$RUNNER_TEMP/build074-rea-tool\`,
  without global npm writes. Uses upstream's documented \`--ignore-scripts\`
  workflow; native providers/addons are not assumed ready.
- Runs the source through \`rea inspect-artifact\` (uImage) or
  \`rea inspect-devicetree\` (optional extracted DTB). Both are offline/static.
- Independent Python SHA-256 checks REA's reported identity, checks magic,
  bounded regular file, path containment, and refuses symlinks. For uImage,
  requires verified CRC and ARM/kernel identity; mismatches fail closed.
- **Only the sanitized report is uploaded** (7-day retention); no original
  firmware, DTB node text, raw REA JSON or stderr containing private paths.
- No root, apt upgrade, SDB, writing to the TV, flashing, kernel invocation,
  decryption, or Secure Boot modification.

### What the generated artifact contains

\`sanitized-report.json\` with file hash/size, verified metadata, declared
addresses, and the 272-byte **unknown** suffix length, as applicable. A DTB
report contains no raw nodes or properties (which might reveal private board
IDs, MAC addresses, serials or bootargs). Runtime addresses are declarations
from the uImage, not verified access rights or memory-map facts.

## Running on GitHub

The workflow is introduced through a **draft PR** stacked on Build 073.
GitHub's **Run workflow** button on \`main\` becomes usable once the relevant
PR stack is reviewed and merged. The workflow deliberately rejects arbitrary
feature branch execution.

1. Confirm the self-hosted runner is online. The account running that runner
   must be able to read the source; the file being accessible to \`root\` on
   the same Debian server does **not** guarantee runner access.
2. On GitHub open **Actions → Build074 REA offline Samsung evidence** and
   select **Run workflow**, with branch **main**.
3. Select \`target: uimage\`. This uses the **observed** source path:
   \`/opt/samsung-atv-lab/samsung/firmware-2743/decrypted/uImage\`.
4. Inspect the job summary and download
   \`build074-rea-summary-<run>-<attempt>\` when successful.
   No complete firmware image is uploaded.

### Optional DTB

To analyze an **existing, already extracted** FDT blob:

1. Verify a \`*.dtb\` file actually exists under the same decrypted evidence
   directory, and that the GitHub Actions runner can read it. This workflow
   does not guess a filename or extract it from \`dtb.bin\`.
2. Select \`target: dtb\` and provide its **simple basename only** in
   \`dtb_filename\` (no slashes, e.g. \`dtb0.dtb\` if that file exists).
3. The script requires FDT magic, valid REA parse, bounded size, and consistent
   source digest. The CI artifact omits DTB contents.

For private/full inspection, run REA locally outside CI and retain the raw
output privately. Do not post detailed raw firmware/DTB evidence to public CI.

## Preflight on server (optional, read-only)

Check as **the runner service's Linux user**, not only \`root\`:

\`\`\`bash
test -r /opt/samsung-atv-lab/samsung/firmware-2743/decrypted/uImage &&
  echo "Readable for this user" || echo "Not readable for this user"
stat -c '%s bytes' /opt/samsung-atv-lab/samsung/firmware-2743/decrypted/uImage
\`\`\`

Do **not** solve permission failures with \`chmod -R 777\` or elevated
workflow execution. Restrict access to the required evidence file for the
runner account if needed.

## Synthetic tests

\`\`\`bash
python3 -m unittest discover -s porting/build074/tests -v
python3 -m py_compile porting/build074/rea_ci.py
\`\`\`

No actual CI run has been completed by creating these files. The tests use
synthetic REA envelopes; live behavior remains **UNVERIFIED** until the first
manual workflow run.

## Future expansion — headless Ghidra

Keep **ARM32 Ghidra disassembly** separate from the initial artifact-inspection
job. Install and verify a Ghidra 12.x release (>=12.1) and compatible full JDK
(e.g. Ghidra 12.1.x with JDK 21) on the Linux x64 host, set
\`GHIDRA_INSTALL_DIR\` and \`JAVA_HOME\`, run
\`rea doctor --provider ghidra --json\`, and analyze a **separately verified
native executable** in an isolated, resource-limited workflow. Do not treat
the raw whole-uImage container as a normal ARM32 ELF or infer a valid processor
mapping from file extension.

### Sources

- https://github.com/morluto/rea/blob/main/docs/ci-analysis.md
- https://github.com/morluto/rea/blob/main/docs/uimage.md
- https://github.com/morluto/rea/blob/main/docs/devicetree.md
- https://github.com/morluto/rea/blob/main/docs/guides/native/native-investigation.md
- https://github.com/morluto/rea/blob/main/docs/getting-started/installation.md

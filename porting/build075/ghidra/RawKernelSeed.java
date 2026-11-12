// Build075: Ghidra headless pre-analysis seed for the declared uImage entry.
// Deliberately works only in the temporary, read-only Ghidra project.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class RawKernelSeed extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address candidateEntry = toAddr(0x80008000L);
        if (!currentProgram.getMemory().contains(candidateEntry)) {
            throw new IllegalStateException("Raw import is not mapped at 0x80008000");
        }
        createLabel(candidateEntry, "uimage_declared_entry_candidate", true);
        boolean decoded = disassemble(candidateEntry);
        println("BUILD075_ENTRY_ASSUMPTION: 0x80008000");
        println("BUILD075_ENTRY_DISASSEMBLY_SEEDED: " + decoded);
        println("BUILD075_RUNTIME_MAPPING_VERIFIED: false");
    }
}

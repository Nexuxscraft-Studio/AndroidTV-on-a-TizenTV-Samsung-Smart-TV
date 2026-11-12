// Build075: small, read-only disassembly evidence near a proposed ARM zImage entry.
// Raw ARM kernel images may contain compressed data. Never disassemble all bytes
// and count them as confirmed instructions, or infer a validated boot entry.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.Memory;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

public class RawKernelAudit extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address start = toAddr(0x80008000L);
        Memory memory = currentProgram.getMemory();
        if (!memory.contains(start)) {
            throw new IllegalStateException("Raw import did not map intended base address");
        }
        byte[] head = new byte[64];
        int read = memory.getBytes(start, head);
        if (read != head.length) {
            throw new IllegalStateException("Raw import short read at candidate entry");
        }
        ByteBuffer bb = ByteBuffer.wrap(head).order(ByteOrder.LITTLE_ENDIAN);
        int magic = bb.getInt(0x24);
        boolean isZimage = (magic == 0x016f2818);
        println("BUILD075_PROGRAM: " + currentProgram.getName());
        println("BUILD075_GHIDRA_IMAGE_BASE: " + currentProgram.getImageBase());
        println("BUILD075_PROCESSOR: " + currentProgram.getLanguageID());
        println("BUILD075_ZIMAGE_MAGIC_AT_OFFSET_0x24: " + isZimage);
        println("BUILD075_DECLARED_START_WORD: 0x" + Integer.toHexString(bb.getInt(0x28)));
        println("BUILD075_DECLARED_END_WORD: 0x" + Integer.toHexString(bb.getInt(0x2c)));
        println("BUILD075_EARLY_INSTRUCTIONS_ONLY:");
        for (int offset = 0; offset < 0x24; offset += 4) {
            Address address = start.add(offset);
            Instruction insn = currentProgram.getListing().getInstructionAt(address);
            println("  " + address + ": " + (insn == null ? "<not decoded>" : insn.toString()));
        }
        println("BUILD075_FULL_DECOMPRESSED_KERNEL_AVAILABLE: false");
        println("BUILD075_TV_BOOT_EXECUTED: false");
    }
}

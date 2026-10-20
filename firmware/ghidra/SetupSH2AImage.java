// Pre-script for DDJ-1000 SH-2A images imported as raw binary.
// Parses the startup section table at image+0x10 (8 groups x 12 words:
// 3x {dst,src,len} copy, 1x {dst,len} zero-fill, 1x link), creates RAM blocks
// initialised from the flash copy, fills the rest of on-chip RAM/IO with
// uninitialised blocks, and marks the reset vector as entry.
//@category DDJ1000
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.SourceType;
import java.io.ByteArrayInputStream;
import java.util.*;

public class SetupSH2AImage extends GhidraScript {
    Memory mem;
    AddressSpace sp;

    Address a(long v) { return sp.getAddress(v & 0xffffffffL); }

    int rd(long addr) throws Exception { return mem.getInt(a(addr)); }

    boolean overlaps(long start, long len) {
        for (MemoryBlock b : mem.getBlocks()) {
            long bs = b.getStart().getOffset(), be = b.getEnd().getOffset();
            if (start <= be && start + len - 1 >= bs) return true;
        }
        return false;
    }

    void fillGaps(String prefix, long start, long end, boolean volatileIo) throws Exception {
        // create uninitialised blocks over [start,end) wherever nothing exists yet
        List<long[]> used = new ArrayList<>();
        for (MemoryBlock b : mem.getBlocks()) used.add(new long[]{b.getStart().getOffset(), b.getEnd().getOffset() + 1});
        used.sort(Comparator.comparingLong(x -> x[0]));
        long cur = start;
        for (long[] u : used) {
            if (u[1] <= cur || u[0] >= end) continue;
            if (u[0] > cur) mk(prefix, cur, u[0] - cur, volatileIo);
            cur = Math.max(cur, u[1]);
        }
        if (cur < end) mk(prefix, cur, end - cur, volatileIo);
    }

    void mk(String prefix, long s, long len, boolean vol) throws Exception {
        MemoryBlock b = mem.createUninitializedBlock(String.format("%s_%08x", prefix, s), a(s), len, false);
        b.setRead(true); b.setWrite(true); b.setExecute(!vol); b.setVolatile(vol);
        println(String.format("  uninit %-22s %08x..%08x", b.getName(), s, s + len - 1));
    }

    @Override
    protected void run() throws Exception {
        mem = currentProgram.getMemory();
        sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        MemoryBlock flash = mem.getBlocks()[0];
        long fbase = flash.getStart().getOffset();
        flash.setWrite(false); flash.setExecute(true);
        flash.setName("FLASH");
        println(String.format("flash image @ %08x size %x", fbase, flash.getSize()));

        long resetPc = rd(fbase) & 0xffffffffL, resetSp = rd(fbase + 4) & 0xffffffffL;
        println(String.format("reset PC=%08x SP=%08x", resetPc, resetSp));

        int groups = getScriptArgs().length > 0 ? Integer.parseInt(getScriptArgs()[0]) : 8;
        println("descriptor groups: " + groups);
        for (int g = 0; g < groups; g++) {
            long p = fbase + 0x10 + g * 0x30;
            for (int t = 0; t < 3; t++) {
                long dst = rd(p + t * 12) & 0xffffffffL, src = rd(p + t * 12 + 4) & 0xffffffffL, len = rd(p + t * 12 + 8) & 0xffffffffL;
                if (len == 0) continue;
                if (src < fbase || src + len > fbase + flash.getSize()) { println(String.format("  skip copy %08x<-%08x len %x (src outside image)", dst, src, len)); continue; }
                byte[] buf = new byte[(int) len];
                mem.getBytes(a(src), buf);
                if (overlaps(dst, len)) { println(String.format("  OVERLAP copy %08x len %x - skipped", dst, len)); continue; }
                MemoryBlock b = mem.createInitializedBlock(String.format("g%d_s%d_%08x", g, t, dst), a(dst), new ByteArrayInputStream(buf), len, monitor, false);
                b.setRead(true); b.setWrite(t == 2); b.setExecute(t == 0);  // s0=code(P) s1=const(C) read-only, s2=data(D)
                b.setComment(String.format("copied from %08x", src));
                println(String.format("  copy   %-22s %08x..%08x <- %08x", b.getName(), dst, dst + len - 1, src));
            }
            long bdst = rd(p + 36) & 0xffffffffL, blen = rd(p + 40) & 0xffffffffL;
            if (blen != 0 && !overlaps(bdst, blen)) {
                MemoryBlock b = mem.createUninitializedBlock(String.format("g%d_bss_%08x", g, bdst), a(bdst), blen, false);
                b.setRead(true); b.setWrite(true);
                println(String.format("  bss    %-22s %08x..%08x", b.getName(), bdst, bdst + blen - 1));
            }
        }
        // remaining on-chip RAM, large on-chip RAM window and peripheral I/O
        fillGaps("ram", 0x1c000000L, 0x1c300000L, false);
        fillGaps("ramnc", 0x3c000000L, 0x3c300000L, false);
        fillGaps("ocram", 0xfff80000L, 0xfffa0000L, false);
        fillGaps("io", 0xfffc0000L, 0x100000000L, true);

        Address ep = a(resetPc);
        currentProgram.getSymbolTable().addExternalEntryPoint(ep);
        createLabel(ep, "Reset", true, SourceType.USER_DEFINED);
        disassemble(ep);
        createFunction(ep, "Reset");
    }
}

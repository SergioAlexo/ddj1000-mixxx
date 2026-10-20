// Headless query helper. Args: <cmd> [params...]; several commands may be chained with ";"
//  stats                      function count / coverage
//  sweep                      create functions at SH prologues (sts.l pr,@-r15 after push run) in exec RAM blocks, re-analyse
//  dec <addr|name> [...]      decompile function(s) containing addr
//  dis <addr> <n>             disassemble n code units
//  xr <addr>                  references to addr (with containing function)
//  lit <lo> [hi]              find 32-bit literals in [lo,hi] (default lo==hi) in initialised memory, report users
//  callers <addr>             functions calling function at addr
//  callees <addr>             functions called by function at addr
//  funcs [lo hi]              list functions in range
//  ren <addr> <name>          rename/create function at addr
//  cmt <addr> <text...>       set plate comment
//@category DDJ1000
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import java.util.*;

public class Q extends GhidraScript {
    AddressSpace sp;
    Address A(String s) {
        Function f = getGlobalFunctions(s).isEmpty() ? null : getGlobalFunctions(s).get(0);
        if (f != null) return f.getEntryPoint();
        return sp.getAddress(Long.parseUnsignedLong(s.replace("0x", ""), 16));
    }
    String fn(Address a) {
        Function f = getFunctionContaining(a);
        return f == null ? "?" : f.getName() + "@" + f.getEntryPoint();
    }

    @Override
    protected void run() throws Exception {
        sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        String all = String.join(" ", getScriptArgs());
        for (String c : all.split(";")) {
            String[] a = c.trim().split("\\s+");
            if (a.length == 0 || a[0].isEmpty()) continue;
            println("=== " + c.trim());
            switch (a[0]) {
                case "stats": stats(); break;
                case "constpool": constpool(); break;
                case "up": up(getFunctionContaining(A(a[1])), 0, a.length > 2 ? Integer.parseInt(a[2]) : 6, new HashSet<>()); break;
                case "hex": { Address ad = A(a[1]); int n = Integer.parseInt(a[2]); byte[] b = new byte[n]; currentProgram.getMemory().getBytes(ad, b);
                    for (int i = 0; i < n; i += 16) { StringBuilder sb = new StringBuilder(String.format("  %s:", ad.add(i))); for (int j = i; j < Math.min(n, i + 16); j += 4) { sb.append(' '); for (int k = j; k < Math.min(n, j + 4); k++) sb.append(String.format("%02x", b[k])); } println(sb.toString()); } break; }
                case "mkio": { long lo = Long.parseUnsignedLong(a[1],16), hi = Long.parseUnsignedLong(a[2],16);
                    MemoryBlock b = currentProgram.getMemory().createUninitializedBlock(a.length > 3 ? a[3] : String.format("io_%08x", lo), sp.getAddress(lo), hi - lo, false); b.setRead(true); b.setWrite(true); b.setVolatile(true); println("  created " + b.getName()); break; }
                case "io": io(Long.parseUnsignedLong(a.length>1?a[1]:"fff80000",16), Long.parseUnsignedLong(a.length>2?a[2]:"ffffffff",16), a.length>3 ? Integer.parseInt(a[3]) : 8); break;
                case "callovr": callovr(); break;
                case "blocks": for (MemoryBlock b : currentProgram.getMemory().getBlocks()) println(String.format("  %-22s %s-%s %s%s%s%s %s", b.getName(), b.getStart(), b.getEnd(), b.isRead()?"r":"-", b.isWrite()?"w":"-", b.isExecute()?"x":"-", b.isVolatile()?"v":"", b.isInitialized()?"init":"")); break;
                case "sweep": sweep(); break;
                case "dec": for (int i = 1; i < a.length; i++) dec(A(a[i])); break;
                case "dis": dis(A(a[1]), Integer.parseInt(a[2])); break;
                case "xr": xr(A(a[1])); break;
                case "lit": lit(Long.parseUnsignedLong(a[1].replace("0x",""),16), Long.parseUnsignedLong((a.length > 2 ? a[2] : a[1]).replace("0x",""),16)); break;
                case "callers": { Function f = getFunctionContaining(A(a[1])); for (Function g : f.getCallingFunctions(monitor)) println("  " + g.getName() + "@" + g.getEntryPoint()); break; }
                case "callees": { Function f = getFunctionContaining(A(a[1])); for (Function g : f.getCalledFunctions(monitor)) println("  " + g.getName() + "@" + g.getEntryPoint()); break; }
                case "funcs": funcs(a); break;
                case "ren": { Address ad = A(a[1]); Function f = getFunctionAt(ad); if (f == null) { disassemble(ad); f = createFunction(ad, a[2]); } else f.setName(a[2], SourceType.USER_DEFINED); println("  " + a[2] + " @ " + ad); break; }
                case "cmt": { Address ad = A(a[1]); setPlateComment(ad, c.trim().split("\\s+", 3)[2]); break; }
                default: println("unknown " + a[0]);
            }
        }
    }

    void constpool() throws Exception {
        // literal pools inside code/const blocks: define as dword/pointer with CONSTANT mutability so the decompiler folds them
        int n = 0;
        Listing l = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized() || b.isWrite() || b.getName().equals("FLASH")) continue;
            for (Instruction ins : l.getInstructions(new AddressSet(b.getStart(), b.getEnd()), true)) {
                for (Reference r : ins.getReferencesFrom()) {
                    if (!r.getReferenceType().isRead()) continue;
                    Address t = r.getToAddress();
                    MemoryBlock tb = mem.getBlock(t);
                    if (tb == null || tb.isWrite() || !tb.isInitialized()) continue;
                    Data d = l.getDataAt(t);
                    if (d == null) { try { d = l.createData(t, ghidra.program.model.data.DWordDataType.dataType); } catch (Exception e) { continue; } }
                    ghidra.program.model.data.MutabilitySettingsDefinition.DEF.setChoice(d, ghidra.program.model.data.MutabilitySettingsDefinition.CONSTANT);
                    n++;
                }
            }
        }
        println("constant pool items: " + n);
    }

    void callovr() throws Exception {
        // resolve "mov.l @(disp,pc),Rn ... jsr @Rn" into call-override references
        Listing l = currentProgram.getListing();
        Memory mem = currentProgram.getMemory();
        ReferenceManager rm = currentProgram.getReferenceManager();
        int n = 0, made = 0;
        for (Instruction ins : l.getInstructions(true)) {
            String m = ins.getMnemonicString();
            if (!(m.equals("jsr") || m.equals("jsr/n") || m.equals("jmp"))) continue;
            Object[] ops = ins.getOpObjects(0);
            if (ops.length != 1 || !(ops[0] instanceof ghidra.program.model.lang.Register)) continue;
            String rn = ((ghidra.program.model.lang.Register) ops[0]).getName();
            n++;
            Instruction p = ins.getPrevious();
            Long target = null;
            for (int k = 0; k < 24 && p != null; k++, p = p.getPrevious()) {
                if (p.getFlowType().isJump() || p.getFlowType().isCall() || p.getFlowType().isTerminal()) break;
                // does p write rn?
                boolean writes = false;
                for (Object o : p.getResultObjects()) if (o instanceof ghidra.program.model.lang.Register && ((ghidra.program.model.lang.Register) o).getName().equals(rn)) writes = true;
                if (!writes) continue;
                if (p.getMnemonicString().equals("mov.l") && p.toString().contains("@(") && p.toString().contains("pc")) {
                    for (Reference r : p.getReferencesFrom()) {
                        if (r.getReferenceType().isRead()) target = mem.getInt(r.getToAddress()) & 0xffffffffL;
                    }
                } else if (p.getMnemonicString().startsWith("movi20")) {
                    Object[] o0 = p.getOpObjects(0);
                    if (o0.length == 1 && o0[0] instanceof ghidra.program.model.scalar.Scalar) target = ((ghidra.program.model.scalar.Scalar) o0[0]).getUnsignedValue() & 0xffffffffL;
                }
                break;
            }
            if (target == null) continue;
            Address t = sp.getAddress(target);
            if (mem.getBlock(t) == null) continue;
            if (getFunctionAt(t) == null && !m.equals("jmp")) { disassemble(t); createFunction(t, null); }
            RefType rt = m.equals("jmp") ? RefType.JUMP_OVERRIDE_UNCONDITIONAL : RefType.CALL_OVERRIDE_UNCONDITIONAL;
            Reference r = rm.addMemoryReference(ins.getAddress(), t, rt, SourceType.USER_DEFINED, 0);
            rm.setPrimary(r, true);
            made++;
        }
        println("indirect calls " + n + ", overrides " + made);
    }

    void io(long lo, long hi, int pageBits) {
        // references into [lo,hi]: group by page, list registers + functions
        TreeMap<Long, TreeMap<Long, TreeSet<String>>> pages = new TreeMap<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (AddressIterator it = rm.getReferenceDestinationIterator(sp.getAddress(lo), true); it.hasNext();) {
            Address t = it.next();
            if (t.getAddressSpace() != sp || (t.getOffset() & 0xffffffffL) > hi) break;
            long v = t.getOffset();
            for (Reference r : rm.getReferencesTo(t)) {
                if (r.getReferenceType().isCall() || r.getReferenceType().isFlow()) continue;
                Function f = getFunctionContaining(r.getFromAddress());
                pages.computeIfAbsent(v >> pageBits << pageBits, k -> new TreeMap<>()).computeIfAbsent(v, k -> new TreeSet<>()).add((f == null ? "?" : f.getEntryPoint().toString()) + (r.getReferenceType().isWrite() ? "W" : "R"));
            }
        }
        for (Map.Entry<Long, TreeMap<Long, TreeSet<String>>> e : pages.entrySet()) {
            TreeSet<String> fs = new TreeSet<>(); for (TreeSet<String> x : e.getValue().values()) for (String y : x) fs.add(y.substring(0, y.length()-1));
            println(String.format("page %08x: %d regs, funcs %s", e.getKey(), e.getValue().size(), fs.size() > 12 ? fs.size() + " funcs" : fs.toString()));
            for (Map.Entry<Long, TreeSet<String>> r : e.getValue().entrySet()) println(String.format("    %08x %s", r.getKey(), r.getValue().size() > 8 ? r.getValue().size() + " refs" : r.getValue().toString()));
        }
    }

    void up(Function f, int depth, int max, Set<Function> seen) throws Exception {
        if (f == null) return;
        println("  " + "  ".repeat(depth) + f.getName() + "@" + f.getEntryPoint() + (seen.contains(f) ? " (seen)" : ""));
        if (seen.contains(f) || depth >= max) return;
        seen.add(f);
        Set<Function> cs = new TreeSet<>(Comparator.comparing(Function::getEntryPoint));
        cs.addAll(f.getCallingFunctions(monitor));
        // also data refs to entry (function pointer tables / task descriptors)
        for (Reference r : getReferencesTo(f.getEntryPoint())) if (!r.getReferenceType().isCall()) { Function g = getFunctionContaining(r.getFromAddress()); if (g == null) println("  " + "  ".repeat(depth+1) + "[ptr @" + r.getFromAddress() + "]"); }
        for (Function g : cs) up(g, depth + 1, max, seen);
    }

    void stats() {
        Listing l = currentProgram.getListing();
        long ins = 0; for (Instruction i : l.getInstructions(true)) ins++;
        println("functions=" + currentProgram.getFunctionManager().getFunctionCount() + " instructions=" + ins);
    }

    void sweep() throws Exception {
        Memory mem = currentProgram.getMemory();
        int made = 0;
        for (int pass = 0; pass < 3; pass++) {
            for (MemoryBlock b : mem.getBlocks()) {
                if (!b.isInitialized() || !b.isExecute() || b.getName().equals("FLASH")) continue;
                Address s = b.getStart(), e = b.getEnd();
                for (Address p = s; p.compareTo(e) < 0; p = p.add(2)) {
                    if (p.getOffset() % 2 != 0) continue;
                    int w = mem.getShort(p) & 0xffff;
                    boolean mm = (w & 0xf0ff) == 0x40f0 || (w & 0xf0ff) == 0x40f1; // movmu.l / movml.l Rn,@-R15 (SH-2A)
                    if (w != 0x4f22 && !mm) continue; // sts.l pr,@-r15
                    // walk back over mov.l rN,@-r15 (2Nf6 -> 0x2Ff6 pattern: 0010 1111 nnnn 0110)
                    Address st = p;
                    while (true) {
                        Address q = st.subtract(2);
                        if (q.compareTo(s) < 0) break;
                        int v = mem.getShort(q) & 0xffff;
                        if ((v & 0xff0f) == 0x2f06 || (v & 0xff0f) == 0x4f03 /*stc.l*/ ) st = q; else break;
                    }
                    if (getFunctionAt(st) != null || getInstructionContaining(st) != null && getInstructionAt(st) == null) continue;
                    if (getFunctionContaining(st) != null && getFunctionContaining(st).getEntryPoint().compareTo(st) != 0) continue;
                    disassemble(st);
                    if (createFunction(st, null) != null) made++;
                }
            }
            analyzeChanges(currentProgram);
        }
        println("sweep created " + made);
        stats();
    }

    void dec(Address ad) {
        Function f = getFunctionContaining(ad);
        if (f == null) { println("no function at " + ad); return; }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        DecompileResults r = di.decompileFunction(f, 60, monitor);
        println("// " + f.getName() + " @ " + f.getEntryPoint());
        println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "decompile failed: " + r.getErrorMessage());
        di.dispose();
    }

    void dis(Address ad, int n) {
        Listing l = currentProgram.getListing();
        CodeUnit cu = l.getCodeUnitContaining(ad);
        if (cu == null) { disassemble(ad); cu = l.getCodeUnitAt(ad); }
        for (int i = 0; i < n && cu != null; i++) {
            String ref = "";
            for (Reference r : cu.getReferencesFrom()) ref += " ->" + r.getToAddress() + (getSymbolAt(r.getToAddress()) != null ? "(" + getSymbolAt(r.getToAddress()).getName() + ")" : "");
            println(String.format("  %s %-28s%s", cu.getAddress(), cu.toString(), ref));
            cu = l.getCodeUnitAfter(cu.getAddress());
        }
    }

    void xr(Address ad) {
        for (Reference r : getReferencesTo(ad)) println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + fn(r.getFromAddress()));
    }

    void lit(long lo, long hi) throws Exception {
        Memory mem = currentProgram.getMemory();
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isInitialized() || b.getName().equals("FLASH")) continue;
            for (Address p = b.getStart(); p.compareTo(b.getEnd().subtract(3)) <= 0; p = p.add(4)) {
                long v = mem.getInt(p) & 0xffffffffL;
                if (v < lo || v > hi) continue;
                String users = "";
                for (Reference r : getReferencesTo(p)) users += " " + r.getFromAddress() + "[" + fn(r.getFromAddress()) + "]";
                println(String.format("  %s = %08x  used by:%s", p, v, users));
            }
        }
    }

    void funcs(String[] a) {
        long lo = a.length > 2 ? Long.parseUnsignedLong(a[1].replace("0x",""),16) : 0, hi = a.length > 2 ? Long.parseUnsignedLong(a[2].replace("0x",""),16) : 0xffffffffL;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            long e = f.getEntryPoint().getOffset();
            if (e >= lo && e <= hi) println(String.format("  %s %-24s size=%d", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses()));
        }
    }
}

// Re-apply annotations written by ExportAnnotations.java to the current program.
// Arg: <tsv file>. Creates missing functions, renames existing ones, adds labels and
// sets comments. Safe to run more than once.
//@category DDJ1000
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

public class ApplyAnnotations extends GhidraScript {
    static String unesc(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\' && i + 1 < s.length()) {
                char n = s.charAt(++i);
                b.append(n == 't' ? '\t' : n == 'n' ? '\n' : n);
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }

    @Override
    protected void run() throws Exception {
        AddressFactory af = currentProgram.getAddressFactory();
        Listing listing = currentProgram.getListing();
        int funcs = 0, labels = 0, cmts = 0, failed = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]), StandardCharsets.UTF_8)) {
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split("\t", -1);
            Address a = af.getAddress(f[1]);
            try {
                switch (f[0]) {
                    case "func": {
                        String name = unesc(f[2]);
                        Function fn = getFunctionAt(a);
                        if (fn == null) {
                            disassemble(a);
                            fn = createFunction(a, name);
                        }
                        if (fn != null) fn.setName(name, SourceType.USER_DEFINED);
                        else failed++;
                        funcs++;
                        break;
                    }
                    case "label":
                        createLabel(a, unesc(f[2]), true, SourceType.USER_DEFINED);
                        labels++;
                        break;
                    case "cmt":
                        listing.setComment(a, CommentType.valueOf(f[2]), unesc(f[3]));
                        cmts++;
                        break;
                }
            } catch (Exception e) {
                failed++;
                printerr(line + " : " + e.getMessage());
            }
        }
        println(String.format("%s: applied %d functions, %d labels, %d comments, %d failed",
                currentProgram.getName(), funcs, labels, cmts, failed));
    }
}

// Export the hand-made annotations of the current program (user-defined function names,
// labels and all comments) to <outdir>/<program name>.tsv, so they can be kept in git
// without the firmware bytes and re-applied to a fresh import with ApplyAnnotations.java.
// Arg: <outdir>
// Line format (tab-separated, \t \n \\ escaped):
//   func  <addr>  <name>
//   label <addr>  <name>
//   cmt   <addr>  <EOL|PRE|POST|PLATE|REPEATABLE>  <text>
//@category DDJ1000
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class ExportAnnotations extends GhidraScript {
    static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "");
    }

    static boolean manual(SourceType s) {
        return s == SourceType.USER_DEFINED || s == SourceType.IMPORTED;
    }

    @Override
    protected void run() throws Exception {
        File dir = new File(getScriptArgs()[0]);
        dir.mkdirs();
        String name = currentProgram.getName().replaceAll("\\.bin$", "");
        List<String> lines = new ArrayList<>();
        int funcs = 0, labels = 0, cmts = 0;

        for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(false)) {
            if (!manual(s.getSource()) || s.isExternal()) continue;
            SymbolType t = s.getSymbolType();
            if (t == SymbolType.FUNCTION) {
                lines.add("func\t" + s.getAddress() + "\t" + esc(s.getName()));
                funcs++;
            } else if (t == SymbolType.LABEL) {
                lines.add("label\t" + s.getAddress() + "\t" + esc(s.getName()));
                labels++;
            }
        }

        Listing listing = currentProgram.getListing();
        AddressIterator it = listing.getCommentAddressIterator(currentProgram.getMemory(), true);
        while (it.hasNext()) {
            Address a = it.next();
            for (CommentType ct : CommentType.values()) {
                String c = listing.getComment(ct, a);
                if (c != null) {
                    lines.add("cmt\t" + a + "\t" + ct + "\t" + esc(c));
                    cmts++;
                }
            }
        }

        Collections.sort(lines);
        File out = new File(dir, name + ".tsv");
        try (PrintWriter w = new PrintWriter(new OutputStreamWriter(new FileOutputStream(out), "UTF-8"))) {
            w.println("# " + currentProgram.getName() + " annotations, exported by ExportAnnotations.java");
            for (String l : lines) w.println(l);
        }
        println(String.format("%s: %d functions, %d labels, %d comments -> %s", name, funcs, labels, cmts, out));
    }
}

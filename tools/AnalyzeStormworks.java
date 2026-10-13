//@category Analysis
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.File;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Set;

public class AnalyzeStormworks extends GhidraScript {
    @Override
    public void run() throws Exception {
        File outFile = new File("stormworks_decompiled_analysis.txt");
        PrintWriter writer = new PrintWriter(outFile);

        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        ConsoleTaskMonitor taskMonitor = new ConsoleTaskMonitor();

        writer.println("=================================================================");
        writer.println(" Stormworks ARM64 Analysis: Graphics & Physics Engine Decomp     ");
        writer.println("=================================================================");

        String[] targetStrings = new String[] {
            "Failed to create GLFW window",
            "OpenGL 3.2 is required",
            "calculateSimulationIslands",
            "islandUnionFindAndQuickSort",
            "Debug Buoyancy Mesh",
            "Debug Buoyancy Volume",
            "Debug Vehicle Physics",
            "data/vehicles/tmp/autosave.png"
        };

        ReferenceManager refMgr = currentProgram.getReferenceManager();
        FunctionManager funcMgr = currentProgram.getFunctionManager();
        Set<String> decompiledFuncs = new HashSet<String>();

        for (String target : targetStrings) {
            writer.println("\n-------------------------------------------------------------");
            writer.println("Searching for string: " + target);
            writer.println("-------------------------------------------------------------");

            StringBuilder sb = new StringBuilder();
            for (byte b : target.getBytes("UTF-8")) {
                sb.append(String.format("%02x ", b));
            }
            String hexStr = sb.toString().trim();

            Address searchAddr = currentProgram.getMinAddress();
            int count = 0;

            while (searchAddr != null && count < 5) {
                Address foundAddr = findBytes(searchAddr, hexStr);
                if (foundAddr == null) {
                    break;
                }
                count++;
                writer.println("Found occurrence at: " + foundAddr.toString());
                ReferenceIterator refIter = refMgr.getReferencesTo(foundAddr);
                while (refIter.hasNext()) {
                    Reference ref = refIter.next();
                    Address fromAddr = ref.getFromAddress();
                    Function func = funcMgr.getFunctionContaining(fromAddr);
                    if (func != null) {
                        String funcEntry = func.getEntryPoint().toString();
                        writer.println("  Referenced in function: " + func.getName() + " at " + funcEntry);
                        if (!decompiledFuncs.contains(funcEntry)) {
                            decompiledFuncs.add(funcEntry);
                            DecompileResults res = decomp.decompileFunction(func, 60, taskMonitor);
                            if (res.decompileCompleted()) {
                                writer.println(res.getDecompiledFunction().getC());
                            }
                        }
                    }
                }
                searchAddr = foundAddr.add(1);
            }
        }

        writer.flush();
        writer.close();
        println("Analysis complete!");
    }
}

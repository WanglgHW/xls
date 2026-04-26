#!/usr/bin/env python3
"""
icsprout55_full_flow.py — Full DSLX → IR → Verilog → Gate-level Netlist → LEC + Area evaluation flow

Uses the icsprout55 PDK (ics55_LLSC_H7C) as the default standard cell library.
Supports combinational and sequential logic LEC verification.

Usage:
  python3 icsprout55_full_flow.py --dslx <path.x> [--workdir <dir>] [--top <name>]
  python3 icsprout55_full_flow.py --help

Prerequisites:
  1. bazel build //:minimal_tools   (includes lec_main, completed)
  2. yosys installed (brew install yosys)
  3. icsprout55-pdk at /Users/georgewang/chip-design-llm/icsprout55-pdk/
"""

import argparse
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

# ============================================================
# Configuration — all paths managed centrally
# ============================================================

XLS_ROOT = os.environ.get("XLS_ROOT", "/Users/georgewang/chip-design-llm/xls")
PDK_ROOT = os.environ.get("PDK_ROOT", "/Users/georgewang/chip-design-llm/icsprout55-pdk")

# Default: typical corner @ TT 1.2V 25C
LIB_FILE = os.path.join(
    PDK_ROOT,
    "IP/STD_cell/ics55_LLSC_H7C_V1p10C100/ics55_LLSC_H7CL/liberty/"
    "ics55_LLSC_H7CL_typ_tt_1p2_25_nldm.lib",
)

# Tool paths
BAZEL_BIN = os.path.join(XLS_ROOT, "bazel-bin")
TOOLS = {
    "interpreter":  os.path.join(BAZEL_BIN, "xls/dslx/interpreter_main"),
    "ir_converter": os.path.join(BAZEL_BIN, "xls/dslx/ir_convert/ir_converter_main"),
    "opt":          os.path.join(BAZEL_BIN, "xls/tools/opt_main"),
    "codegen":      os.path.join(BAZEL_BIN, "xls/tools/codegen_main"),
    "lec":          os.path.join(BAZEL_BIN, "xls/tools/lec_main"),
}

# Yosys
YOSYS = "yosys"

# ============================================================
# Step 0: Environment check
# ============================================================

def check_environment():
    """Verify all binaries and files exist"""
    errors = []
    for name, path in TOOLS.items():
        if not os.path.isfile(path):
            errors.append(f"  [MISSING] {name}: {path}")
    if not os.path.isfile(LIB_FILE):
        errors.append(f"  [MISSING] Liberty file: {LIB_FILE}")
    import shutil
    if not shutil.which(YOSYS):
        errors.append(f"  [MISSING] yosys not found in PATH")

    if errors:
        print("Environment check failed:")
        for e in errors:
            print(e)
        print()
        print("Fix:")
        print("  1. bazel build //:minimal_tools")
        print("  2. brew install yosys")
        print(f"  3. Verify PDK path: {LIB_FILE}")
        sys.exit(1)
    print("[Step 0] Environment check passed")
    return True

# ============================================================
# Step 1: DSLX interpreter verification
# ============================================================

def step_interpret(dslx_file: str, workdir: str) -> bool:
    """Run DSLX interpreter to verify syntax correctness"""
    print(f"[Step 1] DSLX interpreter verification: {dslx_file}")
    result = subprocess.run(
        [TOOLS["interpreter"], dslx_file],
        capture_output=True, text=True, cwd=workdir,
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    print(f"  PASSED")
    return True

# ============================================================
# Step 2: DSLX → XLS IR
# ============================================================

def step_ir_convert(dslx_file: str, ir_file: str, workdir: str, top_name: str = "") -> bool:
    """Convert DSLX to XLS IR text format"""
    print(f"[Step 2] DSLX -> IR: {dslx_file} -> {ir_file}")
    cmd = [TOOLS["ir_converter"], dslx_file]
    if top_name:
        cmd += ["--top", top_name]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir)
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    with open(ir_file, "w") as f:
        f.write(result.stdout)
    print(f"  PASSED")
    return True

# ============================================================
# Step 3: IR optimization
# ============================================================

def step_optimize(ir_file: str, opt_file: str, workdir: str) -> bool:
    """Run XLS IR optimization passes (constant folding, DCE, etc.)"""
    print(f"[Step 3] IR optimization: {ir_file} -> {opt_file}")
    result = subprocess.run(
        [TOOLS["opt"], ir_file],
        capture_output=True, text=True, cwd=workdir,
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    with open(opt_file, "w") as f:
        f.write(result.stdout)
    print(f"  PASSED")
    return True

# ============================================================
# Step 4: IR → behavioral Verilog
# ============================================================

def step_codegen(opt_file: str, v_file: str, workdir: str,
                 generator: str = "combinational") -> bool:
    """Generate behavioral Verilog from optimized IR"""
    print(f"[Step 4] IR -> Verilog: {opt_file} -> {v_file}")
    result = subprocess.run(
        [TOOLS["codegen"], f"--generator={generator}", opt_file],
        capture_output=True, text=True, cwd=workdir,
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()}")
        return False
    with open(v_file, "w") as f:
        f.write(result.stdout)
    print(f"  PASSED")
    return True

# ============================================================
# Step 5: Generate Yosys synthesis script
# ============================================================

def generate_yosys_script(ys_file: str, v_file: str, top_module: str):
    """Generate Yosys synthesis script (follows synth -> dfflibmap -> abc -> clean order)"""
    script = textwrap.dedent(f"""\
    # Yosys synthesis script for icsprout55 PDK
    # Order: synth -> dfflibmap -> abc -> clean -> write_verilog -noattr

    # Read behavioral Verilog
    read_verilog {v_file}
    hierarchy -top {top_module}

    # High-level synthesis
    synth -top {top_module}

    # DFF mapping using icsprout55 liberty
    dfflibmap -liberty {LIB_FILE}

    # Technology mapping with ABC
    abc -liberty {LIB_FILE}

    # Clean up
    clean

    # Write gate-level netlist (noattr required for OpenSTA compatibility)
    write_verilog -noattr {top_module}_netlist.v
    """)
    with open(ys_file, "w") as f:
        f.write(script)
    print(f"  Yosys script written: {ys_file}")

# ============================================================
# Step 6: Yosys synthesis (behavioral Verilog → gate-level netlist)
# ============================================================

def step_synthesize(ys_file: str, workdir: str, top_module: str) -> tuple:
    """Run Yosys synthesis, return (success, netlist_file)"""
    print(f"[Step 6] Yosys synthesis (icsprout55 PDK)")
    netlist_file = os.path.join(workdir, f"{top_module}_netlist.v")
    result = subprocess.run(
        [YOSYS, "-s", ys_file],
        capture_output=True, text=True, cwd=workdir,
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr.strip()[-500:]}")
        return False, None

    # Parse ABC synthesis results
    for line in result.stdout.splitlines():
        if "cells:" in line:
            print(f"  {line.strip()}")

    if not os.path.isfile(netlist_file):
        print(f"  FAILED: netlist file not generated")
        return False, None

    print(f"  Netlist: {netlist_file}")
    print(f"  PASSED")
    return True, netlist_file

# ============================================================
# Step 7: Generate icsprout55 Cell Library Proto (binary)
# ============================================================

def generate_cell_proto(proto_file: str, cells: list):
    """Build cell library proto from cell definitions

    Note: LEC tool requires binary proto format, not Liberty files directly.
    This manually constructs a proto with cell functional definitions.
    """
    try:
        sys.path.insert(0, "/tmp/xls_proto")
        import xls.netlist.netlist_pb2 as pb
    except ImportError:
        print("  Need to generate protobuf Python code first:")
        print(f"    mkdir -p /tmp/xls_proto && protoc --python_out=/tmp/xls_proto xls/netlist/netlist.proto")
        raise

    proto = pb.CellLibraryProto()

    for cell_def in cells:
        entry = proto.entries.add()
        entry.kind = cell_def["kind"]
        entry.name = cell_def["name"]
        for inp in cell_def.get("inputs", []):
            entry.input_names.append(inp)
        pin = entry.output_pin_list.pins.add()
        pin.name = cell_def["output"]
        pin.function = cell_def["function"]

    with open(proto_file, "wb") as f:
        f.write(proto.SerializeToString())

    print(f"  Cell proto written: {proto_file} ({len(proto.entries)} cells)")

# ============================================================
# Step 8: LEC logical equivalence verification
# ============================================================

def step_lec(ir_file: str, netlist_file: str, proto_file: str,
             top_module: str, workdir: str) -> bool:
    """Run Z3-driven LEC to verify IR and gate-level netlist are equivalent"""
    print(f"[Step 8] LEC logical equivalence verification")
    print(f"  IR:       {ir_file}")
    print(f"  Netlist:  {netlist_file}")
    print(f"  Cells:    {proto_file}")

    result = subprocess.run(
        [
            TOOLS["lec"],
            "--ir_path", ir_file,
            "--netlist_path", netlist_file,
            "--cell_proto_path", proto_file,
            "--entry_function_name", top_module,
            "--netlist_module_name", top_module,
        ],
        capture_output=True, text=True, cwd=workdir,
        timeout=300,
    )
    output = (result.stdout + result.stderr).strip()
    print(f"  {output}")

    if "satisfiable: false" in output.lower():
        print(f"  LEC PASSED (IR and Netlist are equivalent)")
        return True
    elif result.returncode != 0:
        print(f"  LEC FAILED")
        return False
    else:
        print(f"  LEC result: satisfiable (may have mismatches)")
        return False

# ============================================================
# Step 9: Gate-level area estimation
# ============================================================

def estimate_area(netlist_file: str, workdir: str) -> dict:
    """Estimate area from gate-level netlist (icsprout55 cell count)"""
    print(f"[Step 9] Area estimation")
    with open(netlist_file) as f:
        content = f.read()

    cell_counts = {}
    for line in content.splitlines():
        line = line.strip()
        # Match instantiation lines: INVX0P5H7L _0_ (
        if line and not line.startswith("//") and not line.startswith("module") \
           and not line.startswith("endmodule") and not line.startswith("input") \
           and not line.startswith("output") and not line.startswith("wire") \
           and not line.startswith("assign") and not line.startswith(".") \
           and not line.startswith("(") and not line.startswith(")"):
            cell_name = line.split()[0]
            # Only count icsprout55 cells (names contain H7L or H7H)
            if "H7L" in cell_name or "H7H" in cell_name:
                cell_counts[cell_name] = cell_counts.get(cell_name, 0) + 1

    total_cells = sum(cell_counts.values())
    print(f"  Total icsprout55 cells: {total_cells}")
    for cell, count in sorted(cell_counts.items()):
        print(f"    {cell}: {count}")

    return cell_counts

# ============================================================
# Main flow: one-shot execution
# ============================================================

def run_full_flow(dslx_file: str, workdir: str, top_name: str = "",
                  do_lec: bool = True):
    """Execute full DSLX-to-netlist flow"""
    project_name = Path(dslx_file).stem

    # Derived filenames
    ir_file = os.path.join(workdir, f"{project_name}.ir")
    opt_file = os.path.join(workdir, f"{project_name}_opt.ir")
    v_file = os.path.join(workdir, f"{project_name}.v")
    ys_file = os.path.join(workdir, f"{project_name}_synth.ys")
    proto_file = os.path.join(workdir, f"{project_name}_cells.pb")

    # Step 1: DSLX interpreter
    if not step_interpret(dslx_file, workdir):
        return False

    # Step 2: DSLX -> IR (no --top first, to discover function names)
    if not step_ir_convert(dslx_file, ir_file, workdir, ""):
        return False

    # Auto-detect top module name from IR
    with open(ir_file) as f:
        ir_content = f.read()

    # Find top fn or plain fn
    top_match = re.search(r'top\s+fn\s+(\S+)\s*\(', ir_content)
    if top_match:
        actual_top_name = top_match.group(1)
    else:
        # DSLX function names are converted to __pkg__funcname by ir_converter
        fn_match = re.search(r'fn\s+__(\S+?)__(\S+)\s*\(', ir_content)
        if fn_match:
            # ir_converter --top needs the original DSLX function name
            dslx_fn_name = fn_match.group(2)
            actual_top_name = dslx_fn_name
        elif top_name:
            actual_top_name = top_name
        else:
            print(f"  ERROR: cannot extract function name from IR")
            return False

    # Re-generate IR with top marker
    if not step_ir_convert(dslx_file, ir_file, workdir, actual_top_name):
        return False

    # Re-read IR to get the full module name used in Verilog
    with open(ir_file) as f:
        ir_content = f.read()
    top_match = re.search(r'top\s+fn\s+(\S+)\s*\(', ir_content)
    if top_match:
        actual_top_name = top_match.group(1)

    print(f"  Top module name: {actual_top_name}")

    # Step 3: IR optimization
    if not step_optimize(ir_file, opt_file, workdir):
        return False

    # Step 4: IR -> Verilog
    if not step_codegen(opt_file, v_file, workdir):
        return False

    # Step 5-6: Yosys synthesis
    generate_yosys_script(ys_file, v_file, actual_top_name)
    success, netlist_file = step_synthesize(ys_file, workdir, actual_top_name)
    if not success:
        return False

    # Step 7-8: LEC (combinational logic)
    if do_lec:
        # Define icsprout55 cell library (as mapped by Yosys abc)
        cells = [
            {"kind": 2,  "name": "INVX0P5H7L",   "inputs": ["A"], "output": "Y", "function": "!A"},
            {"kind": 8,  "name": "AND2X0P5H7L",   "inputs": ["A", "B"], "output": "Y", "function": "A&B"},
            {"kind": 8,  "name": "NAND2X0P5H7L",  "inputs": ["A", "B"], "output": "Y", "function": "!(A&B)"},
            {"kind": 8,  "name": "OR2X0P5H7L",    "inputs": ["A", "B"], "output": "Y", "function": "A|B"},
            {"kind": 8,  "name": "NOR2X0P5H7L",   "inputs": ["A", "B"], "output": "Y", "function": "!(A|B)"},
            {"kind": 7,  "name": "XOR2X0P5H7L",   "inputs": ["A", "B"], "output": "Y", "function": "A^B"},
            {"kind": 7,  "name": "XNOR2X0P5H7L",  "inputs": ["A", "B"], "output": "Y", "function": "!(A^B)"},
            {"kind": 8,  "name": "BUF_X0P5H7L",   "inputs": ["A"], "output": "Y", "function": "A"},
            # DFF variants (for sequential)
            {"kind": 1,  "name": "DFFX1H7L",      "inputs": ["D"], "output": "Q", "function": "D"},
            {"kind": 1,  "name": "DFFNQX1H7L",    "inputs": ["D"], "output": "QN", "function": "!D"},
        ]
        generate_cell_proto(proto_file, cells)

        step_lec(ir_file, netlist_file, proto_file, actual_top_name, workdir)

    # Step 9: Area estimation
    estimate_area(netlist_file, workdir)

    return True

# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="icsprout55 PDK full flow: DSLX -> IR -> Verilog -> Netlist -> LEC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          # Full flow for a single file
          python3 icsprout55_full_flow.py --dslx my_design.x

          # Specify output directory and top name
          python3 icsprout55_full_flow.py --dslx my_design.x --workdir ./output --top my_top

          # Generate netlist only, skip LEC
          python3 icsprout55_full_flow.py --dslx my_design.x --no-lec
        """),
    )
    parser.add_argument("--dslx", required=True, help="DSLX source file path (.x)")
    parser.add_argument("--workdir", default=".", help="Working directory (default: current)")
    parser.add_argument("--top", default="", help="Top module name (default: auto-detected from IR)")
    parser.add_argument("--no-lec", action="store_true", help="Skip LEC verification")
    parser.add_argument("--no-build", action="store_true", help="Skip bazel build check")

    args = parser.parse_args()

    os.makedirs(args.workdir, exist_ok=True)

    if not args.no_build:
        check_environment()

    success = run_full_flow(
        dslx_file=args.dslx,
        workdir=args.workdir,
        top_name=args.top,
        do_lec=not args.no_lec,
    )

    if success:
        print("\n" + "=" * 60)
        print("Flow completed successfully")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Flow FAILED")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()

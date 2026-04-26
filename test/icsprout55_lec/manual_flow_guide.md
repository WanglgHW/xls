# icsprout55 PDK Full Flow — Manual Operation Guide

## Prerequisites

```bash
cd /Users/georgewang/chip-design-llm/xls

# 1. Build the minimal toolchain (includes lec_main)
bazel build //:minimal_tools

# 2. Build icsprout55 LEC tests (optional)
bazel test //xls/solvers:icsprout55_lec_test

# 3. Confirm yosys is installed
yosys --version

# 4. Confirm icsprout55 PDK is present
ls /Users/georgewang/chip-design-llm/icsprout55-pdk/IP/STD_cell/ics55_LLSC_H7C_V1p10C100/ics55_LLSC_H7CL/liberty/
```

## Tool Inventory

| Step | Tool | Path | Purpose |
|------|------|------|---------|
| 1 | `interpreter_main` | `bazel-bin/xls/dslx/interpreter_main` | DSLX syntax verification / interpretive execution |
| 2 | `ir_converter_main` | `bazel-bin/xls/dslx/ir_convert/ir_converter_main` | DSLX to XLS IR |
| 3 | `opt_main` | `bazel-bin/xls/tools/opt_main` | IR optimization |
| 4 | `codegen_main` | `bazel-bin/xls/tools/codegen_main` | IR to behavioral Verilog |
| 5 | `yosys` | `yosys` (system) | Synthesis: behavioral to gate-level netlist |
| 6 | `lec_main` | `bazel-bin/xls/tools/lec_main` (in minimal_tools) | Logical Equivalence Checking |
| 7 | `opensta` | `opensta/build/sta` | Timing analysis (optional) |

## Standard Flow (Combinational Logic)

Using `simple_not.x` as an example:

### Step 1: Write DSLX

```dslx
// simple_not.x
fn main(data_in: bits[4]) -> bits[4] {
    !data_in
}
```

### Step 2: Interpreter Verification

```bash
bazel-bin/xls/dslx/interpreter_main test/icsprout55_lec/simple_not.x
```

### Step 3: DSLX to IR

```bash
bazel-bin/xls/dslx/ir_convert/ir_converter_main --top="main" \
    test/icsprout55_lec/simple_not.x > test/icsprout55_lec/simple_not.ir
```

### Step 4: IR Optimization

```bash
bazel-bin/xls/tools/opt_main test/icsprout55_lec/simple_not.ir \
    > test/icsprout55_lec/simple_not_opt.ir
```

### Step 5: IR to Verilog

```bash
bazel-bin/xls/tools/codegen_main --generator=combinational \
    test/icsprout55_lec/simple_not_opt.ir > test/icsprout55_lec/simple_not.v
```

### Step 6: Yosys Synthesis (icsprout55 PDK)

Create Yosys script `synth.ys`:

```tcl
read_verilog simple_not.v
hierarchy -top __simple_not__main
synth -top __simple_not__main

dfflibmap -liberty /Users/georgewang/chip-design-llm/icsprout55-pdk/IP/STD_cell/ics55_LLSC_H7C_V1p10C100/ics55_LLSC_H7CL/liberty/ics55_LLSC_H7CL_typ_tt_1p2_25_nldm.lib

abc -liberty /Users/georgewang/chip-design-llm/icsprout55-pdk/IP/STD_cell/ics55_LLSC_H7C_V1p10C100/ics55_LLSC_H7CL/liberty/ics55_LLSC_H7CL_typ_tt_1p2_25_nldm.lib

clean
write_verilog -noattr simple_not_netlist.v
```

Run:

```bash
yosys -s synth.ys
```

### Step 7: Generate Cell Library Proto

LEC requires binary proto format. Generate it with Python:

```bash
mkdir -p /tmp/xls_proto
protoc --python_out=/tmp/xls_proto xls/netlist/netlist.proto

python3 << 'PYEOF'
import sys; sys.path.insert(0, '/tmp/xls_proto')
import xls.netlist.netlist_pb2 as pb

proto = pb.CellLibraryProto()

# Add cells used in synthesis (based on Yosys abc output)
entry = proto.entries.add()
entry.kind = pb.INVERTER
entry.name = "INVX0P5H7L"
entry.input_names.append("A")
pin = entry.output_pin_list.pins.add()
pin.name = "Y"
pin.function = "!A"

# Add more cells as needed...
with open("test/icsprout55_lec/icsprout55_cells.pb", "wb") as f:
    f.write(proto.SerializeToString())
PYEOF
```

### Step 8: LEC Logical Equivalence Checking

```bash
bazel-bin/xls/tools/lec_main \
    --ir_path=test/icsprout55_lec/simple_not.ir \
    --netlist_path=test/icsprout55_lec/simple_not_netlist.v \
    --cell_proto_path=test/icsprout55_lec/icsprout55_cells.pb \
    --entry_function_name=__simple_not__main \
    --netlist_module_name=__simple_not__main
```

Success output: `Solver result; satisfiable: false`
(satisfiable: false means no counterexample found, i.e., equivalent)

### Step 9: Area Estimation

```bash
grep -oE '^\s+[A-Z][A-Z0-9_]+H7[LH]?\s' simple_not_netlist.v | sort | uniq -c | sort -rn
```

## PDK Corner Selection

| Corner | Liberty File | Characteristics |
|--------|-------------|-----------------|
| Typical | `ics55_LLSC_H7CL_typ_tt_1p2_25_nldm.lib` | TT 1.2V 25C, nominal |
| Fast | `ics55_LLSC_H7CL_ff_cbest_1p32_125_nldm.lib` | FF corner, fastest |
| Slow | `ics55_LLSC_H7CL_ss_rcworst_1p2_m40_nldm.lib` | SS corner, slowest |

## Common Issues

### lec_main: "XLS_RET_CHECK failure ... translated_.contains(ref)"

Cause: Netlist port naming does not match XLS naming convention. LEC expects wires named `p{stage}_{node_name}_{bit_index}_`.

Fix: Ensure netlist wire naming matches XLS `NodeToNetlistName` function output.

### lec_main: "Unhandled character for Scanning"

Cause: Using Liberty file directly as `--cell_lib_path`, but the parser cannot handle it.

Fix: Use `--cell_proto_path` with a binary proto file instead.

### lec_main: "cell_proto.ParseFromString failed"

Cause: Passed textproto instead of binary proto.

Fix: Generate binary `.pb` file using Python protobuf library.

## Cell Library Proto Reference

```python
# kind enum (from netlist.proto):
#   INVALID=0, FLOP=1, INVERTER=2, BUFFER=3, NAND=4, NOR=5, MULTIPLEXER=6, XOR=7, OTHER=8

# icsprout55 common cell mapping:
cells = [
    # Inverter
    {"kind": 2, "name": "INVX0P5H7L",   "inputs": ["A"],         "output": "Y",  "function": "!A"},

    # 2-input AND
    {"kind": 8, "name": "AND2X0P5H7L",  "inputs": ["A", "B"],    "output": "Y",  "function": "A&B"},

    # 2-input NAND
    {"kind": 4, "name": "NAND2X0P5H7L", "inputs": ["A", "B"],    "output": "Y",  "function": "!(A&B)"},

    # 2-input OR
    {"kind": 8, "name": "OR2X0P5H7L",   "inputs": ["A", "B"],    "output": "Y",  "function": "A|B"},

    # 2-input NOR
    {"kind": 5, "name": "NOR2X0P5H7L",  "inputs": ["A", "B"],    "output": "Y",  "function": "!(A|B)"},

    # 2-input XOR
    {"kind": 7, "name": "XOR2X0P5H7L",  "inputs": ["A", "B"],    "output": "Y",  "function": "A^B"},

    # DFF (positive edge, Q only)
    {"kind": 1, "name": "DFFNQX1H7L",   "inputs": ["D"],         "output": "Q",  "function": "D"},
]
```

## One-Click Automation

Use the provided Python script for the full flow:

```bash
python3 test/icsprout55_lec/icsprout55_full_flow.py \
    --dslx test/icsprout55_lec/simple_not.x \
    --workdir test/icsprout55_lec
```

## Test Case Summary

| Test | DSLX Function | Cells Used | LEC Result |
|------|--------------|-----------|-----------|
| NotGateWithIcsprout55 | 4-bit NOT | INVX0P5H7L | PASSED |
| AdderWithIcsprout55 | 2-bit ADD | AND/OR/XOR | PASSED |
| DetectsMismatch | 4-bit NOT (with bug) | INV + OR | Detected mismatch |

Run all tests: `bazel test //xls/solvers:icsprout55_lec_test`

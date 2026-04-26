# icsprout55 PDK Full Flow

## File Inventory

| File | Description |
|------|-------------|
| `icsprout55_full_flow.py` | One-shot automation script (DSLX to Netlist + LEC) |
| `manual_flow_guide.md` | Manual step-by-step CLI guide |
| `simple_not.x` | Example: 4-bit NOT |
| `simple_logic.x` | Example: NOT + AND + OR + XOR |
| `../xls/solvers/icsprout55_lec_test.cc` | C++ unit tests (icsprout55 cells) |

## Quick Start

### Option A: Automated Script

```bash
# Build tools (lec_main is included in minimal_tools)
cd /Users/georgewang/chip-design-llm/xls
bazel build //:minimal_tools

# Run full flow with example design
python3 test/icsprout55_lec/icsprout55_full_flow.py \
    --dslx test/icsprout55_lec/simple_not.x \
    --workdir test/icsprout55_lec

# Or with your own design
python3 test/icsprout55_lec/icsprout55_full_flow.py \
    --dslx /path/to/my_design.x \
    --workdir /path/to/output_dir
```

### Option B: Manual Step-by-Step

See `manual_flow_guide.md` for individual commands at each stage.

## Flow Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     DSLX source (.x)                        │
│                   (e.g. simple_not.x)                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 1: interpreter_main
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 DSLX interpreter verification               │
│              Validates syntax, no runtime errors            │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 2: ir_converter_main --top=X
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     XLS IR file (.ir)                       │
│                Text IR with top fn marker                   │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 3: opt_main
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Optimized IR (_opt.ir)                     │
│       Constant folding, DCE, algebraic simplification       │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 4: codegen_main --generator=combinational
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 Behavioral Verilog (.v)                     │
│               assign statements, wire declarations          │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 5-6: yosys -s synth.ys
                            │   dfflibmap + abc (icsprout55 liberty)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 Gate-level netlist (_netlist.v)             │
│        INVX0P5H7L, AND2X0P5H7L, OR2X0P5H7L, ...             │
│                     Area estimation data                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ Step 7-8: lec_main
                            │   Z3 SMT Solver + cell proto
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               LEC logical equivalence check                 │
│         satisfiable: false -> equivalent ✓                  │
│         satisfiable: true  -> mismatch ✗ (counterexample)   │
└─────────────────────────────────────────────────────────────┘
```

## Output Artifacts

After a successful run, the working directory contains:

```
<project>.ir              # XLS IR (with top marker)
<project>_opt.ir          # Optimized IR
<project>.v               # Behavioral Verilog
<project>_synth.ys        # Yosys synthesis script
<project>_cells.pb        # Cell library binary proto
__<pkg>__<func>_netlist.v # Gate-level netlist (icsprout55)
```

## PDK Corner Selection

Change the `LIB_FILE` variable in `icsprout55_full_flow.py`:

```python
# Typical (default)
LIB_FILE = "...ics55_LLSC_H7CL_typ_tt_1p2_25_nldm.lib"  # TT 1.2V 25°C

# Fast
LIB_FILE = "...ics55_LLSC_H7CL_ff_cbest_1p32_125_nldm.lib"  # FF 1.32V 125°C

# Slow
LIB_FILE = "...ics55_LLSC_H7CL_ss_rcworst_1p2_m40_nldm.lib"  # SS 1.2V -40°C
```

## Running Tests

```bash
# icsprout55 LEC unit tests
bazel test //xls/solvers:icsprout55_lec_test --test_output=streamed

# Original LEC unit tests (reference)
bazel test //xls/solvers:z3_lec_test --test_output=streamed
```

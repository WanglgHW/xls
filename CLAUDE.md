# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## Project Overview

This is a fork of **google/xls**, a High Level Synthesis (HLS) toolchain that produces synthesizable Verilog/SystemVerilog from high-level DSLX (a Rust-like dataflow DSL) or C++ (via xlscc) descriptions.

**CRITICAL: Do NOT rebuild this repo.** Pre-built binaries are provisioned separately. Treat `bazel-bin/` artifacts as read-only. The `//:minimal_tools` target has already been built; its binaries are the only XLS tools to use.

## Key Directories

- **`xls/dslx/`** — DSLX frontend: lexer, parser, type checker, interpreter, IR converter
- **`xls/ir/`** — XLS IR definition, text parser/formatter, abstract evaluation
- **`xls/passes/`** — Optimization passes on XLS IR
- **`xls/codegen/`** — Verilog AST (VAST) and code generators (Verilog/SystemVerilog output)
- **`xls/scheduling/`** — Pipeline scheduling algorithms
- **`xls/interpreter/`** — XLS IR interpreter
- **`xls/jit/`** — LLVM-based JIT for native-speed execution
- **`xls/solvers/`** — SMT solver integration (Z3) for formal verification
- **`xls/netlist/`** — Netlist parsing and analysis
- **`xls/synthesis/`** — Backend synthesis interface (Yosys integration)
- **`xls/tools/`** — CLI tool source code
- **`xls/modules/`** — Reusable DSLX hardware libraries
- **`xls/fuzzer/`** — Whole-stack fuzzer
- **`xls/examples/`** — Example computations
- **`xls/visualization/`** — IR visualization tools
- **`docs_src/`** — Markdown doc sources (rendered via mkdocs to https://google.github.io/xls)

## Available Tools (from `//:minimal_tools`)

| Tool | Purpose |
|------|---------|
| `interpreter_main` | Execute DSLX directly |
| `ir_converter_main` | DSLX → XLS IR |
| `opt_main` | Optimize XLS IR |
| `codegen_main` | XLS IR → Verilog |
| `sched_printer_main` | Print scheduling info |
| `proc_network_printer_main` | Print proc network |
| `ir_to_proto_main` | IR → Protocol Buffers |
| `ir_to_json_main` | IR → JSON |
| `ir_to_csvs_main` | IR → CSVs |
| `yosys_server_main` | Yosys synthesis server |
| `synthesis_client_main` | Synthesis client (gRPC) |
| `lec_main` | Logical Equivalence Checking (IR vs gate-level netlist) |

## Standard Pipeline

```
DSLX → interpreter_main (verify)
     → ir_converter_main --top=FUNC (→ .ir)
     → opt_main (→ _opt.ir)
     → codegen_main --generator=combinational (→ .v)
     → yosys -s synth.ys (icsprout55 PDK → _netlist.v)
     → lec_main (IR vs netlist equivalence check)
```

## LEC (Logical Equivalence Checking)

`lec_main` compares XLS IR against a gate-level netlist using Z3 SMT solver.
Test file: `xls/solvers/icsprout55_lec_test.cc` (icsprout55 PDK cells).

```bash
# Run LEC tests
bazel test //xls/solvers:icsprout55_lec_test //xls/solvers:z3_lec_test

# Run LEC manually
bazel-bin/xls/tools/lec_main \
    --ir_path=design.ir \
    --netlist_path=design_netlist.v \
    --cell_proto_path=cells.pb \
    --entry_function_name=__pkg__func \
    --netlist_module_name=__pkg__func
```

LEC requires a binary cell library proto (not Liberty files directly). Generate with:
```bash
mkdir -p /tmp/xls_proto && protoc --python_out=/tmp/xls_proto xls/netlist/netlist.proto
python3  # use xls.netlist.netlist_pb2 to write CellLibraryProto to .pb
```

## PDK Flow (icsprout55)

The default PDK is icsprout55 (ics55_LLSC_H7C). Yosys synthesis order must be:
`synth → dfflibmap → abc → clean → write_verilog -noattr`.

Automation script: `test/icsprout55_lec/icsprout55_full_flow.py`
Manual guide: `test/icsprout55_lec/manual_flow_guide.md`

## Build Commands

**Do NOT run these in this workspace.** Only the original XLS upstream maintainers should rebuild. The binaries are pre-provisioned.

For reference (upstream only):
```bash
bazel build //:minimal_tools                          # minimal toolchain
bazel test -c opt -- //xls/... -//xls/contrib/xlscc/...  # DSLX-only tests
bazel test -c opt -- //xls/...                         # full build incl. C++ frontend
```

## Code Style

- Google C++ Style Guide + Google Python Style Guide
- XLS-specific clarifications: https://google.github.io/xls/xls_style/
- DSLX docs use `dslx` (full code), `dslx-snippet` (highlight only), `dslx-bad` (error examples) fenced blocks
- Markdown formatting: `mdformat` with `.mdformat.toml` config

## PR Conventions (upstream google/xls)

- Squash all commits into a single commit per PR
- Lead with a GitHub issue for discussion before sending a PR
- Document PPA impact with 50-seed Yosys runs (ASAP7) for area/timing changes
- Single-commit squash: `git reset --soft $COMMIT_HASH && git commit -a`


## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

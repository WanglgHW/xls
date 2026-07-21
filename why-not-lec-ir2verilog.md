# Why XLS does not implement formal IR-to-Verilog LEC

## Short answer

**IR→netlist LEC is much easier to formalize than IR→Verilog LEC.** A netlist is already reduced to **cells + wires + known Boolean functions**. Verilog is a **hardware programming language** with richer semantics, more corner cases, and more implementation-dependent behavior.

That is why this repository has:

- an **IR translator to Z3** (`xls/solvers/z3_ir_translator.h`)
- a **netlist parser + cell-library-driven netlist translator to Z3** (`xls/netlist/netlist_parser.h`, `xls/solvers/z3_netlist_translator.cc`)
- a **formal IR↔netlist LEC tool** (`xls/tools/lec_main.cc`, `xls/solvers/z3_lec.cc`)
- but **no formal IR↔Verilog LEC tool**

For Verilog, the verification path in this repo is primarily **simulation-based**, through `simulate_module_main` / `ModuleSimulator` (`xls/tools/simulate_module_main.cc`), not SMT-based equivalence checking.

## Current status in this repository

### IR ↔ Verilog

There is **no dedicated formal IR↔Verilog LEC engine** in this repo.

Instead:

- Verilog is produced by codegen.
- The generated Verilog can be executed and checked with simulator-based tooling such as `simulate_module_main` (`xls/tools/simulate_module_main.cc:220-349`).
- The solver docs only describe **IR-to-netlist LEC**, not IR-to-Verilog LEC (`docs_src/solvers.md:72-124`).

So multi-cycle Verilog can be **simulated**, but there is no built-in formal proof flow that directly compares XLS IR against the Verilog text/AST.

### IR ↔ netlist

This repo **does** implement formal IR↔netlist LEC.

- `lec_main` drives the proof (`xls/tools/lec_main.cc`).
- `z3::Lec` constructs the equivalence problem (`xls/solvers/z3_lec.h`, `xls/solvers/z3_lec.cc`).
- The netlist side is interpreted using parsed cells plus cell-library formulas (`docs_src/solvers.md:91-119`).

This netlist LEC can handle **multi-stage feed-forward pipelines**, but in a **stage-aware, clockless** style:

- if a netlist spans multiple stages, `--schedule_path` is required (`xls/tools/lec_main.cc:89-103`)
- stage-based checking uses `Lec::CreateForStage(...)` (`xls/solvers/z3_lec.h:65-69`)
- there are explicit staged tests, including multi-bit pipelines (`xls/solvers/z3_lec_test.cc:184-270`, `368-519`)

However, this is **not** general temporal/sequential equivalence over arbitrary state machines. It is mostly a **pipeline-stage equivalence** strategy.

## Why IR→Verilog LEC is difficult

## 1. Netlists have fixed semantics; Verilog does not

For netlist LEC, the problem is structurally simple:

- the **cell library** gives the Boolean meaning of each cell (`docs_src/tools.md:574-579`)
- the **netlist** only describes connectivity (`docs_src/solvers.md:111-119`)

That makes it practical to translate the netlist into Z3 as a Boolean / bit-vector graph.

For Verilog, a checker would need formal semantics for much more than connectivity:

- procedural blocks
- `always_comb`, `always_ff`, `assign`
- blocking vs non-blocking assignment
- event scheduling and delta cycles
- X/Z behavior
- partial initialization
- reset/clock protocol behavior
- SystemVerilog-specific constructs
- assertions and temporal properties

So IR→Verilog LEC is not “just another frontend”; it requires a **full formal RTL semantics engine**.

## 2. XLS codegen options can intentionally change semantic fidelity

The generated RTL is not always a perfect textual reflection of ideal IR semantics.

The codegen options explicitly warn that some settings may create differences between IR semantics and Verilog simulation:

- `array_index_bounds_checking=false` may cause mismatches (`xls/codegen/codegen_options.h:278-286`)
- `gate_recvs=false` may cause mismatches (`xls/codegen/codegen_options.h:288-297`)

The docs repeat the same caveats:

- `--gate_recvs` may reduce area but may also cause **mismatches between IR-level evaluation and Verilog simulation** (`docs_src/codegen_options.md:545-553`)
- `--array_index_bounds_checking=false` may also cause **mismatches between IR-level evaluation and Verilog simulation** (`docs_src/codegen_options.md:561-567`)

This creates a fundamental formalization question:

- Are we proving equivalence against **ideal IR semantics**?
- Or equivalence against the **specific chosen codegen mode**?
- If a codegen option intentionally weakens or approximates IR behavior, should the proof fail or reinterpret the spec?

Netlist LEC largely avoids this question by checking the actual post-synthesis implementation against the intended IR-level logic structure.

## 3. Generated Verilog is not just pure combinational logic

The RTL lowering docs show that generated Verilog/SystemVerilog contains representational choices that already diverge from a simple mathematical circuit model:

- zero-width values are omitted in RTL (`docs_src/ir_lowering.md:61-63`)
- assertions and covers are omitted in plain Verilog and emitted differently in SystemVerilog (`docs_src/ir_lowering.md:64-90`)

For example:

- combinational assertions are emitted as deferred immediate assertions
- pipelined assertions are emitted as concurrent assertions
- these are only represented in SystemVerilog, not plain Verilog

So a formal IR↔Verilog checker would need to decide:

- what is functionally relevant RTL,
- what is instrumentation,
- what is optional lowering detail,
- and what should be ignored without making the proof unsound.

## 4. Sequential logic is especially hard at the Verilog level

The current IR↔netlist LEC avoids full sequential reasoning by using a **clockless staged model**:

- flop `next_state` is treated as output behavior because “all our current (logic-checking) purposes are clockless” (`xls/netlist/function_extractor.cc:228-243`)
- `clk` and `input_valid` are forced to constant `1` in the netlist translator (`xls/solvers/z3_netlist_translator.cc:84-95,111-121`)
- nonzero pipeline stages replace cross-stage dependencies with fresh symbolic inputs (`xls/solvers/z3_lec.cc:163-193`)

This works because the netlist is already close to a stage-partitioned Boolean graph.

Doing the same at the Verilog level is much harder because the tool would first need to recover:

- where the registers are,
- which statements belong to which stage,
- what the temporal update semantics are,
- and how reset/valid/control protocol logic should be interpreted.

That is a much more complex analysis problem than parsing a mapped netlist.

## 5. The repository has a netlist parser, not a full formal Verilog frontend

The existing parser infrastructure is intentionally aimed at netlists:

- `xls/netlist/netlist_parser.h` handles a restricted structural form
- it ignores attributes and treats them like comments (`xls/netlist/netlist_parser.h:110-116`)

That is totally reasonable for synthesized gate-level netlists.

It is not enough for arbitrary generated Verilog/SystemVerilog, which would need:

- elaboration of modules and processes
- semantic treatment of procedural statements
- scheduling semantics
- richer expression semantics
- temporal constructs

So implementing IR→Verilog LEC would require a **real RTL elaborator + formal translator**, not just reuse of the current netlist stack.

## 6. Solver cost is already high even for netlists

The solver docs explicitly call out the scalability problem:

- netlist-like problems often reduce to hard SAT instances
- multipliers are especially expensive
- proving a single pipeline stage may already take minutes (`docs_src/solvers.md:128-140`)

If netlist LEC is already expensive, then adding a full Verilog semantics layer in front of it would usually make the formal problem **bigger and harder**, not smaller.

That makes simulation a pragmatic choice for Verilog-level checking.

## Why the repository likely chose simulation for Verilog and formal proof for netlists

This split is practical:

- **Verilog simulation** is comparatively cheap and robust for checking emitted RTL behavior.
- **Formal proof** is reserved for the lower-level representation where semantics are simpler: the gate-level or cell-level netlist.

That division also aligns with the repo’s tooling:

- `simulate_module_main` for Verilog execution (`xls/tools/simulate_module_main.cc`)
- `lec_main` for IR↔netlist proof (`xls/tools/lec_main.cc`)

## Netlist multi-cycle support: what is and is not supported

The current netlist LEC support is best understood as follows:

| Case | Supported? | Notes |
|---|---|---|
| **IR ↔ Verilog formal LEC** | **No** | No formal Verilog-to-Z3 path in this repo |
| **IR ↔ netlist, combinational / single-stage** | **Yes** | Standard `Lec::Create(...)` flow |
| **IR ↔ netlist, feed-forward pipelined multi-stage** | **Yes** | Supported via schedule-aware stage checking |
| **General sequential / temporal / FSM equivalence** | **No** | No full time-unrolling or sequential equivalence engine |

Important practical caveats:

1. Stage-aware LEC depends on **XLS naming conventions** like `p0_`, `p1_`, `p2_` (`xls/solvers/z3_lec.cc:492-516`).
2. `--auto_stage` exists, but currently only uses a simple heuristic around large multiplies (`xls/tools/lec_main.cc:185-231`).
3. Constraints are restricted in staged mode: they are only allowed on stage 0 (`xls/solvers/z3_lec.cc:259-278`).

## Bottom line

**IR→Verilog LEC is hard because it requires proving equivalence against the semantics of a full RTL language.**

**IR→netlist LEC is much more tractable because a netlist is just a structural Boolean network with known cell functions.**

That is why this repository implements:

- **simulation for Verilog**
- **formal LEC for netlists**

and not a direct formal IR-to-Verilog equivalence checker.


Optimized tool selection

Read memory

Created 3 todos

Explore LEC architecture

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/tools)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/netlist)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec.h#1-1), lines 1 to 100

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/tools/lec_main.cc#1-1), lines 1 to 150

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec.cc#1-1), lines 1 to 150

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_ir_translator.h#1-1), lines 1 to 100

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_netlist_translator.h#1-1), lines 1 to 100

Read [](file:///Users/georgewang/chip-design-llm/xls/docs_src/solvers.md#1-1), lines 1 to 100

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/netlist/netlist_parser.cc#1-1), lines 1 to 150

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_netlist_translator.cc#1-1), lines 1 to 200

Optimized tool selection

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/tools/lec_main.cc)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec.h)

Read [](file:///Users/georgewang/chip-design-llm/xls/docs_src/solvers.md)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec_test.cc#1-1), lines 1 to 460

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/netlist/netlist_parser.h#1-1), lines 1 to 300

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec.cc#1-1), lines 1 to 430

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_netlist_translator.cc#1-1), lines 1 to 400

Searched for regex `lec_main|IR-to-netlist|cell_proto_path|netlist_path` (`**/docs_src/tools.md`), no results

Searched for files matching `**/test/icsprout55_lec/**`, 5 matches

Searched for regex `write_verilog|codegen_main|lec_main` (`**/test/icsprout55_lec/**`), 19 results

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/solvers/z3_lec.cc#430-430), lines 430 to 521

Searched for text `NodeToNetlistName` (`**/xls/solvers/z3_lec.cc`), 5 results

Searched for regex `ParseModuleStatement|always|function|task|generate` (`**/xls/netlist/netlist_parser.cc`), no results

Read [](file:///Users/georgewang/chip-design-llm/xls/test/icsprout55_lec/manual_flow_guide.md#1-1), lines 1 to 210

Read [](file:///Users/georgewang/chip-design-llm/xls/test/icsprout55_lec/icsprout55_full_flow.py#130-130), lines 130 to 240

Ran terminal command:  bazel-bin/xls/dslx/ir_convert/ir_converter_main --top=main test/icsprout55_lec/simple_not.x | bazel-bin/xls/tools/codegen_main --generator=combinational -

Ran terminal command:  bazel-bin/xls/dslx/ir_convert/ir_converter_main --top=main test/icsprout55_lec/simple_logic.x | bazel-bin/xls/tools/codegen_main --generator=combinational -

Searched for regex `ParseModule\(|ParseModuleStatement|ParseAssignDecl` (`**/xls/netlist/netlist_parser.cc`), no results

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/netlist/netlist_parser.cc)

Read [](file:///Users/georgewang/chip-design-llm/xls/xls/netlist/netlist_parser.h#300-300), lines 300 to 800

Completed: *Inspect current LEC architecture* (1/3)

## Assessment

The existing `lec_main` is **IR-to-structural-netlist LEC**, not direct IR-to-XLS-generated Verilog LEC.

It:
- Parses XLS IR and selects a top `Function`.
- Parses a restricted structural Verilog format through `netlist::rtl::Parser`.
- Uses a cell-library proto or Liberty-derived model to translate standard cells into Z3.
- Proves the negation of bitwise output equality; `satisfiable: false` means equivalent.

The command-line orchestration is in lec_main.cc. The proof coordinator is `Lec` in z3_lec.h and z3_lec.cc.

### Why direct generated-Verilog input does not work today

`codegen_main --generator=combinational` emits behavioral RTL such as:

- vector ports: `input wire [3:0] data_in`
- vector expressions: `assign out = ~data_in`
- operators: `~`, `&`, `|`, `^`
- nested concatenations

The current parser accepts declarations, structural instances, and **wire-to-wire/literal concatenation assignments only**; it has no expression grammar for operator RHSs. See netlist_parser.h and its assignment implementation in netlist_parser.h. The scanner also rejects the generated RTL operators, as shown by its token set in netlist_parser.h.

Additionally, existing LEC binds values by generated internal names such as `p{stage}_{ir_node}_reg`; this works after synthesis retains compatible naming but is unsuitable for direct RTL, whose public ports are simply IR parameter names and `out`. The current mapping is in `NodeToNetlistName()` at z3_lec.cc.

## Recommended implementation plan

### Phase 1 — Define the supported direct-RTL contract

**Goal:** direct LEC only for Verilog emitted by XLS `codegen_main`, initially combinational.

1. Add an explicit input-mode flag to `lec_main`, for example `--verilog_kind=netlist|xls_rtl`, defaulting to `netlist` to preserve compatibility.
2. Document that `xls_rtl` supports output produced by the pinned XLS code generator, not arbitrary Verilog.
3. Establish the public interface mapping:
   - IR parameters $\leftrightarrow$ RTL input ports by exact sanitized name.
   - IR return value $\leftrightarrow$ output port `out`.
4. Reject unsupported IR types or RTL constructs with actionable diagnostics, rather than silently producing incomplete proofs.

**Acceptance test:** a 4-bit `not` function generated by `codegen_main --generator=combinational` proves equivalent without Yosys or a cell library.

### Phase 2 — Add a behavioral Verilog frontend

**Goal:** parse enough generated combinational Verilog to build a Z3 model.

1. Create a distinct RTL representation/parser under the netlist area, such as:
   - `xls/netlist/rtl_verilog_parser.{h,cc}`
   - `xls/solvers/z3_rtl_translator.{h,cc}`
2. Do **not** overload the structural `netlist::rtl::Parser`; its current abstraction is cell/wire based and conflating the two would make maintenance riskier.
3. Implement the minimum AST and grammar needed for observed codegen output:
   - module declarations and ANSI-style ports
   - ranged scalar/vector `input`, `output`, and `wire`
   - continuous `assign`
   - identifiers and bit/range selects
   - literals
   - unary `~`
   - binary `&`, `|`, `^`, arithmetic/shift/compare operators emitted by codegen
   - concatenations, including nesting
   - parentheses and precedence
4. Translate vector expressions directly to Z3 bit-vectors, preserving Verilog widths, bit ordering, and unsigned/signed semantics.
5. Detect combinational cycles before or during translation and report their source locations.

**Acceptance tests:** parser/translator unit tests covering each expression category plus malformed input diagnostics.

### Phase 3 — Implement a direct RTL LEC adapter

**Goal:** reuse the IR half and solver mechanics while replacing only the Verilog half.

1. Introduce a small abstraction for “comparison-side translation,” exposing:
   - bind named input values,
   - retrieve named output bit-vectors,
   - expose the shared Z3 context.
2. Keep `IrTranslator` unchanged.
3. Refactor `Lec` minimally so its equivalence construction can accept either:
   - the existing `NetlistTranslator`, or
   - the new RTL translator.
4. For RTL mode, compare:
   $$
   \neg\left(\bigwedge_{i=0}^{n-1} IR_{\text{out},i} = RTL_{\text{out},i}\right)
   $$
   and ask Z3 whether it is satisfiable.
5. Preserve counterexample output, but print RTL port/output names instead of trying `pN_*` internal-net lookups.

**Acceptance tests:**
- positive: `not`, add, logic/concatenation, select, comparisons, arithmetic;
- negative: deliberately mutate one generated RTL operator/output bit and assert a counterexample;
- regression: existing structural netlist tests in z3_lec_test.cc remain unchanged and pass.

### Phase 4 — Cover XLS pipeline Verilog

**Goal:** support `codegen_main --generator=pipeline`.

1. First inspect actual pipeline Verilog across representative functions to enumerate emitted constructs: register declarations, `always_ff`/`always`, reset handling, valid signals, and scheduling-related names.
2. Select an explicit proof model:
   - **Recommended initial model:** stage-local combinational equivalence with a provided `PipelineSchedule`, matching the current staged LEC approach.
   - **Later model:** bounded sequential equivalence across $k$ cycles, with reset/valid assumptions explicitly encoded.
3. Reuse `PipelineSchedule` to align IR stage boundaries with RTL registers.
4. Define semantics for reset, clock enable, `input_valid`, `output_valid`, and initial state. These must be assumptions/options, not inferred silently.
5. Add sequential RTL translation only once the contract and test matrix are agreed.

**Acceptance tests:** a multi-stage pipelined example proves stage-by-stage; one intentional register or latency mutation fails in the expected stage.

### Phase 5 — Integrate and document

1. Add CLI integration tests that run:
   `DSLX → IR → opt → codegen → lec_main --verilog_kind=xls_rtl`.
2. Keep the existing flow:
   `DSLX → IR → codegen → Yosys → structural netlist → lec_main`
   as the technology-mapping signoff path.
3. Update solvers.md to distinguish:
   - **IR-to-generated-RTL LEC**: validates code generation;
   - **IR-to-gate-netlist LEC**: validates synthesis and mapping;
   - each catches different classes of failures.
4. Add a concise direct-RTL invocation example to the flow guide at manual_flow_guide.md.

## Scope recommendation

Start with **Phase 1–3 for combinational Verilog only**. It is the smallest useful feature, removes the Yosys/cell-library dependency for codegen validation, and has a clear semantic boundary.

Do not replace the existing gate-level flow: direct IR-to-Verilog LEC verifies XLS code generation, while current IR-to-netlist LEC additionally validates synthesis and cell mapping.
# ASAP7 PDK implementation analysis in this repository

## Bottom line

In this repository, **ASAP7 is primarily an estimation and characterization target, not a fully live end-to-end PDK integration**. The codebase still uses ASAP7 as the default analytical delay/area model in several flows, and it still contains the Yosys/OpenSTA plumbing used to characterize and synthesize against ASAP7 libraries, but the open-source workspace configuration now explicitly rejects ASAP7 as a standard-cell target in `xls_oss_config_rules.bzl` (`xls/build_rules/xls_oss_config_rules.bzl:25-26,38-54`).

That split explains the current state well:

- **Still active:** ASAP7 delay/area estimation, scheduling defaults, characterization scripts, docs, and PPA guidance.
- **Partially dormant / workspace-disabled:** direct ASAP7 standard-cell target selection in the OSS Bazel rule configuration.

## 1. Delay model: ASAP7 is an analytical scheduler model

XLS delay estimation is deliberately **not** a live Liberty/NLDM lookup during scheduling. The methodology document says XLS characterizes operations by sweeping synthesized implementations, then fits compact formulas such as `a * bitwidth + b * log2(bitwidth) + c` for use during HLS scheduling (`docs_src/delay_estimation.md:135-177`).

The ASAP7 delay model lives in:

- `xls/estimators/delay_model/models/asap7.textproto`

Its structure shows that ASAP7 timing is encoded as **per-op regressions and aliases**, not as instantiated cells:

- Common ops are modeled from simple features such as `RESULT_BIT_COUNT`, `OPERAND_BIT_COUNT`, and `OPERAND_COUNT` (`xls/estimators/delay_model/models/asap7.textproto:199-258,354-423`).
- Some ops reuse other models through `alias_op`, e.g. `kUMod -> kUDiv`, `kSMod -> kSDiv`, `kShrl/kShra -> kShll`, `kBitSliceUpdate -> kDynamicBitSlice`, and `kArraySlice -> kArrayIndex` (`xls/estimators/delay_model/models/asap7.textproto:348-405,427-430,621-625`).
- Several pure wiring / compile-time constructs are modeled as zero delay, e.g. `kBitSlice`, `kArray`, `kConcat`, `kLiteral`, `kParam`, and `kStateRead` (`xls/estimators/delay_model/models/asap7.textproto:661-700`).
- There are targeted specializations where the generic fit is known to be too coarse:
  - `kSel` with a literal selector becomes fixed zero (`xls/estimators/delay_model/models/asap7.textproto:199-225`).
  - `kUMul` and `kSMul` have `OPERANDS_IDENTICAL` specializations (`xls/estimators/delay_model/models/asap7.textproto:227-260`).
  - `kArrayIndex` and `kArrayUpdate` have literal-index specializations (`xls/estimators/delay_model/models/asap7.textproto:560-619`).

The checked-in model statistics show the ASAP7 model is reasonably accurate for many operations, but multipliers remain the hardest family:

- `kAdd`: mean absolute error `5.613%`
- `kSel`: mean absolute error `4.895%`
- `kUMul`: mean absolute error `10.346%`
- `kSMul`: mean absolute error `9.454%`
- `kUMulp OPERANDS_IDENTICAL`: RMSE `75.42 ps`

These numbers come from `xls/estimators/testdata/asap7_delay_model_stats.csv:3-40`, and the repo has a reproducibility test for them in `xls/estimators/estimator_model_stats_test.py:46-62`.

### Where the ASAP7 delay model is used

- `opt_main` defaults `--delay_model` to `asap7` (`xls/tools/opt_flags.cc:83-87`).
- `codegen_main` uses the selected delay model when scheduling pipeline codegen (`xls/tools/codegen_main.cc:91-128`, `xls/tools/codegen.cc:87-151`).
- The scheduler resolves the named estimator from the registry via `GetDelayEstimator(flags.delay_model())` (`xls/scheduling/scheduling_options.cc:381-389`).

So ASAP7 affects **how XLS schedules operations into cycles** and how timing-aware optimizations reason about critical paths. It does **not** directly mean ASAP7 cells appear in the generated RTL.

## 2. Area model: ASAP7 is also the default analytical area model

The ASAP7 area model lives in:

- `xls/estimators/area_model/models/asap7.textproto`

It mirrors the delay model structurally, but uses `area_regression` instead of `regression`:

- `kSel`, `kUMul`, `kSMul`, `kSDiv`, `kShll`, and `kDynamicBitSlice` are modeled from operand/result shape features (`xls/estimators/area_model/models/asap7.textproto:255-339,413-470`).
- The same style of reuse exists through `alias_op`, e.g. `kUMod -> kUDiv`, `kSMod -> kSDiv`, `kShrl/kShra -> kShll` (`xls/estimators/area_model/models/asap7.textproto:406-465`).
- Literal or wiring-like cases are again zero-cost in the model, e.g. literal select specializations and several structural ops (`xls/estimators/area_model/models/asap7.textproto:273-283` plus other `fixed: 0` entries in the same file).

The important difference is that the area model also embeds **characterization data points** with:

- `delay`
- `delay_offset`
- `total_area`
- `sequential_area`

For example, the earliest ASAP7 area samples include:

- 1-bit `kIdentity`: `total_area: 0.67068`, `sequential_area: 0.5832`
- 4-bit `kNot`: `total_area: 2.50776`, `sequential_area: 2.3328`

See `xls/estimators/area_model/models/asap7.textproto:836-873`.

That connects directly to the area API:

- `AreaEstimator::GetFunctionBaseAreaInSquareMicrons()` sums node areas over the IR graph.
- `AreaEstimator::GetRegisterAreaInSquareMicrons()` scales from the one-bit register cost (`xls/estimators/area_model/area_estimator.cc:35-50`).

`opt_main` defaults `--area_model=asap7` (`xls/tools/opt.h:63-75`, `xls/tools/opt_flags.cc:83-84`), so ASAP7 is also the default cost model for area-sensitive passes.

## 3. Synthesis: ASAP7 support is implemented through Yosys + OpenSTA library plumbing

The clearest ASAP7-specific synthesis wiring is in the characterization script:

- `xls/estimators/run_op_characterization.py`

Its ASAP7 configuration pulls libraries from the OpenROAD ASAP7 platform:

- synthesis library: `flow/objects/asap7/ibex/base/lib/merged.lib`
- STA libraries:
  - `asap7sc7p5t_AO_RVT_FF_nldm_211120.lib.gz`
  - `asap7sc7p5t_INVBUF_RVT_FF_nldm_220122.lib.gz`
  - `asap7sc7p5t_OA_RVT_FF_nldm_211120.lib.gz`
  - `asap7sc7p5t_SIMPLE_RVT_FF_nldm_211120.lib.gz`
  - `asap7sc7p5t_SEQ_RVT_FF_nldm_220123.lib`

See `xls/estimators/run_op_characterization.py:266-289`.

The generic synthesis engine is `YosysSynthesisServiceImpl`, which is not ASAP7-exclusive but is exactly the mechanism ASAP7 characterization and feedback-driven optimization use:

- It builds a Yosys Tcl script that does:
  1. `read_verilog`
  2. `synth -top ...`
  3. `dfflibmap -liberty ...`
  4. `abc -D <target_ps> -liberty ...`
  5. `stat -json -liberty ...`
  6. `write_json`
  7. `write_verilog -noattr -noexpr -nohex -nodec`

  (`xls/synthesis/yosys/yosys_synthesis_service.cc:118-194`)

- It then builds an OpenSTA script that:
  1. `read_liberty` for each STA lib
  2. `read_verilog` on the synthesized netlist
  3. `link_design`
  4. creates a clock on port `clk` if present
  5. reports min period, worst slack, TNS/WNS, and detailed checks

  (`xls/synthesis/yosys/yosys_synthesis_service.cc:341-412`)

- The parsed STA result becomes `slack_ps` and `max_frequency_hz` (`xls/synthesis/yosys/yosys_util.cc:103-147`).

There is also an FDO wrapper, `YosysSynthesizer`, that fixes a 1 GHz target and returns effective path delay as `1000 ps - slack_ps` (`xls/fdo/yosys_synthesizer.h:31-56`, `xls/fdo/yosys_synthesizer.cc:36-50`).

### What this means for ASAP7

ASAP7 is not hardcoded into the synthesis service itself. Instead, ASAP7 enters by supplying:

1. the Liberty file set,
2. the mapped synthesis library,
3. the characterization workflow that produced the estimator textprotos.

So the synthesis implementation is **PDK-parameterized**, while the ASAP7 identity mostly lives in the selected libraries and the checked-in characterized models.

## 4. Verilog: generated RTL is PDK-neutral; ASAP7 mainly changes scheduling

`codegen_main` parses XLS IR, optionally schedules it, and then emits Verilog text (`xls/tools/codegen_main.cc:65-183`).

The important ASAP7-specific behavior is **before** Verilog emission:

- `CodegenMetadata::Create()` resolves the chosen delay estimator and threads it into scheduling/codegen (`xls/tools/codegen.cc:79-145`).
- Pipeline scheduling is driven by that estimator (`xls/tools/codegen.cc:149-186`).
- Final module text generation is still generic RTL generation (`xls/tools/codegen.cc:196-259`).

The public tutorial reflects that separation: `codegen_main --generator=pipeline --delay_model="asap7"` uses ASAP7 to shape the pipeline schedule, then writes a normal Verilog module (`docs_src/tutorials/xlscc_overview.md:121-157`).

So, for Verilog:

- **ASAP7 influences:** cycle boundaries, timing-aware packing, and some optimization decisions.
- **ASAP7 does not directly influence:** emitted cell names, Liberty constructs, or technology-specific primitives in the generated RTL.

The actual cell mapping happens later in synthesis, not in XLS codegen.

## 5. Netlist handling: XLS can consume Liberty + synthesized netlists after ASAP7 mapping

Once RTL has been mapped to cells, the repo has a full internal netlist stack for analysis and equivalence checking.

### Liberty / cell-library side

`function_extractor.cc` converts Liberty-style cell descriptions into `CellLibraryProto` / `CellLibraryEntryProto`:

- pin directions and Boolean functions are extracted from Liberty pin blocks (`xls/netlist/function_extractor.cc:173-225`)
- flop `next_state` is converted into output behavior (`xls/netlist/function_extractor.cc:228-247`)
- state tables are parsed into structured rows (`xls/netlist/function_extractor.cc:105-170`)

Those structures are represented by `CellLibrary`, `CellLibraryEntry`, and `StateTable` (`xls/netlist/cell_library.h:39-167,169-250`).

### Netlist side

The Verilog netlist parser tokenizes names, numbers, comments, block comments, and attributes (`xls/netlist/netlist_parser.cc:105-168,186-243`). Parsed netlists are represented as modules, cells, pins, and nets in `netlist.h` (`xls/netlist/netlist.h:73-152,157-240`).

### Formal / semantic side

`z3_netlist_translator.cc` translates parsed cells into Z3 expressions by:

- resolving each output pin's Boolean function,
- interpreting Liberty state tables when needed,
- recursively mapping `and/or/xor/not` logic into bit-vector formulas

(`xls/solvers/z3_netlist_translator.cc:234-316,318-360`).

This is the key bridge for **LEC-style reasoning on mapped netlists**. In other words: once an ASAP7 Liberty library has been converted into the expected proto form and a mapped netlist is parsed, XLS has the machinery needed to reason about that implementation.

## 6. Repo-level status and inconsistencies worth knowing

There is a real split between documentation/defaults and current OSS workspace behavior:

1. **Docs and defaults still treat ASAP7 as a first-class target**
   - README advertises Yosys synthesis with ASAP7 and SKY130 (`README.md:98-103`).
   - The tutorial uses `--delay_model="asap7"` (`docs_src/tutorials/xlscc_overview.md:128-156`).
   - Contributing guidance asks for 50-seed Yosys PPA evaluation targeting ASAP7 (`CONTRIBUTING.md:82-94`).
   - `opt_main` still defaults both area and delay modeling to ASAP7 (`xls/tools/opt_flags.cc:83-87`).

2. **But current OSS rule configuration disables ASAP7 standard-cell selection**
   - `delay_model_to_standard_cells("asap7")` now fails with: `ASAP7 has been removed from this workspace; choose sky130 or unit` (`xls/build_rules/xls_oss_config_rules.bzl:47-54`).

3. **Some dependency and CI artifacts still reference ASAP7**
   - dependency support patch still wires ASAP7 OpenROAD repos (`dependency_support/rules_hdl/rules_hdl_deps.patch:21-23,40-42`)
   - nightly workflow explicitly clears cached ASAP7 externals (`.github/workflows/nightly-ubuntu-22.04.yml:83-96`)

## 7. Practical interpretation

If you are trying to understand “where ASAP7 matters” in this codebase, the answer is:

- **Most relevant today:** analytical timing/area estimation and characterization.
- **Still present and useful:** Yosys/OpenSTA synthesis plumbing that can target ASAP7 libraries when available.
- **Not technology-specific:** XLS Verilog generation itself.
- **Available for downstream checking:** Liberty extraction, netlist parsing, and Z3-based netlist reasoning.
- **Current caveat:** the open-source workspace no longer exposes ASAP7 as an enabled standard-cell target, even though many defaults, docs, and checked-in models still assume it.

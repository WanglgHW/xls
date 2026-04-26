// Copyright 2026 The XLS Authors
// Test: LEC using icsprout55 PDK cells
// Verifies that the icsprout55 standard cell library functions correctly
// with the Z3-based LEC tool.

#include "xls/solvers/z3_lec.h"

#include <memory>
#include <string>

#include "gtest/gtest.h"
#include "absl/status/statusor.h"
#include "xls/common/status/matchers.h"
#include "xls/common/status/status_macros.h"
#include "xls/ir/function.h"
#include "xls/ir/ir_parser.h"
#include "xls/netlist/cell_library.h"
#include "xls/netlist/netlist.h"
#include "xls/netlist/netlist_parser.h"

namespace xls {
namespace solvers {
namespace z3 {
namespace {

// Create an icsprout55-style cell library from proto entries.
absl::StatusOr<netlist::CellLibrary> MakeIcsprout55CellLibrary() {
  netlist::CellLibraryProto proto;

  // INVX0P5H7L - Inverter (icsprout55 PDK)
  auto* inv = proto.add_entries();
  inv->set_kind(netlist::INVERTER);
  inv->set_name("INV");
  inv->add_input_names("A");
  auto* inv_pin = inv->mutable_output_pin_list()->add_pins();
  inv_pin->set_name("ZN");
  inv_pin->set_function("!A");

  // AND2X0P5H7L - 2-input AND (icsprout55 PDK)
  auto* and2 = proto.add_entries();
  and2->set_kind(netlist::NAND);  // Use NAND kind for .ZN output pin
  and2->set_name("AND");
  and2->add_input_names("A");
  and2->add_input_names("B");
  auto* and_pin = and2->mutable_output_pin_list()->add_pins();
  and_pin->set_name("Z");
  and_pin->set_function("A&B");

  // OR2X0P5H7L - 2-input OR (icsprout55 PDK)
  auto* or2 = proto.add_entries();
  or2->set_kind(netlist::OTHER);
  or2->set_name("OR");
  or2->add_input_names("A");
  or2->add_input_names("B");
  auto* or_pin = or2->mutable_output_pin_list()->add_pins();
  or_pin->set_name("Z");
  or_pin->set_function("A|B");

  // XOR2X0P5H7L - 2-input XOR (icsprout55 PDK)
  auto* xor2 = proto.add_entries();
  xor2->set_kind(netlist::XOR);
  xor2->set_name("XOR");
  xor2->add_input_names("A");
  xor2->add_input_names("B");
  auto* xor_pin = xor2->mutable_output_pin_list()->add_pins();
  xor_pin->set_name("Z");
  xor_pin->set_function("A^B");

  // DFF - Flip-flop (icsprout55 PDK style)
  auto* dff = proto.add_entries();
  dff->set_kind(netlist::FLOP);
  dff->set_name("DFF");
  dff->add_input_names("D");
  auto* dff_pin = dff->mutable_output_pin_list()->add_pins();
  dff_pin->set_name("Q");
  dff_pin->set_function("D");

  return netlist::CellLibrary::FromProto(proto);
}

absl::StatusOr<bool> MatchWithIcsprout55(const std::string& ir_text,
                                         const std::string& netlist_text) {
  XLS_ASSIGN_OR_RETURN(std::unique_ptr<Package> package,
                       Parser::ParsePackage(ir_text));
  XLS_ASSIGN_OR_RETURN(Function * entry_function, package->GetTopAsFunction());

  XLS_ASSIGN_OR_RETURN(netlist::CellLibrary cell_library,
                       MakeIcsprout55CellLibrary());
  netlist::rtl::Scanner scanner(netlist_text);
  XLS_ASSIGN_OR_RETURN(
      std::unique_ptr<netlist::rtl::Netlist> netlist,
      netlist::rtl::Parser::ParseNetlist(&cell_library, &scanner));

  LecParams params;
  params.ir_package = package.get();
  params.ir_function = entry_function;

  params.netlist = netlist.get();
  params.netlist_module_name = "main";

  XLS_ASSIGN_OR_RETURN(std::unique_ptr<Lec> lec, Lec::Create(params));
  return lec->Run();
}

// Test: 4-bit NOT using icsprout55 INVX0P5H7L cell
TEST(Icsprout55LecTest, NotGateWithIcsprout55) {
  std::string ir_text = R"(
package p

top fn main(input: bits[4]) -> bits[4] {
  ret not.2: bits[4] = not(input)
}
)";

  // Netlist uses INV cells (modeling icsprout55 INVX0P5H7L)
  // with same naming convention as XLS codegen
  std::string netlist_text = R"(
module main ( clk, input_3_, input_2_, input_1_, input_0_, out_3_, out_2_, out_1_, out_0_);
  input clk, input_3_, input_2_, input_1_, input_0_;
  output out_3_, out_2_, out_1_, out_0_;
  wire p0_input_3_, p0_input_2_, p0_input_1_, p0_input_0_,
       p0_not_2_comb_3_, p0_not_2_comb_2_, p0_not_2_comb_1_, p0_not_2_comb_0_;

  DFF p0_input_reg_3_ ( .D(input_3_), .CLK(clk), .Q(p0_input_3_) );
  DFF p0_input_reg_2_ ( .D(input_2_), .CLK(clk), .Q(p0_input_2_) );
  DFF p0_input_reg_1_ ( .D(input_1_), .CLK(clk), .Q(p0_input_1_) );
  DFF p0_input_reg_0_ ( .D(input_0_), .CLK(clk), .Q(p0_input_0_) );

  INV p0_not_2_3_ ( .A(p0_input_3_), .ZN(p0_not_2_comb_3_) );
  INV p0_not_2_2_ ( .A(p0_input_2_), .ZN(p0_not_2_comb_2_) );
  INV p0_not_2_1_ ( .A(p0_input_1_), .ZN(p0_not_2_comb_1_) );
  INV p0_not_2_0_ ( .A(p0_input_0_), .ZN(p0_not_2_comb_0_) );

  DFF p0_not_2_reg_3_ (.D(p0_not_2_comb_3_), .CLK(clk), .Q(out_3_));
  DFF p0_not_2_reg_2_ (.D(p0_not_2_comb_2_), .CLK(clk), .Q(out_2_));
  DFF p0_not_2_reg_1_ (.D(p0_not_2_comb_1_), .CLK(clk), .Q(out_1_));
  DFF p0_not_2_reg_0_ (.D(p0_not_2_comb_0_), .CLK(clk), .Q(out_0_));
endmodule
)";

  XLS_ASSERT_OK_AND_ASSIGN(bool match, MatchWithIcsprout55(ir_text, netlist_text));
  ASSERT_TRUE(match);
}

// Test: 2-bit adder using icsprout55 cells (AND, OR, XOR)
TEST(Icsprout55LecTest, AdderWithIcsprout55) {
  std::string ir_text = R"(
package p

top fn main(a: bits[2], b: bits[2]) -> bits[2] {
  ret add.3: bits[2] = add(a, b)
}
)";

  std::string netlist_text = R"(
module main(clk, a_1_, a_0_, b_1_, b_0_, out_1_, out_0_);
  input clk, a_1_, a_0_, b_1_, b_0_;
  output out_1_, out_0_;
  wire p0_a_1_, p0_a_0_, p0_b_1_, p0_b_0_, p0_add_3_comb_0_, p0_add_3_comb_1_, carry, high;

  DFF p0_a_reg_1_ ( .D(a_1_), .CLK(clk), .Q(p0_a_1_) );
  DFF p0_a_reg_0_ ( .D(a_0_), .CLK(clk), .Q(p0_a_0_) );
  DFF p0_b_reg_1_ ( .D(b_1_), .CLK(clk), .Q(p0_b_1_) );
  DFF p0_b_reg_0_ ( .D(b_0_), .CLK(clk), .Q(p0_b_0_) );

  XOR out_0_cell ( .A(p0_a_0_), .B(p0_b_0_), .Z(p0_add_3_comb_0_) );

  AND carry_cell ( .A(p0_a_0_), .B(p0_b_0_), .Z(carry) );
  XOR high_cell ( .A(p0_a_1_), .B(p0_b_1_), .Z(high) );
  XOR out_1_cell ( .A(high), .B(carry), .Z(p0_add_3_comb_1_) );

  DFF p0_add_3_reg_1_ ( .D(p0_add_3_comb_1_), .CLK(clk), .Q(out_1_) );
  DFF p0_add_3_reg_0_ ( .D(p0_add_3_comb_0_), .CLK(clk), .Q(out_0_) );
endmodule
)";

  XLS_ASSERT_OK_AND_ASSIGN(bool match, MatchWithIcsprout55(ir_text, netlist_text));
  ASSERT_TRUE(match);
}

// Test: icsprout55 cells correctly detect mismatch
TEST(Icsprout55LecTest, DetectsMismatch) {
  std::string ir_text = R"(
package p

top fn main(input: bits[4]) -> bits[4] {
  ret not.2: bits[4] = not(input)
}
)";

  // Same netlist but one INV replaced with OR (wrong function)
  std::string netlist_text = R"(
module main ( clk, input_3_, input_2_, input_1_, input_0_, out_3_, out_2_, out_1_, out_0_);
  input clk, input_3_, input_2_, input_1_, input_0_;
  output out_3_, out_2_, out_1_, out_0_;
  wire p0_input_3_, p0_input_2_, p0_input_1_, p0_input_0_,
       p0_not_2_comb_3_, p0_not_2_comb_2_, p0_not_2_comb_1_, p0_not_2_comb_0_;

  DFF p0_input_reg_3_ ( .D(input_3_), .CLK(clk), .Q(p0_input_3_) );
  DFF p0_input_reg_2_ ( .D(input_2_), .CLK(clk), .Q(p0_input_2_) );
  DFF p0_input_reg_1_ ( .D(input_1_), .CLK(clk), .Q(p0_input_1_) );
  DFF p0_input_reg_0_ ( .D(input_0_), .CLK(clk), .Q(p0_input_0_) );

  INV p0_not_2_3_ ( .A(p0_input_3_), .ZN(p0_not_2_comb_3_) );
  INV p0_not_2_2_ ( .A(p0_input_2_), .ZN(p0_not_2_comb_2_) );
  OR  p0_not_2_1_ ( .A(p0_input_1_), .B(p0_input_1_), .Z(p0_not_2_comb_1_) );
  INV p0_not_2_0_ ( .A(p0_input_0_), .ZN(p0_not_2_comb_0_) );

  DFF p0_not_2_reg_3_ (.D(p0_not_2_comb_3_), .CLK(clk), .Q(out_3_));
  DFF p0_not_2_reg_2_ (.D(p0_not_2_comb_2_), .CLK(clk), .Q(out_2_));
  DFF p0_not_2_reg_1_ (.D(p0_not_2_comb_1_), .CLK(clk), .Q(out_1_));
  DFF p0_not_2_reg_0_ (.D(p0_not_2_comb_0_), .CLK(clk), .Q(out_0_));
endmodule
)";

  XLS_ASSERT_OK_AND_ASSIGN(bool match, MatchWithIcsprout55(ir_text, netlist_text));
  ASSERT_FALSE(match);
}

}  // namespace
}  // namespace z3
}  // namespace solvers
}  // namespace xls

// Simple logic function for LEC testing with icsprout55 PDK
// Tests: NOT, AND, OR, XOR

fn main(a: bits[4], b: bits[4]) -> bits[16] {
    let not_a = !a;
    let and_ab = a & b;
    let or_ab = a | b;
    let xor_ab = a ^ b;
    not_a ++ and_ab ++ or_ab ++ xor_ab
}

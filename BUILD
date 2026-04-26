# Copyright 2022 The XLS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# NOTE: this is the build file for the root directory of the workspace. The
# root directory generally has very few files of interest.
#
# Targets for XLS are generally in the `xls` subdirectory; e.g.
# can be seen via:
#
#   bazel query //xls/...
#
# And built (in optimized mode) via:
#
#   bazel build -c opt //xls/...
#
# See https://google.github.io/xls/build_system/#whirlwind-intro-to-bazel for
# more tutorial information.

load("@rules_license//rules:license.bzl", "license")

package(
    default_applicable_licenses = ["//:license"],
    default_visibility = ["//xls:xls_internal"],
    licenses = ["notice"],  # Apache 2.0
)

license(
    name = "license",
    package_name = "xls",
)

exports_files([
    "LICENSE",
    "mkdocs.yml",
])

# Minimal build entrypoint (no PDK / OpenROAD flows).
alias(
    name = "interpreter_main",
    actual = "//xls/dslx:interpreter_main",
)

alias(
    name = "ir_converter_main",
    actual = "//xls/dslx/ir_convert:ir_converter_main",
)

alias(
    name = "opt_main",
    actual = "//xls/tools:opt_main",
)

alias(
    name = "codegen_main",
    actual = "//xls/tools:codegen_main",
)

alias(
    name = "sched_printer_main",
    actual = "//xls/visualization:sched_printer_main",
)


alias(
    name = "proc_network_printer_main",
    actual = "//xls/visualization:proc_network_printer_main",
)

alias(
    name = "ir_to_proto_main",
    actual = "//xls/visualization/ir_viz:ir_to_proto_main",
)

alias(
    name = "ir_to_json_main",
    actual = "//xls/visualization/ir_viz:ir_to_json_main",
)

alias(
    name = "ir_to_csvs_main",
    actual = "//xls/visualization/ir_viz:ir_to_csvs_main",
)

alias(
    name = "yosys_server_main",
    actual = "//xls/synthesis/yosys:yosys_server_main",
)

alias(
    name = "synthesis_client_main",
    actual = "//xls/synthesis:synthesis_client_main",
)

alias(
    name = "lec_main",
    actual = "//xls/tools:lec_main",
)

filegroup(
    name = "minimal_tools",
    srcs = [
        ":interpreter_main",
        "ir_converter_main",
        ":opt_main",
        ":codegen_main",
        ":sched_printer_main",
        ":proc_network_printer_main",
        ":ir_to_proto_main",
        ":ir_to_json_main",
        ":ir_to_csvs_main",
        ":yosys_server_main",
        ":synthesis_client_main",
        ":lec_main",
    ],
)

%bcond check 1

# Goose is being shipped in RHEL 9.x extensions, and in such environment, we
# don't have access to `_smp_tasksize_proc` due to it being added a newer
# version of rpm, and to allow our package to build in such environment and to
# avoid OOM during our builds, we have borrowed a macro from the rust commpiler
# package to allow us to set constraints in that environment.
#   * https://src.fedoraproject.org/rpms/rust/blob/rawhide/f/rust.spec#_820
%if %undefined constrain_build
%define constrain_build(m:) %{lua:
  for l in io.lines('/proc/meminfo') do
    if l:sub(1, 9) == "MemTotal:" then
      local opt_m = math.tointeger(rpm.expand("%{-m*}"))
      local mem_total = math.tointeger(string.match(l, "MemTotal:%s+(%d+)"))
      local cpu_limit = math.max(1, mem_total // (opt_m * 1024))
      if cpu_limit < math.tointeger(rpm.expand("%_smp_build_ncpus")) then
        rpm.define("_smp_build_ncpus " .. cpu_limit)
      end
      break
    end
  end
}
%endif

%constrain_build -m 6144

%global rustflags_codegen_units 16
# Features used at build and test time via '%%cargo_build -n -f' and
# '%%cargo_test -n -f' (-n = --no-default-features, -f = --features).
# Must match the --features argument in generate-vendor-tarball.sh so the vendor
# tarball contains exactly the crates needed to build this feature set.
%global downstream_features native-tls,otel,telemetry,system-keyring,disable-update

# Shared cargo flags for '%%cargo_build'/'%%cargo_test' (see %%build/%%check),
# kept in one place so both call sites can't drift out of sync.
#
# -n -f "%%{downstream_features}": explicitly disable upstream defaults
# (includes rustls-tls, aws-providers, tui, code-mode, and other features
# incompatible with Fedora packaging guidelines) and activate only the
# features needed for downstream packaging.
#
# -- --package goose-cli: scopes the build/test to the goose-cli package and
# its dependency tree only. With resolver = "2", building the whole
# workspace in one invocation activates any --features name across *every*
# workspace member that defines it, not just the ones goose-cli actually
# depends on; that let aws-lc-rs/aws-lc-sys leak into the build via unrelated
# crates even though goose-cli never needs it. Scoping via a build flag
# (rather than patching default-members into Cargo.toml) keeps this
# controllable via build flags, which upstream also suggested and which is
# easier to review/maintain across version bumps than a Cargo.toml patch.
# '%%cargo_build'/'%%cargo_test's own getopt only recognizes -n/-a/-f, so a
# bare '-p' errors ("Unknown option p"); everything after a literal '--' is
# instead passed through raw to the underlying 'cargo build'/'cargo test'
# invocation.
#
# --ignore-rust-version: goose 1.45.0 declares rust-version = "1.94.1", but
# RHEL 9/10 and EPEL 9/10 currently ship an older Rust toolset (1.92.0) and
# won't pick up 1.94 until ~Nov 2026. This skips cargo's pre-flight MSRV
# check and attempts the build anyway; it only works if the code doesn't
# actually rely on a post-1.92 compiler feature. EXPERIMENTAL — drop this
# flag if a real build shows the older rustc genuinely can't compile it.
%global goose_cargo_flags -n -f "%{downstream_features}" -- --package goose-cli --ignore-rust-version

Name:           goose
Version:        1.45.0
Release:        %autorelease
Summary:        Extensible AI agent client
URL:            https://github.com/aaif-goose/goose


Source:         %{url}/releases/download/v%{version}/%{name}-source-v%{version}.tar.gz
# To create the vendor tarball, use the generate-vendor-tarball.sh script:
#   chmod +x generate-vendor-tarball.sh
#   ./generate-vendor-tarball.sh
Source1:        %{name}-%{version}-vendor.tar.zstd
# This script is used to generate the vendor tarball for goose, and while it
# does not offer any practical/real usage for the application, it helps us to
# easily generate the vendored tarball and apply the correct patches while
# doing so.
Source99:       generate-vendor-tarball.sh
# This adds the changelog information used during Fedora/EPEL/RHEL builds to
# inform what has changed from version to version. It has no practical effect
# other than just being here to facilitate `fedpkg/rhpkg import` in the downstream.
Source100:      changelog

## Dependency patches (1-19)
#
# Strip non-Linux platform deps (Windows winapi/winreg, macOS metal/apple-native
# keyring), remove the vendor/v8 workspace member and all [patch.crates-io]
# entries (v8, cudaforge). Remove keyring 'vendored' feature (use system dbus).
# Switch sqlx from bundled 'sqlite' to 'sqlite-unbundled' to use system libsqlite3.
# Remove 'nostr', 'aws-providers', and 'rustls-tls' from goose-cli default
# features to prevent unwanted crates from leaking into the vendor tarball via
# cargo vendor-filterer workspace-level resolution (resolver=2 does not propagate
# --no-default-features to individual workspace members).
# Feature flags (native-tls, otel, telemetry, system-keyring, disable-update) are
# passed explicitly at build time via '%%cargo_build -n -f' and '%%cargo_test -n -f',
# into Cargo.toml; see %build and %check.
Patch1:         0001-Strip-non-Linux-deps-and-use-system-libraries.patch
# Remove aws_lc_rs from the workspace-level rustls default-features so it is
# not pulled into the native-tls build path. Activate it explicitly only under
# the rustls-tls feature flag in crates/goose/Cargo.toml.
Patch2:         0002-aws-lc-rs-feature-flag.patch

## Code patches (20-99)
#
# Avoid the 'RETURNING' SQL statement (requires SQLite 3.35.0) and the
# 'unixepoch()' function (requires SQLite 3.38.0). EPEL 9 is stuck on
# SQLite 3.34.1, so we split the INSERT + SELECT into two statements and
# replace unixepoch() with CAST(strftime('%s', ...) AS INTEGER).
Patch20:         0020-Fix-sql-statement-from-session-manager.patch
# code-mode is not in the --features list passed at build time, so we update
# the snapshot test so it passes without that feature. That's better than
# skipping the test entirely.
Patch21:         0021-Update-snapshot-test-without-codemode-instructions.patch

## Downstream only patches (100-799)
#
# Patch the `build.rs` for `ring` crate to avoid using the pre-generated object
# files that comes with the vendored crate, and instead, build from system
# libraries.
# The patch was taken from:
#   * https://src.fedoraproject.org/rpms/rust-ring/blob/d6d681ed07c088671cb5accc0102470b059a5e88/f/rust-ring.spec#_24
#
# We have it placed in our directory due to the need of modifications depending
# on the version bump from ring, otherwise, we should
Patch0100:      0100-Downstream-only-never-use-pre-generated-object-files.patch
# Enable the `pkg-config` feature in zstd-sys and zstd-safe so they link
# against the system libzstd-devel instead of compiling from bundled sources.
Patch0101:      0101-Downstream-only-enable-zstd-sys-pkg-config.patch

## RHEL only patches (800-899)
# Patches in the 800-899 range are applied only to RHEL.
#
# Add disclaimer as required by legal only on RHEL
Patch800:       0800-Include-legal-message-for-goose-proxy-provider.patch

# i686: https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:    %{ix86}

# This package provides a binary called goose and it will conflict with our
# package, as both installs the resulting binary to `/usr/bin/goose`, so it's
# better that we indicate it has a conflict.
Conflicts: golang-github-pressly-goose


# The license for the goose project is Apache-2.0, except for:
#
# MIT (Minified JavaScript libraries):
#   - crates/goose-mcp/src/autovisualiser/templates/assets/chart.min.js
#   - crates/goose-mcp/src/autovisualiser/templates/assets/mermaid.min.js
#   - crates/goose-mcp/src/autovisualiser/templates/assets/leaflet.markercluster.min.js
#
# ISC (Minified JavaScript library):
#   - crates/goose-mcp/src/autovisualiser/templates/assets/d3.min.js
#
# BSD-3-Clause (Minified Javascript library):
#   - crates/goose-mcp/src/autovisualiser/templates/assets/d3.sankey.min.js
#
# BSD-2-Clause: (Minified JavaScript library and CSS stylesheet)
#   - crates/goose-mcp/src/autovisualiser/templates/assets/leaflet.min.js
#   - crates/goose-mcp/src/autovisualiser/templates/assets/leaflet.min.css
#
# CC-BY-4.0:
#   - All documentation (excluding specifications)
#
# CDLA-Permissive-2.0:
#   - introduced by the opentelemetry-semantic-conventions crate
#
# MPL-2.0+:
#   - introduced by the option-ext crate.

# licensecheck will report that set of 6 licenses for the source archive.
#
# A couple of files present under `crates/goose-mcp` and `crates/goose-cli`
# were discussed in the legal ML due to them not having a clear license or
# copyright terms in the upstream repository. The discussion of those items can
# be seen at:
#   - https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/thread/JDE6YNL42ZKVA5ZF4PEUGI5SV2PCSHIR/
#
#   For convenience, the items discussed in the legal ML thread are namely:
#   	- https://github.com/block/goose/tree/v1.45.0/crates/goose-mcp/src/computercontroller/tests/data
#   	- https://github.com/block/goose/tree/v1.45.0/crates/goose-cli/src/scenario_tests/recordings
#
# Rust crates compiled into the executable contribute additional license terms.
# To obtain the following list of licenses, build the package and note the
# output of %%{cargo_license_summary}.

#
# (Apache-2.0 OR MIT) AND BSD-3-Clause
# (MIT OR Apache-2.0) AND Unicode-3.0
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 AND ISC
# Apache-2.0 OR BSL-1.0
# Apache-2.0 OR BSL-1.0 OR MIT
# Apache-2.0 OR ISC OR MIT
# Apache-2.0 OR MIT
# Apache-2.0 OR MIT OR Zlib
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSD-2-Clause
# BSD-2-Clause OR Apache-2.0 OR MIT
# BSD-3-Clause
# BSD-3-Clause AND MIT
# BSD-3-Clause OR Apache-2.0
# BSD-3-Clause OR MIT
# BSL-1.0
# CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception
# CC0-1.0 OR MIT-0 OR Apache-2.0
# CDLA-Permissive-2.0
# ISC
# ISC AND (Apache-2.0 OR ISC)
# ISC AND (Apache-2.0 OR ISC) AND Apache-2.0 AND MIT AND BSD-3-Clause AND (Apache-2.0 OR ISC OR MIT) AND (Apache-2.0 OR ISC OR MIT-0)
# LGPL-3.0-or-later
# MIT
# MIT AND BSD-3-Clause
# MIT OR Apache-2.0
# MIT OR Apache-2.0 OR LGPL-2.1-or-later
# MIT OR Apache-2.0 OR Zlib
# MIT OR Zlib OR Apache-2.0
# MIT-0
# MPL-2.0
# MPL-2.0+
# Unicode-3.0
# Unlicense OR MIT
# Unlicense OR MIT OR Apache-2.0 OR CC0-1.0
# Zlib
# Zlib OR Apache-2.0 OR MIT
# bzip2-1.0.6
License:        %{shrink:
                (0BSD OR Apache-2.0 OR MIT)
                AND Apache-2.0
                AND (Apache-2.0 AND ISC)
                AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR CC0-1.0)
                AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR MIT)
                AND (Apache-2.0 OR BSD-2-Clause OR MIT)
                AND (Apache-2.0 OR BSD-3-Clause)
                AND (Apache-2.0 OR BSL-1.0)
                AND (Apache-2.0 OR BSL-1.0 OR MIT)
                AND (Apache-2.0 OR CC0-1.0 OR MIT OR Unlicense)
                AND (Apache-2.0 OR CC0-1.0 OR MIT-0)
                AND (Apache-2.0 OR ISC)
                AND (Apache-2.0 OR ISC OR MIT)
                AND (Apache-2.0 OR ISC OR MIT-0)
                AND (Apache-2.0 OR LGPL-2.1-or-later OR MIT)
                AND (Apache-2.0 OR MIT)
                AND (Apache-2.0 OR MIT OR Zlib)
                AND BSD-2-Clause
                AND BSD-3-Clause
                AND (BSD-3-Clause AND MIT)
                AND (BSD-3-Clause OR MIT)
                AND BSL-1.0
                AND CDLA-Permissive-2.0
                AND ISC
                AND LGPL-3.0-or-later
                AND MIT
                AND (MIT OR Unlicense)
                AND MIT-0
                AND MPL-2.0
                AND MPL-2.0+
                AND Unicode-3.0
                AND Zlib
                AND bzip2-1.0.6
                }
# LICENSE.dependencies contains a full license breakdown

BuildRequires:  cargo-rpm-macros >= 25

# Required by crate libdbus-sys (vendored)
BuildRequires:  dbus-devel
# Required by crate libsqlite3-sys (vendored)
BuildRequires:  clang-devel
BuildRequires:  pkgconfig(sqlite3)
# Required by crate onig_sys (vendored)
BuildRequires:  oniguruma-devel
# Required by crate openssl-sys (vendored)
BuildRequires:  openssl-devel
# Required by crate ring (vendored)
BuildRequires:  /usr/bin/perl
# Required by crate zstd-sys (vendored)
BuildRequires:  libzstd-devel

# Sublime Text 3 language definitions for syntax highlighting
# from: https://github.com/sublimehq/Packages/tree/fa6b862
# - all except Rust: LicenseRef-Fedora-UltraPermissive
#   https://gitlab.com/fedora/legal/fedora-license-data/-/issues/516
# - Rust: MIT
Provides:       bundled(sublime-syntax) = 4075~gitfa6b862

# In RHEL 9, we depend on sqlite3 3.34.1-10 as it contains a necessary fix for
# exporting the `sqlite3_deserialize` function for goose builds.
# More info on: https://redhat.atlassian.net/browse/RHEL-155950
%if 0%{?rhel} == 9
Requires:       sqlite-libs >= 3.34.1-10
%endif

# Third-party language definitions for syntax highlighting The `syntect` crate
# is bundling all of sublimehq/Packages syntax definitions. To achieve the
# below list of langauge definitions syntaxes, use the following command:
#    * strings %%{name}-%%{version}/vendor/syntect-*/assets/default_newlines.packdump | grep 'Packages/'
Provides:       bundled(sublime-syntax-ASP)
Provides:       bundled(sublime-syntax-ActionScript)
Provides:       bundled(sublime-syntax-AppleScript)
Provides:       bundled(sublime-syntax-BatchFile)
Provides:       bundled(sublime-syntax-CSharp)
Provides:       bundled(sublime-syntax-Cpp)
Provides:       bundled(sublime-syntax-CSS)
Provides:       bundled(sublime-syntax-Clojure)
Provides:       bundled(sublime-syntax-D)
Provides:       bundled(sublime-syntax-Diff)
Provides:       bundled(sublime-syntax-Erlang)
Provides:       bundled(sublime-syntax-Go)
Provides:       bundled(sublime-syntax-Graphviz)
Provides:       bundled(sublime-syntax-Groovy)
Provides:       bundled(sublime-syntax-HTML)
Provides:       bundled(sublime-syntax-Haskell)
Provides:       bundled(sublime-syntax-Java)
Provides:       bundled(sublime-syntax-JavaScript)
Provides:       bundled(sublime-syntax-LaTeX)
Provides:       bundled(sublime-syntax-Lisp)
Provides:       bundled(sublime-syntax-Lua)
Provides:       bundled(sublime-syntax-Makefile)
Provides:       bundled(sublime-syntax-Markdown)
Provides:       bundled(sublime-syntax-Matlab)
Provides:       bundled(sublime-syntax-OCaml)
Provides:       bundled(sublime-syntax-Object-C)
Provides:       bundled(sublime-syntax-PHP)
Provides:       bundled(sublime-syntax-Pascal)
Provides:       bundled(sublime-syntax-Perl)
Provides:       bundled(sublime-syntax-Python)
Provides:       bundled(sublime-syntax-R)
Provides:       bundled(sublime-syntax-Rails)
Provides:       bundled(sublime-syntax-Regular-Expressions)
Provides:       bundled(sublime-syntax-RestructuredText)
Provides:       bundled(sublime-syntax-Ruby)
Provides:       bundled(sublime-syntax-Rust)
Provides:       bundled(sublime-syntax-SQL)
Provides:       bundled(sublime-syntax-Scala)
Provides:       bundled(sublime-syntax-ShellScript)
Provides:       bundled(sublime-syntax-TCL)
Provides:       bundled(sublime-syntax-Textile)
Provides:       bundled(sublime-syntax-XML)
Provides:       bundled(sublime-syntax-YAML)

# Default themes that are shipped with `syntect` crate under the assets folder.
# To achieve the below list of themes definitions, see:
#   * https://github.com/trishume/syntect/blob/v5.3.0/src/dumps.rs#L207-L218.
#
# InspiredGithub theme: MIT
Provides:       bundled(syntect-theme-InspiredGithub)
# Solarized theme: MIT
Provides:       bundled(syntect-theme-Solarized)
# Spacegray theme: MIT
# The specific themes mentioned in the above snippet for syntect#v5.3.0
# (src/dump.rs#L212) is included in the Spacegray theme.
Provides:       bundled(sublime-theme-Spacegray)

# BLAKE3 cryptographic hash function C/assembly implementation bundled in the
# `blake3` crate. The upstream build.rs has no pkg-config hook to use the
# system blake3-devel package, so the C sources are compiled at build time.
# blake3: CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception
Provides:       bundled(blake3) = 1.8.5

# Minified JavaScript libraries and minified CSS stylesheets contained in
# `goose-mcp` crate for the autovisualizer tool.
#   * crates/goose-mcp/src/autovisualizer/templates/assets/
#
# Note: Versions where checked under each minified file.
#
# chart.min.js: MIT
Provides:       bundled(chart-min-js) = 4.5.0
# d3.min.js: ISC
Provides:       bundled(d3-min-js) = 7.9.0
# d3-sakey.min.js: BSD-3-Clause
Provides:       bundled(d3-sankey-min-js) = 0.12.3
# leaflet.min.js: BSD-2-Clause
Provides:       bundled(leaflet-min-js) = 1.9.4
# leaflet.min.css: BSD-2-Clause
Provides:       bundled(leaflet-min-css) = 1.9.4
# leaflet-markercluster.min.js: MIT
Provides:       bundled(leaflet-markercluster-min-js) = 1.5.3
# mermaid.min.js: MIT
# Couldn't find a version of the mermaid library inside the minified file. We
# assume it is the latest version, as all the others are also in the latest,
# but since we were not able to identify it, better to be safe and not provide
# any version here.
Provides:       bundled(mermaid-min-js)

# Tree-sitter parsing library and language grammars. The C sources are compiled
# at build time from the vendored crates. System packages exist in Fedora for
# most of these, but the upstream build.rs scripts have no pkg-config hook to
# use them. tree-sitter-kotlin and tree-sitter-swift have no Fedora system
# package at all.
# tree-sitter: MIT
Provides:       bundled(tree-sitter) = 0.26.10
# tree-sitter-go: MIT
Provides:       bundled(tree-sitter-go) = 0.25.0
# tree-sitter-java: MIT
Provides:       bundled(tree-sitter-java) = 0.23.5
# tree-sitter-javascript: MIT
Provides:       bundled(tree-sitter-javascript) = 0.25.0
# tree-sitter-kotlin-ng: MIT (no Fedora system package available)
Provides:       bundled(tree-sitter-kotlin) = 1.1.0
# tree-sitter-python: MIT
Provides:       bundled(tree-sitter-python) = 0.25.0
# tree-sitter-ruby: MIT
Provides:       bundled(tree-sitter-ruby) = 0.23.1
# tree-sitter-rust: MIT
Provides:       bundled(tree-sitter-rust) = 0.24.2
# tree-sitter-swift: MIT (no Fedora system package available)
Provides:       bundled(tree-sitter-swift) = 0.7.3
# tree-sitter-typescript: MIT
Provides:       bundled(tree-sitter-typescript) = 0.23.2

%global _description %{expand:
Goose is your on-machine AI agent, capable of automating complex development
tasks from start to finish. More than just code suggestions, goose can build
entire projects from scratch, write and execute code, debug failures,
orchestrate workflows, and interact with external APIs - autonomously.

Whether you're prototyping an idea, refining existing code, or managing
intricate engineering pipelines, goose adapts to your workflow and executes
tasks with precision.

Designed for maximum flexibility, goose works with any LLM and supports
multi-model configuration to optimize performance and cost, seamlessly
integrates with MCP servers, and is available as both a desktop app as well as
CLI - making it the ultimate AI assistant for developers who want to move
faster and focus on innovation.}

%description    %{_description}

%prep

# Break the patches into batches since
# patches >= 800 are only applied on RHEL systems.
# The release artifact extracts to goose-v%%{version}/ (note the 'v' prefix),
# unlike the old auto-generated archive which used goose-%%{version}/.
%setup -q -n %{name}-v%{version} -a1
%autopatch -p1 -M 799

%if 0%{?rhel}
%autopatch -p1 -m 800 -M 899
%endif

# Remove the documentation folder but leave `static/img/logo_{dark,light}.png`
# in it, as they are used in goose-cli crate. All the other markdown, audio,
# images and etc are not necessary to be present here.
find documentation \
    -depth \( -type f ! -path "documentation/static/img/logo_dark.png" ! -path "documentation/static/img/logo_light.png" -delete \) \
    -o \( -type d -empty -delete \)

# The following folders are being deleted here so they are not present in the
# rebuilt srpm.
#   * Delete the `ui` folder as it contains the electron desktop app for Goose,
#     which should not be packaged here.
#
#   * Remove the `bin` folder as it is managed by hermit
#     (https://github.com/cashapp/hermit) to bootstrap development tools used
#     by goose.
#
#   * Remove evals folder as they are used in upstream CI for evaluation, but
#     serve no purpose on downstream
#
#   * Remove the `services` and `oidc-proxy folder as it contains an
#     `ask-ai-bot` that is used mainly for the discord community, which, does
#     not provide any benefit to keep it here as it is not being used by the
#     goose source in any way or form.
#
#   * Remove the in-tree vendor/v8 shim crate (used by upstream for code-mode
#     feature which we disable). Already removed from workspace members by
#     patch.
rm -rf ui bin .claude .codex .cursor evals services oidc-proxy vendor/v8

# Remove the `test_image.jpg` as we are not sure if this was LLM generated or
# made by a human. Since there is no copyright data anywhere in the repository
# mentioning this and the PR that introduced it
# (https://github.com/block/goose/pull/3688) does not mention anything about
# the source of the image, it's better that we remove this anyway.
rm crates/goose-cli/src/scenario_tests/test_data/test_image.jpg

# Sometimes Rust sources start with #![...] attributes, and "smart" editors
# think it's a shebang and make them executable. Then brp-mangle-shebangs gets
# upset...
find -name '*.rs' -type f -perm /111 -exec chmod -v -x '{}' '+'

%cargo_prep -v vendor

%build
# The oniguruma-sys crate does not have a feature to enable using system lib
# (pkg-config), so we have to set `RUSTONIG_SYSTEM_LIBONIG` in order for it to
# use pkg-config.
export RUSTONIG_SYSTEM_LIBONIG=1

# See the goose_cargo_flags definition above for what these flags do and why.
%cargo_build %{goose_cargo_flags}

# Generate man pages from clap CLI definitions
export CARGO_MANIFEST_DIR="target/rpm"
target/rpm/generate_manpages

%cargo_vendor_manifest
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies

%install
install -Dpm 0755 target/rpm/goose -t %{buildroot}%{_bindir}

# Install man pages
install -d %{buildroot}%{_mandir}/man1
install -pm 0644 target/man/*.1 -t %{buildroot}%{_mandir}/man1

%if %{with check}
%check
# The oniguruma-sys crate does not have a feature to enable using system lib
# (pkg-config), so we have to set `RUSTONIG_SYSTEM_LIBONIG` in order for it to
# use pkg-config.
export RUSTONIG_SYSTEM_LIBONIG=1

# The following tests are skipped for reasons of:
#
#   * Network / DNS resolution failures:
skip="${skip-} --skip providers::gcpauth::tests::test_token_refresh_race_condition"
#   * Potential copyrightable content (see %%prep for a longer explanation):
skip="${skip-} --skip scenario_tests::scenarios::tests::test_image_analysis"
#   * Flaky test failing, better to skip for now.
skip="${skip-} --skip model::tests::with_canonical_limits::skips_canonical_output_limit_when_it_equals_context_limit"
skip="${skip-} --skip plugins::tests::auto_update_plugins_skips_recently_checked_plugins"
skip="${skip-} --skip plugins::tests::auto_update_plugins_updates_enabled_plugins"
skip="${skip-} --skip plugins::tests::updates_git_backed_plugin"
#   * Timing-sensitive test: races against run completion in slow build environments.
skip="${skip-} --skip test_steer_session_adds_input_to_active_prompt"

# See the goose_cargo_flags definition above for what these flags do and why.
# The trailing `-- ${skip-}` here is cargo test's own separator for the
# test-harness skip args (goose_cargo_flags already has its own `--` to get
# --package/--ignore-rust-version past %%cargo_test's getopt parsing).
%cargo_test %{goose_cargo_flags} -- ${skip-}
%endif


%files
%doc README.md
%doc SECURITY.md
%doc GOVERNANCE.md

%license LICENSE
%license LICENSE.dependencies
%license crates/goose-mcp/licenses/chart-js.license
%license crates/goose-mcp/licenses/d3-js.license
%license crates/goose-mcp/licenses/d3-sankey.license
%license crates/goose-mcp/licenses/leaflet.license
%license crates/goose-mcp/licenses/leaflet-markercluster.license
%license crates/goose-mcp/licenses/mermaid.license
%license cargo-vendor.txt

%{_bindir}/goose
%{_mandir}/man1/goose*.1*

%changelog
%autochangelog

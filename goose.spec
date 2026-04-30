%bcond check 1
# Limit parallel processes to prevent OOM during build:
%global _smp_tasksize_proc 4096

Name:           goose
# We are currently stuck on this stable version due to some constraints related
# to newer dependencies to goose and how they handle their releases. We will be
# able to update to >=1.24 once upstream have a more logical way of handling
# features like code execution, plugins and etc, which brings dependencies like
# `v8` and `deno-core`, that are very difficult to handle.
# See https://issues.redhat.com/browse/RSPEED-2434 for more details.
Version:        1.23.2
Release:        %autorelease
Summary:        Extensible AI agent client
URL:            https://github.com/block/goose

Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
# To create the vendor tarball, use the generate-vendor-tarball.sh script:
#   chmod +x generate-vendor-tarball.sh
#   ./generate-vendor-tarball.sh
Source1:        %{name}-%{version}-vendor.tar.xz
# License files for JavaScript/CSS minified files present in goose-mcp crate.
#   * See https://github.com/block/goose/pull/7352.
#
# This can be removed once the above is merged, *AND* we are able to update to
# newer versions of Goose.
# See https://issues.redhat.com/browse/RSPEED-2434 for more details.
Source2:        chart-js.license
Source3:        d3-js.license
Source4:        d3-sankey.license
Source5:        leaflet.license
Source6:        leaflet-markercluster.license
Source7:        mermaid.license

# This script is used to generate the vendor tarball for goose, and while it
# does not offer any practical/real usage for the application, it helps us to
# easily generate the vendored tarball and apply the correct patches while
# doing so.
Source99:       generate-vendor-tarball.sh

# Remove windows specific dependencies (winapi/winreg) from goose crates.
Patch:          0001-Patch-windows-dependencies-across-workspace.patch
# This patch disable the default features for some dependencies that were
# bringing unwanted crates, like `rustls` or `ring` and swap to use
# `native-tls` where is possible for the other dependencies.
Patch1:         0002-Disable-rustls-and-default-features-for-some-librari.patch
# Patch the source code of goose to make use of `native-tls` instead of
# `rustls`. This is not contained in the above patch on purpose, so we can
# re-create the dependencies patch easily without having to modify source code
# when a new version is pushed.
Patch2:         0003-Patch-code-to-use-native-tls-instead-of-rustls.patch
# Downstream patch to update tar for version 0.4.45. This patch can be dropped
# once https://issues.redhat.com/browse/RSPEED-2434 is fixed.
Patch3:         0004-Fix-for-CVE-2026-33056-on-tar.patch
# This fix is intended to be EPEL 9 only, but for convenience, we will try to
# use it on all versions since that should not be a breaking change across any
# target and the functionality should be the same.
Patch4:         0005-Fix-sql-statement-from-session-manager.patch
# Add disclaimer as required by legal only on RHEL
%if 0%{?rhel}
Patch5:         0006-Include-legal-message-for-goose-proxy-provider.patch
%endif
# Backport of https://github.com/aaif-goose/goose/pull/8118
# Sets permissions of newly created secrets.yaml file to 0600.
Patch6:         0007-Better-default-permissions-for-secrets.patch

# Patch the `build.rs` for `ring` crate to avoid using the pre-generated object
# files that comes with the vendored crate, and instead, build from system
# libraries.
# The patch was taken from:
#   * https://src.fedoraproject.org/rpms/rust-ring/blob/d6d681ed07c088671cb5accc0102470b059a5e88/f/rust-ring.spec#_24
Patch1001:      1001-Downstream-only-never-use-pre-generated-object-files.patch
# Raise recursion limit to fix test failures. This is fixed upstream so is only needed
# to prevent test failures when packaging.
Patch1002:      1002-Raise-recursion-limit.patch

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
# licensecheck will report that set of 6 licenses for the source archive.
#
# CC0-1.0 (constant_time_eq, vendored):
#   - This package was discussed over the legal ML, due to it being present in
#     Fedora already, but having a SPDX license that is not allowed.
#   - https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/thread/262UHMIUTLU3IMEQCFJUIS4EJIMEIRCN/
#
# A couple of files present under `crates/goose-mcp` and `crates/goose-bench`
# were discussed in the legal ML due to them not having a clear license or
# copyright terms in the usptream repository.The discussion of those items can
# be seen at:
#   - https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/thread/JDE6YNL42ZKVA5ZF4PEUGI5SV2PCSHIR/
#
# For convenience, the items discussed in the legal ML thread are namely:
#   - https://github.com/block/goose/tree/v1.23.2/crates/goose-mcp/src/computercontroller/tests/data
#   - https://github.com/block/goose/tree/v1.23.2/crates/goose-bench/src/assets
#   - https://github.com/block/goose/tree/v1.23.2/crates/goose-cli/src/scenario_tests/recordings
#
#
# Rust crates compiled into the executable contribute additional license terms.
# To obtain the following list of licenses, build the package and note the
# output of %%{cargo_license_summary}.
#
# (Apache-2.0 OR MIT) AND BSD-3-Clause
# (MIT OR Apache-2.0) AND Unicode-3.0
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 OR BSL-1.0
# Apache-2.0 OR GPL-2.0-only
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSD-2-Clause
# BSD-2-Clause OR Apache-2.0 OR MIT
# BSD-3-Clause
# BSD-3-Clause AND MIT
# BSD-3-Clause OR Apache-2.0
# BSD-3-Clause OR MIT
# BSD-3-Clause OR MIT OR Apache-2.0
# BSL-1.0
# CC0-1.0
# CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception
# CC0-1.0 OR MIT-0 OR Apache-2.0
# ISC
# LGPL-3.0-or-later
# MIT
# MIT AND BSD-3-Clause
# MIT OR Apache-2.0
# MIT OR Apache-2.0 OR LGPL-2.1-or-later
# MIT OR Apache-2.0 OR Zlib
# MIT OR Zlib OR Apache-2.0
# MIT-0
# MPL-2.0
# Unicode-3.0
# Unlicense OR MIT
# Zlib
# Zlib OR Apache-2.0 OR MIT
License:        %{shrink:
                (0BSD OR Apache-2.0 OR MIT)
                AND Apache-2.0
                AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR CC0-1.0)
                AND (Apache-2.0 OR Apache-2.0 WITH LLVM-exception OR MIT)
                AND (Apache-2.0 OR BSD-2-Clause OR MIT)
                AND (Apache-2.0 OR BSD-3-Clause)
                AND (Apache-2.0 OR BSD-3-Clause OR MIT)
                AND (Apache-2.0 OR BSL-1.0)
                AND (Apache-2.0 OR CC0-1.0 OR MIT-0)
                AND (Apache-2.0 OR GPL-2.0-only)
                AND (Apache-2.0 OR LGPL-2.1-or-later OR MIT)
                AND (Apache-2.0 OR MIT)
                AND (Apache-2.0 OR MIT OR Zlib)
                AND BSD-2-Clause
                AND BSD-3-Clause
                AND (BSD-3-Clause OR MIT)
                AND BSL-1.0
                AND CC0-1.0
                AND ISC
                AND LGPL-3.0-or-later
                AND MIT
                AND (MIT OR Unlicense)
                AND MIT-0
                AND MPL-2.0
                AND Unicode-3.0
                AND Zlib
                }
# LICENSE.dependencies contains a full license breakdown

BuildRequires:  cargo-rpm-macros >= 25

# Required by crate bzip2-sys (vendored)
BuildRequires:  pkgconfig(bzip2)
# Required by crate libdbus-sys (vendored)
BuildRequires:  dbus-devel
# Required by crate libgit2-sys (vendored)
BuildRequires:  libgit2-devel
# Required by crate libsqlite3-sys (vendored)
BuildRequires:  clang-devel
BuildRequires:  pkgconfig(sqlite3)
# Required by crate onig_sys (vendored)
BuildRequires:  oniguruma-devel
# Required by crate openssl-sys (vendored)
BuildRequires:  openssl-devel
# Required by crate ring (vendored)
BuildRequires:  /usr/bin/perl
# Required by crate xcap (vendored)
# Goose has an extension called "Developer Extension" which allows the program
# to take screenshots of the screen or specified windows when debugging visual
# issues (Not enabled by default. Needs manual activation).
# https://github.com/block/goose/issues/6302#issuecomment-3744200583
BuildRequires:  libxcb-devel
# Required by crate zstd-sys (vendored)
BuildRequires:  libzstd-devel

# Sublime Text 3 language definitions for syntax highlighting
# from: https://github.com/sublimehq/Packages/tree/fa6b862
# - all except Rust: LicenseRef-Fedora-UltraPermissive
#   https://gitlab.com/fedora/legal/fedora-license-data/-/issues/516
# - Rust: MIT
Provides:       bundled(sublime-syntax) = 4075~gitfa6b862

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
%autosetup -p1 -a1

# Copy JavaScript/CSS license text into %%{name}-%%{version} folder.
cp -pav %{SOURCE2} %{SOURCE3} %{SOURCE4} %{SOURCE5} %{SOURCE6} %{SOURCE7} .

# Reomve the documentation folder but leave `static/img/logo_{dark,light}.png`
# in it, as they are used in goose-cli crate. All the other markdown, audio,
# images and etc are not necessary to be present here.
find documentation \
    -depth \( -type f ! -path "documentation/static/img/logo_dark.png" ! -path "documentation/static/img/logo_light.png" -delete \) \
    -o \( -type d -empty -delete \)
# Delete the `ui` folder as it contains the electron desktop app for Goose,
# which should not be packaged here.
rm -rf ui
# Remove the `bin` folder as it is managed by hermit
# (https://github.com/cashapp/hermit) to bootstrap development tools used by
# goose.
rm -rf bin

# Remove the `services` folder as it contains an `ask-ai-bot` that is used
# mainly for the discord community, which, does not provide any benefit to keep
# it here as it is not being used by the goose source in any way or form.
rm -rf services

# Remove the `test_image.jpg` as we are not sure if this was LLM generated or
# made by a human. Since there is no copyright data anywhere in the repository
# mentioning this and the PR that introduced it
# (https://github.com/block/goose/pull/3688) does not mention anything about
# the source of the image, it's better that we remove this anyway.
rm crates/goose-cli/src/scenario_tests/test_data/test_image.jpg

# Helper function to prune vendored folders that contains C libraries or
# pre-defined objects. All pruned libraries here should be linked against
# system libraries instead.
#
# Note: The operations `rm` and `find` in this helper function are split to
# allow easier reading and maintenance, but they could be grouped together in
# just one find command.
prune_vendor() {
    local crate_pattern="$1"
    local path_to_remove="$2"

    # We use ${var} without quotes here to allow the '*' glob to expand
    rm -rf ${crate_pattern}/${path_to_remove}

    # Patch the cargo checksum to ignore the deleted files
    find . -path "*/${crate_pattern}/.cargo-checksum.json" \
        -exec sed -i.uncheck -e 's/"files":{[^}]*}/"files":{ }/' '{}' '+'
}

pushd vendor

prune_vendor "bzip2-sys-*" "bzip-*"
prune_vendor "libdbus-sys-*" "vendor"
prune_vendor "libsqlite3-sys-*" "{sqlite3,sqlcipher}"
prune_vendor "onig_sys-*" "oniguruma"
prune_vendor "ring-*" "pregenerated"

# This expression will match:
#   - zstd-* / zstd-*+zstd*
#   - zstd-safe-* / zstd-safe*+zstd*
#   - zstd-sys-*+zstd*
# And will add the `pkg-config` to the default-features, and patch
# .cargo-checksum.json to ignore the changed files.
find . -maxdepth 1 -path "*/zstd-*" \
    -exec sed -i '/^default = \[/s/\[/&"pkg-config", /' "{}/Cargo.toml" \; \
    -exec sed -i.uncheck -e 's/"files":{[^}]*}/"files":{ }/' "{}/.cargo-checksum.json" \;

prune_vendor "zstd-sys-*" "zstd"

# Update posthog-rs to use reqwest 0.12.28 (same version as goose) so we are
# able to swap rustls-tls for native-tls in the features.
#
# This is a workaround until https://github.com/PostHog/posthog-rs/pull/55 get
# merged and released. Once that happens, we will be able to swap in the
# Cargo.toml (via our existing patch) and not have to modify the vendored
# Cargo.toml directly.
find . -maxdepth 1 -path "*/posthog-rs-*" \
    -exec sed -i \
        -e '/reqwest.*=.*{/{s/version = "[^"]*"/version = "0.12.28"/;s/"rustls-tls"/"native-tls"/;}' \
        -e '/^\[dependencies\.reqwest\]/,/^\[/{/^version\s*=/{s/"[^"]*"/"0.12.28"/;};s/"rustls-tls"/"native-tls"/;}' \
        "{}/Cargo.toml" \; \
    -exec sed -i.uncheck -e 's/"files":{[^}]*}/"files":{ }/' "{}/.cargo-checksum.json" \;
popd

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

%cargo_build
%cargo_vendor_manifest
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies

%install
install -Dpm 0755 target/rpm/goose -t %{buildroot}%{_bindir}
install -Dpm 0755 target/rpm/goosed -t %{buildroot}%{_bindir}
install -Dpm 0755 target/rpm/goose-acp-server -t %{buildroot}%{_bindir}

%if %{with check}
%check
# The oniguruma-sys crate does not have a feature to enable using system lib
# (pkg-config), so we have to set `RUSTONIG_SYSTEM_LIBONIG` in order for it to
# use pkg-config.
export RUSTONIG_SYSTEM_LIBONIG=1

# The following tests are skipped particulary for reasons of:
#
#   * Network / DNS resolution failures:
skip="${skip-} --skip providers::gcpauth::tests::test_token_refresh_race_condition"
skip="${skip-} --skip routes::audio::tests::test_transcribe_endpoint_requires_auth"
skip="${skip-} --skip tunnel::lapstone_test::test_tunnel_end_to_end"
skip="${skip-} --skip tunnel::lapstone_test::test_tunnel_post_request"
#   * Potential copyrightable content (see %%prep for a longer explanation):
skip="${skip-} --skip scenario_tests::scenarios::tests::test_image_analysis"
%cargo_test -- -- ${skip-}
%endif


%files
%doc README.md
%doc SECURITY.md
%doc GOVERNANCE.md

%license LICENSE
%license LICENSE.dependencies
%license chart-js.license
%license d3-js.license
%license d3-sankey.license
%license leaflet.license
%license leaflet-markercluster.license
%license mermaid.license
%license cargo-vendor.txt

%{_bindir}/goose
%{_bindir}/goosed
%{_bindir}/goose-acp-server

%changelog
%autochangelog

# https://github.com/bootc-dev/bootc/issues/1640
%if 0%{?fedora} || 0%{?rhel} >= 10 || 0%{?rust_minor} >= 89
    %global new_cargo_macros 1
%else
    %global new_cargo_macros 0
%endif

%define vendor_url https://github.com/rhel-lightspeed/goose

Name:           goose
Version:        1.14.0
Release:        %autorelease
Summary:        an open source, extensible AI agent that goes beyond code suggestions - install, execute, edit, and test with any LLM
URL:            https://github.com/block/goose
Source0:        %{vendor_url}/releases/download/v%{version}/%{name}-%{version}-patched.tar.zstd

License:  %{shrink:
    (Apache-2.0 OR MIT) AND BSD-3-Clause
    (MIT OR Apache-2.0) AND NCSA
    (MIT OR Apache-2.0) AND Unicode-3.0
    0BSD OR MIT OR Apache-2.0
    Apache-2.0
    Apache-2.0 OR BSL-1.0
    Apache-2.0 OR ISC OR MIT
    Apache-2.0 OR MIT
    Apache-2.0 WITH LLVM-exception
    Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
    BSD-2-Clause
    BSD-2-Clause OR Apache-2.0 OR MIT
    BSD-3-Clause
    BSD-3-Clause AND MIT
    BSD-3-Clause OR MIT
    BSL-1.0
    CC0-1.0
    CC0-1.0 OR Apache-2.0
    CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception
    CC0-1.0 OR MIT-0 OR Apache-2.0
    ISC
    ISC AND (Apache-2.0 OR ISC)
    ISC AND (Apache-2.0 OR ISC) AND OpenSSL
    LGPL-3.0-or-later
    MIT
    MIT AND BSD-3-Clause
    MIT OR Apache-2.0
    MIT OR Apache-2.0 OR Zlib
    MIT OR Zlib OR Apache-2.0
    MIT-0
    MPL-2.0
    Unicode-3.0
    Unlicense OR MIT
    Zlib
    Zlib OR Apache-2.0 OR MIT
}

BuildRequires: cargo-rpm-macros >= 25
BuildRequires: systemd
BuildRequires: openssl-devel
BuildRequires: cmake
BuildRequires: clang-libs
BuildRequires: clang
BuildRequires: libxcb-devel

%description
an open source, extensible AI agent that goes beyond code suggestions - install, execute, edit, and test with any LLM


%prep
%autosetup -a1 -n %{name}-%{version}

# Taken from https://src.fedoraproject.org/rpms/bpfman/blob/f43/f/bpfman.spec#_88
find -name '*.rs' -type f -perm /111 -exec chmod -v -x '{}' '+'

%generate_buildrequires
%cargo_generate_buildrequires

%build
%cargo_build

%install
# Install binaries
install -D -m 0755 target/release/goose %{buildroot}%{_bindir}/goose
install -D -m 0755 target/release/goosed %{buildroot}%{_bindir}/goosed

%files
%license LICENSE
%license LICENSE.dependencies
%license cargo-vendor.txt
%{_bindir}/goose
%{_bindir}/goosed

%changelog
* Tue Nov 11 2025 Rodolfo Olivieri <rolivier@redhat.com> - 1.13.1-1
- Initial goose package release

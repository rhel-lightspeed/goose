# https://github.com/bootc-dev/bootc/issues/1640
%if 0%{?fedora} || 0%{?rhel} >= 10 || 0%{?rust_minor} >= 89
    %global new_cargo_macros 1
%else
    %global new_cargo_macros 0
%endif

Name:           goose
Version:        1.13.1
Release:        1%{?dist}
Summary:        an open source, extensible AI agent that goes beyond code suggestions - install, execute, edit, and test with any LLM 

License:        Apache-2.0
URL:            https://github.com/rhel-lightspeed/goose
Source0:        %{name}-%{version}-patched.tar.gz
Source1:        %{name}-%{version}-vendored.tar.zstd


%if 0%{?rhel}
BuildRequires: rust-toolset
%else
BuildRequires: cargo-rpm-macros >= 25
%endif
BuildRequires: systemd
BuildRequires: openssl-devel
BuildRequires: cmake
BuildRequires: clang-libs
BuildRequires: clang
BuildRequires: lixcb-devel

%description
an open source, extensible AI agent that goes beyond code suggestions - install, execute, edit, and test with any LLM 


%prep
%autosetup -a1 -n %{name}-%{version}

# Default -v vendor config doesn't support non-crates.io deps (i.e. git)
cp .cargo/vendor-config.toml .
%cargo_prep -N 
cat vendor-config.toml >> .cargo/config.toml
rm vendor-config.toml

%build
# Build the main bootc binary
%cargo_build

%cargo_vendor_manifest

# https://pagure.io/fedora-rust/rust-packaging/issue/33
sed -i -e '/https:\/\//d' cargo-vendor.txt
%cargo_license_summary
%{cargo_license} > LICENSE.dependencies

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
* Tue Nov 10 2025 Rodolfo Olivieri <rolivier@redhat.com> - $$VERSION-1
- Initial goose package release⏎
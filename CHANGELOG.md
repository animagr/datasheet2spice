# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic
Versioning.

## [1.0.1] - 2026-05-18

### Added

- `CHANGELOG.md` for release notes.
- Local workbench request-size protection for PDF uploads and JSON requests.
- Local workbench same-origin checks for browser POST requests.
- Local workbench host-binding guard that keeps the server on localhost unless
  `DATASHEET2SPICE_ALLOW_NETWORK_BIND=1` is set intentionally.

### Changed

- Package version bumped to `1.0.1`.
- Static browser workbench no longer loads third-party CDN JavaScript.
- Static browser workbench now disables PDF extraction unless the local Python
  workbench is used.
- Static browser workbench exports generated model files as individual local
  downloads instead of using CDN-provided ZIP packaging.
- Runtime contracts and documentation now describe only browser-pages and
  local-python modes.
- Third-party Python entry-point plugins are disabled by default and require
  explicit opt-in through `DATASHEET2SPICE_ENABLE_ENTRYPOINT_PLUGINS=1` or
  `load_plugins(include_entrypoints=True)`.
- README, citation metadata, and docs now use local documentation/repository
  links instead of hosted workbench, badges, or Pages URLs.
- Documentation now describes static browser files and local docs without
  hosted static-site deployment assumptions.

### Removed

- CDN imports for `pdfjs-dist` and `JSZip` from the static workbench.
- Future remote API mode from runtime metadata, service contracts, and docs.
- Hosted automation workflow files for tests and static-site deployment.

### Security

- Reduced browser supply-chain exposure by removing remote script imports from
  the static workbench.
- Reduced plugin execution risk by making installed third-party plugin entry
  points opt-in.
- Reduced localhost API exposure by rejecting cross-origin POST requests.
- Reduced accidental LAN exposure by blocking non-local server bindings unless
  explicitly enabled.

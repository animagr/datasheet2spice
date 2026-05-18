# Security Policy

## Supported Versions

The `main` branch is the active development line. Tagged releases are supported
on a best-effort basis until the project has a larger maintainer group.

## Reporting A Vulnerability

Please use GitHub private vulnerability reporting if available, or contact the
maintainer through GitHub.

Do not publish:

- private datasheets,
- proprietary vendor model files,
- credentials or internal file paths,
- confidential lab waveforms,
- payloads that trigger unsafe local file access.

## Scope

Security issues may include unsafe archive handling, path traversal, arbitrary
file reads/writes, unsafe PDF processing behavior, or browser/local backend
data exposure.

Model accuracy problems are important, but they should usually be filed as
ordinary issues unless they create a safety or confidentiality risk.


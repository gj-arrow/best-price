# Nessy CLI Project Directory

## Overview

This directory serves as a working directory for the **Nessy CLI** - an interactive CLI agent platform developed by T-Command. It contains configuration files, cached binaries, and installed plugins that enable the CLI's functionality.

## Directory Structure

```
newProject/
├── NESSY.md           # This file - context for AI agent interactions
├── config.json        # CLI configuration (core version, plugins)
├── cache_version.json # Cached core binary download URLs by platform
└── plugins/           # Installed plugin binaries
    ├── wixie          # Confluence wiki page management plugin
    ├── gitlab         # GitLab integration plugin
    └── tihon          # Tihon AI assistant plugin
```

## Key Files

### config.json
Contains the CLI configuration including:
- **core.version**: Current core CLI version (13.23.0)
- **plugins**: Registry of installed plugins with versions and install timestamps

### cache_version.json
Stores cached download URLs for the core CLI binary:
- Platform-specific URLs for darwin, linux, and windows
- Used for CLI updates and version management

### plugins/
Binary plugin files that extend CLI functionality:
- **wixie** (v3.5.0): Create and edit Confluence wiki pages
- **gitlab**: GitLab merge requests, pipelines, and repository management
- **tihon**: Integration with Tihon AI assistant

## Usage

This directory is used by the Nessy CLI to:
1. Store configuration state between sessions
2. Cache plugin binaries for offline operation
3. Track installed plugins and their versions
4. Provide context to the AI agent via NESSY.md

## Commands

The Nessy CLI provides various commands through its plugin system. Common operations include:

- **Wiki Management**: Create/edit Confluence pages via `wixie` plugin
- **GitLab Operations**: Manage merge requests, pipelines, and repositories
- **AI Assistant**: Chat with Tihon AI for assistance

## Development Notes

- Plugin binaries are stored directly in the `plugins/` directory
- Configuration files use JSON format
- The NESSY.md file provides contextual information to the AI agent for more informed interactions

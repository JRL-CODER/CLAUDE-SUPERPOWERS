# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **Superpowers** plugin (v5.x) — a skills/workflow system for AI coding agents — combined with two additional projects in subdirectories:

- `skills/` — The core of Superpowers: each subdirectory is a skill with a `SKILL.md`
- `claude-usage-widget/` — Electron desktop widget for Claude.ai usage monitoring
- `tokscale/` — Rust TUI + Next.js dashboard for tracking token usage across AI agents

The root `package.json` points to `.opencode/plugins/superpowers.js` as the plugin entry point.

## Development Branch

All changes go to branch `claude/install-usage-widget-OaNt8`. Push with:
```bash
git push -u origin claude/install-usage-widget-OaNt8
```

## claude-usage-widget (Electron App)

```bash
cd claude-usage-widget
npm install
npm start                  # Dev mode (DevTools open)
npm run dev                # Explicit dev env
npm run build:win          # Windows installer → dist/
npm run build:mac          # macOS DMG (must run on Mac)
npm run build:linux        # Linux AppImage
```

**Key architecture:**
- `main.js` — Electron main process: window creation, tray, IPC, update checks, credential storage via `electron-store` (encrypted)
- `preload.js` — Context bridge exposing safe IPC channels to renderer
- `src/renderer/` — Pure JS/CSS/HTML frontend (no framework)
- `src/fetch-via-window.js` — Fetches Claude.ai API through a hidden `BrowserWindow` to bypass Cloudflare bot detection. This is intentional; direct Node.js `http` requests are blocked. Do not replace with `fetch` or `axios`.

**Debug mode:**
```bash
DEBUG_LOG=1 npm start
# or
electron . --debug
```

**Config storage locations:**
- Windows: `%APPDATA%/claude-usage-widget/config.json`
- macOS: `~/Library/Application Support/claude-usage-widget/config.json`

## tokscale (Rust CLI + Next.js Frontend)

```bash
cd tokscale

# Build Rust TUI
cargo build --release
./target/release/tokscale

# Or install globally via npm
npx tokscale

# Run Next.js frontend
cd packages/frontend
bun install && bun dev    # http://localhost:3000
```

**Rust workspace layout:**
- `crates/tokscale-core/` — Parsing, aggregation, pricing lookups, session readers for 20+ AI clients
- `crates/tokscale-cli/` — Ratatui TUI, commands (including `wrapped`), auth

The `fetch-via-window` approach in the Electron widget and the hidden `BrowserWindow` pattern are coupling points — both work around Cloudflare protection on `claude.ai`.

## Superpowers Skills System

Skills live in `skills/<name>/SKILL.md`. They are loaded by the agent at session start via the `hooks/hooks.json` `SessionStart` hook, which runs `hooks/session-start/`.

```bash
# Run integration tests (requires `claude` CLI and ~10-30 min)
cd tests/claude-code
./test-subagent-driven-development-integration.sh

# Analyze token usage from any session transcript
python3 tests/claude-code/analyze-token-usage.py ~/.claude/projects/<path>/<session>.jsonl
```

Session transcripts are stored in `~/.claude/projects/` with the working directory path encoded (slashes → hyphens). Find recent sessions:
```bash
find ~/.claude/projects -name "*.jsonl" -mmin -60 | sort -r | head -5
```

## Commit Convention

```
<type>: <description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`

**PR body authoring:** Write to a temp file, then use `--body-file`. Do NOT use inline heredocs with backticks — single-quoted heredocs don't escape backticks but `\`` renders as literal backslash + backtick in GitHub markdown.

Write PR/issue body paragraphs as **continuous lines** (no hard-wrapping at 80 cols) — GitHub collapses single newlines to spaces in rendered markdown, making hard-wrapped prose look chopped in the raw edit view.

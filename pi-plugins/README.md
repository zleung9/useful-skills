# pi-plugins

Placeholders for pi (pi-coding-agent) plugins, extensions, and related configuration.

Each plugin lives in its own subfolder, e.g. `pi-plugins/<plugin-name>/`.

## How to use

pi extensions are TypeScript/JavaScript modules that plug into the pi agent harness.
Common install locations:

- User-level: `~/.pi/extensions/<plugin-name>/`
- Project-level: `.pi/extensions/<plugin-name>/`
- Via packages: `pi install <package>`

This folder is the source-of-truth copy (kept in this repo). Copy or symlink a
subfolder into one of the locations above to activate it.

## Docs

- Main docs: `README.md` of the pi-coding-agent package
- Extensions: `docs/extensions.md`
- Examples: `examples/extensions/`

(Paths are relative to the installed `@earendil-works/pi-coding-agent` package,
e.g. `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/`.)

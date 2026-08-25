# J-Telemetry

General-purpose Maya script profiler. Wraps every `maya.cmds` command and
`maya.mel.eval` with timing and call-counting, runs any script **unmodified**,
and reports where the time went. No disk files involved — it's a shelf tool.

## Installation

Open `jTelemetry.py` on GitHub, copy its entire contents, and paste it into a
new shelf button's **Python** command (or a **Python** tab in Maya's Script
Editor). No companion module, `PYTHONPATH` change, or package installation is
required.

## Usage

Click the shelf button. A window opens with a text box — paste any one of:

| you paste | it profiles |
|---|---|
| a shelf button label, e.g. `linkLights` | that button's Python command |
| an interpreter function name, e.g. `my_tool` | that function |
| a GitHub URL (browser `blob` links fine) | the script it points at |
| a whole script (multi-line paste) | the pasted code |

and click **Profile**. The input kind is detected automatically, and the
report appears in the window's monospace pane as well as the Script Editor.

The underlying functions are also callable directly, each returning the
`Telemetry` object and taking `top=N` for rows per report table:

```python
profile_shelf("linkLights")
profile_call(my_function)
profile_code("""<paste any script here>""")
profile_url("https://github.com/JensenAbler/J-Link/blob/master/linkLights.py")
show()          # reopen the window
```

The `maya.cmds`/`mel.eval` wrappers are always removed afterward, even if the
profiled script errors or calls `sys.exit()`.

## Air-gapped workstations

Everything except `profile_url` works with no network. On offline machines
your scripts already live in the shelf or the interpreter, and the profiler
reads from both — paste a shelf label or function name into the window, or a
whole script. (`profile_call` skips the per-line hotspot table since the
function wasn't compiled by the profiler; the per-command and slowest-call
tables are unaffected.)

## The report

- **Total wall time** vs. **time inside cmds/mel** — how much is Maya calls
  vs. pure Python.
- **Cumulative time per command** — calls, total, avg, max per command.
- **Slowest individual calls** — with the script line and truncated args.
- **Hotspots by script line** — total cmds/mel time attributed to each line
  of the profiled script, with source. This is the table that points at the
  bottleneck.

## Optional sections

Profiled scripts get a `jtel_section` context manager injected — no import
needed:

```python
with jtel_section("build sceneLights"):
    ...
```

Section totals appear in their own table in the report.

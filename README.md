# J-Telemetry

General-purpose Maya script profiler. Wraps every `maya.cmds` command and
`maya.mel.eval` with timing and call-counting, runs any script **unmodified**,
and reports where the time went. No disk files involved — profile straight
from a GitHub URL or a pasted string.

## Installation

Open `jTelemetry.py` on GitHub, copy its entire contents, and paste it into a
**Python** tab in Maya's Script Editor (or a shelf button). No companion
module, `PYTHONPATH` change, or package installation is required.

## Usage

Profile any script by its GitHub URL — just paste the link from your browser
(`blob` URLs are converted to raw automatically):

```python
profile_url("https://github.com/JensenAbler/J-Link/blob/master/linkLights.py")
```

Or profile pasted code directly:

```python
profile_code("""
<paste any script here>
""")
```

`top=N` controls rows per report table. The wrappers are always removed
afterward, even if the profiled script errors or calls `sys.exit()`.

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

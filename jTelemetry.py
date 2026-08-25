'''
jTelemetry_v003
Author: Jensen Abler & Claude
Date: 8/25/2026
Description: General-purpose Maya script profiler. Wraps maya.cmds and maya.mel.eval
with timing and call-counting, runs any script unmodified, and reports where the
time went: total wall time, cumulative time per command, slowest individual calls,
and per-line hotspots in the profiled script. No disk files involved: profile
from a GitHub URL, a shelf button, a pasted string, or an interpreter function.

Usage (paste this whole file into a Python tab in Maya's Script Editor, then):

    profile_url("https://github.com/JensenAbler/J-Link/blob/master/linkLights.py")

github.com "blob" URLs are converted to raw automatically, so just paste the
URL from your browser.

Air-gapped workstations (no network) — profile a shelf button's Python
command by the button's label:

    profile_shelf("linkLights")

or paste code directly:

    profile_code(""\"
    <paste any script here>
    ""\")

or profile a function already defined in the interpreter:

    profile_call(my_function)

Options:

    profile_url(url, top=15)   # rows per report table
'''
import sys
import time
import traceback

try:
    from urllib.request import urlopen        # Python 3 (Maya 2022+)
except ImportError:
    from urllib2 import urlopen               # Python 2 fallback

try:
    import maya
    import maya.cmds
    import maya.mel
except ImportError:
    maya = None  # Allows self-test outside Maya with a stubbed maya module.


class _CallRecord(object):
    __slots__ = ("command", "duration", "lineno", "arg_preview")

    def __init__(self, command, duration, lineno, arg_preview):
        self.command = command
        self.duration = duration
        self.lineno = lineno
        self.arg_preview = arg_preview


class Telemetry(object):
    '''Collects timing data while a script runs, then renders a report.'''

    SCRIPT_FILENAME = "<jTelemetry>"

    def __init__(self):
        self.records = []
        self.section_times = []       # (name, duration) in the order sections close
        self._section_stack = []
        self.wall_start = None
        self.wall_end = None
        self.error = None

    # ---- capture -----------------------------------------------------------

    def record(self, command, duration, arg_preview):
        lineno = self._caller_lineno()
        self.records.append(_CallRecord(command, duration, lineno, arg_preview))

    def _caller_lineno(self):
        '''Line number in the profiled script that triggered this call, or None.'''
        frame = sys._getframe(2)  # skip record() and the wrapper
        while frame is not None:
            if frame.f_code.co_filename == self.SCRIPT_FILENAME:
                return frame.f_lineno
            frame = frame.f_back
        return None

    def section(self, name):
        return _Section(self, name)

    # ---- report ------------------------------------------------------------

    def report(self, script_lines=None, top=15):
        lines = []
        add = lines.append
        wall = (self.wall_end or time.time()) - (self.wall_start or 0)
        tracked = sum(r.duration for r in self.records)

        add("=" * 78)
        add("jTelemetry report")
        add("=" * 78)
        add("Total wall time : %.3f s" % wall)
        add("Time in cmds/mel: %.3f s (%.0f%% of wall)"
            % (tracked, (tracked / wall * 100) if wall else 0))
        add("Calls recorded  : %d" % len(self.records))
        if self.error:
            add("Script ended with error: %s" % self.error)

        if self.section_times:
            add("")
            add("-- Sections ------------------------------------------------")
            add("%-40s %10s" % ("section", "total s"))
            for name, duration in self.section_times:
                add("%-40s %10.3f" % (name[:40], duration))

        # Cumulative time per command
        by_command = {}
        for r in self.records:
            entry = by_command.setdefault(r.command, [0, 0.0, 0.0])
            entry[0] += 1
            entry[1] += r.duration
            entry[2] = max(entry[2], r.duration)
        ranked = sorted(by_command.items(), key=lambda kv: kv[1][1], reverse=True)

        add("")
        add("-- Cumulative time per command (top %d) ----------------------" % top)
        add("%-28s %8s %10s %10s %10s" % ("command", "calls", "total s", "avg ms", "max ms"))
        for command, (count, total, peak) in ranked[:top]:
            add("%-28s %8d %10.3f %10.2f %10.2f"
                % (command[:28], count, total, total / count * 1000, peak * 1000))

        # Slowest individual calls
        slowest = sorted(self.records, key=lambda r: r.duration, reverse=True)
        add("")
        add("-- Slowest individual calls (top %d) -------------------------" % top)
        add("%-28s %10s %6s  %s" % ("command", "ms", "line", "args"))
        for r in slowest[:top]:
            add("%-28s %10.2f %6s  %s"
                % (r.command[:28], r.duration * 1000,
                   r.lineno if r.lineno else "-", r.arg_preview))

        # Per-line hotspots in the profiled script
        by_line = {}
        for r in self.records:
            if r.lineno is None:
                continue
            entry = by_line.setdefault(r.lineno, [0, 0.0])
            entry[0] += 1
            entry[1] += r.duration
        if by_line:
            hot = sorted(by_line.items(), key=lambda kv: kv[1][1], reverse=True)
            add("")
            add("-- Hotspots by script line (top %d) --------------------------" % top)
            add("%6s %8s %10s  %s" % ("line", "calls", "total s", "source"))
            for lineno, (count, total) in hot[:top]:
                source = ""
                if script_lines and 0 < lineno <= len(script_lines):
                    source = script_lines[lineno - 1].strip()[:60]
                add("%6d %8d %10.3f  %s" % (lineno, count, total, source))

        add("=" * 78)
        return "\n".join(lines)


class _Section(object):
    def __init__(self, telemetry, name):
        self.telemetry = telemetry
        self.name = name

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.telemetry.section_times.append((self.name, time.time() - self.start))
        return False


def _preview(args, kwargs, limit=48):
    parts = [repr(a) for a in args]
    parts += ["%s=%r" % (k, v) for k, v in sorted(kwargs.items())]
    text = ", ".join(parts)
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


class _Patcher(object):
    '''Temporarily wraps every callable on maya.cmds plus maya.mel.eval.'''

    def __init__(self, telemetry):
        self.telemetry = telemetry
        self._saved_cmds = {}
        self._saved_mel_eval = None

    def __enter__(self):
        for name in dir(maya.cmds):
            if name.startswith("_"):
                continue
            original = getattr(maya.cmds, name)
            if not callable(original):
                continue
            self._saved_cmds[name] = original
            setattr(maya.cmds, name, self._wrap("cmds." + name, original))
        self._saved_mel_eval = maya.mel.eval
        maya.mel.eval = self._wrap("mel.eval", self._saved_mel_eval)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        for name, original in self._saved_cmds.items():
            setattr(maya.cmds, name, original)
        maya.mel.eval = self._saved_mel_eval
        return False

    def _wrap(self, label, original):
        telemetry = self.telemetry

        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return original(*args, **kwargs)
            finally:
                telemetry.record(label, time.time() - start,
                                 _preview(args, kwargs))
        return wrapper


def _run(telemetry, thunk):
    '''Run thunk with the patcher active, capturing errors into telemetry.'''
    telemetry.wall_start = time.time()
    with _Patcher(telemetry):
        try:
            thunk()
        except SystemExit:
            telemetry.error = "SystemExit (script called sys.exit)"
        except Exception:
            telemetry.error = traceback.format_exc().splitlines()[-1]
    telemetry.wall_end = time.time()


def profile_code(code, top=15, description=None):
    '''Profile a string of Python code. Returns the Telemetry object.'''
    if maya is None:
        raise RuntimeError("maya module not available")
    telemetry = Telemetry()
    script_lines = code.splitlines()
    compiled = compile(code, Telemetry.SCRIPT_FILENAME, "exec")
    scope = {
        "__name__": "__main__",
        "maya": maya,
        "jtel_section": telemetry.section,
    }
    def _thunk():
        exec(compiled, scope)
    _run(telemetry, _thunk)
    if description:
        print("Profiled: %s" % description)
    print(telemetry.report(script_lines=script_lines, top=top))
    return telemetry


def profile_call(func, top=15):
    '''Profile a zero-argument callable already defined in the interpreter.
    Per-line hotspots are not available in this mode; the per-command and
    slowest-call tables are. Returns the Telemetry object.'''
    if maya is None:
        raise RuntimeError("maya module not available")
    telemetry = Telemetry()
    _run(telemetry, func)
    print("Profiled: %s" % getattr(func, "__name__", repr(func)))
    print(telemetry.report(top=top))
    return telemetry


def profile_shelf(label, top=15):
    '''Profile a shelf button's Python command, found by the button's label
    (also matches its overlay text or name). Works fully offline. Returns
    the Telemetry object.'''
    if maya is None:
        raise RuntimeError("maya module not available")
    top_shelf = maya.mel.eval("$jtelTmp = $gShelfTopLevel")
    shelves = maya.cmds.tabLayout(top_shelf, query=True, childArray=True) or []
    seen = []
    for shelf in shelves:
        buttons = maya.cmds.shelfLayout(shelf, query=True, childArray=True) or []
        for button in buttons:
            try:
                names = (
                    maya.cmds.shelfButton(button, query=True, label=True),
                    maya.cmds.shelfButton(button, query=True,
                                          imageOverlayLabel=True),
                    button,
                )
            except Exception:
                continue  # not a shelfButton (separators etc.)
            seen.extend(n for n in names[:2] if n)
            if label not in names:
                continue
            source = maya.cmds.shelfButton(button, query=True, sourceType=True)
            if source != "python":
                raise ValueError("shelf button %r is %s, not python"
                                 % (label, source))
            code = maya.cmds.shelfButton(button, query=True, command=True)
            return profile_code(code, top=top,
                                description="shelf button %r" % label)
    raise ValueError("no shelf button labeled %r found (saw: %s)"
                     % (label, ", ".join(sorted(set(seen))) or "none"))


def _to_raw_url(url):
    '''Convert a github.com blob URL to its raw equivalent; pass others through.'''
    if "github.com" in url and "/blob/" in url:
        url = url.replace("github.com", "raw.githubusercontent.com", 1)
        url = url.replace("/blob/", "/", 1)
    return url


def profile_url(url, top=15):
    '''Profile a script fetched from a URL (github.com links are converted to
    raw automatically). Returns the Telemetry object.'''
    raw = _to_raw_url(url)
    handle = urlopen(raw)
    try:
        code = handle.read().decode("utf-8")
    finally:
        handle.close()
    return profile_code(code, top=top, description=url)

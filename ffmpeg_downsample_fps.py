#!/usr/bin/env python3

"""ffmpeg_downsample_fps.py

Small CLI wrapper around ffmpeg via the `ffmpeg-python` library.

Modes:
    - drop:   Reduce FPS by dropping frames to TARGET_FPS (keeps duration the same).
    - slowmo: Stretch timestamps so all frames are preserved and playback becomes
                        slower. Example: 120fps -> 30fps becomes ~4x longer.

Notes:
    - Requires the `ffmpeg` and `ffprobe` executables on PATH (ffmpeg-python is a
        wrapper; the heavy lifting is done by ffmpeg).
    - Audio (slowmo): default is muted to avoid confusing desync. Use
        `--audio stretch` to time-stretch audio (re-encodes audio), or `--audio copy`
        to copy audio as-is (typically ends early / de-syncs).

Examples:
    # In the birdcam conda env (without activating it):
    python ffmpeg_downsample_fps.py drop \
        -i in.mp4 -o out_30fps.mp4 -f 30

    python ffmpeg_downsample_fps.py slowmo \
        -i in.mp4 -o out_slowmo_30fps.mp4 -f 30

    python ffmpeg_downsample_fps.py slowmo \
        -i in.mp4 -o out_slowmo_30fps_with_audio.mp4 -f 30 --audio stretch

    # Batch mode (process all *.mp4 in a directory):
    python ffmpeg_downsample_fps.py drop \
        --input-dir /path/in --output-dir /path/out -f 30

    python ffmpeg_downsample_fps.py slowmo \
        --input-dir /path/in --output-dir /path/out -f 30
"""

import argparse
import math
import shutil
import sys
from pathlib import Path

import ffmpeg


def die(msg: str) -> None:
    """Terminate execution with a formatted error message.

    Args:
        msg: Human-readable error detail to include in the exit message.

    Returns:
        None.

    Raises:
        SystemExit: Always raised with an ``ERROR: ...`` message.
    """
    raise SystemExit(f"ERROR: {msg}")


def need_cmd(cmd: str) -> None:
    """Ensure an external executable is available on PATH.

    Args:
        cmd: Executable name to locate (for example ``ffmpeg`` or ``ffprobe``).

    Returns:
        None.

    Raises:
        SystemExit: If the executable cannot be found.
    """
    if shutil.which(cmd) is None:
        die(f"Missing required executable on PATH: {cmd}")


def probe(path: Path) -> dict:
    """Run ``ffprobe`` on a media file and return probe metadata.

    Args:
        path: Input media file path to inspect.

    Returns:
        Dictionary returned by ``ffmpeg.probe`` containing stream/format metadata.

    Raises:
        SystemExit: If ``ffprobe`` is unavailable or probing fails.
    """
    need_cmd("ffprobe")
    try:
        return ffmpeg.probe(str(path))
    except ffmpeg.Error as e:
        stderr = ""
        try:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        except Exception:
            stderr = ""
        die(f"ffprobe failed for {path}: {stderr.strip() or e!s}")


def has_audio_stream(info: dict) -> bool:
    """Check whether probe metadata contains at least one audio stream.

    Args:
        info: Probe metadata dictionary (typically from :func:`probe`).

    Returns:
        ``True`` if any stream has ``codec_type == 'audio'``, else ``False``.
    """
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


def parse_fraction(frac: str) -> float:
    """Parse an ffprobe frame-rate value into a float.

    Args:
        frac: Frame-rate text value (for example ``"30000/1001"`` or ``"120"``).

    Returns:
        Parsed numeric value as a float.

    Raises:
        SystemExit: If the denominator is zero for fractional input.
        ValueError: If numeric conversion fails.
    """
    # e.g. "30000/1001" or "120".
    if "/" in frac:
        num_s, den_s = frac.split("/", 1)
        num = float(num_s)
        den = float(den_s)
        if den == 0:
            die(f"Invalid frame rate fraction: {frac}")
        return num / den
    return float(frac)


def get_source_fps(info: dict) -> float:
    """Extract source video FPS from probe metadata.

    Args:
        info: Probe metadata dictionary containing stream entries.

    Returns:
        Positive source frame rate as a float.

    Raises:
        SystemExit: If no video stream exists or FPS cannot be determined.
    """
    # Prefer avg_frame_rate; fall back to r_frame_rate.
    vstreams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not vstreams:
        die("No video stream found")

    v0 = vstreams[0]
    for key in ("avg_frame_rate", "r_frame_rate"):
        val = v0.get(key)
        if val and val != "0/0":
            fps = parse_fraction(val)
            if fps > 0:
                return fps

    die("Could not determine source FPS from probe")


def atempo_chain(tempo: float) -> list[float]:
    """Split a desired audio tempo into ffmpeg-compatible ``atempo`` steps.

    ffmpeg's ``atempo`` filter accepts factors only in the range [0.5, 2.0], so
    this function decomposes an arbitrary positive tempo multiplier into a list of
    valid factors whose product approximates the requested tempo.

    Args:
        tempo: Desired overall tempo multiplier.

    Returns:
        List of tempo factors, each in [0.5, 2.0].

    Raises:
        SystemExit: If ``tempo`` is not positive.
    """
    if tempo <= 0:
        die(f"Invalid audio tempo: {tempo}")

    factors: list[float] = []

    # ffmpeg atempo only supports 0.5..2.0 per filter.
    t = tempo
    while t < 0.5:
        factors.append(0.5)
        t /= 0.5
    while t > 2.0:
        factors.append(2.0)
        t /= 2.0

    factors.append(t)
    return factors


def build_common_output_kwargs(crf: int, preset: str) -> dict:
    """Build shared ffmpeg output settings used by all modes.

    Args:
        crf: Constant Rate Factor value for x264 quality control.
        preset: x264 preset name controlling encode speed vs. compression.

    Returns:
        Dictionary of output keyword arguments passed to ``ffmpeg.output``.
    """
    return {
        "vcodec": "libx264",
        "preset": preset,
        "crf": str(crf),
        "pix_fmt": "yuv420p",
        "movflags": "+faststart",
    }


def cmd_drop(input_path: Path, output_path: Path, target_fps: float, crf: int, preset: str) -> None:
    """Downsample video by dropping frames while preserving duration.

    Args:
        input_path: Source video file path.
        output_path: Destination video file path.
        target_fps: Target output frame rate.
        crf: x264 CRF value for video quality.
        preset: x264 preset value.

    Returns:
        None.

    Raises:
        SystemExit: If required tools are missing or probe fails.
        ffmpeg.Error: If ffmpeg execution fails.
    """
    need_cmd("ffmpeg")
    info = probe(input_path)
    input_stream = ffmpeg.input(str(input_path))

    v = input_stream.video.filter("fps", fps=target_fps)

    out_kwargs = build_common_output_kwargs(crf=crf, preset=preset)

    if has_audio_stream(info):
        a = input_stream.audio
        stream = (
            ffmpeg.output(v, a, str(output_path), acodec="copy", **out_kwargs)
            .global_args("-hide_banner")
            .overwrite_output()
        )
    else:
        stream = (
            ffmpeg.output(v, str(output_path), **out_kwargs)
            .global_args("-hide_banner")
            .overwrite_output()
        )

    stream.run()


def cmd_slowmo(
    input_path: Path,
    output_path: Path,
    target_fps: float,
    src_fps: float | None,
    audio_mode: str,
    crf: int,
    preset: str,
) -> None:
    """Create slow-motion output by stretching timestamps and forcing target FPS.

    Args:
        input_path: Source video file path.
        output_path: Destination video file path.
        target_fps: Desired output frame rate.
        src_fps: Source frame rate override. If ``None``, inferred via probe.
        audio_mode: Audio handling mode: ``mute``, ``stretch``, or ``copy``.
        crf: x264 CRF value for video quality.
        preset: x264 preset value.

    Returns:
        None.

    Raises:
        SystemExit: If FPS values are invalid, audio mode is invalid, or tool/probe
            preconditions fail.
        ffmpeg.Error: If ffmpeg execution fails.
    """
    need_cmd("ffmpeg")
    info = probe(input_path)
    input_stream = ffmpeg.input(str(input_path))

    if src_fps is None:
        src_fps = get_source_fps(info)

    if src_fps <= 0 or target_fps <= 0:
        die("FPS values must be > 0")

    slow_factor = src_fps / target_fps
    if not math.isfinite(slow_factor) or slow_factor <= 0:
        die(f"Invalid slow factor computed: {slow_factor}")

    # Stretch video timestamps, then force CFR at target fps.
    v = input_stream.video.filter("setpts", f"{slow_factor}*PTS")

    out_kwargs = build_common_output_kwargs(crf=crf, preset=preset)

    # -r and -vsync are output args.
    out_kwargs |= {
        "r": str(target_fps),
        "vsync": "cfr",
    }

    have_audio = has_audio_stream(info)
    if audio_mode == "stretch" and not have_audio:
        print("WARNING: --audio stretch requested but input has no audio; using mute.", file=sys.stderr)
        audio_mode = "mute"

    if audio_mode == "mute" or not have_audio:
        stream = (
            ffmpeg.output(v, str(output_path), **out_kwargs)
            .global_args("-hide_banner")
            .overwrite_output()
        )
        stream.run()
        return

    if audio_mode == "copy":
        print("WARNING: --audio copy will likely de-sync (audio ends early).", file=sys.stderr)
        a = input_stream.audio
        stream = (
            ffmpeg.output(v, a, str(output_path), acodec="copy", **out_kwargs)
            .global_args("-hide_banner")
            .overwrite_output()
        )
        stream.run()
        return

    if audio_mode != "stretch":
        die("Invalid audio mode (expected mute|stretch|copy)")

    # Time-stretch audio to match slowmo.
    # If video is slowed by slow_factor, audio tempo needs to be 1/slow_factor.
    tempo = 1.0 / slow_factor
    a = input_stream.audio
    for f in atempo_chain(tempo):
        a = a.filter("atempo", f)

    stream = (
        ffmpeg.output(v, a, str(output_path), acodec="aac", audio_bitrate="128k", **out_kwargs)
        .global_args("-hide_banner")
        .overwrite_output()
    )
    stream.run()


def positive_float(s: str) -> float:
    """argparse type converter that accepts only positive floats.

    Args:
        s: Raw argument string.

    Returns:
        Parsed positive float value.

    Raises:
        argparse.ArgumentTypeError: If parsing fails or value is not > 0.
    """
    try:
        v = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Expected a number, got: {s}")
    if v <= 0:
        raise argparse.ArgumentTypeError(f"Expected > 0, got: {s}")
    return v


def iter_mp4_files(input_dir: Path) -> list[Path]:
    """List ``.mp4`` files in a directory (non-recursive), sorted by name.

    Args:
        input_dir: Directory to scan.

    Returns:
        Sorted list of file paths ending in ``.mp4`` (case-insensitive).

    Raises:
        SystemExit: If ``input_dir`` does not exist or is not a directory.
    """
    if not input_dir.exists() or not input_dir.is_dir():
        die(f"Input directory not found: {input_dir}")
    return sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"])


def resolve_single_or_batch(args: argparse.Namespace) -> tuple[list[tuple[Path, Path]], bool]:
    """Resolve CLI paths into one or more input/output processing pairs.

    Args:
        args: Parsed argparse namespace containing ``input`` and ``output`` values.

    Returns:
        Tuple ``(pairs, is_batch)`` where:
            - ``pairs`` is a list of ``(input_path, output_path)`` tuples.
            - ``is_batch`` is ``True`` when directory batch mode is active.

    Raises:
        SystemExit: If required paths are missing or invalid.
    """

    input_file = getattr(args, "input", None)
    output_file = getattr(args, "output", None)

    # If input_file is a directory, treat as batch mode (input_dir/output_dir).
    if input_file is not None and input_file.is_dir():
        output_file.mkdir(parents=True, exist_ok=True)
        input_dir = Path(input_file)
        output_dir = Path(output_file)
        output_dir.mkdir(parents=True, exist_ok=True)

        files = iter_mp4_files(input_dir)
        if not files:
            die(f"No .mp4 files found in directory: {input_dir}")

        pairs = [(p, output_dir / p.name) for p in files]
        return pairs, True

    # Single-file mode
    if input_file is not None or output_file is not None:
        if input_file is None or output_file is None:
            die("Single-file mode requires both -i/--input and -o/--output")
        return [(Path(input_file), Path(output_file))], False

    die("Missing input/output. Use -i/-o for a single file or --input-dir/--output-dir for a directory.")


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser for this CLI.

    Args:
        None.

    Returns:
        Configured ``argparse.ArgumentParser`` instance.
    """
    p = argparse.ArgumentParser(
        prog="ffmpeg_downsample_fps.py",
        description="Downsample fps (drop frames) or create slow-motion by stretching time.",
    )

    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="veryfast")

    sub = p.add_subparsers(dest="mode", required=True)

    drop = sub.add_parser("drop", help="Drop frames to target FPS; keep same duration")
    drop_in = drop.add_mutually_exclusive_group(required=False)
    drop_out = drop.add_mutually_exclusive_group(required=False)
    drop_in.add_argument("-i", "--input", type=Path, help="Input mp4 file or directory")
    drop_out.add_argument("-o", "--output", type=Path, help="Output mp4 file or directory")
    drop.add_argument("-f", "--fps", required=True, type=positive_float)

    slow = sub.add_parser("slowmo", help="Stretch time so playback becomes slow-motion at target FPS")
    slow_in = slow.add_mutually_exclusive_group(required=False)
    slow_out = slow.add_mutually_exclusive_group(required=False)
    slow_in.add_argument("-i", "--input", type=Path, help="Input mp4 file or directory")
    slow_out.add_argument("-o", "--output", type=Path, help="Output mp4 file or directory")
    slow.add_argument("-f", "--fps", required=True, type=positive_float)
    slow.add_argument("--src-fps", type=positive_float)
    slow.add_argument("--audio", choices=["mute", "stretch", "copy"], default="mute")

    return p


def main(argv: list[str]) -> int:
    """Program entrypoint for command-line execution.

    Args:
        argv: Command-line arguments excluding program name.

    Returns:
        Process exit code (``0`` on success).

    Raises:
        SystemExit: For fatal validation or mode-selection errors.
        ffmpeg.Error: Propagated from ffmpeg run failures.
    """
    args = build_parser().parse_args(argv)

    pairs, is_batch = resolve_single_or_batch(args)

    if args.mode == "drop":
        for idx, (in_path, out_path) in enumerate(pairs, start=1):
            if not in_path.exists():
                die(f"Input not found: {in_path}")
            if is_batch:
                print(f"[{idx}/{len(pairs)}] drop {in_path.name} -> {out_path}")
            cmd_drop(in_path, out_path, args.fps, args.crf, args.preset)
        return 0

    if args.mode == "slowmo":
        for idx, (in_path, out_path) in enumerate(pairs, start=1):
            if not in_path.exists():
                die(f"Input not found: {in_path}")
            if is_batch:
                print(f"[{idx}/{len(pairs)}] slowmo {in_path.name} -> {out_path}")
            cmd_slowmo(in_path, out_path, args.fps, args.src_fps, args.audio, args.crf, args.preset)
        return 0

    die(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

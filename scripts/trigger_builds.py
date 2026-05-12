#!/usr/bin/env python3
"""
Trigger COPR builds for goose in @rhel-lightspeed/goose.

Each target runs with no options, which means that the builds take quite a bit
longer since the checks run during build.

Authentication requires a ~/.config/copr file or COPR_LOGIN, COPR_TOKEN, COPR_USERNAME env vars.
"""

import argparse
import dataclasses
import math
import os
import sys
import time
import typing as t

from pathlib import Path

from copr.v3 import Client
from copr.v3 import CoprRequestException
from copr.v3.exceptions import CoprAuthException
from copr.v3.exceptions import CoprConfigException
from rich.live import Live
from rich.table import Table


OWNER = "@rhel-lightspeed"
PROJECT = "goose"
PACKAGE = "goose"

TERMINAL_STATES = {"succeeded", "failed", "canceled", "forked"}

STATE_STYLES = {
    "succeeded": "[bold green]succeeded[/]",
    "failed": "[bold red]failed[/]",
    "canceled": "[dim]canceled[/]",
    "forked": "[dim]forked[/]",
    "running": "[bold yellow]running[/]",
    "starting": "[yellow]starting[/]",
    "importing": "[yellow]importing[/]",
    "pending": "[dim yellow]pending[/]",
    "waiting": "[dim]waiting[/]",
}


@dataclasses.dataclass(frozen=True)
class Targeter:
    """Build chroots based on versions and architectures."""

    fedora_versions: t.Iterable[str] = ("43", "44", "rawhide")
    rhel_versions: t.Iterable[str] = ("9", "10")
    architectures: t.Iterable[str] = ("x86_64", "aarch64", "s390x", "ppc64le")
    chroots: t.Iterable[str] = dataclasses.field(init=False)

    def __post_init__(self):
        targets = [
            *[f"fedora-{ver}" for ver in self.fedora_versions],
            *[f"{dist}-{ver}" for dist in ("epel", "rhel") for ver in self.rhel_versions],
        ]
        chroots = [f"{target}-{arch}" for target in targets for arch in self.architectures]
        super().__setattr__("chroots", chroots)


def create_client(config_file: Path | None = None) -> Client:
    login = os.environ.get("COPR_LOGIN")
    token = os.environ.get("COPR_TOKEN")

    if login and token:
        return Client(
            {
                "copr_url": os.environ.get("COPR_URL", "https://copr.fedorainfracloud.org"),
                "login": login,
                "token": token,
                "username": os.environ.get("COPR_USERNAME"),
            }
        )

    try:
        return Client.create_from_config_file(config_file)
    except CoprConfigException as exc:
        sys.exit(f"ERROR: {exc}")


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"

    return f"{m}m {s}s" if m else f"{s}s"


def _build_table(builds: list[dict]) -> Table:
    table = Table(title="COPR Build Status", title_style="bold cyan")
    table.add_column("Build ID", justify="right")
    table.add_column("Chroots", max_width=60)
    table.add_column("State", justify="center")
    table.add_column("Duration", justify="right")

    now = time.monotonic()
    for b in builds:
        state = b["state"]
        elapsed = b.get("finished_at", now) - b["submitted_at"]
        table.add_row(
            str(b["build_id"]),
            ", ".join(b["chroots"]),
            STATE_STYLES.get(state, f"[dim]{state}[/]"),
            _format_duration(elapsed),
        )

    return table


def monitor_builds(client: Client, builds: list[dict], poll_interval: float) -> bool:
    try:
        with Live(_build_table(builds), refresh_per_second=2) as live:
            while True:
                for b in builds:
                    if b["state"] in TERMINAL_STATES:
                        continue
                    try:
                        b["state"] = client.build_proxy.get(b["build_id"]).state
                        if b["state"] in TERMINAL_STATES:
                            b["finished_at"] = time.monotonic()
                    except CoprRequestException:
                        pass
                live.update(_build_table(builds))
                if all(b["state"] in TERMINAL_STATES for b in builds):
                    break
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nInterrupted.")

        return False

    return all(b["state"] == "succeeded" for b in builds)


def positive_float(value: str | float) -> float:
    if not isinstance(value, float):
        exception = argparse.ArgumentTypeError(f"Value must be a positive float: {value}")
        try:
            value = float(value)
        except ValueError:
            raise exception

        if value <= 0 or not math.isfinite(value):
            raise exception

    return value


def positive_int(value: str | int) -> int:
    if not isinstance(value, int):
        exception = argparse.ArgumentTypeError(f"Value must be a positive integer: {value}")
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise exception

        if value <= 0:
            raise exception

    return value


def parse_args() -> argparse.Namespace:
    targeter = Targeter()
    parser = argparse.ArgumentParser(
        description="Trigger COPR builds for goose across all chroots.",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be built without triggering.",
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Submit builds without waiting for results.",
    )
    parser.add_argument(
        "--poll-interval",
        "-S",
        type=positive_float,
        default=30.0,
        metavar="S",
        help="Seconds between status polls (default: 30).",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=positive_int,
        default=36000,
        metavar="S",
        help="Build timeout in seconds (default: 36000).",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        help="Path to Copr config file.",
    )
    parser.add_argument(
        "chroots",
        nargs="*",
        help="Chroots to build for. If not specified, all chroots are used.",
        default=targeter.chroots,
        choices=targeter.chroots,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chroots = args.chroots

    print(f"Package: {PACKAGE}")
    print(f"Project: {OWNER}/{PROJECT}")
    print(f"Chroots ({len(chroots)}):")
    for chroot in chroots:
        print(f"  - {chroot}")

    client = create_client(args.config)

    if args.dry_run:
        print("\nDry-run mode: no builds triggered.")
        return

    print(f"\nTriggering build for {PACKAGE} ...", flush=True)
    try:
        result = client.package_proxy.build(
            OWNER,
            PROJECT,
            PACKAGE,
            buildopts={"chroots": chroots, "timeout": args.timeout},
        )
        print(f"Build submitted (#{result.id})")
    except (CoprRequestException, CoprAuthException) as exc:
        sys.exit(f"FAILED: {exc}")

    submitted = [
        {
            "build_id": result.id,
            "state": "pending",
            "submitted_at": time.monotonic(),
            "chroots": chroots,
        }
    ]

    if args.no_monitor:
        print(f"\nBuild #{result.id} submitted.")
        return

    print(f"\nMonitoring build #{result.id}...  Use --no-monitor to skip waiting.\n")
    if not monitor_builds(client, submitted, args.poll_interval):
        sys.exit("\nBuild did not succeed.")

    print("\nBuild succeeded.")


if __name__ == "__main__":
    main()

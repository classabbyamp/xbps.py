import sys
from pathlib import Path

from xbps.util import StageDiff, get_remote_repo, read_repodata, compute_stage


BOLD = "\033[0;1m"
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"


def format_diff(diff: StageDiff) -> str:
    return (
        f"{BOLD}shlib:{RESET} {diff.shlib}\n"
        f"\t{BOLD}provider:{RESET} {diff.provider or "[not found]"}\n"
        f"\t{BOLD}required by:{RESET} {", ".join(diff.required_by)}"
    )


def main() -> None:
    if sys.argv[1:]:
        if sys.argv[1:] == ["-h"] or sys.argv[1:] == ["--help"]:
            print(
                f"usage: {sys.argv[0]} [urls-or-paths-to-repodatas]\n"
                "lists staged packages in each listed repodata\n"
                "defaults to all repositories on repo-default\n"
            )
            exit()
        args = sys.argv[1:]
    else:
        args = [
            "https://repo-default.voidlinux.org/current/" + f for f in [
                "x86_64-repodata", "i686-repodata", "armv7l-repodata", "armv6l-repodata",
                "musl/x86_64-musl-repodata", "musl/armv7l-musl-repodata", "musl/armv6l-musl-repodata",
                "aarch64/aarch64-repodata", "aarch64/aarch64-musl-repodata",
            ]
        ]

    for arg in args:
        print(f"{BOLD}=> Checking repodata at {arg}... ", end="")

        if arg.startswith(("http://", "https://")):
            repodata = get_remote_repo(arg)
        else:
            repodata = Path(arg)
            if not repodata.is_file():
                print(f"{RED}ERROR: {repodata} is not a file{RESET}", file=sys.stderr)
                exit(1)

        index, stage = read_repodata(repodata)

        diffs = compute_stage(index, stage)
        if diffs:
            print(f"{RED}STAGED!{RESET}")
            for diff in diffs:
                print(format_diff(diff))
        else:
            print(f"{BLUE}OK{RESET}")


if __name__ == "__main__":
    main()

import plistlib
import sys
import tarfile
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import IO, BinaryIO
from urllib.request import urlopen
from xml.parsers.expat import ExpatError

if sys.version_info >= (3, 14):
    from compression.zstd import ZstdFile
else:
    from pyzstd import ZstdFile

@dataclass
class Package:
    pkgver: str
    shlib_provides: list[str] = field(default_factory=list)
    shlib_requires: list[str] = field(default_factory=list)


@dataclass
class StageDiff:
    shlib: str
    provider: str | None
    required_by: list[str]


type RepoIndex = dict[str, Package]


def get_remote_repo(url: str) -> BinaryIO:
    resp = urlopen(url)
    return BytesIO(resp.read())


def extract_index(tar: tarfile.TarFile, fname: str) -> IO[bytes]:
    try:
        f = tar.extractfile(fname)
    except KeyError:
        raise FileNotFoundError(fname)
    if f is None:
        raise FileNotFoundError("not a file")
    return f


def read_index(f: IO[bytes]) -> RepoIndex:
    idx = {}
    try:
        for pkgname, pkg in plistlib.load(f, fmt=plistlib.FMT_XML).items():
            idx[pkgname] = Package(
                pkgver=pkg["pkgver"],
                shlib_provides=pkg.get("shlib-provides", []),
                shlib_requires=pkg.get("shlib-requires", []),
            )
    except ExpatError:
        # empty/invalid
        pass
    return idx


def read_repodata(rdf: BinaryIO | Path) -> tuple[RepoIndex, RepoIndex]:
    index = {}
    stage = {}
    with ZstdFile(rdf, mode="r") as fp, tarfile.open(fileobj=fp) as tar:
        f = extract_index(tar, "index.plist")
        index = read_index(f)
        f = extract_index(tar, "stage.plist")
        stage = read_index(f)
    return index, stage


def compute_stage(index: RepoIndex, stage: RepoIndex) -> list[StageDiff]:
    # this algorithm matches bin/xbps-rindex/index-add.c:repodata_commit() as of 0.60.5
    res = []

    if not len(stage):
        # nothing staged
        return res

    old_shlibs = {}
    used_shlibs = defaultdict(list)

    # find all old shlib-provides
    for pkgname in stage:
        if (pkg := index.get(pkgname)) is not None:
            for shlib in pkg.shlib_provides:
                old_shlibs[shlib] = pkgname

    # throw away all unused shlibs
    for pkgname in index:
        if (pkg := stage.get(pkgname, index.get(pkgname))) is not None:
            for shlib in pkg.shlib_requires:
                if shlib not in old_shlibs:
                    continue
                used_shlibs[shlib].append(pkgname)

    # purge all packages fulfulled by the index and not in the stage
    for pkgname, pkg in index.items():
        if pkgname in stage:
            continue
        for shlib in pkg.shlib_provides:
            if shlib in used_shlibs:
                del used_shlibs[shlib]

    # purge all packages fulfilled by the stage
    for pkgname, pkg in stage.items():
        for shlib in pkg.shlib_provides:
            if shlib in used_shlibs:
                del used_shlibs[shlib]

    # collect inconsistent shlibs
    for shlib, reqs in used_shlibs.items():
        prov = old_shlibs.get(shlib)
        res.append(StageDiff(shlib=shlib, provider=prov, required_by=reqs))
    return res

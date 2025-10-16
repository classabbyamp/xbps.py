import plistlib
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from typing import IO, BinaryIO
from urllib.request import urlopen
from xml.parsers.expat import ExpatError

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from .package import Package

if sys.version_info >= (3, 14):
    from compression.zstd import ZstdFile
else:
    from pyzstd import ZstdFile


type RepoIndex = dict[str, Package]


class SignatureType(Enum):
    RSA = "rsa"


@dataclass
class RepoMeta:
    public_key: str
    public_key_size: int
    signature_by: str
    signature_type: SignatureType


@dataclass
class StageDiff:
    shlib: str
    provider: str | None
    required_by: list[str]


def _extract_index(tar: tarfile.TarFile, fname: str) -> IO[bytes]:
    try:
        f = tar.extractfile(fname)
    except KeyError:
        raise FileNotFoundError(fname)
    if f is None:
        raise FileNotFoundError("not a file")
    return f


def _read_index(f: IO[bytes]) -> RepoIndex:
    idx = {}
    try:
        for pkgname, pkg in plistlib.load(f, fmt=plistlib.FMT_XML).items():
            idx[pkgname] = Package(**pkg)
    except ExpatError:
        # empty/invalid
        pass
    return idx


def _read_repodata(rdf: BinaryIO | Path) -> tuple[RepoIndex, RepoIndex, RepoMeta | None]:
    index = {}
    stage = {}
    with ZstdFile(rdf, mode="r") as fp, tarfile.open(fileobj=fp) as tar:
        f = _extract_index(tar, "index.plist")
        index = _read_index(f)
        f = _extract_index(tar, "stage.plist")
        stage = _read_index(f)
    return index, stage, None


@dataclass
class Repodata:
    index: RepoIndex
    stage: RepoIndex
    meta: RepoMeta | None = None

    @classmethod
    def from_repodata(cls, url: str | Path):
        if isinstance(url, Path):
            return cls.from_local(url)
        else:
            if url.startswith(("http://", "https://", "ftp://", "socks5://")):
                return cls.from_remote(url)
            else:
                return cls.from_local(Path(url))


    @classmethod
    def from_local(cls, path: Path):
        index, stage, meta = _read_repodata(path)
        return cls(index, stage, meta)


    @classmethod
    def from_remote(cls, url: str):
        resp = urlopen(url)
        index, stage, meta = _read_repodata(BytesIO(resp.read()))
        return cls(index, stage, meta)


    def compute_stage(self) -> list[StageDiff]:
        # this algorithm matches bin/xbps-rindex/index-add.c:repodata_commit() as of 0.60.5
        res = []

        if not len(self.stage):
            # nothing staged
            return res

        old_shlibs = {}
        used_shlibs = defaultdict(list)

        # find all old shlib-provides
        for pkgname in self.stage:
            if (pkg := self.index.get(pkgname)) is not None:
                for shlib in pkg.shlib_provides:
                    old_shlibs[shlib] = pkgname

        # throw away all unused shlibs
        for pkgname in self.index:
            if (pkg := self.stage.get(pkgname, self.index.get(pkgname))) is not None:
                for shlib in pkg.shlib_requires:
                    if shlib not in old_shlibs:
                        continue
                    used_shlibs[shlib].append(pkgname)

        # purge all packages fulfulled by the index and not in the stage
        for pkgname, pkg in self.index.items():
            if pkgname in self.stage:
                continue
            for shlib in pkg.shlib_provides:
                if shlib in used_shlibs:
                    del used_shlibs[shlib]

        # purge all packages fulfilled by the stage
        for pkgname, pkg in self.stage.items():
            for shlib in pkg.shlib_provides:
                if shlib in used_shlibs:
                    del used_shlibs[shlib]

        # collect inconsistent shlibs
        for shlib, reqs in used_shlibs.items():
            prov = old_shlibs.get(shlib)
            res.append(StageDiff(shlib=shlib, provider=prov, required_by=reqs))
        return res

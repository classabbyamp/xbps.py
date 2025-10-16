from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path


type Alternative = tuple[str, Path]


@dataclass(init=False, repr=False)
class Package:
    pkgver: str
    architecture: str
    alternatives: dict[str, list[Alternative]] = field(default_factory=dict)
    automatic_install: bool | None = None
    build_date: str | None = None
    build_options: list[str] = field(default_factory=list)
    changelog: str | None = None
    conf_files: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    filename_sha256: str | None = None
    filename_size: str | None = None
    hold: bool | None = None
    homepage: str | None = None
    # TODO: parse to datetime. this is hard because XBPS emits ambiguous timezones
    # like "EDT" that can only be parsed if it's the current timezone or "UTC"
    # datetime.strptime ignores timezones, and dateutil.parser.parse doesn't understand
    # it if not current timezone
    install_date: str | None = None
    install_msg: str | None = None
    install_script: str | None = None
    installed_size: str | None = None
    license: str | None = None
    long_desc: str | None = None
    maintainer: str | None = None
    metafile_sha256: str | None = None
    packaged_with: str | None = None
    preserve: bool | None = None
    provides: list[str] = field(default_factory=list)
    remove_msg: str | None = None
    remove_script: str | None = None
    replaces: list[str] = field(default_factory=list)
    repolock: bool | None = None
    repository: str | None = None
    reverts: list[str] = field(default_factory=list)
    run_depends: list[str] = field(default_factory=list)
    shlib_provides: list[str] = field(default_factory=list)
    shlib_requires: list[str] = field(default_factory=list)
    short_desc: str | None = None
    source_revisions: str | None = None
    sourcepkg: str | None = None
    tags: list[str] = field(default_factory=list)

    def __init__(self, **kwargs):
        names = set(f.name for f in fields(self))
        for k, v in kwargs.items():
            if "-" in k:
                k = k.replace("-", "_")
            if k not in names:
                continue
            match k:
                case "alternatives":
                    if isinstance(v, str):
                        v_split = []
                        for itm in v:
                            parts = itm.partition(":")
                            itm = (parts[0], Path(parts[2]))
                            v_split.append(itm)
                        v = v_split
                case "build_options":
                    if isinstance(v, str):
                        v = v.split(" ")
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f"Package(pkgname='{self.pkgname}', version='{self.version}', arch='{self.architecture}')"

    @property
    def pkgname(self) -> str:
        return self.pkgver.rpartition("-")[0]

    @property
    def version(self) -> str:
        # TODO: parse into dewey tuple
        return self.pkgver.rpartition("-")[2]

    # TODO: ordering functions based on version/dewey

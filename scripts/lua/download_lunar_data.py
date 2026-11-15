"""Download the datasets whose acquisition mode is 'full' or 'remote_zip_member'.

usage: python download_lunar_data.py [dataset_id ...]
Files go to data/raw/<dataset_id>/ unaltered; every file gets a manifest entry
(URL, size, remote Last-Modified, SHA-256, UTC retrieval time) in
data/raw/download_manifest.json.  'stream' and 'remote_rows' datasets are acquired
inside process_lunar_data.py because acquisition and reduction are coupled there.
"""

from __future__ import annotations

import datetime as _dt
import io
import re
import sys
import zipfile
from pathlib import Path

from dataset_registry import DATASETS
from lunar_common import RAW, sha256_file
from lunar_io import download, get_range, head, save_manifest_entry


class HTTPRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP Range (lets zipfile read single members)."""

    def __init__(self, url):
        self.size, _, self.url = head(url)
        self.pos = 0
        self._cache = {}

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        blk = 1 << 20
        out = bytearray()
        p = self.pos
        while len(out) < n:
            b0 = (p // blk) * blk
            if b0 not in self._cache:
                if len(self._cache) > 64:
                    self._cache.clear()
                self._cache[b0] = get_range(self.url, b0, min(blk, self.size - b0))
            chunk = self._cache[b0][p - b0 : p - b0 + (n - len(out))]
            out += chunk
            p += len(chunk)
        self.pos = p
        return bytes(out)

    def readinto(self, b):
        d = self.read(len(b))
        b[: len(d)] = d
        return len(d)


ZIP_MEMBERS = {
    # USGS Unified Geologic Map: unit polygons only (plus .prj and documentation of units)
    "USGS_UGM_2020": [
        r"Shapefiles/GeoUnits\.(shp|shx|dbf|prj|cpg)$",
        r"DOMU_descriptions\.csv$",
        r"GeologyUnit_colors\.csv$",
        r"Moon_v2_March2020\.txt$",
    ],
    # Wieczorek et al. 2013: the 4 published crustal-thickness models (spread = model uncertainty) + doc
    "GRAIL_CRUST_WIECZOREK2013": [
        r"^GRAILCrustalThicknessArchive/Data/Model[1-4]_thick\.dat$",
        r"^GRAILCrustalThicknessArchive/GRAILCrustalThicknessArchive\.html$",
    ],
}


def fetch_zip_members(ds):
    url = ds["urls"][0]
    dest = RAW / ds["dataset_id"]
    dest.mkdir(parents=True, exist_ok=True)
    f = HTTPRangeFile(url)
    z = zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 20))
    names = z.namelist()
    (dest / "_zip_listing.txt").write_text(
        "\n".join(f"{i.file_size}\t{i.filename}" for i in z.infolist()), encoding="utf-8"
    )
    pats = [re.compile(p) for p in ZIP_MEMBERS[ds["dataset_id"]]]
    chosen = [n for n in names if any(p.search(n) for p in pats) and not n.endswith("/")]
    total = sum(z.getinfo(n).file_size for n in chosen)
    print(
        f"  zip has {len(names)} members; extracting {len(chosen)} ({total / 1e6:.1f} MB uncompressed)"
    )
    if total > 900e6:
        raise SystemExit("selection too large; refine patterns")
    for n in chosen:
        out = dest / Path(n).name
        with z.open(n) as src, open(out, "wb") as dst:
            dst.write(src.read())
        save_manifest_entry(
            f"{ds['dataset_id']}:{out.name}",
            dict(
                dataset_id=ds["dataset_id"],
                url=url,
                zip_member=n,
                local_path=str(out.relative_to(RAW.parent.parent)),
                size_bytes=out.stat().st_size,
                sha256=sha256_file(out),
                mode="remote_zip_member",
                zip_size_bytes=f.size,
                retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
            ),
        )
        print("   +", n)


def main(ids):
    for ds in DATASETS:
        if ids and ds["dataset_id"] not in ids:
            continue
        mode = ds["acquisition"]
        if mode == "full":
            print(f"[{ds['dataset_id']}] full download of {len(ds['urls'])} file(s)")
            for u in ds["urls"]:
                name = u.rstrip("/").split("/")[-1].split("?")[0]
                if ds["dataset_id"] == "RAVAT2020_MAG":
                    name = "ravat2020_lunar_magnetic_model_viewcontent.bin"
                if ds["dataset_id"] == "ROBBINS2018_CRATERS":
                    name = "lunar_crater_database_robbins_2018.zip"
                try:
                    e = download(u, RAW / ds["dataset_id"] / name.lower(), ds["dataset_id"])
                    print(f"   ok {name} {e['size_bytes'] / 1e6:.1f} MB sha256={e['sha256'][:12]}")
                except Exception as ex:  # noqa
                    print(f"   FAILED {name}: {ex}")
        elif mode == "remote_zip_member":
            print(f"[{ds['dataset_id']}] selective zip extraction")
            try:
                fetch_zip_members(ds)
            except Exception as ex:  # noqa
                print(f"   FAILED: {ex}")


if __name__ == "__main__":
    main(set(sys.argv[1:]))

"""Network and file I/O helpers: parallel ranged downloads, remote row sampling,
PDS3 label parsing, and the download manifest (provenance + SHA-256).

Rationale for remote row sampling
---------------------------------
Several global rasters are far larger than the regional analysis needs (regions are
~790,000 km^2 each) and than the available disk/bandwidth.  Instead of substituting a
thumbnail or visualisation, we read a systematic subset of the ORIGINAL science
records (every k-th image line, full lines, native values, native scaling) straight
from the official archive with HTTP Range requests.  The stride is recorded per
dataset and the digest of every fetched byte block is stored in the manifest so the
exact sample is reproducible.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from lunar_common import RAW, ROOT

UA = {"User-Agent": "lunar-analog-research-pipeline/1.0 (python-requests)"}
MANIFEST = RAW / "download_manifest.json"
_lock = threading.Lock()
_session_local = threading.local()


def _session():
    s = getattr(_session_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        _session_local.s = s
    return s


def head(url, retries=8):
    for k in range(retries):
        try:
            r = _session().head(url, allow_redirects=True, timeout=60)
            r.raise_for_status()
            size = int(r.headers.get("Content-Length", -1))
            return size, r.headers.get("Last-Modified", ""), r.url
        except Exception:  # noqa
            if k == retries - 1:
                raise
            _session_local.s = None
            time.sleep(3 * (k + 1))


def get_range(url, start, length, retries=10):
    end = start + length - 1
    for k in range(retries):
        try:
            r = _session().get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=180)
            if r.status_code in (
                429,
                503,
            ):  # rate limited: honour Retry-After, back off progressively
                wait = float(r.headers.get("Retry-After", 0) or 0) or min(120, 5 * 2**k)
                time.sleep(wait)
                raise OSError(f"rate limited {r.status_code}")
            if r.status_code == 206 and len(r.content) == length:
                return r.content
            if r.status_code == 200 and start == 0 and len(r.content) >= length:
                return r.content[:length]
            raise OSError(f"bad range response {r.status_code} len={len(r.content)} want={length}")
        except Exception as e:  # noqa
            if k == retries - 1:
                raise
            _session_local.s = None  # drop a possibly broken keep-alive connection
            time.sleep(2 * (k + 1))


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest_entry(key, entry):
    from lunar_common import update_json

    with _lock:
        update_json(MANIFEST, lambda m: m.__setitem__(key, entry))


def download(url, dest: Path, dataset_id: str, nconn=8, chunk=4 << 20, force=False):
    """Parallel ranged download with resume-by-skip and SHA-256 manifest entry."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, lastmod, final = head(url)
    key = f"{dataset_id}:{dest.name}"
    m = load_manifest()
    if (
        dest.exists()
        and not force
        and dest.stat().st_size == size
        and key in m
        and m[key].get("sha256")
    ):
        return m[key]
    t0 = time.time()
    if size <= 0:
        r = _session().get(url, timeout=600)
        r.raise_for_status()
        dest.write_bytes(r.content)
    else:
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            f.truncate(size)
        offsets = list(range(0, size, chunk))

        def job(off):
            data = get_range(final, off, min(chunk, size - off))
            with _lock:
                with open(tmp, "r+b") as f:
                    f.seek(off)
                    f.write(data)
            return len(data)

        with ThreadPoolExecutor(nconn) as ex:
            got = sum(ex.map(job, offsets))
        assert got == size, (got, size)
        os.replace(tmp, dest)
    h = hashlib.sha256()
    with open(dest, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    entry = dict(
        dataset_id=dataset_id,
        url=url,
        local_path=str(dest.relative_to(ROOT)),
        size_bytes=size,
        remote_last_modified=lastmod,
        sha256=h.hexdigest(),
        mode="full_file",
        retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
    )
    save_manifest_entry(key, entry)
    return entry


def remote_rows(url, dataset_id, header_bytes, row_bytes, row_indices, nconn=8, tag="", max_run=64):
    """Fetch selected fixed-length rows (image lines / table records) from a remote file.

    Returns dict row_index -> bytes and records a manifest entry with a digest of all rows.
    """
    size, lastmod, final = head(url)
    rows = sorted(set(int(i) for i in row_indices))
    # group contiguous rows into runs to limit requests
    runs, cur = [], [rows[0], rows[0]]
    for r in rows[1:]:
        if r == cur[1] + 1 and (cur[1] - cur[0]) < max_run - 1:
            cur[1] = r
        else:
            runs.append(tuple(cur))
            cur = [r, r]
    runs.append(tuple(cur))

    def job(run):
        a, b = run
        data = get_range(final, header_bytes + a * row_bytes, (b - a + 1) * row_bytes)
        return {a + i: data[i * row_bytes : (i + 1) * row_bytes] for i in range(b - a + 1)}

    out = {}
    t0 = time.time()
    with ThreadPoolExecutor(nconn) as ex:
        for d in ex.map(job, runs):
            out.update(d)
    h = hashlib.sha256()
    for r in rows:
        h.update(out[r])
    entry = dict(
        dataset_id=dataset_id,
        url=url,
        size_bytes=size,
        remote_last_modified=lastmod,
        mode="remote_row_sample",
        header_bytes=header_bytes,
        row_bytes=row_bytes,
        n_rows_fetched=len(rows),
        first_row=rows[0],
        last_row=rows[-1],
        row_stride=(rows[1] - rows[0]) if len(rows) > 1 else None,
        rows_per_request_max=max_run,
        sha256_of_fetched_rows=h.hexdigest(),
        retrieved_utc=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
    )
    save_manifest_entry(f"{dataset_id}:{url.rsplit('/', 1)[-1]}{tag}", entry)
    return out


# ---------------------------------------------------------------------------
# PDS3 label parsing (sufficient for IMG cylindrical/polar products used here)
# ---------------------------------------------------------------------------
def parse_pds3_label(text: str) -> dict:
    """Flat parse; keys inside OBJECT blocks are prefixed 'OBJECT.KEY' (last object wins)."""
    out, stack = {}, []
    lines = text.replace("\r", "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].split("/*")[0].rstrip()
        i += 1
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        # multi-line values
        if (
            v.count('"') == 1
            or (v.startswith("(") and not v.endswith(")"))
            or (v.startswith("{") and not v.endswith("}"))
        ):
            while i < len(lines):
                v += " " + lines[i].strip()
                i += 1
                if (
                    v.count('"') % 2 == 0
                    and v.count("(") <= v.count(")")
                    and v.count("{") <= v.count("}")
                ):
                    break
        if k == "OBJECT":
            stack.append(v.strip('"'))
            continue
        if k == "END_OBJECT":
            if stack:
                stack.pop()
            continue
        key = ".".join(stack + [k]) if stack else k
        out[key] = v
        out.setdefault("_flat_" + k, v)
    return out


def lbl_num(lbl, key, default=None):
    v = lbl.get(key, lbl.get("_flat_" + key.split(".")[-1]))
    if v is None:
        return default
    m = re.match(r'^\s*"?([-+0-9.eE]+)', v)
    return float(m.group(1)) if m else default


def lbl_str(lbl, key, default=None):
    v = lbl.get(key, lbl.get("_flat_" + key.split(".")[-1]))
    return v.strip().strip('"') if v is not None else default


def fetch_text(url, retries=10):
    for k in range(retries):
        try:
            r = _session().get(url, timeout=120)
            if r.status_code in (429, 503):
                time.sleep(float(r.headers.get("Retry-After", 0) or 0) or min(120, 5 * 2**k))
                continue
            r.raise_for_status()
            return r.text
        except Exception:  # noqa
            if k == retries - 1:
                raise
            _session_local.s = None
            time.sleep(3 * (k + 1))
    raise OSError(f"rate limited too long: {url}")


PDS_DTYPES = {
    ("LSB_INTEGER", 16): "<i2",
    ("MSB_INTEGER", 16): ">i2",
    ("LSB_INTEGER", 32): "<i4",
    ("MSB_INTEGER", 32): ">i4",
    ("PC_REAL", 32): "<f4",
    ("IEEE_REAL", 32): ">f4",
    ("LSB_UNSIGNED_INTEGER", 16): "<u2",
    ("MSB_UNSIGNED_INTEGER", 16): ">u2",
    ("UNSIGNED_INTEGER", 8): "u1",
    ("MSB_UNSIGNED_INTEGER", 8): "u1",
    ("LSB_UNSIGNED_INTEGER", 8): "u1",
    ("PC_REAL", 64): "<f8",
    ("IEEE_REAL", 64): ">f8",
}


def img_meta_from_label(lbl: dict) -> dict:
    """Extract image geometry from a PDS3 IMG label (IMAGE + IMAGE_MAP_PROJECTION)."""

    def g(k):
        for key in (f"IMAGE.{k}", f"UNCOMPRESSED_FILE.IMAGE.{k}", k):
            if key in lbl:
                return lbl[key]
        return lbl.get("_flat_" + k)

    def gn(k, d=None):
        v = g(k)
        if v is None:
            return d
        m = re.match(r'^\s*"?([-+0-9.eE]+)', v)
        return float(m.group(1)) if m else d

    stype = g("SAMPLE_TYPE").strip('"')
    bits = int(gn("SAMPLE_BITS"))
    meta = dict(
        lines=int(gn("LINES")),
        samples=int(gn("LINE_SAMPLES")),
        dtype=PDS_DTYPES[(stype, bits)],
        scale=gn("SCALING_FACTOR", 1.0),
        offset=gn("OFFSET", 0.0),
        missing=gn("MISSING_CONSTANT", None),
        unit=(g("UNIT") or "").strip('"'),
        name=(g("NAME") or "").strip('"'),
    )
    proj = {k.split(".")[-1]: v for k, v in lbl.items() if k.startswith("IMAGE_MAP_PROJECTION.")}
    meta["projection"] = proj
    rec_bytes = lbl_num(lbl, "RECORD_BYTES")
    ptr = lbl.get("^IMAGE")
    hdr = 0
    if ptr:
        m = re.search(r"(\d+)\s*(<BYTES>)?\s*\)?\s*$", ptr)
        if m:
            n = int(m.group(1))
            hdr = (n - 1) if m.group(2) else (n - 1) * int(rec_bytes or 0)
    meta["header_bytes"] = hdr
    return meta

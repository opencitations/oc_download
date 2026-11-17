"""Load and validate the data shown on the download page.

Layout of the data directory:

    data/datasets.json            the datasets, in the order they appear on the page
    data/<dataset id>/YYYY-MM-DD.json   one file per dump, named after its release date

The most recent file of each dataset is the "latest" dump; the others are
listed in the version selector. See the README for the fields of each file.

Run ``python3 -m src.dumps`` to check the data without starting the server.
"""
import html
import json
import os
import re
import sys
from datetime import date
from types import SimpleNamespace
from urllib.parse import urlparse

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

COLORS = ("purple", "blue")

# field name -> (type, required)
DATASET_FIELDS = {
    "id": (str, True),
    "name": (str, True),
    "tagline": (str, True),
    "description": (str, True),
    "color": (str, False),
}
DUMP_FIELDS = {
    "label": (str, False),
    "description": (str, False),
    "stats": (list, False),
    "stats_note": (str, False),
    "files": (list, True),
    "additional_files": (list, False),
}
STAT_FIELDS = {
    "value": (str, True),
    "label": (str, True),
    "detail": (str, False),
}
FILE_FIELDS = {
    "name": (str, True),
    "url": (str, True),
    "format": (str, False),
    "size": (str, False),
    "uncompressed": (str, False),
    "badge": (str, False),
    "note": (str, False),
    "repository": (str, False),
}

DUMP_FILENAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.json$")
DATASET_ID = re.compile(r"^[a-z][a-z0-9]*$")
MD_LINK = re.compile(r"\[([^\[\]]+)\]\((https?://[^\s()]+)\)")
HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z]")
BRAND = '<span class="oc-purple">Open</span><span class="oc-blue">Citations</span>'


class DumpDataError(Exception):
    """A data file is missing, malformed or has unexpected content."""


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise DumpDataError(f"{path}: file not found") from None
    except json.JSONDecodeError as e:
        raise DumpDataError(
            f"{path}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from None


def _check(obj, fields, where):
    """Check that obj is an object with only known fields of the right type."""
    if not isinstance(obj, dict):
        raise DumpDataError(f"{where}: expected an object like {{...}}")
    unknown = sorted(set(obj) - set(fields))
    if unknown:
        raise DumpDataError(
            f"{where}: unknown field(s) {', '.join(unknown)}. "
            f"Allowed fields: {', '.join(fields)}"
        )
    for name, (kind, required) in fields.items():
        if name not in obj:
            if required:
                raise DumpDataError(f"{where}: missing required field \"{name}\"")
            continue
        value = obj[name]
        if not isinstance(value, kind):
            expected = "a text string" if kind is str else "a list like [...]"
            raise DumpDataError(f"{where}: \"{name}\" must be {expected}")
        if kind is str and not value.strip():
            raise DumpDataError(f"{where}: \"{name}\" is empty")


def render_text(text, where, brand=False):
    """Turn plain text with [label](url) links into safe HTML paragraphs.

    Everything is HTML-escaped, so the data files cannot inject markup.
    With brand=True, "OpenCitations" gets its two-colour styling.
    """
    if HTML_TAG.search(text):
        raise DumpDataError(
            f"{where}: HTML tags are not supported, write links as [label](https://...)"
        )
    paragraphs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        parts = []
        pos = 0
        for m in MD_LINK.finditer(block):
            parts.append(_plain(block[pos:m.start()], brand))
            parts.append(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>'.format(
                    html.escape(m.group(2), quote=True), html.escape(m.group(1))
                )
            )
            pos = m.end()
        parts.append(_plain(block[pos:], brand))
        paragraphs.append("<p>" + "".join(parts) + "</p>")
    return "\n".join(paragraphs)


def _plain(text, brand):
    escaped = html.escape(text)
    return escaped.replace("OpenCitations", BRAND) if brand else escaped


def _repository(url):
    """Name of the archive hosting a file, guessed from its URL."""
    lowered = url.lower()
    if "zenodo" in lowered:
        return "Zenodo"
    if "figshare" in lowered:
        return "Figshare"
    host = urlparse(url).netloc.lower()
    if host == "archive.org" or host.endswith(".archive.org"):
        return "Internet Archive"
    return host[4:] if host.startswith("www.") else host


def _build_file(raw, where):
    _check(raw, FILE_FIELDS, where)
    url = raw["url"].strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise DumpDataError(f"{where}: \"url\" must start with http:// or https://")
    return SimpleNamespace(
        name=raw["name"].strip(),
        url=url,
        format=raw.get("format", "").strip(),
        size=raw.get("size", "").strip(),
        uncompressed=raw.get("uncompressed", "").strip(),
        badge=raw.get("badge", "").strip(),
        note=raw.get("note", "").strip(),
        repository=raw.get("repository", "").strip() or _repository(url),
    )


def _build_group(title, raw_files, where):
    if not raw_files:
        raise DumpDataError(f"{where}: the list is empty")
    files = [_build_file(raw, f"{where}[{i}]") for i, raw in enumerate(raw_files, 1)]
    return SimpleNamespace(
        title=title,
        files=files,
        # a column is shown only when at least one file of the group fills it
        has_format=any(f.format for f in files),
        has_size=any(f.size for f in files),
        has_uncompressed=any(f.uncompressed for f in files),
    )


def _summary(stats):
    """One sentence with the key figures, for the card at the top of the page."""
    parts = [f"{s.value} {s.label.lower()}" for s in stats]
    if not parts:
        return ""
    if len(parts) > 2:
        listed = ", ".join(parts[:-1]) + ", and " + parts[-1]
    else:
        listed = " and ".join(parts)
    return "Includes data on " + listed


def _build_dump(path, dataset_id, day):
    raw = _read_json(path)
    _check(raw, DUMP_FIELDS, path)

    stats = []
    for i, raw_stat in enumerate(raw.get("stats", []), 1):
        _check(raw_stat, STAT_FIELDS, f"{path}: stats[{i}]")
        stats.append(SimpleNamespace(
            value=raw_stat["value"].strip(),
            label=raw_stat["label"].strip(),
            detail=raw_stat.get("detail", "").strip(),
        ))

    groups = [_build_group("Download files", raw["files"], f"{path}: files")]
    if "additional_files" in raw:
        groups.append(_build_group(
            "Additional files", raw["additional_files"], f"{path}: additional_files"
        ))

    description = raw.get("description", "")
    return SimpleNamespace(
        date=day,
        iso=day.isoformat(),
        label=raw.get("label", "").strip() or f"{MONTHS[day.month - 1]} {day.year}",
        anchor=f"{dataset_id}-{day.isoformat()}",
        latest=False,
        option_label="",
        description_html=render_text(description, f"{path}: description") if description else "",
        stats=stats,
        stats_note=raw.get("stats_note", "").strip(),
        summary=_summary(stats),
        groups=groups,
        file_count=sum(len(g.files) for g in groups),
    )


def _load_dumps(folder, dataset_id):
    if not os.path.isdir(folder):
        raise DumpDataError(f"{folder}: folder not found (one is needed for each dataset)")
    dumps = []
    for filename in sorted(os.listdir(folder)):
        if filename.startswith((".", "_")):
            continue
        path = os.path.join(folder, filename)
        m = DUMP_FILENAME.match(filename)
        if not m:
            raise DumpDataError(
                f"{path}: unexpected file name, dump files are named after "
                f"their release date, e.g. 2026-06-27.json"
            )
        try:
            day = date(*map(int, m.groups()))
        except ValueError:
            raise DumpDataError(f"{path}: the file name is not a valid date") from None
        dumps.append(_build_dump(path, dataset_id, day))
    if not dumps:
        raise DumpDataError(f"{folder}: no dump files found")

    dumps.sort(key=lambda d: d.date, reverse=True)
    dumps[0].latest = True
    labels = [d.label for d in dumps]
    for d in dumps:
        # the date is added only to tell apart two dumps with the same label
        name = d.label if labels.count(d.label) == 1 else f"{d.label} · {d.iso}"
        d.option_label = name + (" (latest)" if d.latest else "")
    return dumps


def load_datasets(data_dir="data"):
    """Return the datasets with their dumps, most recent first.

    Raises DumpDataError with a message pointing at the faulty file.
    """
    index_path = os.path.join(data_dir, "datasets.json")
    raw_datasets = _read_json(index_path)
    if not isinstance(raw_datasets, list) or not raw_datasets:
        raise DumpDataError(f"{index_path}: expected a non-empty list of datasets")

    datasets = []
    seen = set()
    for i, raw in enumerate(raw_datasets, 1):
        where = f"{index_path}: dataset {i}"
        _check(raw, DATASET_FIELDS, where)
        dataset_id = raw["id"]
        if not DATASET_ID.match(dataset_id):
            raise DumpDataError(f"{where}: \"id\" must be lowercase letters and digits only")
        if dataset_id in seen:
            raise DumpDataError(f"{where}: duplicate id \"{dataset_id}\"")
        seen.add(dataset_id)
        color = raw.get("color", COLORS[0])
        if color not in COLORS:
            raise DumpDataError(f"{where}: \"color\" must be one of: {', '.join(COLORS)}")

        dumps = _load_dumps(os.path.join(data_dir, dataset_id), dataset_id)
        datasets.append(SimpleNamespace(
            id=dataset_id,
            name=raw["name"].strip(),
            tagline=raw["tagline"].strip(),
            description_html=render_text(raw["description"], f"{where}: description", brand=True),
            color=color,
            dumps=dumps,
            latest=dumps[0],
        ))
    return datasets


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else os.getenv("DATA_DIR", "data")
    try:
        datasets = load_datasets(data_dir)
    except DumpDataError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for ds in datasets:
        print(f"{ds.id}: {len(ds.dumps)} dumps, latest {ds.latest.iso} "
              f"({ds.latest.file_count} files)")
    print("Dump data OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

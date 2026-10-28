"""Import explicit references only. Never infer derivation from similar text."""
from hashlib import sha256
from pathlib import Path
import json
import os
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


def index_links(catalog):
    with catalog.db() as db:
        known = {os.path.normcase(row["path"]): dict(row) for row in db.execute("SELECT id,path,hash FROM files WHERE status != 'missing'")}
        count, unresolved = 0, 0

        def local(value, parent):
            nonlocal unresolved
            text = unquote(value.split("#")[0].strip("<>"))
            if not text or len(text) > 2000:
                return None
            try:
                candidates = [Path(text)] if Path(text).is_absolute() else [parent / text] + [root / text for root in catalog.roots.values()]
                matches = {known[os.path.normcase(str(p.resolve()))]["id"]: known[os.path.normcase(str(p.resolve()))] for p in candidates if os.path.normcase(str(p.resolve())) in known}
            except (OSError, ValueError):
                return None
            if len(matches) == 1:
                return next(iter(matches.values()))
            unresolved += 1
            return None

        def external(value):
            try:
                parsed = urlsplit(value)
                if parsed.scheme not in {"https", "http"} or not parsed.hostname:
                    return None
                query = [(key, "<redacted>" if re.search(r"(?i)token|key|secret|password|signature", key) else val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)]
                host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
                uri = urlunsplit((parsed.scheme, host, parsed.path, urlencode(query), parsed.fragment))
                ident = "uri:" + sha256(uri.encode("utf-8")).hexdigest()[:24]
                db.execute("INSERT OR REPLACE INTO externals VALUES (?,?)", (ident, uri))
                return ident
            except ValueError:
                return None

        def edge(source, target, target_hash, relation, origin):
            nonlocal count
            db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?)", (source["id"], source["hash"], target, target_hash or "", relation, origin))
            count += 1

        cursor = db.execute("SELECT f.id,f.path,f.hash,b.text FROM files f JOIN blobs b ON f.hash=b.hash AND f.extractor=b.extractor WHERE f.status IN ('extracted','partial')")
        while True:
            batch = cursor.fetchmany(30)
            if not batch:
                break
            for row in batch:
                parent = Path(row["path"]).parent
                refs = re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", row["text"])
                refs += [x for x in re.findall(r"`([^`\r\n]+)`", row["text"]) if re.search(r"\.(md|pdf|json|txt|yaml|yml|docx|csv|xlsx)$", x, re.I)]
                objects = []
                if Path(row["path"]).suffix.lower() == ".json":
                    try:
                        objects = [json.loads(row["text"])]
                    except (ValueError, TypeError):
                        pass
                if objects and str(row["path"]).endswith(".prov.json") and isinstance(objects[0], dict):
                    record = objects[0]
                    primary = local(str(record.get("file", "")), parent)
                    uri = external(str(record.get("source_url", "")))
                    if primary and uri and record.get("sha256") == primary["hash"]:
                        edge(primary, uri, "", "downloaded_from", "byte_hash_matched_provenance")
                visited = 0
                while objects and visited < 10000:
                    obj = objects.pop()
                    visited += 1
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and key in {"path", "source_file", "input_path", "output_path", "file", "source_url", "url", "locator"}:
                                refs.append(value)
                            elif isinstance(value, (dict, list)):
                                objects.append(value)
                    elif isinstance(obj, list):
                        objects.extend(x for x in obj if isinstance(x, (dict, list)))
                for ref in set(refs):
                    if ref.startswith(("https://", "http://")):
                        uri = external(ref)
                        if uri:
                            edge(row, uri, "", "references", "explicit_document_reference")
                    elif not ref.startswith("#") and "://" not in ref:
                        target = local(ref, parent)
                        if target and target["id"] != row["id"]:
                            edge(row, target["id"], target["hash"], "links_to", "explicit_document_reference")
        result = {"observed_links_processed": count, "unresolved_or_ambiguous_local_refs": unresolved,
                  "inferred_links_admitted": 0}
        db.execute("INSERT OR REPLACE INTO meta VALUES ('links',?)", (json.dumps(result),))
    return result

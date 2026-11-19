"""Save byte-identical PDF payloads from the preserved download receipts."""

import hashlib
import json

from bist_analytics.config import project_root
from bist_analytics.data.originals import pdf_payload, verify_original_hashes
from bist_analytics.io import sha256, write_json


def main():
    root = project_root()
    verify_original_hashes(root)
    manifest = json.loads((root/"data/raw/fintables/originals/originals_manifest.json").read_text())
    destination = root/"output/pdf/originals"
    destination.mkdir(parents=True, exist_ok=True)
    copies = []
    for year, item in manifest["files"].items():
        payload, offset = pdf_payload((root/item["path"]).read_bytes())
        if hashlib.sha256(payload).hexdigest() != item["pdf_payload_sha256"]:
            raise ValueError(f"PDF payload hash mismatch: {year}")
        path = destination/f"THYAO_{year}_original.pdf"
        path.write_bytes(payload)
        assert sha256(path) == item["pdf_payload_sha256"]
        copies.append({"receipt": item["path"], "pdf": path.relative_to(root).as_posix(),
                       "sha256": sha256(path), "removed_envelope_bytes": offset,
                       "pdf_content_modified": False, "pages": item["pages"]})
    write_json(root/"outputs/verification/original_pdf_copies.json", {"copies": copies})
    print("Four readable copies match the original PDF payload hashes exactly.")


if __name__ == "__main__":
    main()

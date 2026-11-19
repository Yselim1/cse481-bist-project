# Post-TMS 29 original statements

These six 2025–2026 original THYAO reports were downloaded from Fintables while signed in. The primary importer also uses the previously verified FY2024 original in the neighboring `originals/` folder as its annual TTM anchor. The files retain the byte-array envelope supplied by Fintables; `pdf_payload()` validates and removes that envelope in memory without deserializing it.

The period, statement-page map, source URL, publication date, and Fintables/KAP evidence URL are fixed in `src/bist_analytics/data/tms29.py`. Running `bist import-tms29` parses both current and comparative columns, verifies accounting identities, writes the normalized observation file, and records SHA-256 hashes in `tms29_manifest.json`.

The analysis uses one accounting basis: consolidated THY/TFRS statements presented in million TRY under TMS 29. Text from KAP disclosures is kept as contextual evidence and is never used as a numerical substitute for these statements.

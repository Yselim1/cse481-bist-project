# Downloading the original Fintables reports

## Ready to download

The following links were opened from THYAO's annual statement attachment menus in the signed-in Fintables browser. These are the financial statements, not the separately listed board activity reports. The files have not been marked as downloaded or validated merely because their browser tabs opened.

| Year | Fintables attachment | Suggested local filename |
| --- | --- | --- |
| 2024 | [THY A.O. Aralık 2024.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202024.pdf) | `THYAO_2024_original.pdf` |
| 2023 | [THY A.O. Aralık 2023.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202023.pdf) | `THYAO_2023_original.pdf` |
| 2022 | [THY A.O. Aralık 2022.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202022.pdf) | `THYAO_2022_original.pdf` |
| 2021 | [THY A.O. Aralık 2021.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202021.pdf) | `THYAO_2021_original.pdf` |

## Save each file

1. Select the report's PDF tab.
2. Click the **down-arrow immediately left of the printer icon** in the PDF toolbar at the top right.
3. If a save dialog appears, paste this folder into its address bar:

   `C:\Users\yavuz\Desktop\CSE481-Term-Project\data\raw\fintables\originals`

4. Use the corresponding filename above. If the browser saves automatically to Downloads, keep its original filename and tell Codex the location; a copy can then be placed in the project without deleting the downloaded original.
5. Repeat for the other three reports. If clicking Download opens a separate browser page, use that page's normal download control. No subscription purchase or security-setting change is required by these instructions.

The FY2024 viewer displayed 101 pages. That is a useful check against accidentally downloading only a one-page notice. The browser automation API could read the displayed PDF image but refused to click inside its closed viewer component; this is why the user's download click is needed. It is not another sign-in request.

## What about 2020?

On inspection, the **2020/12 attachment menu displayed `Ek bulunamadı.` (No attachment found)**. Do not guess a 2020 URL or download an unrelated report.

The FY2021 financial statements may contain the FY2020 comparative figures needed for growth and average-balance calculations. If sufficient and comparable, those values can be used **from the FY2021 report's actual publication date onward**, with that later document recorded as their source. They cannot be backdated to the original FY2020 release. This may provide the necessary warm-up for the 2023-2025 evaluation without a standalone FY2020 PDF. Sufficiency remains to be checked after download.

## What happens after downloading?

Codex will verify each file, record its hash and source URL, extract the relevant statement lines and inspect the pages. Publication evidence must establish when the figures became public. Financial units, currency translation and comparative revisions must be reconciled before any `vintage_verified` flag changes.

Downloading a PDF alone does not validate the current historical table or its modeled dates. The existing retrospective dataset and results stay preserved while the original reports are assessed. The new source evidence will determine whether and how a verified-only rerun can proceed.

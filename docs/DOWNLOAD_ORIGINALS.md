# Downloading the original Fintables reports

## Download complete and validated

The following links were opened from THYAO's annual statement attachment menus in the signed-in Fintables browser. These are the financial statements, not the separately listed board activity reports. The user downloaded all four files into the expected folder. Their bytes, pages, tables, release dates and comparative revisions have now been validated. See `ORIGINALS_AUDIT.md`; no further download is needed for the agreed scope.

| Year | Fintables attachment | Suggested local filename |
| --- | --- | --- |
| 2024 | [THY A.O. Aralık 2024.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202024.pdf) | `THYAO_2024_original.pdf` |
| 2023 | [THY A.O. Aralık 2023.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202023.pdf) | `THYAO_2023_original.pdf` |
| 2022 | [THY A.O. Aralık 2022.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202022.pdf) | `THYAO_2022_original.pdf` |
| 2021 | [THY A.O. Aralık 2021.pdf](https://storage.fintables.com/media/uploads/kap-attachments/THY%20A.O.%20Aral%C4%B1k%202021.pdf) | `THYAO_2021_original.pdf` |

## Download procedure (retained for reference)

1. Select the report's PDF tab.
2. Click the **down-arrow immediately left of the printer icon** in the PDF toolbar at the top right.
3. If a save dialog appears, paste this folder into its address bar:

   `C:\Users\yavuz\Desktop\CSE481-Term-Project\data\raw\fintables\originals`

4. Use the corresponding filename above. If the browser saves automatically to Downloads, keep its original filename and tell Codex the location; a copy can then be placed in the project without deleting the downloaded original.
5. Repeat for the other three reports. If clicking Download opens a separate browser page, use that page's normal download control. No subscription purchase or security-setting change is required by these instructions.

The FY2024 viewer displayed 101 pages. That is a useful check against accidentally downloading only a one-page notice. The browser automation API could read the displayed PDF image but refused to click inside its closed viewer component; this is why the user's download click is needed. It is not another sign-in request.

## FY2020 comparative resolved

The FY2020 menu displayed `Ek bulunamadı.` The FY2021 original contains all required FY2020 comparative inputs. They are imported with the FY2021 release date of 1 March 2022 and usable from 2 March, not backdated to an assumed FY2020 release. This is sufficient warm-up for the 2023-2025 annual study.

## Audit result

All four receipts are preserved in `data/raw/fintables/originals/`. Their page counts are 98, 99, 101 and 101. Open the standard PDF copies in `output/pdf/originals/`: these remove only the 27-byte download wrapper and match the original PDF payload hashes exactly. The source audit records 136 observations, zero assumed release dates and 40 exact statement reconciliations. Original statements use TRY presentation. The earlier USD table dataset and results remain separate. See `ORIGINALS_AUDIT.md` and `WALKTHROUGH.md` for the completed import and implementation.

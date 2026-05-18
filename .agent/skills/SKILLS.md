---
name: report-google-sheet-telegram
description: Automatically process posts from Google Sheet, generate content, require Codex to create real images based on the topic, save them into the images folder, and only then send the result via Telegram.
---

# Skill: Process Google Sheet Posts and Send Telegram Notifications

This skill describes a workflow using Python + Google Sheets + Codex + Telegram to process post data from a sheet. The script does not post to Facebook. The agent finds rows that need processing, generates content if missing, must use Codex to create images if missing, saves real image files into `images/`, and only then sends the result through Telegram.

Codex-only image rule

If an image is missing, the real image file must be created only by Codex image generation. The agent must not create the image by Python code, PIL, canvas drawing, SVG generation, HTML screenshot, placeholder file creation, downloading from external sources, or any non-Codex fallback.

Important

All paths must use relative paths so the project can be moved to another machine and still run correctly. Do not use absolute paths such as `C:\...`, `D:\...`, or `F:\...`.

---

## 1. Goal

- Connect to Google Sheet.
- Find rows where `Status = PD`.
- Only process rows that contain data in the `Nội Dung` column.
- Before generating anything, the agent must first check the current Google Sheet values for `Tiêu Đề` and `Hình ảnh` on that row.
- If `Tiêu Đề` is missing, the script generates post content and writes it back to the sheet.
- In the same workflow turn as content generation, a real image is mandatory. If `Hình ảnh` is missing, the script generates an image filename and writes it back to the sheet, then the agent must create the real image file for that filename in `images/` before Telegram is allowed.
- If the real image file does not exist yet, the agent must use Codex to generate an image based on the topic and save it into `images/`. This is a required continuation of the same content-generation task, not an optional follow-up. The image must be created by Codex only, not by Python, PIL, scripts, manual placeholder assets, downloaded stock images, or skipped assets.
- Telegram results may only be sent after both content and a real image exist in `images/`.
- Do not post to Facebook.
- After processing succeeds and Telegram is sent, update `Status` to `POSTED`.

---

## 2. `.env` Configuration

The script reads the following variables from the `.env` file:

- `SHEET_ID`
- `WORKSHEET_NAME`
- `GOOGLE_CREDENTIALS_FILE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Example:

```env
SHEET_ID=your_google_sheet_id
WORKSHEET_NAME=fanpage_tvhpt
GOOGLE_CREDENTIALS_FILE=gen-lang-client-0450618162-54ea7d476a02.json
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

`GOOGLE_CREDENTIALS_FILE` must be a filename or a relative path from the project root.

Before running the workflow, the agent must:

1. Check whether `.env` exists in the project root.
2. If it does not exist, copy `.env.example` to `.env`.
3. Then verify that the following required variables have been filled in inside `.env`:
   - `SHEET_ID`
   - `WORKSHEET_NAME`
   - `GOOGLE_CREDENTIALS_FILE`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. The workflow must not continue if the values are still placeholders or have not been updated, for example:

```env
SHEET_ID=SheetID
WORKSHEET_NAME=sheetName
GOOGLE_CREDENTIALS_FILE=gen-lang-client.....json
TELEGRAM_BOT_TOKEN=Token
TELEGRAM_CHAT_ID=chatID
```

5. The agent must clearly report which variables are missing or still using placeholders so the user can fix them before running the workflow.

---

## 3. Input Data in Google Sheet

Main columns:

| Column | Meaning |
|-----|---------|
| `Tiêu Đề` | Final post content |
| `Nội Dung` | Topic or source keyword |
| `Hình ảnh` | Image filename to find or create in `images/` |
| `Status` | Processing status, the script only picks rows with `PD` |

If an older sheet uses unaccented column names such as `Tieu De`, `Noi Dung`, `Hinh anh`, the agent must still support compatible reading.

---

## 4. Standard Processing Flow

1. The script connects to Google Sheet using `SHEET_ID`.
2. The script opens the worksheet using `WORKSHEET_NAME`.
3. The script scans each row and only selects rows where:
   - `Status = PD`
   - the `Nội Dung` column contains data
   - before generating anything, the script or agent must first read the current values of `Tiêu Đề` and `Hình ảnh` from Google Sheet
   - if `Tiêu Đề` already has content, it must not be regenerated or overwritten
   - if `Hình ảnh` already has a filename, it must not generate a new filename or overwrite that cell
   - the row is still processed even if `Tiêu Đề` and `Hình ảnh` already exist, so the script can verify the real image file and send Telegram `SUCCESS`
4. If `Tiêu Đề` is empty:
   - the script generates post content from `Nội Dung`
   - writes it back into the `Tiêu Đề` column
5. If `Hình ảnh` is empty:
   - the script generates an image filename, for example `hoc-machine-learning.png`
   - writes it back into the `Hình ảnh` column
6. The script checks whether the image file already exists in `images/`.
7. If the image does not exist:
   - the agent must use Codex to generate an image matching that row's topic
   - save the image as `images/<filename>.png`
   - the image must be produced by Codex image generation only
   - the agent must not generate the image by writing code that draws or exports an image file
   - the agent must not use PIL, Pillow, OpenCV, matplotlib, cairo, SVG export, browser screenshot, or any similar fallback
   - the agent must not create a dummy file just to satisfy the existence check
   - this image creation must happen in the same workflow turn that generated the content or filename
   - it must not stop at filename generation
   - it must not only return an instruction
   - it must not skip the real image creation step
   - it must not ask the user whether to create the image
8. Only when the real image file exists in `images/`:
   - Telegram may send `SUCCESS`
   - `Status` must be updated to `POSTED`
9. If the real image does not exist yet:
   - Telegram must not be sent
   - `Status` must not be changed to `ERROR`
   - the image must be created first before continuing to the notification step
10. If a real error occurs during processing:
   - Telegram sends `FAILED`
   - only update `Status` if the workflow explicitly requires it

Summary:

```text
Status = PD -> check Nội Dung -> generate Tiêu Đề if missing -> generate image filename if missing -> if image does not exist then use Codex to create image in the same workflow turn -> save the real image into images -> rerun the copied root script -> send Telegram SUCCESS -> update Status to POSTED
```

---

## 5. Mandatory Rules

- Do not post to Facebook.
- Only use the `images/` folder in the project root.
- Do not use absolute paths.
- A `.env` file in the project root is mandatory. If missing, it must be copied from `.env.example` before any other step.
- The agent must verify all 5 variables `SHEET_ID`, `WORKSHEET_NAME`, `GOOGLE_CREDENTIALS_FILE`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` inside `.env`.
- The workflow must not run if `.env` still contains placeholder values such as `SheetID`, `sheetName`, `gen-lang-client.....json`, `Token`, or `chatID`.
- Before creating content or images, the agent must check Google Sheet first and read the current values in `Tiêu Đề` and `Hình ảnh`.
- The agent must only generate `Tiêu Đề` when that cell is still empty.
- The agent must only generate the `Hình ảnh` filename when that cell is still empty.
- If `Tiêu Đề` or `Hình ảnh` already contains a value in Google Sheet, the agent must keep the existing value and continue the workflow without overwriting that cell.
- The file `.agent/skills/scripts/google_sheet_telegram_report.py` must always be copied to the project root as `google_sheet_telegram_report.py` before running, even if a root copy already exists. Use `Copy-Item ... -Force` so the root script is always refreshed from the skill script.
- After copying, all workflow execution must operate on the copied root script `.\google_sheet_telegram_report.py`. Do not run the script directly from `.agent/skills/scripts/` during the workflow.
- Do not ask the user to open code to edit `SHEET_ID`, `WORKSHEET_NAME`, `GOOGLE_CREDENTIALS_FILE`, or Telegram config.
- All configuration must be stored in `.env`.
- When content is generated for a row, a real image for that same row is mandatory in the same workflow turn.
- When an image is missing, the agent must use Codex to create a real image immediately, not stop at only generating the filename. The generated file must be a real project asset saved under `images/`.
- When an image is missing, the only allowed way to create that image is Codex image generation.
- The agent must not use Python code, PIL/Pillow, local scripts, SVG renderers, screenshots, external download tools, or hand-made placeholder files to create or fake the required image.
- The workflow must not stop after only generating a prompt or instruction. It is only considered complete when the real image file exists in `images/`.
- The agent must not ask the user whether it should create the image, continue the workflow, rerun the script, or send Telegram after the image is created. Those actions are mandatory and automatic.
- The agent must not ask for confirmation with phrases such as "náº¿u báº¡n muá»‘n", "tÃ´i cÃ³ thá»ƒ táº¡o áº£nh", "báº¡n cÃ³ muá»‘n tÃ´i tiáº¿p tá»¥c", or any equivalent follow-up when the workflow is already blocked only by a missing image.
- Missing image is an execution step, not a decision point. The correct behavior is to create the real image immediately, save it into `images/`, rerun the copied root script, and finish the workflow in the same turn.
- If Codex image generation is unavailable or fails hard, the agent must stop and report that specific Codex image-generation failure. It must not silently switch to another image-creation method.
- The agent must not end its final answer while the row is still waiting for image creation if image generation is available in the current environment.
- The only acceptable reasons to stop and ask the user are missing `.env` values, placeholder configuration, missing credentials file, or a hard tool/runtime failure that prevents image creation or rerun.
- Telegram may only be sent after the real image file has been created and saved correctly inside `images/`.
- After Telegram `SUCCESS` is sent for a completed row, the script must update that row's `Status` to `POSTED`.
- Missing image is not a normal failure state. Do not send Telegram `FAILED` and do not change `Status` to `ERROR` only because the image file is missing; create the image and continue.
- Do not use `venv` in the run instructions for this skill. It must run with the machine's real Python environment.
- If the machine is missing required libraries, they must be installed into the real Python environment before running.

---

## 6. Telegram

The script sends Telegram notifications using:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Telegram messages include:

- status `SUCCESS` or `FAILED`
- sheet row number
- `Nội Dung`
- `Tiêu Đề`
- `Hình ảnh`
- error details or success details

---

## 7. How to Run

You must use the machine's real Python environment.

The agent must first copy the skill script to the project root. This copy step is mandatory every time before running the workflow:

```powershell
Copy-Item .\.agent\skills\scripts\google_sheet_telegram_report.py .\google_sheet_telegram_report.py -Force
```

After the script file has been copied to the same level as `.env`, run the root copy. All later reruns in the same workflow must also use this copied root file:

```powershell
python .\google_sheet_telegram_report.py
```

Do not use:

```powershell
.\venv\Scripts\python.exe ...
```

If any libraries are missing, install them into the real Python environment before running:

```powershell
pip install gspread requests python-dotenv google-auth
```

The agent must check dependencies before running. If anything is missing, install it into the system Python first and then continue the workflow.

---

## 8. Expected Agent Behavior

When the user asks to run this workflow, the agent must:

1. Check the `.env` file in the project root.
2. If `.env` is missing, copy it from `.env.example`.
3. Verify that the 5 variables `SHEET_ID`, `WORKSHEET_NAME`, `GOOGLE_CREDENTIALS_FILE`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` contain real values and are not placeholders. If they are missing, the agent must ask the user to fill them in.
4. Always copy `.agent/skills/scripts/google_sheet_telegram_report.py` to `.\google_sheet_telegram_report.py` with `Copy-Item ... -Force` before running, so the root script is in the same directory level as `.env` and is refreshed from the skill script every time.
5. After the copy step, run and rerun only `.\google_sheet_telegram_report.py` for the workflow. Do not execute `.agent/skills/scripts/google_sheet_telegram_report.py` directly.
6. Check Google Sheet.
7. Find rows where `Status = PD`.
8. Read the current row values first and check whether `Tiêu Đề` and `Hình ảnh` are empty or already filled.
9. Generate `Tiêu Đề` only if that cell is empty.
10. Generate the image filename only if that cell is empty.
11. If the image is missing, the agent must use Codex to create a real image for the topic immediately in the same workflow turn.
12. The agent must do this automatically without asking the user for permission to create the image or continue the workflow.
13. Save the Codex-created image into the `images/` folder.
14. The agent must not replace this step with Python/PIL drawing code, generated placeholders, downloaded files, screenshots, or any non-Codex fallback.
15. Run the copied root script again after the image exists so the workflow can verify the file and send Telegram.
16. Only after the real image exists may Telegram send the result.
17. After Telegram `SUCCESS`, the script must update the processed row's `Status` to `POSTED`.
18. The workflow is not complete until the rerun has happened, Telegram has been sent successfully, and `Status` has been changed to `POSTED`, unless a real blocking error occurs.
19. If dependencies are missing, install them into the real Python environment before running.
20. Do not post to Facebook.

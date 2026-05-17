import os
import re
import sys
import unicodedata

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve_project_root() -> str:
    current_dir = SCRIPT_DIR
    for candidate in [current_dir, *[os.path.dirname(current_dir) for _ in range(3)]]:
        if os.path.exists(os.path.join(candidate, ".env")):
            return candidate
        current_dir = os.path.dirname(current_dir)
    return SCRIPT_DIR


PROJECT_ROOT = resolve_project_root()
IMAGE_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "images")

SHEET_ID = os.getenv("SHEET_ID", "").strip()
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "").strip()
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "").strip()
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, GOOGLE_CREDENTIALS_FILE) if GOOGLE_CREDENTIALS_FILE else ""
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

IMAGE_DIRS = [IMAGE_OUTPUT_DIR]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


class MissingImageError(RuntimeError):
    pass


def clean_cell(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def normalize_text(value: object) -> str:
    text = clean_cell(value)
    normalized = unicodedata.normalize("NFKD", text)
    no_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", no_accents.lower())


def slugify_filename(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "post-image"


def build_post_content(keyword: str) -> str:
    keyword = clean_cell(keyword)
    upper_keyword = keyword.upper()
    return (
        f"🚀 {upper_keyword}: HỌC NHANH HƠN, LÀM THẬT SỚM HƠN!\n\n"
        f"Bạn đang quan tâm đến {keyword} nhưng chưa biết bắt đầu từ đâu? "
        "Đây là thời điểm phù hợp để học đúng lộ trình, thực hành đúng cách và ứng dụng ngay vào công việc thực tế.\n\n"
        f"💡 Vì sao {keyword} đang được nhiều người chọn học?\n"
        "- Tự động hóa quy trình, giảm việc lặp lại thủ công\n"
        "- Kết nối dữ liệu giữa nhiều công cụ như Google Sheets, Telegram, CRM và AI\n"
        "- Giúp xử lý công việc nhanh hơn mà vẫn giảm lỗi thao tác\n"
        "- Phù hợp cho người làm vận hành, marketing, bán hàng và cả kỹ thuật\n\n"
        "📚 Nếu bạn là người mới:\n"
        "- Bắt đầu từ các workflow đơn giản, dễ thấy kết quả\n"
        "- Học cách kích hoạt tự động bằng form, sheet, webhook hoặc lịch chạy\n"
        "- Thực hành bằng case thật trong công việc hằng ngày\n"
        "- Tối ưu dần để quy trình chạy ổn định và tiết kiệm thời gian hơn\n\n"
        f"🔥 Khi học đúng cách, {keyword} không chỉ là một kỹ năng mới mà còn là lợi thế giúp bạn làm việc thông minh hơn, nhanh hơn và có hệ thống hơn.\n\n"
        f"👇 Comment “{keyword}” nếu bạn muốn mình chia sẻ lộ trình học từ cơ bản đến ứng dụng thực chiến nhé!"
    )


def get_row_value(row: dict, *candidates: str) -> str:
    normalized_row = {normalize_text(key): value for key, value in row.items()}
    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate in normalized_row:
            return clean_cell(normalized_row[normalized_candidate])
    return ""


def build_codex_image_instruction(keyword: str, tieu_de: str, image_name: str) -> str:
    topic = clean_cell(keyword)
    caption = clean_cell(tieu_de)
    return (
        f"Codex can tao anh cho chu de '{topic}' va luu thanh images/{image_name}. "
        f"Noi dung bai viet de tham khao: {caption}"
    )


def require_existing_image(keyword: str, tieu_de: str, image_name: str) -> str:
    existing_path = find_image_path(image_name)
    if existing_path:
        return existing_path

    raise MissingImageError(build_codex_image_instruction(keyword, tieu_de, image_name))


def find_image_path(img_name: str) -> str:
    if not img_name:
        return ""

    if os.path.exists(img_name):
        return img_name

    possible_exts = ["", ".jpg", ".png", ".jpeg", ".webp"]
    for directory in IMAGE_DIRS:
        if not os.path.exists(directory):
            continue
        for ext in possible_exts:
            candidate = os.path.join(directory, img_name + ext)
            if os.path.exists(candidate):
                return candidate
    return ""


def ensure_column(worksheet, headers: list[str], names: list[str]) -> tuple[list[str], int]:
    for name in names:
        if name in headers:
            return headers, headers.index(name) + 1

    worksheet.update_cell(1, len(headers) + 1, names[0])
    headers = worksheet.row_values(1)
    return headers, headers.index(names[0]) + 1


def should_process_post(status: str, noi_dung: str, tieu_de: str, hinh_anh: str) -> bool:
    return clean_cell(status).upper() == "PD" and bool(clean_cell(noi_dung))


def send_telegram_message(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID, bo qua gui Telegram.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }
    response = requests.post(url, json=payload, timeout=30)
    if not response.ok:
        raise RuntimeError(f"Loi gui Telegram: {response.text}")


def build_telegram_message(
    status: str, row_num: int, noi_dung: str, tieu_de: str, hinh_anh: str, detail: str
) -> str:
    return (
        f"[{status}] Google Sheet row {row_num}\n"
        f"Noi dung goc: {noi_dung}\n"
        f"Tieu de: {tieu_de or '(trong)'}\n"
        f"Hinh anh: {hinh_anh or '(trong)'}\n"
        f"Chi tiet: {detail}"
    )


def validate_required_settings() -> None:
    missing_settings = []
    if not SHEET_ID:
        missing_settings.append("SHEET_ID")
    if not WORKSHEET_NAME:
        missing_settings.append("WORKSHEET_NAME")
    if not GOOGLE_CREDENTIALS_FILE:
        missing_settings.append("GOOGLE_CREDENTIALS_FILE")

    if missing_settings:
        raise RuntimeError(f"Thieu cau hinh trong .env: {', '.join(missing_settings)}")

    if not os.path.exists(CREDENTIALS_FILE):
        raise RuntimeError(f"Khong tim thay file credentials: {GOOGLE_CREDENTIALS_FILE}")


def main() -> None:
    print("==========================================================")
    print("VAN HANH XU LY GOOGLE SHEET + THONG BAO TELEGRAM")
    print("==========================================================")
    print("Dang ket noi toi Google Sheet...")

    try:
        validate_required_settings()
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        workbook = gc.open_by_key(SHEET_ID)

        try:
            worksheet = workbook.worksheet(WORKSHEET_NAME)
        except Exception:
            print(f"Khong tim thay tab '{WORKSHEET_NAME}', dang dung tab dau tien...")
            worksheet = workbook.sheet1

        records = worksheet.get_all_records()
        headers = worksheet.row_values(1)

        headers, tieu_de_col = ensure_column(worksheet, headers, ["Tiêu Đề", "Tieu De"])
        headers, _ = ensure_column(worksheet, headers, ["Nội Dung", "Noi Dung"])
        headers, hinh_anh_col = ensure_column(worksheet, headers, ["Hình ảnh", "Hinh anh", "Images"])
        headers, status_col = ensure_column(worksheet, headers, ["Status"])

        os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)

        print(f"Da tai {len(records)} dong trang thai tu Google Sheet.")

        for idx, row in enumerate(records):
            row_num = idx + 2
            noi_dung = get_row_value(row, "Nội Dung", "Noi Dung")
            tieu_de = get_row_value(row, "Tiêu Đề", "Tieu De")
            hinh_anh = get_row_value(row, "Hình ảnh", "Hinh anh", "Images")
            status = get_row_value(row, "Status").upper()

            if not should_process_post(status, noi_dung, tieu_de, hinh_anh):
                continue

            print(f"\n=> Dang xu ly dong {row_num} - Noi dung goc: {noi_dung[:60]}...")

            try:
                if not tieu_de:
                    tieu_de = build_post_content(noi_dung)
                    worksheet.update_cell(row_num, tieu_de_col, tieu_de)
                    print("Da sinh noi dung bai dang va luu vao cot 'Tiêu Đề'.")

                if not hinh_anh:
                    hinh_anh = f"{slugify_filename(noi_dung)}.png"
                    worksheet.update_cell(row_num, hinh_anh_col, hinh_anh)
                    print(f"Da luu ten file anh du kien vao sheet: {hinh_anh}")

                real_image_path = require_existing_image(noi_dung, tieu_de, hinh_anh)
                print(f"Anh san sang tai: {real_image_path}")

                detail = f"Xu ly thanh cong. Anh tim thay tai: {real_image_path}"
                send_telegram_message(
                    build_telegram_message("SUCCESS", row_num, noi_dung, tieu_de, hinh_anh, detail)
                )
                print("Da gui Telegram thanh cong.")
                print(f"Giu nguyen trang thai tren dong {row_num} de nguoi dung tu xu ly.")
                print("\n--- HOAN TAT XU LY 1 DONG ---")
                break

            except MissingImageError as image_exc:
                print(f"Can tao anh that truoc khi gui Telegram: {image_exc}")
                print(f"Giu nguyen trang thai dong {row_num}; agent phai tao anh vao images/ roi chay lai workflow.")
                break

            except Exception as row_exc:
                detail = str(row_exc)
                try:
                    send_telegram_message(
                        build_telegram_message("FAILED", row_num, noi_dung, tieu_de, hinh_anh, detail)
                    )
                except Exception as telegram_exc:
                    print(f"Gui Telegram loi: {telegram_exc}")
                worksheet.update_cell(row_num, status_col, "ERROR")
                print(f"Loi xu ly dong {row_num}: {row_exc}")
                break

    except Exception as exc:
        print(f"Loi cau hinh tai Sheet/API he thong: {exc}")


if __name__ == "__main__":
    main()

"""
task1_prepare_data.py
=====================
Chuẩn hóa và phân đoạn dữ liệu — KHÔNG phụ thuộc embedding model.
task1 chỉ tạo chunk text, việc embed là của task2.

CHIẾN LƯỢC CHUNKING:

━━ NGUỒN A: SẢN PHẨM (products_final.json) ━━━━━━━━━━━━━━━━━
  1 sản phẩm = 4 chunk:
  [1] name_only      : tên + danh mục (match chính xác khi query tên sp)
  [2] identity_price : tên + danh mục + tags + giá gốc + giá sale + % giảm
  [3] physical       : tên + chất liệu + kích thước
  [4] description    : tên + full_description (hoặc summary)

━━ NGUỒN B: FILE .md trong data/ ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tự detect heading level (#, ##, ###) cho từng file
  RecursiveCharacterTextSplitter: chunk_size=400, overlap=100
  Thêm file .md vào data/ → tự động đọc, không cần sửa code

Cài thư viện:
  pip install langchain langchain-text-splitters
"""

import json
import re
import os
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ─────────────────────────────────────────────────────────────
# ĐƯỜNG DẪN
# ─────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__)) # thư mục hiện tại của script
DATA_DIR     = os.path.join(BASE_DIR, "data") # thư mục data chứa products_final.json và các file .md
PRODUCT_FILE = os.path.join(DATA_DIR, "products_final.json") # file JSON sản phẩm

# ─────────────────────────────────────────────────────────────
# THAM SỐ CHUNKING CHÍNH SÁCH
# ─────────────────────────────────────────────────────────────
POLICY_CHUNK_SIZE    = 400
POLICY_CHUNK_OVERLAP = 100


# ═════════════════════════════════════════════════════════════
# NGUỒN A — SẢN PHẨM
# ═════════════════════════════════════════════════════════════

def format_price(value) -> str:
    """3990000 → '3.990.000đ'"""
    try:
        return f"{int(float(value)):,}đ".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def calc_discount(original, sale) -> str:
    """Tính % giảm giá, trả về '' nếu không có."""
    try:
        orig = float(original)
        sal  = float(sale)
        if orig > sal > 0:
            pct = round((orig - sal) / orig * 100)
            return f"giảm {pct}%"
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    return ""


def build_product_chunks(p: dict) -> list[dict]:
    """
    Nhận 1 dict sản phẩm, trả về 4 chunk.

    Lý do có chunk name_only:
      BGE-M3 rất giỏi semantic search nhưng khi query chứa tên model cụ thể
      ("oslo 901", "hobro 301"), chunk ngắn chỉ chứa tên sẽ có cosine
      cao nhất → đảm bảo đúng sản phẩm được kéo lên top.
    """
    product_id     = p.get("product_id", "unknown")
    category_name  = p.get("category", {}).get("name", "")
    content        = p.get("content", {})
    ai_meta        = p.get("ai_metadata", {})

    name           = content.get("name", "")
    price_original = content.get("price_original", 0) 
    price_sale     = content.get("price_sale", 0)
    material       = content.get("material", "")
    size           = content.get("size", "").strip()
    summary        = content.get("summary", "")
    full_desc      = ai_meta.get("full_description", "") or summary
    tags           = ai_meta.get("tags", [])

    shared_meta = {
        "product_id":     product_id,
        "name":           name,
        "category":       category_name,
        "price_sale":     price_sale,
        "price_original": price_original,
    }

    chunks = []

    # ── [1] NAME ONLY ──────────────────────────────────────────
    chunks.append({
        "content_type": "product",
        "chunk_type":   "name_only",
        "raw_text":     f"Sản phẩm: {name} | Danh mục: {category_name}",
        "metadata":     shared_meta,
    })

    # ── [2] ĐỊNH DANH + GIÁ ────────────────────────────────────
    tag_str      = ", ".join(tags) if tags else ""
    discount_str = calc_discount(price_original, price_sale)
    price_line   = f"Giá bán: {format_price(price_sale)}"
    if discount_str:
        price_line += f" ({discount_str} từ {format_price(price_original)})"

    parts = [f"Sản phẩm: {name}", f"Danh mục: {category_name}"]
    if tag_str:
        parts.append(f"Từ khóa: {tag_str}")
    parts.append(price_line)

    chunks.append({
        "content_type": "product",
        "chunk_type":   "identity_price",
        "raw_text":     " | ".join(parts),
        "metadata":     shared_meta,
    })

    # ── [3] VẬT LÝ ────────────────────────────────────────────
    phys_parts = [f"Sản phẩm: {name}"]
    if material:
        phys_parts.append(f"Chất liệu: {material}")
    if size:
        phys_parts.append(f"Kích thước: {size}")

    if len(phys_parts) > 1: # Nếu chỉ có tên mà không có thông tin vật lý nào khác thì thôi, không tạo chunk này
        chunks.append({
            "content_type": "product",
            "chunk_type":   "physical",
            "raw_text":     " | ".join(phys_parts),
            "metadata":     shared_meta,
        })

    # ── [4] MÔ TẢ ─────────────────────────────────────────────
    if full_desc:
        chunks.append({
            "content_type": "product",
            "chunk_type":   "description",
            "raw_text":     f"Sản phẩm: {name}\n{full_desc}",
            "metadata":     shared_meta,
        })

    return chunks


def load_product_chunks(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        products = json.load(f)

    all_chunks = []
    for p in products:
        all_chunks.extend(build_product_chunks(p))

    n   = len(products)
    avg = len(all_chunks) // n if n else 0
    print(f"[Nguồn A] {n} sản phẩm → {len(all_chunks)} chunk (~{avg} chunk/sp).")
    return all_chunks


# ═════════════════════════════════════════════════════════════
# NGUỒN B — FILE .md
# ═════════════════════════════════════════════════════════════

def clean_markdown(text: str) -> str:
    """Làm sạch Markdown, convert bảng thành text đọc được. 
    Bỏ các ký tự định dạng #, **, *."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    # Bỏ dòng kẻ bảng
    text = re.sub(r"^\|[\s\-:\|]+\|$", "", text, flags=re.MULTILINE)
    # Convert hàng bảng "| A | B |" → "A: B"
    def table_row(m): # m.group(0) là dòng bảng, split theo | rồi join lại
        cells = [c.strip() for c in m.group(0).split("|") if c.strip()]
        if len(cells) == 2:
            return f"{cells[0]}: {cells[1]}"
        return " - ".join(cells) if cells else ""
    text = re.sub(r"^\|.+\|$", table_row, text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_heading_level(raw_markdown: str) -> str:
    """Phát hiện cấp heading: 'sub' (##/###), 'top' (#), 'none'."""
    if re.search(r"^#{2,3}\s+.+", raw_markdown, re.MULTILINE):
        return "sub"
    if re.search(r"^#\s+.+", raw_markdown, re.MULTILINE):
        return "top"
    return "none"

# Việc này đảm bảo một "đoạn văn" không bị cắt ngang xương, giữ trọn vẹn ngữ cảnh của một mục 
# (ví dụ: toàn bộ thông tin "Quy định bảo hành" nằm trong một khối).
def split_by_heading(raw_markdown: str, filename: str = "") -> list[dict]:
    """Tách Markdown theo heading, tự detect cấp #/##{/###}."""
    level = detect_heading_level(raw_markdown)

    if level == "sub":
        pattern = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
    elif level == "top":
        pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    else:
        title = os.path.splitext(filename)[0] if filename else "Nội dung"
        return [{"title": title, "body": raw_markdown}]

    matches  = list(pattern.finditer(raw_markdown))
    sections = []

    if matches and matches[0].start() > 0:
        preamble = raw_markdown[:matches[0].start()].strip()
        if preamble:
            fname = os.path.splitext(filename)[0] if filename else "Tổng quan"
            sections.append({"title": fname, "body": preamble})

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(raw_markdown)
        body  = raw_markdown[start:end].strip()
        if body:
            sections.append({"title": title, "body": body})

    return sections if sections else [{"title": "Nội dung", "body": raw_markdown}]


"""Nếu một mục sau khi tách ở Bước 2 vẫn còn quá dài (trên 400 ký tự), thư viện LangChain sẽ nhảy vào:

Sử dụng RecursiveCharacterTextSplitter để cắt nhỏ hơn dựa trên các dấu ngắt tự nhiên như xuống dòng, dấu chấm, dấu phẩy.
Overlap (100 ký tự): Đoạn sau sẽ chứa một phần đoạn trước để tránh mất ngữ cảnh ở điểm cắt."""
def load_md_file_chunks( # Cắt nhỏ lần 2 (Recursive Character Splitter)
    filepath: str,
    splitter: RecursiveCharacterTextSplitter
) -> list[dict]:
    filename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        raw_md = f.read()

    heading_level = detect_heading_level(raw_md)
    sections      = split_by_heading(raw_md, filename)
    chunks        = []
    chunk_idx     = 0

    for section in sections:
        title      = section["title"]
        body_clean = clean_markdown(section["body"])
        if not body_clean:
            continue

        full_text = f"{title}\n{body_clean}"
        sub_docs  = splitter.create_documents(
            [full_text],
            metadatas=[{"section": title, "source": filename}]
        )

        for sub_doc in sub_docs:
            sub_text = sub_doc.page_content.strip()
            if not sub_text:
                continue
            if not sub_text.startswith(title):
                sub_text = f"{title}\n{sub_text}"

            chunks.append({
                "content_type": "policy",
                "chunk_type":   "heading_section" if len(full_text) <= POLICY_CHUNK_SIZE
                                else "recursive_sub",
                "raw_text":     sub_text,
                "metadata": {
                    "chunk_index":   chunk_idx,
                    "section":       title,
                    "source":        filename,
                    "heading_level": heading_level,
                    "chunk_size":    POLICY_CHUNK_SIZE,
                    "chunk_overlap": POLICY_CHUNK_OVERLAP,
                }
            })
            chunk_idx += 1

    return chunks
"""
Một điểm cực kỳ quan trọng trong code là mỗi chunk được gắn kèm Metadata:
Với sản phẩm: Lưu product_id, price, category.
Với chính sách: Lưu source (tên file), section (tên mục).
Tác dụng: Sau này khi AI tìm thấy một chunk, nó có thể dùng metadata này để truy xuất ngược lại toàn bộ thông tin sản phẩm hoặc dẫn nguồn link file cho khách hàng.
"""




def load_all_md_chunks(data_dir: str) -> list[dict]: # Tìm tất cả file .md trong data/, tách chunk, gắn metadata
    md_files = sorted(glob.glob(os.path.join(data_dir, "*.md")))
    if not md_files:
        print("[Nguồn B] Không tìm thấy file .md!")
        return []

    print(f"[Nguồn B] Tìm thấy {len(md_files)} file .md:")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=POLICY_CHUNK_SIZE,
        chunk_overlap=POLICY_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", ",", " "],
        length_function=len,
        keep_separator=False,
    )

    all_chunks = []
    for filepath in md_files:
        filename = os.path.basename(filepath)
        chunks   = load_md_file_chunks(filepath, splitter)
        all_chunks.extend(chunks)
        level = chunks[0]["metadata"]["heading_level"] if chunks else "?"
        print(f"  [{filename}] heading={level} → {len(chunks)} chunk")

    print(f"[Nguồn B] Tổng: {len(all_chunks)} chunk "
          f"(size={POLICY_CHUNK_SIZE}, overlap={POLICY_CHUNK_OVERLAP})")
    return all_chunks


# ═════════════════════════════════════════════════════════════
# HÀM TỔNG HỢP
# ═════════════════════════════════════════════════════════════

def prepare_all_chunks() -> list[dict]: # Tải và chuẩn hóa tất cả chunk từ cả 2 nguồn, trả về một list duy nhất.
    product_chunks = load_product_chunks(PRODUCT_FILE)
    policy_chunks  = load_all_md_chunks(DATA_DIR)
    all_chunks     = product_chunks + policy_chunks
    print(f"\n[Tổng] {len(all_chunks)} chunk sẵn sàng để embedding.")
    return all_chunks


# ─────────────────────────────────────────────────────────────
# CHẠY THỬ ĐỘC LẬP
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    all_chunks = prepare_all_chunks()

    print("\n" + "="*60)
    print("VÍ DỤ: 4 chunk của sản phẩm đầu tiên")
    print("="*60)
    prod_chunks = [c for c in all_chunks if c["content_type"] == "product"]
    if prod_chunks:
        first_id = prod_chunks[0]["metadata"]["product_id"]
        for c in prod_chunks:
            if c["metadata"]["product_id"] == first_id:
                print(f"\n  [chunk_type: {c['chunk_type']}]")
                print(f"  {c['raw_text'][:200]}")

    print("\n" + "="*60)
    print("THỐNG KÊ CHUNK THEO FILE .md")
    print("="*60)
    pol_chunks = [c for c in all_chunks if c["content_type"] == "policy"]
    by_source: dict[str, list] = {}
    for c in pol_chunks:
        src = c["metadata"].get("source", "unknown")
        by_source.setdefault(src, []).append(c)
    for src, clist in by_source.items():
        level = clist[0]["metadata"].get("heading_level", "?")
        print(f"\n  [{src}] heading={level} — {len(clist)} chunk")
        for c in clist[:2]:
            n = len(c["raw_text"])
            print(f"    {c['metadata']['section']!r}  {n} ký tự")
            print(f"    {c['raw_text'][:100]}" + ("..." if n > 100 else ""))









"""Với file Markdown bạn cung cấp, code sẽ xử lý qua các bước "phẫu thuật" dữ liệu
như sau:

Bước 1: Phát hiện cấp độ (Hàm detect_heading_level)

Code quét nội dung và thấy có các ký tự ## (Heading 2).

  - Kết quả: Xác định đây là file có cấu trúc phân mục (level = "sub").

Bước 2: Tách đoạn theo tiêu đề (Hàm split_by_heading)

Code dùng Regex để cắt file thành các phần độc lập dựa trên dấu ##. Dựa trên
file của bạn, nó sẽ chia thành 5 phần:

1.  Phần Tiền đề (Preamble): Tiêu đề H1 ban đầu.
2.  Phần 1: "Thời gian bảo hành chi tiết cho từng dòng hàng"
3.  Phần 2: "Điều kiện để được chấp nhận bảo hành"
4.  Phần 3: "Các trường hợp từ chối bảo hành"
5.  Phần 4: "Quy trình yêu cầu bảo hành"

Bước 3: Làm sạch nội dung (Hàm clean_markdown)

Trong mỗi phần, code sẽ xóa bỏ các ký tự thừa để AI đọc "mượt" hơn:

  - Bỏ dấu ** (in đậm).
  - Bỏ các dấu gạch đầu dòng - hoặc giữ lại tùy cấu trúc.
  - Ví dụ: Dòng - **Khung xương gỗ chính:** ...
      - Thành: Khung xương gỗ chính: Đối với các sản phẩm gỗ tự nhiên...

Bước 4: Cắt nhỏ theo kích thước (Hàm load_md_file_chunks)

Đây là bước quan trọng nhất. Giả sử POLICY_CHUNK_SIZE = 400 ký tự.

  - Xét "Phần 1: Thời gian bảo hành...": Đoạn này khá dài (khoảng 550 ký tự).
    Vì 550 > 400, nên RecursiveCharacterTextSplitter sẽ chia nó làm 2 chunk:

      - Chunk 1.1: Chứa tiêu đề + 3 dòng đầu tiên về bảo hành gỗ.
      - Chunk 1.2: Chứa tiêu đề (được code tự động lặp lại) + các dòng về phụ
        kiện (có chồng lấp overlap một chút với đoạn trên).

  - Xét "Phần 4: Quy trình...": Đoạn này ngắn (khoảng 250 ký tự). Vì 250 < 400,
    nên nó chỉ tạo thành 1 chunk duy nhất.

KẾT QUẢ CUỐI CÙNG (Dữ liệu sau xử lý)

Sau khi chạy xong, file của bạn sẽ biến thành các Object trong danh sách
all_chunks như sau (minh họa):

Chunk 1 (Loại: recursive_sub)

{
  "content_type": "policy",
  "chunk_type": "recursive_sub",
  "raw_text": "Thời gian bảo hành chi tiết cho từng dòng hàng\nCửa hàng cam kết mang lại sự an tâm tuyệt đối cho khách hàng với chế độ bảo hành dài hạn:\nKhung xương gỗ chính: Đối với các sản phẩm gỗ tự nhiên, khung xương chính như sườn giường, chân bàn, mặt bàn được bảo hành lên tới 60 tháng (5 năm)...",
  "metadata": {
    "section": "Thời gian bảo hành chi tiết cho từng dòng hàng",
    "source": "chinh_sach.md",
    "chunk_index": 1
  }
}

Chunk 2 (Loại: recursive_sub - phần tiếp theo của Chunk 1)

{
  "content_type": "policy",
  "chunk_type": "recursive_sub",
  "raw_text": "Thời gian bảo hành chi tiết cho từng dòng hàng\nBề mặt sơn và hoàn thiện: Bảo hành 12 tháng đối với hiện tượng bong tróc sơn tự nhiên. Phụ kiện đi kèm: Bản lề, ray kéo, tay nắm được thay thế miễn phí trong vòng 06 tháng đầu...",
  "metadata": {
    "section": "Thời gian bảo hành chi tiết cho từng dòng hàng",
    "source": "chinh_sach.md",
    "chunk_index": 2
  }
}

Chunk cuối (Loại: heading_section - vì ngắn nên không cần cắt nhỏ)

{
  "content_type": "policy",
  "chunk_type": "heading_section",
  "raw_text": "Quy trình yêu cầu bảo hành\nKhi gặp sự cố, quý khách vui lòng thực hiện các bước:\n1. Chụp ảnh hoặc quay video ngắn...\n2. Gửi thông tin qua Zalo...\n3. Nhân viên kỹ thuật sẽ tiếp nhận...",
  "metadata": {
    "section": "Quy trình yêu cầu bảo hành",
    "source": "chinh_sach.md",
    "chunk_index": 5
  }
}

Tại sao làm vậy lại tốt?

1.  Tính liên kết: Chunk 2 vẫn lặp lại tiêu đề "Thời gian bảo hành...", giúp AI
    không bị quên ngữ cảnh khi đang đọc dở phần phụ kiện.
2.  Dễ tìm kiếm: Nếu khách hỏi "Bảo hành gỗ MDF bao lâu?", AI sẽ tìm thấy
    Chunk 1 có điểm số cao nhất và trả lời chính xác.
3.  Gọn gàng: Toàn bộ định dạng Markdown rác bị loại bỏ, chỉ còn lại thông tin
    thuần túy.
"""
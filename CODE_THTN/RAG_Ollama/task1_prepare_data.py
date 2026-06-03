import json
import re
import os
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ─────────────────────────────────────────────────────────────
# ĐƯỜNG DẪN
# ─────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data")
PRODUCT_FILE = os.path.join(DATA_DIR, "products_final.json")

# ─────────────────────────────────────────────────────────────
# THAM SỐ CHUNKING CHÍNH SÁCH
# ─────────────────────────────────────────────────────────────
POLICY_CHUNK_SIZE    = 550
POLICY_CHUNK_OVERLAP = 120

# ═════════════════════════════════════════════════════════════
# NGUỒN A — SẢN PHẨM
# 1 sản phẩm = 1 chunk từ full_description
# ═════════════════════════════════════════════════════════════
def build_product_chunk(p: dict) -> dict:
    """
    Tạo 1 chunk duy nhất cho 1 sản phẩm.

    Điều kiện:
      - Data JSON đã chuẩn.
      - Bắt buộc phải có ai_metadata.full_description.

    raw_text:
      - Lưu full_description.
      - Đây là nội dung dùng để embedding.
      - Đây cũng là nội dung chatbot đọc để trả lời phần mô tả.

    metadata:
      - Chỉ lưu dữ liệu có cấu trúc để build context nhanh.
      - Không cần lưu full_description vào metadata vì raw_text đã lưu rồi.
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
    summary        = content.get("summary", "").strip()
    full_desc      = ai_meta.get("full_description", "").strip()

    if not full_desc: # full_description là bắt buộc để embedding + LLM đọc trả lời
        raise ValueError( # Dừng chương trình ngay nếu thiếu full_description
            f"Sản phẩm thiếu ai_metadata.full_description: "
            f"product_id={product_id}, name={name}"
        )

    return {
        "content_type": "product",
        "chunk_type":   "full_description",
        "raw_text":     full_desc,
        "metadata": {
            "product_id":     product_id,
            "name":           name,
            "category":       category_name,
            "price_sale":     price_sale,
            "price_original": price_original,
            "material":       material,
            "size":           size,
            "summary":        summary,
        }
    }


def load_product_chunks(filepath: str) -> list[dict]:
    """
    Đọc products_final.json và tạo 1 chunk cho mỗi sản phẩm.

    Nếu có sản phẩm thiếu full_description:
      - Dừng chương trình ngay.
      - Báo rõ product_id và name để sửa data.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        products = json.load(f)

    chunks = []

    for p in products:
        chunk = build_product_chunk(p)
        chunks.append(chunk)

    print(
        f"[Nguồn A] {len(products)} sản phẩm → {len(chunks)} chunk "
        f"(1 chunk/sp từ full_description)"
    )

    return chunks


# ═════════════════════════════════════════════════════════════
# NGUỒN B — FILE .md CHÍNH SÁCH
# Heading split + RecursiveCharacterTextSplitter
# ═════════════════════════════════════════════════════════════

def clean_markdown(text: str) -> str:
    """
    Làm sạch Markdown để nội dung dễ embedding hơn:
      - Bỏ ký hiệu heading #, ##, ###
      - Bỏ bold/italic
      - Chuyển bảng Markdown thành text dễ đọc
      - Giảm dòng trống liên tiếp
    """
    # re. là module xử lý regex, re.sub() thay thế pattern bằng text mới
    # flags=re.MULTILINE cho phép ^ và $ khớp với đầu/cuối dòng, không chỉ đầu/cuối toàn bộ text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE) # bỏ # heading
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text) # bỏ **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text) # bỏ *italic*

    # Bỏ dòng phân cách bảng Markdown: | --- | --- |
    text = re.sub(r"^\|[\s\-:\|]+\|$", "", text, flags=re.MULTILINE)

    # Convert dòng bảng "| A | B |" thành "A: B"
    def table_row(m): # để tránh lỗi nếu có nhiều cột, chỉ lấy 2 cột đầu để tạo text đơn giản. Nếu có nhiều cột hơn, nối bằng " - ".
        cells = [c.strip() for c in m.group(0).split("|") if c.strip()]
        if len(cells) == 2:
            return f"{cells[0]}: {cells[1]}"
        return " - ".join(cells) if cells else ""

    text = re.sub(r"^\|.+\|$", table_row, text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def detect_heading_level(raw_markdown: str) -> str:
    """
    Phát hiện cấp heading chính trong file Markdown.

    Trả về:
      - "sub"  nếu file có heading ## hoặc ###
      - "top"  nếu file chỉ có heading #
      - "none" nếu không có heading
    """
    if re.search(r"^#{2,3}\s+.+", raw_markdown, re.MULTILINE):
        return "sub"

    if re.search(r"^#\s+.+", raw_markdown, re.MULTILINE):
        return "top"

    return "none"


def split_by_heading(raw_markdown: str, filename: str = "") -> list[dict]:
    """
    Tách nội dung Markdown theo heading.

    Mục tiêu:
      - Giữ mỗi section có ngữ cảnh rõ ràng.
      - Tránh cắt ngang các mục như bảo hành, đổi trả, vận chuyển.
    """
    level = detect_heading_level(raw_markdown)

    if level == "sub": # Nếu có heading ## hoặc ###, ưu tiên tách theo đó để có section rõ ràng hơn, vì thường heading # chỉ là tiêu đề chung của cả file, còn ##/### mới là các mục chi tiết.
        pattern = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
    elif level == "top": # Nếu chỉ có heading #, vẫn tách theo đó để giữ ngữ cảnh, nhưng sẽ cảnh báo vì có thể không đủ chi tiết
        pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    else: # Nếu không có heading, coi toàn bộ file là 1 section duy nhất
        title = os.path.splitext(filename)[0] if filename else "Nội dung"
        return [{"title": title, "body": raw_markdown}]

    matches = list(pattern.finditer(raw_markdown)) # tìm tất cả heading phù hợp và lưu vị trí để tách section
    sections = [] # để lưu kết quả section sau khi tách theo heading

    # Nếu có đoạn mở đầu trước heading đầu tiên
    if matches and matches[0].start() > 0:
        preamble = raw_markdown[:matches[0].start()].strip()
        if preamble:
            fname = os.path.splitext(filename)[0] if filename else "Tổng quan"
            sections.append({
                "title": fname,
                "body": preamble
            })

    # Tách từng heading thành section
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_markdown)

        body = raw_markdown[start:end].strip()

        if body:
            sections.append({
                "title": title,
                "body": body
            })

    if sections:
        return sections

    return [{
        "title": "Nội dung",
        "body": raw_markdown
    }]


def load_md_file_chunks(
    filepath: str,
    splitter: RecursiveCharacterTextSplitter
) -> list[dict]:
    """
    Đọc 1 file .md, tách theo heading, sau đó dùng recursive splitter nếu section dài.

    Mỗi chunk policy có metadata:
      - chunk_index để biết thứ tự chunk trong file, có thể dùng để debug hoặc build context theo thứ tự.
      - section : tên section (tên heading) để biết nội dung chunk thuộc phần nào của chính sách.
      - source : tên file gốc để trace lại nếu cần.
      - heading_level : "top" | "sub" | "none" để biết cấu trúc heading của file, có thể dùng để build context theo cấp độ.
      - chunk_size : kích thước chunk đã được tách, để biết độ dài nội dung thực tế của chunk (không phải raw_text đã bị cắt để giới hạn VARCHAR).
      - chunk_overlap : độ dài overlap đã dùng khi tách, để biết mức độ trùng lặp giữa các chunk con nếu có tách bằng recursive splitter.
    """
    filename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        raw_md = f.read()

    heading_level = detect_heading_level(raw_md)
    sections = split_by_heading(raw_md, filename)

    chunks = []
    chunk_idx = 0

    for section in sections:
        title = section["title"]
        body_clean = clean_markdown(section["body"])

        if not body_clean:
            continue

        full_text = f"{title}\n{body_clean}"

        sub_docs = splitter.create_documents(
            [full_text],
            metadatas=[{
                "section": title,
                "source": filename
            }]
        )

        for sub_doc in sub_docs:
            sub_text = sub_doc.page_content.strip()

            if not sub_text:
                continue

            # Đảm bảo chunk nào cũng có title section ở đầu
            if not sub_text.startswith(title):
                sub_text = f"{title}\n{sub_text}"

            chunks.append({
                "content_type": "policy",
                "chunk_type": (
                    "heading_section"
                    if len(full_text) <= POLICY_CHUNK_SIZE
                    else "recursive_sub"
                ),
                "raw_text": sub_text,
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


def load_all_md_chunks(data_dir: str) -> list[dict]:
    """
    Tìm tất cả file .md trong thư mục data/ và tạo chunk policy.
    """
    md_files = sorted(glob.glob(os.path.join(data_dir, "*.md")))

    if not md_files:
        print("[Nguồn B] Không tìm thấy file .md!")
        return []

    print(f"[Nguồn B] Tìm thấy {len(md_files)} file .md:")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=POLICY_CHUNK_SIZE,
        chunk_overlap=POLICY_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", ",", " "], # ưu tiên tách theo đoạn, sau đó là dòng mới, rồi đến câu, cuối cùng là khoảng trắng nếu cần thiết để đảm bảo chunk không quá dài. Không dùng ký tự đặc biệt như - vì có thể gây lỗi khi tách các mục liệt kê trong chính sách.
        length_function=len, # đếm số ký tự để tách, vì Milvus VARCHAR giới hạn theo ký tự, không phải token.
        keep_separator=False,
    )

    all_chunks = []

    for filepath in md_files:
        filename = os.path.basename(filepath)
        chunks = load_md_file_chunks(filepath, splitter)

        all_chunks.extend(chunks)

        level = chunks[0]["metadata"]["heading_level"] if chunks else "?"
        print(f"  [{filename}] heading={level} → {len(chunks)} chunk")

    print(
        f"[Nguồn B] Tổng: {len(all_chunks)} chunk "
        f"(size={POLICY_CHUNK_SIZE}, overlap={POLICY_CHUNK_OVERLAP})"
    )

    return all_chunks


# ═════════════════════════════════════════════════════════════
# HÀM TỔNG HỢP
# ═════════════════════════════════════════════════════════════

def prepare_all_chunks() -> list[dict]:
    """
    Tải và chuẩn hóa toàn bộ dữ liệu:
      - Product chunks từ products_final.json
      - Policy chunks từ các file .md trong data/
    """
    product_chunks = load_product_chunks(PRODUCT_FILE)
    policy_chunks = load_all_md_chunks(DATA_DIR)

    all_chunks = product_chunks + policy_chunks

    print(f"\n[Tổng] {len(all_chunks)} chunk sẵn sàng để embedding.")

    return all_chunks


# ─────────────────────────────────────────────────────────────
# CHẠY THỬ ĐỘC LẬP
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_chunks = prepare_all_chunks()

    print("\n" + "=" * 60)
    print("VÍ DỤ: PRODUCT CHUNK ĐẦU TIÊN")
    print("=" * 60)

    prod_chunks = [
        c for c in all_chunks
        if c["content_type"] == "product"
    ]

    if prod_chunks:
        first = prod_chunks[0]

        print(f"\n  [chunk_type: {first['chunk_type']}]")
        print(f"  product_id: {first['metadata'].get('product_id')}")
        print(f"  name      : {first['metadata'].get('name')}")
        print(f"  category  : {first['metadata'].get('category')}")
        print(f"  material  : {first['metadata'].get('material')}")
        print(f"  size      : {first['metadata'].get('size')}")
        print("\n  raw_text / full_description:")
        print(f"  {first['raw_text'][:500]}")

    print("\n" + "=" * 60)
    print("THỐNG KÊ CHUNK THEO FILE .md")
    print("=" * 60)

    pol_chunks = [
        c for c in all_chunks
        if c["content_type"] == "policy"
    ]

    by_source: dict[str, list] = {}

    for c in pol_chunks:
        src = c["metadata"].get("source", "unknown")
        by_source.setdefault(src, []).append(c)

    for src, clist in sorted(by_source.items()):
        level = clist[0]["metadata"].get("heading_level", "?")
        print(f"  {src}: {len(clist)} chunk | heading={level}")
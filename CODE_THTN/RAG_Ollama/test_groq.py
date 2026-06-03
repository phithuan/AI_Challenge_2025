from pathlib import Path
from groq import Groq


BASE_DIR = Path(__file__).resolve().parent
API_KEY_FILE = BASE_DIR / "api_key.txt"


def load_api_key() -> str:
    if not API_KEY_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {API_KEY_FILE}")

    api_key = API_KEY_FILE.read_text(encoding="utf-8").strip()

    if not api_key:
        raise ValueError("File api_key.txt đang rỗng.")

    return api_key


client = Groq(
    api_key=load_api_key()
)

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {
            "role": "system",
            "content": "Bạn là trợ lý tiếng Việt, trả lời ngắn gọn."
        },
        {
            "role": "user",
            "content": "Xin chào, bạn là ai?"
        }
    ],
    temperature=0.2,
    max_completion_tokens=200,
)

print(response.choices[0].message.content)
function toggleChat() { // dùng để mở/đóng hộp thoại chat.
  let box = document.getElementById("chatbot-box");
  let bubble = document.getElementById("chatbot-bubble");
  if (box.style.display === "flex") {
    box.style.display = "none";
    bubble.style.display = "block";
  } else {
    box.style.display = "flex";
    bubble.style.display = "none";
  }
}

async function sendMessage() { // gửi tin nhắn và nhận phản hồi từ chatbot
  let input = document.getElementById("chatbot-text"); // input text area
  let messages = document.getElementById("chatbot-messages"); // div chứa tin nhắn
  let text = input.value.trim(); // lấy nội dung và loại bỏ khoảng trắng thừa

  if (text === "") return; // nếu rỗng thì không làm gì

  // Tin nhắn người dùng
  let userMsg = document.createElement("div");
  userMsg.className = "message user";
  userMsg.textContent = text;
  messages.appendChild(userMsg);

  // Separator giữa các lượt chat (⭐)
  let sep = document.createElement("div");
  sep.className = "separator";
  sep.innerHTML = "⭐";
  messages.appendChild(sep);

  messages.scrollTop = messages.scrollHeight;

  // Gửi request lên API Django
  try {
    const res = await fetch("/chatbot_api/", {
      method: "POST", // phương thức POST
      headers: { "Content-Type": "application/json" }, // định dạng JSON
      body: JSON.stringify({ question: text }) // gửi câu hỏi dưới dạng JSON 
    });
    const data = await res.json(); // chờ phản hồi và parse JSON

    // Tin nhắn từ bot
    let botMsg = document.createElement("div"); 
    botMsg.className = "message bot";
    botMsg.textContent = data.answer;
    messages.appendChild(botMsg);
  } catch (err) {
    let botMsg = document.createElement("div");
    botMsg.className = "message bot";
    botMsg.textContent = "❌ Lỗi server";
    messages.appendChild(botMsg);
  }

  input.value = "";
  messages.scrollTop = messages.scrollHeight;
}

// Enter = gửi, Shift+Enter = xuống dòng
document.addEventListener("DOMContentLoaded", () => {
  let input = document.getElementById("chatbot-text");
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
// Xóa nội dung chat khi đóng hộp thoại
document.getElementById("chatbot-close").onclick = function() {
    document.getElementById("chatbot-messages").innerHTML = "";
    toggleChat();
};


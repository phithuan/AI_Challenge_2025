function toggleChat() { // Hiển thị/hấp hộp hộp thoại
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

async function sendMessage() {
  let input = document.getElementById("chatbot-text");
  let messages = document.getElementById("chatbot-messages");
  let text = input.value.trim();

  if (text === "") return;

  // Tin nhắn người dùng
  let userMsg = document.createElement("div");
  userMsg.className = "message user";
  userMsg.textContent = text;
  messages.appendChild(userMsg);

  // Separator
  let sep = document.createElement("div");
  sep.className = "separator";
  sep.innerHTML = "⭐";
  messages.appendChild(sep);

  messages.scrollTop = messages.scrollHeight;

  // Gửi request lên API Django
  try {
    const res = await fetch("/chatbot_api/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text })
    });
    const data = await res.json();

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


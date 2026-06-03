// =========================================================
// CHATBOT GLOBAL STATE - GIỮ CHAT KHI CHUYỂN TRANG
// =========================================================

const CHAT_STORAGE_KEY = "tth_chat_messages";
const CHAT_OPEN_KEY = "tth_chat_is_open";
const CHAT_PENDING_KEY = "tth_chat_pending";

// Lưu vị trí thanh cuộn hiện tại của khung chat
// Mục đích: render lại tin nhắn nhưng không tự động kéo xuống dưới
const CHAT_SCROLL_KEY = "tth_chat_scroll_top";


function makeId() {
  return "msg_" + Date.now() + "_" + Math.random().toString(16).slice(2);
}


function getStoredMessages() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}


function saveMessages(messages) {
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
}


function getPendingChat() {
  try {
    const raw = localStorage.getItem(CHAT_PENDING_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}


function setPendingChat(data) {
  localStorage.setItem(CHAT_PENDING_KEY, JSON.stringify(data));
}


function clearPendingChat() {
  localStorage.removeItem(CHAT_PENDING_KEY);
}


function setChatOpen(isOpen) {
  localStorage.setItem(CHAT_OPEN_KEY, isOpen ? "1" : "0");
}


function isChatOpen() {
  return localStorage.getItem(CHAT_OPEN_KEY) === "1";
}


function getDefaultMessages() {
  return [
    {
      id: makeId(),
      type: "bot",
      text: "Chào bạn! 😊 Mình là ChatRAG AI. Bạn cần tìm sản phẩm nội thất hay hỏi về chính sách bảo hành, đổi trả?",
      extraClass: ""
    }
  ];
}


// =========================================================
// SCROLL - GIỮ NGUYÊN VỊ TRÍ THANH TRƯỢT
// =========================================================

function saveChatScrollPosition() {
  const messagesBox = document.getElementById("chatbot-messages");
  if (!messagesBox) return;

  localStorage.setItem(CHAT_SCROLL_KEY, String(messagesBox.scrollTop));
}


function restoreChatScrollPosition() {
  const messagesBox = document.getElementById("chatbot-messages");
  if (!messagesBox) return;

  const savedScrollTop = localStorage.getItem(CHAT_SCROLL_KEY);

  if (savedScrollTop === null) return;

  requestAnimationFrame(() => {
    messagesBox.scrollTop = Number(savedScrollTop);
  });
}


// =========================================================
// RENDER UI
// =========================================================

function renderMessages() {
  const messagesBox = document.getElementById("chatbot-messages");
  if (!messagesBox) return;

  // Lưu vị trí hiện tại trước khi render lại
  const currentScrollTop = messagesBox.scrollTop;

  let messages = getStoredMessages();

  if (messages.length === 0) {
    messages = getDefaultMessages();
    saveMessages(messages);
  }

  messagesBox.innerHTML = "";

  messages.forEach((item) => {
    if (item.type === "separator") {
      const sep = document.createElement("div");
      sep.className = "separator";
      sep.innerHTML = "⭐";
      messagesBox.appendChild(sep);
      return;
    }

    const msg = document.createElement("div");
    msg.className = `message ${item.type} ${item.extraClass || ""}`.trim();

    // Bot cho phép hiển thị HTML để render link sản phẩm
    if (item.type === "bot") {
      msg.innerHTML = item.text;
    } else {
      // User dùng textContent để an toàn
      msg.textContent = item.text;
    }

    messagesBox.appendChild(msg);
  });

  // Không tự động scroll xuống dưới nữa
  // Render xong thì giữ lại vị trí cũ
  requestAnimationFrame(() => {
    messagesBox.scrollTop = currentScrollTop;
  });
}


function addMessage(type, text, extraClass = "") {
  const messages = getStoredMessages();

  const item = {
    id: makeId(),
    type: type,
    text: text,
    extraClass: extraClass
  };

  messages.push(item);
  saveMessages(messages);
  renderMessages();

  return item.id;
}


function addSeparator() {
  const messages = getStoredMessages();

  messages.push({
    id: makeId(),
    type: "separator",
    text: "",
    extraClass: ""
  });

  saveMessages(messages);
  renderMessages();
}


function updateMessage(messageId, newText, extraClass = "") {
  const messages = getStoredMessages();

  const updated = messages.map((item) => {
    if (item.id === messageId) {
      return {
        ...item,
        text: newText,
        extraClass: extraClass
      };
    }

    return item;
  });

  saveMessages(updated);
  renderMessages();
}


function clearChatHistory() {
  localStorage.removeItem(CHAT_STORAGE_KEY);
  localStorage.removeItem(CHAT_PENDING_KEY);
  localStorage.removeItem(CHAT_SCROLL_KEY);

  const defaultMessages = getDefaultMessages();
  saveMessages(defaultMessages);
  renderMessages();

  const input = document.getElementById("chatbot-text");
  if (input) {
    input.value = "";
    input.focus();
  }
}


// =========================================================
// OPEN / CLOSE CHAT
// =========================================================

function toggleChat() {
  const box = document.getElementById("chatbot-box");
  const bubble = document.getElementById("chatbot-bubble");
  const tooltip = document.getElementById("chatbot-tooltip");
  const input = document.getElementById("chatbot-text");

  if (!box) return;

  const opening = box.style.display !== "flex";

  if (opening) {
    box.style.display = "flex";

    if (bubble) {
      bubble.style.display = "none";
    }

    if (tooltip) {
      tooltip.style.display = "none";
    }

    setChatOpen(true);

    // Khi mở lại chat, giữ vị trí thanh cuộn cũ
    restoreChatScrollPosition();

    setTimeout(() => {
      if (input) input.focus();
    }, 120);

  } else {
    // Trước khi đóng, lưu vị trí thanh cuộn hiện tại
    saveChatScrollPosition();

    box.style.display = "none";

    if (bubble) {
      bubble.style.display = "flex";
    }

    setChatOpen(false);
  }
}


function restoreChatOpenState() {
  const box = document.getElementById("chatbot-box");
  const bubble = document.getElementById("chatbot-bubble");
  const tooltip = document.getElementById("chatbot-tooltip");

  if (!box) return;

  if (isChatOpen()) {
    box.style.display = "flex";

    if (bubble) {
      bubble.style.display = "none";
    }

    if (tooltip) {
      tooltip.style.display = "none";
    }

    // Khi load lại trang, giữ vị trí thanh cuộn cũ
    restoreChatScrollPosition();

  } else {
    box.style.display = "none";

    if (bubble) {
      bubble.style.display = "flex";
    }
  }
}


// =========================================================
// INPUT
// =========================================================

function autoResizeTextarea(textarea) {
  if (!textarea) return;

  textarea.style.height = "46px";
  textarea.style.height = Math.min(textarea.scrollHeight, 110) + "px";
}


function setSendingState(isSending) {
  const sendBtn = document.querySelector("#chatbot-input button");
  const input = document.getElementById("chatbot-text");

  if (sendBtn) {
    sendBtn.disabled = isSending;
  }

  if (input) {
    input.disabled = isSending;
    input.placeholder = isSending
      ? "Chatbot đang trả lời..."
      : "Nhập câu hỏi của bạn...";
  }
}


// =========================================================
// CALL BACKEND
// =========================================================

async function callChatbotApi(question, botMessageId) {
  setSendingState(true);

  try {
    const res = await fetch("/chatbot_api/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: question,
        history: getHistoryForBackend(question)
      })
    });

    let data = {};

    try {
      data = await res.json();
    } catch (e) {
      data = {
        answer: "❌ Server trả về dữ liệu không hợp lệ."
      };
    }

    if (!res.ok) {
      updateMessage(
        botMessageId,
        data.answer || "❌ Có lỗi xảy ra khi gọi chatbot.",
        ""
      );
      return;
    }

    updateMessage(
      botMessageId,
      data.answer || "Xin lỗi, tôi chưa có thông tin về vấn đề này.",
      ""
    );

  } catch (err) {
    updateMessage(
      botMessageId,
      "❌ Không kết nối được server chatbot.",
      ""
    );

  } finally {
    clearPendingChat();
    setSendingState(false);

    const input = document.getElementById("chatbot-text");
    if (input) {
      input.focus();
    }
  }
}


// =========================================================
// SEND MESSAGE
// =========================================================

async function sendMessage() {
  const input = document.getElementById("chatbot-text");

  if (!input) return;

  const text = input.value.trim();

  if (text === "") return;

  // Lưu vị trí trước khi thêm tin nhắn
  saveChatScrollPosition();

  addMessage("user", text);
  addSeparator();

  input.value = "";
  autoResizeTextarea(input);

  const botMessageId = addMessage(
    "bot",
    "🤖 Đang phân tích câu hỏi và tìm dữ liệu phù hợp...",
    "thinking"
  );

  // Lưu pending để nếu chuyển trang vẫn tiếp tục trạng thái đang xử lý
  setPendingChat({
    question: text,
    botMessageId: botMessageId,
    createdAt: Date.now()
  });

  await callChatbotApi(text, botMessageId);
}


// =========================================================
// RESTORE PENDING CHAT SAU KHI CHUYỂN TRANG
// =========================================================

function resumePendingChatIfNeeded() {
  const pending = getPendingChat();

  if (!pending) return;

  const messages = getStoredMessages();
  const botMsg = messages.find((item) => item.id === pending.botMessageId);

  let botMessageId = pending.botMessageId;

  if (!botMsg) {
    botMessageId = addMessage(
      "bot",
      "🤖 Đang phân tích câu hỏi và tìm dữ liệu phù hợp...",
      "thinking"
    );

    setPendingChat({
      ...pending,
      botMessageId: botMessageId
    });
  } else {
    updateMessage(
      botMessageId,
      "🤖 Đang phân tích câu hỏi và tìm dữ liệu phù hợp...",
      "thinking"
    );
  }

  callChatbotApi(pending.question, botMessageId);
}


function getHistoryForBackend(currentQuestion = "") {
  const messages = getStoredMessages();
  const history = [];

  messages.forEach((item) => {
    if (item.type === "user") {
      history.push({
        role: "user",
        content: item.text
      });
    }

    if (item.type === "bot" && !(item.extraClass || "").includes("thinking")) {
      history.push({
        role: "assistant",
        content: item.text
      });
    }
  });

  if (
    history.length > 0 &&
    history[history.length - 1].role === "user" &&
    history[history.length - 1].content.trim() === currentQuestion.trim()
  ) {
    history.pop();
  }

  return history.slice(-5);
}


// =========================================================
// INIT
// =========================================================

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chatbot-text");
  const closeBtn = document.getElementById("chatbot-close");
  const clearBtn = document.getElementById("chatbot-clear");
  const tooltip = document.getElementById("chatbot-tooltip");
  const messagesBox = document.getElementById("chatbot-messages");

  renderMessages();
  restoreChatOpenState();

  // Mỗi lần người dùng tự kéo thanh trượt thì lưu vị trí lại
  if (messagesBox) {
    messagesBox.addEventListener("scroll", function () {
      saveChatScrollPosition();
    });
  }

  if (input) {
    input.addEventListener("input", function () {
      autoResizeTextarea(input);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (closeBtn) {
    closeBtn.onclick = function () {
      toggleChat();
    };
  }

  if (clearBtn) {
    clearBtn.onclick = function () {
      const ok = confirm("Bạn có chắc muốn xóa toàn bộ lịch sử chat không?");

      if (ok) {
        clearChatHistory();
      }
    };
  }

  if (tooltip) {
    function showTooltip() {
      const box = document.getElementById("chatbot-box");

      if (box && box.style.display === "flex") {
        return;
      }

      tooltip.classList.remove("tooltip-show");
      void tooltip.offsetWidth;
      tooltip.classList.add("tooltip-show");
    }

    setTimeout(showTooltip, 1000);
    setInterval(showTooltip, 6000);
  }

  // Nếu muốn tiếp tục pending chat thì mở dòng này
  // resumePendingChatIfNeeded();
});
document.addEventListener("DOMContentLoaded", function () {
  const chatMessages = document.getElementById("chatMessages");
  const userInput = document.getElementById("userInput");
  const sendButton = document.getElementById("sendButton");

  function addTypingIndicator() {
    const typingDiv = document.createElement("div");
    typingDiv.className = "message bot typing-indicator";
    typingDiv.innerHTML = `
      <i class="fas fa-robot bot-icon"></i>
      <div class="message-content">
        <div style="display: flex; padding: 8px;">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return typingDiv;
  }

  function removeTypingIndicator(typingDiv) {
    if (typingDiv && typingDiv.parentNode) {
      typingDiv.parentNode.removeChild(typingDiv);
    }
  }

  function addMessage(message, isUser = false) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${isUser ? "user" : "bot"}`;

    if (!isUser) {
      const botIcon = document.createElement("i");
      botIcon.className = "fas fa-robot bot-icon";
      messageDiv.appendChild(botIcon);
    }

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    const messageText = document.createElement("p");
    messageText.textContent = message;

    contentDiv.appendChild(messageText);
    messageDiv.appendChild(contentDiv);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, true);
    userInput.value = "";

    // Add typing indicator
    const typingIndicator = addTypingIndicator();

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: message }),
      });

      // Simulate minimum typing time
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const data = await response.json();
      removeTypingIndicator(typingIndicator);
      addMessage(data.response);
    } catch (error) {
      console.error("Error:", error);
      removeTypingIndicator(typingIndicator);
      addMessage("Sorry, I encountered an error. Please try again.");
    }
  }

  sendButton.addEventListener("click", sendMessage);
  userInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      sendMessage();
    }
  });
});

// Preloader
var loader = document.getElementById("preloader");
setTimeout(function () {
  loader.style.display = "none";
}, 2000);

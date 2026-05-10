// static/js/chat.js

(function setupProcessChat() {
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  const chatSources = document.getElementById("chatSources");
  const chatProcessLine = document.getElementById("chatProcessLine");

  if (!chatForm || !chatInput || !chatMessages) return;

  const params = new URLSearchParams(window.location.search);
  const processSlug = params.get("process") || "deposition";

  const userProfile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");

  const chatHistory = [];

  function processLabel(slug) {
    return slug
      .split("-")
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  if (chatProcessLine) {
    const role = userProfile.current_role || "your role";
    chatProcessLine.textContent = `Using ${processLabel(processSlug)} context · personalized for ${role}`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function addMessage(role, text) {
    const bubble = document.createElement("div");

    if (role === "user") {
      bubble.className = "rounded-xl bg-gray-900 text-white p-4 text-sm ml-12 whitespace-pre-wrap";
      bubble.textContent = text;
    } else {
      bubble.className = "chat-bubble-ai rounded-xl bg-gray-50 border border-gray-100 text-gray-700 p-4 text-sm mr-12";

      if (window.marked) {
        bubble.innerHTML = marked.parse(text || "");
      } else {
        bubble.innerHTML = escapeHtml(text).replaceAll("\n", "<br>");
      }
    }

  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

  function addLoading() {
    const bubble = document.createElement("div");
    bubble.id = "chatLoading";
    bubble.className = "rounded-xl bg-gray-50 border border-gray-100 text-gray-400 p-4 text-sm mr-12";
    bubble.textContent = "Thinking…";
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeLoading() {
    document.getElementById("chatLoading")?.remove();
  }

  function renderSources(sources) {
    if (!chatSources) return;

    if (!sources || !sources.length) {
      chatSources.innerHTML = "";
      return;
    }

    chatSources.innerHTML = `
      <p class="font-semibold text-gray-700 mb-2">Related SOPs used as context:</p>
      <div class="flex flex-wrap gap-2">
        ${sources.map(src => `
          <a href="/documents/${escapeHtml(src.id)}"
             class="inline-flex rounded-full border border-gray-200 px-3 py-1 hover:bg-gray-50 text-gray-600">
            ${escapeHtml(src.title || ("Document " + src.id))}
          </a>
        `).join("")}
      </div>
    `;
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const message = chatInput.value.trim();
    if (!message) return;

    chatInput.value = "";

    addMessage("user", message);
    chatHistory.push({ role: "user", content: message });

    addLoading();

    try {
      const res = await fetch(`/api/chat/process/${processSlug}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_profile: userProfile,
          message,
          chat_history: chatHistory,
        }),
      });

      if (!res.ok) {
        throw new Error(`Chat request failed (${res.status})`);
      }

      const data = await res.json();

      removeLoading();

      const answer = data.answer || "I could not generate an answer.";
      addMessage("assistant", answer);
      chatHistory.push({ role: "assistant", content: answer });

      renderSources(data.sources || []);

    } catch (err) {
      removeLoading();
      addMessage("assistant", `Sorry, I could not answer that. ${err.message}`);
    }
  });
})();
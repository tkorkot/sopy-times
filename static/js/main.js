/**
 * main.js — handles the profile form (index.html) and
 * document list (documents.html) + dashboard (dashboard.html).
 */

/* ── Profile form (index.html) ─────────────────────────── */
const profileForm = document.getElementById("profileForm");
if (profileForm) {
  profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const profile = {
      job_title:        document.getElementById("jobTitle").value.trim(),
      experience_level: document.getElementById("experienceLevel").value,
      area_of_interest: document.getElementById("areaOfInterest").value.trim(),
    };

    document.getElementById("loadingMsg").classList.remove("hidden");
    document.getElementById("errorMsg").classList.add("hidden");

    try {
      const res = await fetch("/api/search/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (!res.ok) throw new Error("Search failed");

      const ranked = await res.json();
      sessionStorage.setItem("sopResults", JSON.stringify(ranked));
      sessionStorage.setItem("userProfile", JSON.stringify(profile));
      window.location.href = "/dashboard";
    } catch (err) {
      document.getElementById("loadingMsg").classList.add("hidden");
      const errEl = document.getElementById("errorMsg");
      errEl.textContent = err.message;
      errEl.classList.remove("hidden");
    }
  });
}

/* ── Dashboard (dashboard.html) ────────────────────────── */
const resultsEl = document.getElementById("results");
if (resultsEl) {
  const ranked  = JSON.parse(sessionStorage.getItem("sopResults") || "[]");
  const profile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");
  const summary = document.getElementById("profileSummary");

  if (profile.job_title) {
    summary.textContent =
      `${profile.job_title} · ${profile.experience_level} · ${profile.area_of_interest}`;
  }

  resultsEl.innerHTML = "";

  if (!ranked.length) {
    resultsEl.innerHTML = '<p class="text-gray-400 text-sm">No results. <a href="/" class="text-blue-500 underline">Try a different profile.</a></p>';
  } else {
    const tmpl = document.getElementById("sopCard");
    ranked.forEach(({ document: doc, relevance_score, reason }) => {
      const card = tmpl.content.cloneNode(true);
      card.querySelector(".sop-title").textContent = doc.title;
      card.querySelector(".sop-title").href = `/documents/${doc.id}`;
      card.querySelector(".sop-score").textContent = `${Math.round(relevance_score * 100)}% match`;
      card.querySelector(".sop-area").textContent = doc.process_area;
      card.querySelector(".sop-reason").textContent = reason;

      const tagsEl = card.querySelector(".sop-tags");
      (doc.tags || []).forEach(tag => {
        const pill = document.createElement("span");
        pill.className = "tag-pill";
        pill.textContent = tag;
        tagsEl.appendChild(pill);
      });

      resultsEl.appendChild(card);
    });
  }
}

/* ── Document list (documents.html) ────────────────────── */
const docList = document.getElementById("docList");
if (docList) {
  let allDocs = [];

  async function loadDocs() {
    const res = await fetch("/api/documents/");
    allDocs = await res.json();
    renderDocs(allDocs);
  }

  function renderDocs(docs) {
    docList.innerHTML = "";
    if (!docs.length) {
      docList.innerHTML = '<p class="text-gray-400 text-sm">No SOPs yet. Create one!</p>';
      return;
    }
    const tmpl = document.getElementById("docCard");
    docs.forEach(doc => {
      const card = tmpl.content.cloneNode(true);
      card.querySelector(".doc-title").textContent = doc.title;
      card.querySelector(".doc-title").href = `/documents/${doc.id}`;
      card.querySelector(".doc-area").textContent = doc.process_area;
      card.querySelector(".doc-version").textContent = `v${doc.version}`;
      card.querySelector(".doc-edit").href = `/documents/${doc.id}`;

      const tagsEl = card.querySelector(".doc-tags");
      (doc.tags || []).forEach(tag => {
        const pill = document.createElement("span");
        pill.className = "tag-pill";
        pill.textContent = tag;
        tagsEl.appendChild(pill);
      });

      docList.appendChild(card);
    });
  }

  // Filter
  document.getElementById("filterInput")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderDocs(allDocs.filter(d =>
      d.title.toLowerCase().includes(q) || (d.process_area || "").toLowerCase().includes(q)
    ));
  });

  // New doc modal
  document.getElementById("newDocBtn")?.addEventListener("click", () => {
    document.getElementById("newDocModal").classList.remove("hidden");
  });
  document.getElementById("cancelNewDoc")?.addEventListener("click", () => {
    document.getElementById("newDocModal").classList.add("hidden");
  });
  document.getElementById("saveNewDoc")?.addEventListener("click", async () => {
    const body = {
      title:        document.getElementById("newTitle").value.trim(),
      process_area: document.getElementById("newArea").value.trim(),
      tags:         document.getElementById("newTags").value.split(",").map(t => t.trim()).filter(Boolean),
      content:      document.getElementById("newContent").value,
    };
    const res = await fetch("/api/documents/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) {
      document.getElementById("newDocModal").classList.add("hidden");
      await loadDocs();
    }
  });

  loadDocs();
}

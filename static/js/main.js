/**
 * main.js — profile form (index.html), dashboard, and document list with PDF upload.
 */

/* ── Profile form (index.html) ─────────────────────────── */
const profileForm = document.getElementById("profileForm");
if (profileForm) {
  profileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(profileForm);

    const profile = {
      linkedin_url:     fd.get("linkedin_url") || "",
      education:        fd.get("education") || "",
      field_of_study:   fd.get("field_of_study") || "",
      current_role:     fd.get("current_role") || "",
      experience_level: fd.get("experience_level") || "",
      tool_names:       fd.get("tool_names") || "",
      certifications:   fd.getAll("certifications"),
      process_areas:    fd.getAll("process_areas"),
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

  if (profile.current_role) {
    const parts = [profile.current_role, profile.experience_level, profile.field_of_study].filter(Boolean);
    summary.textContent = parts.join(" · ");
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

/* ── Document list + PDF upload (documents.html) ───────── */
const docList = document.getElementById("docList");
if (docList) {
  let allDocs = [];

  /* ── Load & render doc list ── */
  async function loadDocs() {
    const res = await fetch("/api/documents/");
    allDocs = await res.json();
    renderDocs(allDocs);
  }

  function renderDocs(docs) {
    docList.innerHTML = "";
    if (!docs.length) {
      docList.innerHTML = '<p class="text-gray-400 text-sm">No SOPs yet — upload a PDF to get started.</p>';
      return;
    }
    const tmpl = document.getElementById("docCard");
    docs.forEach(doc => {
      const card = tmpl.content.cloneNode(true);
      card.querySelector(".doc-title").textContent = doc.title;
      card.querySelector(".doc-title").href = `/documents/${doc.id}`;
      card.querySelector(".doc-edit").href   = `/documents/${doc.id}`;
      card.querySelector(".doc-version").textContent = `v${doc.version}`;

      if (doc.process_area) card.querySelector(".doc-area").textContent = doc.process_area;
      if (doc.location)     card.querySelector(".doc-location").textContent = `📍 ${doc.location}`;
      if (doc.coral_name && doc.coral_name !== "N/A (General Lab Procedure)")
        card.querySelector(".doc-coral").textContent = `CORAL: ${doc.coral_name}`;
      if (doc.source_pdf)   card.querySelector(".doc-pdf-badge").classList.remove("hidden");

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

  document.getElementById("filterInput")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderDocs(allDocs.filter(d =>
      [d.title, d.process_area, d.location, d.coral_name, ...(d.tags || [])]
        .some(v => (v || "").toLowerCase().includes(q))
    ));
  });

  /* ── PDF upload ── */
  const uploadBtn      = document.getElementById("uploadBtn");
  const uploadZone     = document.getElementById("uploadZone");
  const pdfInput       = document.getElementById("pdfInput");
  const browseBtn      = document.getElementById("browseBtn");
  const uploadIdle     = document.getElementById("uploadIdle");
  const uploadProgress = document.getElementById("uploadProgress");
  const uploadSuccess  = document.getElementById("uploadSuccess");
  const uploadError    = document.getElementById("uploadError");

  uploadBtn.addEventListener("click", () => {
    uploadZone.classList.toggle("hidden");
    resetUploadUI();
  });

  browseBtn.addEventListener("click", () => pdfInput.click());

  pdfInput.addEventListener("change", () => {
    if (pdfInput.files[0]) uploadFile(pdfInput.files[0]);
  });

  // Drag-and-drop
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("border-blue-500", "bg-blue-100");
  });
  uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("border-blue-500", "bg-blue-100");
  });
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("border-blue-500", "bg-blue-100");
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith(".pdf")) {
      uploadFile(file);
    } else {
      showUploadError("Only PDF files are accepted.");
    }
  });

  document.getElementById("uploadRetry")?.addEventListener("click", resetUploadUI);

  async function uploadFile(file) {
    // Show progress state
    uploadIdle.classList.add("hidden");
    uploadProgress.classList.remove("hidden");
    uploadSuccess.classList.add("hidden");
    uploadError.classList.add("hidden");

    document.getElementById("uploadFileName").textContent = file.name;
    document.getElementById("uploadStatus").textContent = "Extracting content from PDF…";
    animateProgress();

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        // Try JSON first; fall back to raw text so HTML error pages don't hide the real message
        const text = await res.text();
        let msg = "Upload failed";
        try { msg = JSON.parse(text).error || msg; } catch { msg = `Server error (${res.status})`; }
        throw new Error(msg);
      }

      const doc = await res.json();

      // Show success
      uploadProgress.classList.add("hidden");
      uploadSuccess.classList.remove("hidden");
      document.getElementById("uploadedTitle").textContent = doc.title;
      document.getElementById("uploadedLink").href = `/documents/${doc.id}`;

      await loadDocs();
    } catch (err) {
      showUploadError(err.message);
    }
  }

  function showUploadError(msg) {
    uploadProgress.classList.add("hidden");
    uploadError.classList.remove("hidden");
    document.getElementById("uploadErrorMsg").textContent = msg;
  }

  function resetUploadUI() {
    uploadIdle.classList.remove("hidden");
    uploadProgress.classList.add("hidden");
    uploadSuccess.classList.add("hidden");
    uploadError.classList.add("hidden");
    pdfInput.value = "";
  }

  // Fake progress bar animation while waiting for server
  function animateProgress() {
    const bar = document.getElementById("progressBar");
    let pct = 0;
    const iv = setInterval(() => {
      pct = Math.min(pct + Math.random() * 12, 85);
      bar.style.width = pct + "%";
      if (pct >= 85) clearInterval(iv);
    }, 300);
  }

  loadDocs();
}

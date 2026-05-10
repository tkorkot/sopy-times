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
      learner_name:     fd.get("learner_name") || "",
      linkedin_url:     fd.get("linkedin_url") || "",
      education:        fd.get("education") || "",
      field_of_study:   fd.get("field_of_study") || "",
      current_role:     fd.get("current_role") || "",
      experience_level: fd.get("experience_level") || "",
      tool_names:       fd.get("tool_names") || "",
      certifications:   fd.getAll("certifications"),
      process_areas:    fd.getAll("process_areas"),
      target_role:      fd.get("target_role") || "",
      learning_goal:    fd.get("learning_goal") || "",
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
(function populateDashboard() {
  if (!document.getElementById("db-name")) return;   // not on dashboard

  const ranked  = JSON.parse(sessionStorage.getItem("sopResults")  || "[]");
  const profile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");

  const AREA_IMPACT = {
    "Lithography / Exposure":        "Your step defines the pattern — accuracy here directly determines CD, overlay, and downstream etch results.",
    "Etch / Pattern Transfer":       "Your step transfers the resist pattern into film — selectivity and etch rate determine feature fidelity.",
    "Deposition / Film Formation":   "Your step adds the layers that become devices — thickness, stress, and composition all flow downstream.",
    "Thermal Processing":            "Your step modifies material properties — anneal temperature and time affect dopant profiles and film quality.",
    "Resist Processing":             "Your step prepares the resist stack — spin speed, bake times, and dose sensitivity all feed into the exposure result.",
    "Sample Prep / Surface Cleaning":"Your step sets the baseline — contamination or oxide left here propagates through every layer above.",
    "Strip Resist / Clean":          "Your step removes residues after pattern transfer — incomplete strip causes defects in subsequent layers.",
    "Metrology / Inspection":        "Your step validates the process — the measurements you take decide whether wafers advance or are reworked.",
    "Packaging / Wirebonding":       "Your step connects the die to the world — bond quality determines electrical yield and long-term reliability.",
  };

  const name        = profile.learner_name  || "Your";
  const role        = profile.current_role  || "—";
  const areas       = profile.process_areas || [];
  const primaryArea = areas.find(a => a !== "None / not currently working in a process area") || areas[0] || "—";
  const targetRole  = profile.target_role   || "Specialist / Lead";
  const impact      = AREA_IMPACT[primaryArea] || "Your step is part of the wafer flow — understanding it helps you see upstream causes and downstream effects.";

  // Header
  document.getElementById("db-name").textContent        = name;
  document.getElementById("db-role").textContent        = role;
  document.getElementById("db-area").textContent        = primaryArea;
  document.getElementById("db-impact").textContent      = impact;

  // Path strip
  document.getElementById("db-current-role").textContent = role;
  document.getElementById("db-target-role").textContent  = targetRole;

  // Profile summary chips
  const chips = document.getElementById("db-profile-chips");
  if (chips) {
    const parts = [
      profile.experience_level,
      profile.education,
      profile.field_of_study,
      profile.learning_goal,
    ].filter(Boolean);
    chips.innerHTML = parts.map(p => `<span class="profile-chip">${p}</span>`).join("");
  }

  // Recommended SOPs section
  const resultsEl = document.getElementById("db-sop-results");
  if (!resultsEl) return;

  if (!ranked.length) {
    resultsEl.innerHTML = `
      <div class="db-no-results">
        <p>No SOP recommendations yet.</p>
        <a href="/" class="btn btn-secondary" style="margin-top:12px;">Fill your profile →</a>
      </div>`;
    return;
  }

  resultsEl.innerHTML = "";
  ranked.forEach(({ document: doc, relevance_score, reason }) => {
    const pct  = Math.round(relevance_score * 100);
    const card = document.createElement("a");
    card.href      = `/documents/${doc.id}`;
    card.className = "db-sop-card";
    card.innerHTML = `
      <div class="db-sop-top">
        <span class="db-sop-score">${pct}%</span>
        <span class="db-sop-area">${doc.process_area || ""}</span>
      </div>
      <p class="db-sop-title">${doc.title}</p>
      <p class="db-sop-reason">${reason}</p>
      <div class="db-sop-tags">
        ${(doc.tags || []).map(t => `<span class="tag-pill">${t}</span>`).join("")}
      </div>`;
    resultsEl.appendChild(card);
  });
})();

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

  function buildCard(doc) {
    const tmpl = document.getElementById("docCard");
    const card = tmpl.content.cloneNode(true);
    card.querySelector(".doc-title").textContent = doc.title;
    card.querySelector(".doc-title").href = `/documents/${doc.id}`;
    card.querySelector(".doc-edit").href  = `/documents/${doc.id}`;
    card.querySelector(".doc-version").textContent = `v${doc.version}`;

    if (doc.process_area) card.querySelector(".doc-area").textContent = doc.process_area;
    if (doc.location)     card.querySelector(".doc-location").textContent = `📍 ${doc.location}`;
    if (doc.coral_name && doc.coral_name !== "N/A (General Lab Procedure)")
      card.querySelector(".doc-coral").textContent = `CORAL: ${doc.coral_name}`;

    // doc_type badge: SOP = blue, INFO = gray
    const badge = card.querySelector(".doc-type-badge");
    if (doc.doc_type === "SOP") {
      badge.textContent = "SOP";
      badge.classList.add("bg-blue-100", "text-blue-700");
    } else if (doc.doc_type === "INFO") {
      badge.textContent = "INFO";
      badge.classList.add("bg-gray-100", "text-gray-500");
    }

    const tagsEl = card.querySelector(".doc-tags");
    (doc.tags || []).forEach(tag => {
      const pill = document.createElement("span");
      pill.className = "tag-pill";
      pill.textContent = tag;
      tagsEl.appendChild(pill);
    });

    return card;
  }

  function renderDocs(docs) {
    docList.innerHTML = "";
    if (!docs.length) {
      docList.innerHTML = '<p class="text-gray-400 text-sm">No SOPs yet — upload a PDF to get started.</p>';
      return;
    }

    // Group: step_name → step_type_name → [docs]
    const byStep = new Map();
    docs.forEach(doc => {
      const step = doc.step_name || "Uncategorized";
      const type = doc.step_type_name || "General";
      if (!byStep.has(step)) byStep.set(step, new Map());
      const byType = byStep.get(step);
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type).push(doc);
    });

    byStep.forEach((byType, stepName) => {
      // Step section header
      const stepSection = document.createElement("div");

      const stepHeader = document.createElement("h2");
      stepHeader.className = "text-base font-semibold text-gray-800 mb-3 border-b border-gray-200 pb-1";
      stepHeader.textContent = stepName;
      stepSection.appendChild(stepHeader);

      byType.forEach((typeDocs, typeName) => {
        const typeSection = document.createElement("div");
        typeSection.className = "mb-4";

        // Only show the type sub-header if it differs from the step name
        if (typeName !== stepName && typeName !== "General") {
          const typeHeader = document.createElement("h3");
          typeHeader.className = "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 ml-1";
          typeHeader.textContent = typeName;
          typeSection.appendChild(typeHeader);
        }

        const grid = document.createElement("div");
        grid.className = "space-y-2";
        typeDocs.forEach(doc => grid.appendChild(buildCard(doc)));
        typeSection.appendChild(grid);
        stepSection.appendChild(typeSection);
      });

      docList.appendChild(stepSection);
    });
  }

  document.getElementById("filterInput")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    renderDocs(allDocs.filter(d =>
      [d.title, d.process_area, d.location, d.coral_name, d.step_name, d.step_type_name, ...(d.tags || [])]
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

  // Load existing steps for the dropdowns
  let _stepsCache = null;
  async function loadSteps() {
    if (_stepsCache) return _stepsCache;
    try {
      const res = await fetch("/api/documents/steps");
      _stepsCache = await res.json();
    } catch { _stepsCache = []; }
    return _stepsCache;
  }

  async function populateStepDropdown() {
    const steps = await loadSteps();
    const sel = document.getElementById("stepSelect");
    sel.innerHTML = '<option value="">— select or type —</option>';
    steps.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = s.name;
      sel.appendChild(opt);
    });
  }

  document.getElementById("stepSelect")?.addEventListener("change", async (e) => {
    const steps = await loadSteps();
    const chosen = steps.find(s => s.name === e.target.value);
    const typeSel = document.getElementById("typeSelect");
    typeSel.innerHTML = '<option value="">— select or type —</option>';
    if (chosen) {
      chosen.types.forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.name;
        opt.textContent = t.name;
        typeSel.appendChild(opt);
      });
    }
    document.getElementById("stepInput").value = "";
  });

  document.getElementById("stepInput")?.addEventListener("input", () => {
    document.getElementById("stepSelect").value = "";
  });
  document.getElementById("typeInput")?.addEventListener("input", () => {
    document.getElementById("typeSelect").value = "";
  });

  uploadBtn.addEventListener("click", () => {
    uploadZone.classList.toggle("hidden");
    resetUploadUI();
    if (!uploadZone.classList.contains("hidden")) populateStepDropdown();
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
    // Resolve step / type from either the dropdown or the free-text input
    const stepName = (document.getElementById("stepSelect")?.value ||
                      document.getElementById("stepInput")?.value || "").trim();
    const typeName = (document.getElementById("typeSelect")?.value ||
                      document.getElementById("typeInput")?.value || "").trim();

    if (!stepName) {
      showUploadError("Please select or enter a Process Step before uploading.");
      return;
    }

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
    formData.append("step_name", stepName);
    if (typeName) formData.append("step_type_name", typeName);

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

/* ── Personalized process page (process.html) ─────────── */
(function populateProcessPage() {
  if (!window.PROCESS_SLUG) return;

  const profile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");

  const personaLine = document.getElementById("personaLine");
  if (personaLine) {
    const name = profile.learner_name || "your profile";
    const role = profile.current_role || "your role";
    personaLine.textContent = `Personalized for ${name} · ${role}`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function paragraphs(text) {
    const chunks = String(text || "")
      .split(/\n+/)
      .map(s => s.trim())
      .filter(Boolean);

    if (!chunks.length) {
      return `<p class="text-gray-400">No summary available yet.</p>`;
    }

    return chunks.map(p => `<p>${escapeHtml(p)}</p>`).join("");
  }

  async function loadPersonalizedProcess() {
    try {
      const res = await fetch(`/api/process/${window.PROCESS_SLUG}/personalized`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(profile),
      });

      if (!res.ok) {
        throw new Error(`Could not load process page (${res.status})`);
      }

      const data = await res.json();

      const processSummaryText = document.getElementById("processSummaryText");
      if (processSummaryText) {
        processSummaryText.innerHTML = paragraphs(data.process_summary);
      }

      const toolSummaryText = document.getElementById("toolSummaryText");
      if (toolSummaryText) {
        toolSummaryText.innerHTML = paragraphs(data.tool_summary);
      }

      const learningFocusList = document.getElementById("learningFocusList");
      if (learningFocusList) {
        const items = data.learning_focus || [];
        if (items.length) {
          learningFocusList.innerHTML = items
            .map(item => `<li>${escapeHtml(item)}</li>`)
            .join("");
        } else {
          learningFocusList.innerHTML = `<li class="text-gray-400">No learning focus generated.</li>`;
        }
      }

      const parameterTableBody = document.getElementById("parameterTableBody");
      if (parameterTableBody) {
        const rows = data.parameters || [];
        if (rows.length) {
          parameterTableBody.innerHTML = rows.map(row => `
            <tr>
              <td class="px-4 py-3 font-medium">${escapeHtml(row.parameter)}</td>
              <td class="px-4 py-3">${escapeHtml(row.example_value)}</td>
              <td class="px-4 py-3">${escapeHtml(row.purpose)}</td>
              <td class="px-4 py-3 text-gray-500">${escapeHtml(row.notes)}</td>
            </tr>
          `).join("");
        } else {
          parameterTableBody.innerHTML = `
            <tr>
              <td colspan="4" class="px-4 py-3 text-gray-400">
                No parameters generated.
              </td>
            </tr>`;
        }
      }

      // Inject process + tool images sourced from extracted PDF images
      function _setProcessImg(imgId, placeholderId, url) {
        const img = document.getElementById(imgId);
        const ph  = document.getElementById(placeholderId);
        if (!img) return;
        if (url) {
          img.src = url;
        } else if (ph) {
          ph.querySelector("p:last-child").textContent = "No image available yet.";
        }
      }
      _setProcessImg("processImg", "processImgPlaceholder", data.process_image_url);
      _setProcessImg("toolImg",    "toolImgPlaceholder",    data.tool_image_url);

      const processSopList = document.getElementById("processSopList");
      if (processSopList) {
        const sops = data.recommended_sops || [];

        if (sops.length) {
          processSopList.innerHTML = sops.map(sop => `
            <a href="/documents/${escapeHtml(sop.id)}"
              class="rounded-xl border border-gray-100 bg-gray-50 hover:bg-gray-100 transition p-4 block">
              <h3 class="font-semibold text-gray-900">${escapeHtml(sop.title)}</h3>
              <p class="text-sm text-gray-600 mt-1 leading-6">${escapeHtml(sop.reason)}</p>
            </a>
          `).join("");
        } else {
          processSopList.innerHTML = `
            <p class="text-sm text-gray-400">
              No matching SOPs found for this process yet.
            </p>`;
        }
      }

    } catch (err) {
      console.error(err);

      const processSummaryText = document.getElementById("processSummaryText");
      if (processSummaryText) {
        processSummaryText.innerHTML = `
          <p class="text-red-600">
            Could not generate the personalized process page.
          </p>
          <p class="text-xs text-gray-500">
            ${escapeHtml(err.message)}
          </p>
        `;
      }
    }
  }

  loadPersonalizedProcess();
})();

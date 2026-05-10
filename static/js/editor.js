/**
 * editor.js — SOP viewer page (/documents/<id>)
 * DOC_ID is injected by the Jinja template.
 */

let currentDoc = null;

async function loadDocument() {
  const res = await fetch(`/api/documents/${DOC_ID}`);
  if (!res.ok) { alert("Document not found."); return; }

  currentDoc = await res.json();

  document.getElementById("docTitle").textContent = currentDoc.title;
  document.getElementById("docMeta").textContent =
    `v${currentDoc.version}  ·  updated ${new Date(currentDoc.updated_at).toLocaleDateString()}`;

  // Step › StepType breadcrumb
  if (currentDoc.step_name) {
    document.getElementById("hStep").textContent = currentDoc.step_name;
    if (currentDoc.step_type_name && currentDoc.step_type_name !== currentDoc.step_name) {
      document.getElementById("hStepSep").classList.remove("hidden");
      document.getElementById("hStepType").textContent = currentDoc.step_type_name;
    }
  }

  document.getElementById("hCoral").textContent    = currentDoc.coral_name    || "—";
  document.getElementById("hLocation").textContent = currentDoc.location      || "—";
  document.getElementById("hCategory").textContent = currentDoc.category      || "—";
  document.getElementById("hContact").textContent  = currentDoc.contact       || "—";
  document.getElementById("hRevision").textContent = currentDoc.last_revision || "—";
  document.getElementById("hAuthor").textContent   = currentDoc.author        || "—";

  // Load PDF into iframe
  if (currentDoc.source_pdf) {
    document.getElementById("pdfViewer").src = `/documents/${DOC_ID}/pdf`;
  } else {
    document.getElementById("pdfViewer").classList.add("hidden");
    document.getElementById("noPdf").classList.remove("hidden");
  }

  renderRelated(currentDoc.related || {});
}

function renderRelated(related) {
  const el = document.getElementById("relatedList");
  el.innerHTML = "";
  const all = [
    ...(related.upstream   || []).map(d => ({ ...d, rel: "upstream" })),
    ...(related.downstream || []).map(d => ({ ...d, rel: "downstream" })),
    ...(related.similar    || []).map(d => ({ ...d, rel: "similar" })),
  ];
  if (!all.length) {
    el.innerHTML = '<p class="text-xs text-gray-400">No related SOPs linked yet.</p>';
    return;
  }
  all.forEach(doc => {
    const a = document.createElement("a");
    a.href = `/documents/${doc.id}`;
    a.className = "block text-blue-600 hover:underline text-sm";
    a.textContent = `${doc.title} (${doc.rel})`;
    el.appendChild(a);
  });
}

/* ── Content cleaner (display-side) ─────────────────── */
function cleanContent(md) {
  const pageHeader = /^Page\s+\d+\s+of\s+\d+\s*$/i;
  const lastRev    = /^Last\s+revision[:\s]/i;
  const version    = /^Version[:\s]+\S+\s*$/i;

  const lines = md.split("\n");

  // Find lines that repeat ≥ 40 % of total lines (running headers/footers)
  const freq = {};
  lines.forEach(l => {
    const t = l.trim();
    if (t.length > 3 && !t.startsWith("|"))
      freq[t] = (freq[t] || 0) + 1;
  });
  const threshold = Math.max(3, lines.length * 0.04);
  const repeated  = new Set(Object.keys(freq).filter(k => freq[k] >= threshold));

  const kept = [];
  let blanks = 0;
  for (const line of lines) {
    const t = line.trim();
    if (repeated.has(t) || pageHeader.test(t) || lastRev.test(t) || version.test(t)) continue;
    if (t === "") {
      if (++blanks <= 2) kept.push("");
    } else {
      blanks = 0;
      kept.push(line);
    }
  }
  return kept.join("\n");
}

/* ── PDF / Content toggle ────────────────────────────── */
function activateTab(tab) {
  const pdfEl     = document.getElementById("pdfViewer");
  const noPdfEl   = document.getElementById("noPdf");
  const contentEl = document.getElementById("contentView");
  const imagesEl  = document.getElementById("imagesView");
  const tabPdf    = document.getElementById("tabPdf");
  const tabContent= document.getElementById("tabContent");
  const tabImages = document.getElementById("tabImages");

  const active   = ["bg-white", "shadow", "text-gray-800"];
  const inactive = ["text-gray-500", "hover:text-gray-700"];

  // Hide everything, reset all tabs
  pdfEl.classList.add("hidden");
  noPdfEl.classList.add("hidden");
  contentEl.classList.add("hidden");
  imagesEl.classList.add("hidden");
  [tabPdf, tabContent, tabImages].forEach(t => {
    t.classList.remove(...active);
    t.classList.add(...inactive);
  });

  if (tab === "pdf") {
    pdfEl.classList.remove("hidden");
    tabPdf.classList.add(...active);
    tabPdf.classList.remove(...inactive);
  } else if (tab === "content") {
    contentEl.classList.remove("hidden");
    tabContent.classList.add(...active);
    tabContent.classList.remove(...inactive);
    if (currentDoc) renderFormattedContent();
  } else if (tab === "images") {
    imagesEl.classList.remove("hidden");
    tabImages.classList.add(...active);
    tabImages.classList.remove(...inactive);
    loadImagesTab();
  }
}

async function renderFormattedContent() {
  const el = document.getElementById("contentRendered");
  const cacheKey = `formatted_${DOC_ID}`;
  const cached = sessionStorage.getItem(cacheKey);

  if (cached) {
    el.innerHTML = marked.parse(cached);
    styleSopContent(el);
    return;
  }

  el.innerHTML = '<p style="font-size:0.8rem;color:#9ca3af;padding:1rem;">Formatting content…</p>';

  try {
    const res  = await fetch(`/api/documents/${DOC_ID}/formatted`);
    const data = await res.json();
    const md   = data.formatted || currentDoc.content || "_No content extracted._";
    sessionStorage.setItem(cacheKey, md);
    el.innerHTML = marked.parse(md);
  } catch {
    el.innerHTML = marked.parse(currentDoc.content || "_No content extracted._");
  }
  styleSopContent(el);
}

function styleSopContent(container) {
  const SECTION_MAP = {
    "introduction":  "introduction",
    "safety":        "safety",
    "qualification": "qualifications",
    "operating":     "procedure",
    "procedure":     "procedure",
    "appendix":      "appendix",
  };

  // Group child nodes into sections split by h2 headings
  const children = [...container.childNodes];
  const groups = [];   // [{ name, heading|null, nodes[] }]
  let current = null;

  children.forEach(node => {
    if (node.nodeName === "H2") {
      if (current) groups.push(current);
      const text = node.textContent.toLowerCase();
      let name = "generic";
      for (const [keyword, section] of Object.entries(SECTION_MAP)) {
        if (text.includes(keyword)) { name = section; break; }
      }
      current = { name, heading: node, nodes: [] };
    } else {
      if (!current) current = { name: "preamble", heading: null, nodes: [] };
      current.nodes.push(node);
    }
  });
  if (current) groups.push(current);

  // Rebuild container with styled section wrappers
  container.innerHTML = "";

  // Mini TOC
  const mainGroups = groups.filter(g => g.heading && g.name !== "preamble");
  if (mainGroups.length > 1) {
    const toc = document.createElement("nav");
    toc.className = "sop-toc";
    mainGroups.forEach((g, i) => {
      g.id = `sop-section-${i}`;
      const a = document.createElement("a");
      a.href = `#sop-section-${i}`;
      a.className = `toc-link toc-${g.name}`;
      a.textContent = g.heading.textContent.replace(/^\d+\s+/, "").trim();
      toc.appendChild(a);
    });
    container.appendChild(toc);
  }

  groups.forEach((g, i) => {
    const div = document.createElement("div");
    div.className = `sop-section section-${g.name}`;
    if (g.id) div.id = g.id;
    if (g.heading) div.appendChild(g.heading);
    g.nodes.forEach(n => div.appendChild(n));
    container.appendChild(div);
  });
}

const SECTION_LABELS = {
  introduction:   "Introduction",
  safety:         "Safety",
  qualifications: "Qualifications",
  procedure:      "Operating Procedures",
  appendix:       "Appendix",
};

const SECTION_COLORS = {
  introduction:   "bg-blue-50 text-blue-700",
  safety:         "bg-amber-50 text-amber-700",
  qualifications: "bg-purple-50 text-purple-700",
  procedure:      "bg-green-50 text-green-700",
  appendix:       "bg-gray-100 text-gray-600",
};

async function loadImagesTab() {
  const grid   = document.getElementById("imageGrid");
  const noImg  = document.getElementById("noImages");

  // Only fetch once per page load
  if (grid.dataset.loaded) return;
  grid.dataset.loaded = "1";
  grid.innerHTML = '<p class="text-xs text-gray-400 col-span-2">Loading images…</p>';

  let images;
  try {
    const res = await fetch(`/api/documents/${DOC_ID}/images`);
    images = await res.json();
  } catch {
    grid.innerHTML = '<p class="text-xs text-red-400 col-span-2">Failed to load images.</p>';
    return;
  }

  grid.innerHTML = "";
  if (!images.length) {
    noImg.classList.remove("hidden");
    return;
  }

  images.forEach(img => {
    const sectionLabel = SECTION_LABELS[img.section_name] || img.section_name;
    const sectionColor = SECTION_COLORS[img.section_name] || "bg-gray-100 text-gray-600";

    const card = document.createElement("div");
    card.className = "border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm flex flex-col";
    card.innerHTML = `
      <div class="bg-gray-50 flex items-center justify-center p-3" style="min-height:180px">
        <img src="${img.url}" alt="Page ${img.page_number + 1}"
             class="max-h-48 max-w-full object-contain rounded"
             id="imgEl-${img.id}">
      </div>
      <div class="p-3 flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <span class="text-xs font-medium text-gray-500">Page ${img.page_number + 1}</span>
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${sectionColor}">${sectionLabel}</span>
        </div>
        <div class="text-xs text-gray-400">${img.width} × ${img.height} px${img.is_replaced ? ' · <span class="text-indigo-500">replaced</span>' : ''}</div>
        <label class="mt-1 cursor-pointer flex items-center justify-center gap-1.5 text-xs font-semibold
               text-indigo-600 border border-indigo-200 bg-indigo-50 hover:bg-indigo-100
               rounded-lg py-1.5 transition">
          ↑ Replace image
          <input type="file" accept="image/*" class="hidden"
                 onchange="replaceImage(${img.id}, this)">
        </label>
      </div>`;
    grid.appendChild(card);
  });
}

async function injectImages(container) {
  let images;
  try {
    const res = await fetch(`/api/documents/${DOC_ID}/images`);
    images = await res.json();
  } catch { return; }
  if (!images.length) return;

  images.forEach(img => {
    // Match by section_name — much more reliable than page-position ratio
    const sectionClass = `section-${img.section_name || "procedure"}`;
    const section = container.querySelector(`.${sectionClass}`)
                 || container.querySelector(".section-procedure")
                 || container.querySelector(".sop-section");

    const wrapper = document.createElement("div");
    wrapper.className = "sop-image-block";
    wrapper.dataset.imgId = img.id;

    const imgEl = document.createElement("img");
    imgEl.src   = img.url;
    imgEl.alt   = `Figure (page ${img.page_number + 1})`;
    imgEl.style.cssText = "max-width:100%;max-height:340px;object-fit:contain;border-radius:0.5rem;border:1px solid #e5e7eb;";

    const caption = document.createElement("div");
    caption.className = "sop-image-caption";
    caption.innerHTML = `
      <span>Page ${img.page_number + 1}${img.is_replaced ? " · <em>replaced</em>" : ""}</span>
      <label class="sop-replace-btn" title="Replace this image">
        ↑ Replace
        <input type="file" accept="image/*" style="display:none"
               onchange="replaceImage(${img.id}, this)">
      </label>`;

    wrapper.appendChild(imgEl);
    wrapper.appendChild(caption);
    section.appendChild(wrapper);
  });
}

async function replaceImage(imgId, input) {
  if (!input.files.length) return;
  const form = new FormData();
  form.append("file", input.files[0]);

  const res = await fetch(`/api/documents/${DOC_ID}/images/${imgId}/replace`, {
    method: "POST", body: form,
  });
  if (res.ok) {
    const updated = await res.json();
    const bust = "?t=" + Date.now();
    // Refresh in Images tab
    const tabImg = document.getElementById(`imgEl-${imgId}`);
    if (tabImg) tabImg.src = updated.url + bust;
    // Refresh in Content tab if injected there
    const inlineImg = document.querySelector(`[data-img-id="${imgId}"] img`);
    if (inlineImg) inlineImg.src = updated.url + bust;
    sessionStorage.removeItem(`formatted_${DOC_ID}`);
  }
}

document.getElementById("tabPdf").addEventListener("click",     () => activateTab("pdf"));
document.getElementById("tabContent").addEventListener("click", () => activateTab("content"));
document.getElementById("tabImages").addEventListener("click",  () => activateTab("images"));

/* ── AI Edit ─────────────────────────────────────────── */
document.getElementById("aiEditBtn").addEventListener("click", () => {
  document.getElementById("aiEditPanel").classList.toggle("hidden");
});

let _pendingEdit = null;  // { full_content, original_snippet, replacement, summary, edit_type }

document.getElementById("runAiEdit").addEventListener("click", async () => {
  const desc = document.getElementById("editDescription").value.trim();
  if (!desc) return;

  const status = document.getElementById("aiEditStatus");
  const result = document.getElementById("aiEditResult");
  status.classList.remove("hidden");
  result.classList.add("hidden");

  const res = await fetch("/api/changes/suggest-edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: DOC_ID, edit_description: desc }),
  });
  const data = await res.json();
  status.classList.add("hidden");

  if (data.suggested_content) {
    _pendingEdit = data;

    // Show diff view if we have a specific snippet, otherwise show full content
    const diffEl = document.getElementById("aiEditDiff");
    const fullEl = document.getElementById("aiEditContent");

    if (data.original_snippet && data.replacement) {
      document.getElementById("diffOriginal").textContent  = data.original_snippet;
      document.getElementById("diffReplacement").textContent = data.replacement;
      if (data.summary) document.getElementById("diffSummary").textContent = data.summary;
      diffEl.classList.remove("hidden");
      fullEl.classList.add("hidden");
    } else {
      fullEl.textContent = data.suggested_content;
      diffEl.classList.add("hidden");
      fullEl.classList.remove("hidden");
    }

    result.classList.remove("hidden");
  }
});

document.getElementById("applyAiEdit").addEventListener("click", async () => {
  const newContent      = _pendingEdit?.full_content
    || document.getElementById("aiEditContent").textContent;
  const description     = document.getElementById("editDescription").value.trim();
  const origSnippet     = _pendingEdit?.original_snippet || "";
  const origReplacement = _pendingEdit?.replacement || "";
  const origEditType    = _pendingEdit?.edit_type || "replace";

  const res = await fetch("/api/changes/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: DOC_ID, new_content: newContent, description }),
  });
  const change = await res.json();

  await fetch(`/api/changes/${change.id}/apply`, { method: "POST" });

  // Clear cached formatted content so Current Version shows the new text
  sessionStorage.removeItem(`formatted_${DOC_ID}`);

  // Reload document metadata
  await loadDocument();

  document.getElementById("aiEditResult").classList.add("hidden");
  document.getElementById("editDescription").value = "";
  _pendingEdit = null;

  // If the doc has a PDF, load annotated version and switch to PDF tab
  if (currentDoc?.source_pdf) {
    const snippet = encodeURIComponent(origSnippet);
    const repl    = encodeURIComponent(origReplacement);
    const etype   = encodeURIComponent(origEditType);
    document.getElementById("pdfViewer").src =
      `/api/changes/${change.id}/annotated-pdf?snippet=${snippet}&replacement=${repl}&edit_type=${etype}`;
    document.getElementById("annotatedBadge").classList.remove("hidden");
    activateTab("pdf");   // show PDF tab so the highlight is actually visible
  } else {
    activateTab("content");
  }

  loadChangeHistory();

  if (change.proposals?.length) {
    renderProposals(change.proposals);
  }
});

document.getElementById("discardAiEdit").addEventListener("click", () => {
  document.getElementById("aiEditResult").classList.add("hidden");
  _pendingEdit = null;
});

document.getElementById("resetPdfBtn")?.addEventListener("click", () => {
  document.getElementById("pdfViewer").src = `/documents/${DOC_ID}/pdf`;
  document.getElementById("annotatedBadge").classList.add("hidden");
});

function renderProposals(proposals) {
  const section = document.getElementById("proposalsSection");
  const list    = document.getElementById("proposalsList");
  list.innerHTML = "";
  section.classList.remove("hidden");

  const tmpl = document.getElementById("proposalCard");
  proposals.forEach(p => {
    const card = tmpl.content.cloneNode(true);
    card.querySelector(".proposal-target").textContent   = `Doc ID ${p.target_document_id}`;
    card.querySelector(".proposal-reason").textContent   = p.reason;
    card.querySelector(".proposal-original").textContent = p.original_section;
    card.querySelector(".proposal-proposed").textContent = p.proposed_section;
    card.querySelector(".proposal-confidence").textContent = `Confidence: ${Math.round(p.confidence * 100)}%`;

    const el = card.querySelector("div");
    card.querySelector(".apply-btn").addEventListener("click", async () => {
      await fetch(`/api/changes/proposals/${p.id}/apply`, { method: "POST" });
      el.style.opacity = "0.4";
    });
    card.querySelector(".reject-btn").addEventListener("click", async () => {
      await fetch(`/api/changes/proposals/${p.id}/reject`, { method: "POST" });
      el.style.opacity = "0.4";
    });
    list.appendChild(card);
  });
}

/* ── Study Guide ─────────────────────────────────────── */
async function loadRoles() {
  const res   = await fetch("/api/summaries/roles");
  const roles = await res.json();
  const sel   = document.getElementById("roleSelect");
  sel.innerHTML = roles.map(r =>
    `<option value="${r.value}">${r.label}</option>`
  ).join("");

  const profile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");
  const roleMap = {
    "student": "student",
    "fab operator": "technician", "manufacturing technician": "technician",
    "process technician": "technician",
    "process engineer": "process_engineer",
    "equipment engineer": "mechanical_engineer",
  };
  const currentRole = (profile.current_role || "").toLowerCase();
  for (const [keyword, value] of Object.entries(roleMap)) {
    if (currentRole.includes(keyword)) { sel.value = value; break; }
  }
}

function triggerSummary() {
  document.getElementById("generateSummaryBtnSidebar").click();
}

document.getElementById("generateSummaryBtn")?.addEventListener("click", triggerSummary);

document.getElementById("generateSummaryBtnSidebar").addEventListener("click", async () => {
  const role         = document.getElementById("roleSelect").value;
  const status       = document.getElementById("summaryStatus");
  const errorEl      = document.getElementById("summaryError");
  const extraContext = document.getElementById("studyGuideContext").value.trim();
  const profile      = JSON.parse(sessionStorage.getItem("userProfile") || "{}");

  errorEl.classList.add("hidden");
  status.classList.remove("hidden");
  document.getElementById("generateSummaryBtnSidebar").disabled = true;

  try {
    const res = await fetch(`/api/summaries/${DOC_ID}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, user_profile: profile, extra_context: extraContext }),
    });

    if (!res.ok) {
      throw new Error(`Server error ${res.status}`);
    }

    const data = await res.json();
    if (data.error) throw new Error(data.error);

    document.getElementById("summaryModalTitle").textContent = `${data.role_label} Study Guide`;
    document.getElementById("summaryModalSubtitle").textContent = currentDoc?.title || "";
    document.getElementById("summaryContent").innerHTML = marked.parse(data.summary);
    document.getElementById("summaryModal").classList.remove("hidden");
    document.body.style.overflow = "hidden";
  } catch (err) {
    errorEl.textContent = `Failed to generate: ${err.message}`;
    errorEl.classList.remove("hidden");
  } finally {
    status.classList.add("hidden");
    document.getElementById("generateSummaryBtnSidebar").disabled = false;
  }
});

document.getElementById("closeSummaryModal").addEventListener("click", () => {
  document.getElementById("summaryModal").classList.add("hidden");
  document.body.style.overflow = "";
});

document.getElementById("copySummaryBtn").addEventListener("click", () => {
  const text = document.getElementById("summaryContent").innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById("copySummaryBtn");
    btn.textContent = "Copied!";
    setTimeout(() => btn.textContent = "Copy", 2000);
  });
});

document.getElementById("printSummaryBtn").addEventListener("click", () => {
  const title   = document.getElementById("summaryModalTitle").textContent;
  const docName = document.getElementById("summaryModalSubtitle").textContent;
  const content = document.getElementById("summaryContent").innerHTML;
  const win = window.open("", "_blank", "width=800,height=900");
  win.document.write(`<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <title>${title}</title>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 700px; margin: 40px auto; color: #1f2937; line-height: 1.6; }
      h1 { font-size: 1.25rem; margin-bottom: 0.25rem; }
      .sub { color: #6b7280; font-size: 0.8rem; margin-bottom: 1.5rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.75rem; }
      h2 { font-size: 1rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem; }
      h3 { font-size: 0.9rem; font-weight: 600; color: #7c3aed; margin-top: 1rem; margin-bottom: 0.25rem; }
      ul, ol { padding-left: 1.5rem; } li { margin: 0.2rem 0; }
      blockquote { border-left: 3px solid #a855f7; background: #faf5ff; padding: 0.5rem 1rem; margin: 0.75rem 0; color: #581c87; border-radius: 0 0.25rem 0.25rem 0; }
      table { border-collapse: collapse; width: 100%; font-size: 0.85rem; } th, td { border: 1px solid #d1d5db; padding: 0.4rem 0.6rem; text-align: left; } th { background: #f3f4f6; }
      code { background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 0.25rem; font-size: 0.85em; }
      strong { color: #111827; }
    </style>
  </head><body>
    <h1>${title}</h1><p class="sub">${docName}</p>
    ${content}
  </body></html>`);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 400);
});

/* ── Change History ──────────────────────────────────── */
async function loadChangeHistory() {
  const el = document.getElementById("changeHistoryList");
  let changes;
  try {
    const res = await fetch(`/api/changes/?doc_id=${DOC_ID}`);
    changes = await res.json();
  } catch {
    el.innerHTML = '<p class="text-xs text-red-400">Failed to load history.</p>';
    return;
  }

  if (!changes.length) {
    el.innerHTML = '<p class="text-xs text-gray-400">No changes recorded yet.</p>';
    return;
  }

  el.innerHTML = "";
  changes.forEach(c => {
    const div = document.createElement("div");
    div.className = "bg-white border border-gray-200 rounded-lg p-2.5 text-xs space-y-1";
    const date = new Date(c.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    const statusColor = c.status === "applied" ? "text-green-600 bg-green-50" : "text-gray-500 bg-gray-100";

    div.innerHTML = `
      <div class="flex justify-between items-start gap-1">
        <span class="text-gray-800 font-medium leading-snug">${c.description || "(no description)"}</span>
        <span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${statusColor}">${c.status}</span>
      </div>
      <div class="flex justify-between items-center text-gray-400">
        <span>${date}</span>
        <button data-change-id="${c.id}" class="view-change-pdf text-blue-500 hover:underline">View PDF</button>
      </div>
    `;
    div.querySelector(".view-change-pdf").addEventListener("click", () => {
      document.getElementById("pdfViewer").src = `/api/changes/${c.id}/annotated-pdf`;
      document.getElementById("annotatedBadge").classList.remove("hidden");
      activateTab("pdf");
    });
    el.appendChild(div);
  });
}

/* ── Init ────────────────────────────────────────────── */
loadDocument();
loadRoles();
loadChangeHistory();

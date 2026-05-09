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

/* ── AI Edit ─────────────────────────────────────────── */
document.getElementById("aiEditBtn").addEventListener("click", () => {
  document.getElementById("aiEditPanel").classList.toggle("hidden");
});

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
    document.getElementById("aiEditContent").textContent = data.suggested_content;
    result.classList.remove("hidden");
  }
});

document.getElementById("applyAiEdit").addEventListener("click", async () => {
  const newContent = document.getElementById("aiEditContent").textContent;
  const description = document.getElementById("editDescription").value.trim();

  const res = await fetch("/api/changes/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: DOC_ID, new_content: newContent, description }),
  });
  const change = await res.json();

  await fetch(`/api/changes/${change.id}/apply`, { method: "POST" });

  document.getElementById("aiEditResult").classList.add("hidden");
  document.getElementById("editDescription").value = "";

  if (change.proposals?.length) {
    renderProposals(change.proposals);
  }
});

document.getElementById("discardAiEdit").addEventListener("click", () => {
  document.getElementById("aiEditResult").classList.add("hidden");
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
  const role    = document.getElementById("roleSelect").value;
  const status  = document.getElementById("summaryStatus");
  const profile = JSON.parse(sessionStorage.getItem("userProfile") || "{}");

  status.classList.remove("hidden");
  document.getElementById("generateSummaryBtnSidebar").disabled = true;

  try {
    const res = await fetch(`/api/summaries/${DOC_ID}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, user_profile: profile }),
    });
    const data = await res.json();

    document.getElementById("summaryModalTitle").textContent = `${data.role_label} Study Guide`;
    document.getElementById("summaryModalSubtitle").textContent = currentDoc?.title || "";
    document.getElementById("summaryContent").innerHTML = marked.parse(data.summary);
    document.getElementById("summaryModal").classList.remove("hidden");
    document.body.style.overflow = "hidden";
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

/* ── Init ────────────────────────────────────────────── */
loadDocument();
loadRoles();

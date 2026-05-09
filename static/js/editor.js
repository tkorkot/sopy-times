/**
 * editor.js — handles the single-SOP editor page.
 * DOC_ID is injected by the Jinja template before this script loads.
 */

let currentDoc = null;
let activeChangeId = null;

async function loadDocument() {
  const res = await fetch(`/api/documents/${DOC_ID}`);
  if (!res.ok) { alert("Document not found."); return; }

  currentDoc = await res.json();

  document.getElementById("docTitle").textContent = currentDoc.title;
  document.getElementById("docMeta").textContent =
    `v${currentDoc.version}  ·  updated ${new Date(currentDoc.updated_at).toLocaleDateString()}`;
  document.getElementById("hCoral").textContent    = currentDoc.coral_name    || "—";
  document.getElementById("hLocation").textContent = currentDoc.location      || "—";
  document.getElementById("hCategory").textContent = currentDoc.category      || "—";
  document.getElementById("hContact").textContent  = currentDoc.contact       || "—";
  document.getElementById("hRevision").textContent = currentDoc.last_revision || "—";
  document.getElementById("hAuthor").textContent   = currentDoc.author        || "—";
  document.getElementById("contentEditor").value = currentDoc.content;

  renderRelated(currentDoc.related || {});
}

function renderRelated(related) {
  const el = document.getElementById("relatedList");
  el.innerHTML = "";
  const all = [
    ...(related.upstream   || []).map(d => ({ ...d, type: "upstream" })),
    ...(related.downstream || []).map(d => ({ ...d, type: "downstream" })),
    ...(related.similar    || []).map(d => ({ ...d, type: "similar" })),
  ];
  if (!all.length) {
    el.innerHTML = '<p class="text-xs text-gray-400">No related SOPs linked yet.</p>';
    return;
  }
  all.forEach(doc => {
    const a = document.createElement("a");
    a.href = `/documents/${doc.id}`;
    a.className = "block text-blue-600 hover:underline text-sm";
    a.textContent = `${doc.title} (${doc.type})`;
    el.appendChild(a);
  });
}

/* ── Save button ─────────────────────────────────────── */
document.getElementById("saveBtn").addEventListener("click", async () => {
  const newContent = document.getElementById("contentEditor").value;
  const description = prompt("Briefly describe this change (used for AI propagation):");
  if (description === null) return;  // user cancelled

  document.getElementById("saveBtn").textContent = "Saving…";

  const res = await fetch("/api/changes/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id: DOC_ID,
      new_content: newContent,
      description,
    }),
  });

  const change = await res.json();
  activeChangeId = change.id;

  // Apply the change to the document immediately
  await fetch(`/api/changes/${change.id}/apply`, { method: "POST" });

  document.getElementById("saveBtn").textContent = "Save Changes";
  document.getElementById("proposalsEmpty").classList.add("hidden");
  renderProposals(change.proposals || []);
  await loadDocument();
});

/* ── Proposals ────────────────────────────────────────── */
function renderProposals(proposals) {
  const list = document.getElementById("proposalsList");
  list.innerHTML = "";

  if (!proposals.length) {
    document.getElementById("proposalsEmpty").classList.remove("hidden");
    document.getElementById("proposalsEmpty").textContent =
      "AI found no related changes needed in other SOPs.";
    return;
  }

  const tmpl = document.getElementById("proposalCard");
  proposals.forEach(p => {
    const card = tmpl.content.cloneNode(true);
    card.querySelector(".proposal-target").textContent = `Doc ID ${p.target_document_id}`;
    card.querySelector(".proposal-reason").textContent = p.reason;
    card.querySelector(".proposal-original").textContent = p.original_section;
    card.querySelector(".proposal-proposed").textContent = p.proposed_section;
    card.querySelector(".proposal-confidence").textContent =
      `Confidence: ${Math.round(p.confidence * 100)}%`;

    const el = card.querySelector("div");  // outermost div of cloned card

    card.querySelector(".apply-btn").addEventListener("click", async () => {
      await fetch(`/api/changes/proposals/${p.id}/apply`, { method: "POST" });
      el.style.opacity = "0.4";
      el.querySelector(".apply-btn").textContent = "Applied ✓";
    });

    card.querySelector(".reject-btn").addEventListener("click", async () => {
      await fetch(`/api/changes/proposals/${p.id}/reject`, { method: "POST" });
      el.style.opacity = "0.4";
      el.querySelector(".reject-btn").textContent = "Rejected";
    });

    list.appendChild(card);
  });
}

/* ── AI Edit panel ────────────────────────────────────── */
document.getElementById("aiEditBtn").addEventListener("click", () => {
  document.getElementById("aiEditPanel").classList.toggle("hidden");
});

document.getElementById("runAiEdit").addEventListener("click", async () => {
  const desc = document.getElementById("editDescription").value.trim();
  if (!desc) return;

  const status = document.getElementById("aiEditStatus");
  status.classList.remove("hidden");

  const res = await fetch("/api/changes/suggest-edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: DOC_ID, edit_description: desc }),
  });

  const data = await res.json();
  status.classList.add("hidden");

  if (data.suggested_content) {
    document.getElementById("contentEditor").value = data.suggested_content;
    document.getElementById("aiEditPanel").classList.add("hidden");
  }
});

/* ── Init ────────────────────────────────────────────── */
loadDocument();

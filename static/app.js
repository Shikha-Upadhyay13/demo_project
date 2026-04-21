// AdaptivAI Mini — vanilla JS.
// Two entry points:
//   renderCatalogPage() — index.html
//   renderCoursePage()  — course.html

// ---------- shared ----------

async function streamSSE(url, body, onEvent) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error("Stream failed: " + res.status);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const parsed = parseSSEBlock(block);
      if (parsed) onEvent(parsed.event, parsed.data);
    }
  }
}
function parseSSEBlock(block) {
  if (!block.trim()) return null;
  let event = "message", data = "";
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  try { return { event, data: data ? JSON.parse(data) : {} }; }
  catch { return { event, data: {} }; }
}
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---------- topic theming ----------
//
// Stable per-topic gradient + emoji picker. Makes the catalog feel alive
// without shipping a design system.
const TOPIC_ICONS = [
  { kw: ["docker", "container"], emoji: "🐳" },
  { kw: ["react", "jsx", "hook"], emoji: "⚛️" },
  { kw: ["python", "decorator", "django", "flask"], emoji: "🐍" },
  { kw: ["kubernetes", "k8s", "pod", "helm"], emoji: "☸️" },
  { kw: ["git", "rebase", "merge"], emoji: "🌿" },
  { kw: ["graphql", "apollo"], emoji: "🔗" },
  { kw: ["rust", "cargo"], emoji: "🦀" },
  { kw: ["go", "golang"], emoji: "🐹" },
  { kw: ["node", "express", "npm"], emoji: "🟢" },
  { kw: ["typescript"], emoji: "🔷" },
  { kw: ["javascript", " js"], emoji: "💛" },
  { kw: ["rag", "llm", "embedding", "agent", "langchain"], emoji: "🤖" },
  { kw: ["sql", "postgres", "mysql", "database", "db"], emoji: "🗃️" },
  { kw: ["aws", "cloud", "lambda", "s3"], emoji: "☁️" },
  { kw: ["css", "tailwind", "design"], emoji: "🎨" },
  { kw: ["security", "auth", "jwt", "oauth"], emoji: "🔒" },
  { kw: ["test", "ci", "cd", "pipeline"], emoji: "⚙️" },
  { kw: ["api", "rest", "http"], emoji: "🔌" },
  { kw: ["ml", "pytorch", "tensorflow", "neural", "model"], emoji: "🧠" },
];
const GRADIENTS = [
  "linear-gradient(135deg, #6366f1 0%, #8b5cf6 60%, #d946ef 100%)",
  "linear-gradient(135deg, #0ea5e9 0%, #6366f1 60%, #8b5cf6 100%)",
  "linear-gradient(135deg, #10b981 0%, #14b8a6 60%, #0ea5e9 100%)",
  "linear-gradient(135deg, #f59e0b 0%, #ef4444 60%, #ec4899 100%)",
  "linear-gradient(135deg, #8b5cf6 0%, #ec4899 60%, #f97316 100%)",
  "linear-gradient(135deg, #0891b2 0%, #06b6d4 60%, #22d3ee 100%)",
  "linear-gradient(135deg, #4f46e5 0%, #ec4899 60%, #f97316 100%)",
];
function themeFor(topic) {
  const t = (topic || "").toLowerCase();
  const entry = TOPIC_ICONS.find((e) => e.kw.some((k) => t.includes(k)));
  const emoji = entry ? entry.emoji : "✨";
  let h = 0;
  for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) >>> 0;
  const gradient = GRADIENTS[h % GRADIENTS.length];
  return { emoji, gradient };
}

// ========================================================================
// CATALOG PAGE
// ========================================================================

async function renderCatalogPage() {
  const grid = document.getElementById("catalog-grid");
  const empty = document.getElementById("catalog-empty");
  const count = document.getElementById("catalog-count");
  try {
    const res = await fetch("/api/catalog");
    const courses = await res.json();
    if (!courses.length) {
      empty.classList.remove("hidden");
    } else {
      empty.classList.add("hidden");
      grid.innerHTML = courses.map(courseCardHtml).join("");
      count.textContent = `${courses.length} course${courses.length === 1 ? "" : "s"}`;
      count.classList.remove("hidden");
    }
  } catch {
    empty.textContent = "Failed to load catalog.";
    empty.classList.remove("hidden");
  }

  document.getElementById("topbar-form").addEventListener("submit", onSubmitTopic);
  document.getElementById("hero-form").addEventListener("submit", onSubmitTopic);
  document.querySelectorAll("[data-chip]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const topic = btn.dataset.chip;
      const input = document.querySelector('#hero-form input[name="topic"]');
      input.value = topic;
      document.getElementById("hero-form").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    });
  });
}

function courseCardHtml(c) {
  const when = c.created_at ? timeAgo(c.created_at) : "";
  const { emoji, gradient } = themeFor(c.topic);
  return `
    <a href="/course/${encodeURIComponent(c.course_id)}" class="course-card">
      <div class="course-card-header" style="background: ${gradient}">
        <span class="course-card-emoji">${emoji}</span>
      </div>
      <div class="course-card-body">
        <div class="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Course</div>
        <div class="mt-1 course-card-topic">${escapeHtml(c.topic)}</div>
        <div class="course-card-meta">
          <span>${c.video_count} video${c.video_count === 1 ? "" : "s"} · ${escapeHtml(when)}</span>
          <span class="course-card-cta">View →</span>
        </div>
      </div>
    </a>
  `;
}

function timeAgo(iso) {
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  if (diff < 86400 * 30) return Math.floor(diff / 86400) + "d ago";
  return new Date(iso).toLocaleDateString();
}

async function onSubmitTopic(e) {
  e.preventDefault();
  const input = e.target.querySelector('input[name="topic"]');
  const topic = (input.value || "").trim();
  if (!topic) return;

  const overlay = document.getElementById("gen-overlay");
  const steps = document.getElementById("gen-steps");
  const topicLbl = document.getElementById("gen-topic");
  const errBox = document.getElementById("gen-error");
  errBox.classList.add("hidden"); errBox.textContent = "";

  const NODE_LABELS = {
    video_finder: "Searching for the best videos",
    transcript_fetcher: "Fetching transcripts",
    chunker_embedder: "Indexing knowledge",
  };
  const seen = new Set();
  steps.innerHTML = Object.entries(NODE_LABELS)
    .map(([k, v]) => `<li class="step-todo" data-step="${k}">${v}</li>`)
    .join("");
  topicLbl.textContent = topic;
  overlay.classList.remove("hidden");
  overlay.classList.add("flex");

  try {
    await streamSSE("/api/courses/generate", { topic }, (event, data) => {
      if (event === "status" && data.node && NODE_LABELS[data.node]) {
        steps.querySelectorAll("li").forEach((li) => {
          if (seen.has(li.dataset.step)) li.className = "step-done";
        });
        const li = steps.querySelector(`[data-step="${data.node}"]`);
        if (li) li.className = "step-doing";
        seen.add(data.node);
      } else if (event === "complete" && data.course_id) {
        steps.querySelectorAll("li").forEach((li) => (li.className = "step-done"));
        window.location.href = "/course/" + encodeURIComponent(data.course_id);
      } else if (event === "error") {
        errBox.textContent = data.message || "Generation failed.";
        errBox.classList.remove("hidden");
      }
    });
  } catch (err) {
    errBox.textContent = "Stream failed: " + err.message;
    errBox.classList.remove("hidden");
  }
}

// ========================================================================
// COURSE PAGE
// ========================================================================

let COURSE = null;

async function renderCoursePage() {
  const courseId = decodeURIComponent(location.pathname.split("/").pop());
  const res = await fetch("/api/courses/" + encodeURIComponent(courseId));
  if (!res.ok) {
    document.getElementById("course-title").textContent = "Course not found";
    return;
  }
  COURSE = await res.json();

  const { emoji, gradient } = themeFor(COURSE.topic);

  document.getElementById("course-topic").textContent = COURSE.topic;
  document.getElementById("course-title").innerHTML =
    `<span style="font-size: 0.85em; margin-right: 10px;">${emoji}</span>${escapeHtml(COURSE.topic)}`;
  document.getElementById("course-video-count").textContent =
    `${(COURSE.videos || []).length} videos`;
  document.getElementById("course-created").textContent = timeAgo(COURSE.created_at);

  // Apply theme gradient to the course header bar on the left of the chip
  const header = document.querySelector(".course-header");
  if (header) header.style.background = `
    linear-gradient(135deg, rgba(255,255,255,0.8), rgba(255,255,255,0.3)),
    ${gradient}
  `;

  renderVideos(COURSE.videos || []);

  // Render cached summary / quiz if already present.
  if (COURSE.summary) showSummary(COURSE.summary);
  if ((COURSE.quiz || []).length) showQuiz(COURSE.quiz);

  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Lazy generation
  document.getElementById("gen-summary-btn").addEventListener("click", () => generateSummary());
  document.getElementById("gen-quiz-btn").addEventListener("click", () => generateQuiz());

  // Chat
  document.getElementById("chat-form").addEventListener("submit", onSendChat);
  document.getElementById("quiz-submit").addEventListener("click", onSubmitQuiz);
}

function renderVideos(videos) {
  const transcripts = COURSE.transcripts || [];
  const root = document.getElementById("videos");
  root.innerHTML = videos
    .map((v, i) => {
      const transcript = transcripts[i] || "";
      return `
        <article class="video-card">
          <div class="aspect-video w-full bg-black">
            <iframe src="https://www.youtube.com/embed/${escapeHtml(v.id)}" title="${escapeHtml(v.title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
          </div>
          <div class="p-4">
            <div class="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Video ${i + 1} · ${escapeHtml(v.channel || "")}</div>
            <div class="mt-1 font-medium">${escapeHtml(v.title)}</div>
            <details class="mt-3 text-sm text-slate-600">
              <summary class="inline-flex items-center gap-1 text-indigo-600">
                <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                Show transcript
              </summary>
              <pre class="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">${escapeHtml(transcript)}</pre>
            </details>
          </div>
        </article>
      `;
    })
    .join("");
}

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("tab-active", b.dataset.tab === tab);
  });
  document.querySelectorAll("[data-tab-panel]").forEach((p) => {
    const show = p.dataset.tabPanel === tab;
    p.classList.toggle("hidden", !show);
    // chat panel uses flex column
    if (p.dataset.tabPanel === "chat" && show) p.classList.add("chat-wrap");
  });
}

// ---------- lazy summary ----------

async function generateSummary() {
  document.getElementById("summary-empty").classList.add("hidden");
  document.getElementById("summary-loading").classList.remove("hidden");
  try {
    const res = await fetch(
      "/api/courses/" + encodeURIComponent(COURSE.course_id) + "/generate-summary",
      { method: "POST" },
    );
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    COURSE.summary = data.summary;
    showSummary(data.summary);
  } catch (e) {
    document.getElementById("summary-loading").classList.add("hidden");
    document.getElementById("summary-empty").classList.remove("hidden");
    alert("Summary generation failed. Try again.");
  }
}
function showSummary(markdown) {
  document.getElementById("summary-empty").classList.add("hidden");
  document.getElementById("summary-loading").classList.add("hidden");
  const el = document.getElementById("summary-content");
  el.innerHTML = window.marked ? window.marked.parse(markdown || "") : escapeHtml(markdown);
  el.classList.remove("hidden");
}

// ---------- lazy quiz ----------

async function generateQuiz() {
  document.getElementById("quiz-empty").classList.add("hidden");
  document.getElementById("quiz-loading").classList.remove("hidden");
  try {
    const res = await fetch(
      "/api/courses/" + encodeURIComponent(COURSE.course_id) + "/generate-quiz",
      { method: "POST" },
    );
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    COURSE.quiz = data.quiz;
    showQuiz(data.quiz);
  } catch (e) {
    document.getElementById("quiz-loading").classList.add("hidden");
    document.getElementById("quiz-empty").classList.remove("hidden");
    alert("Quiz generation failed. Try again.");
  }
}
function showQuiz(quiz) {
  document.getElementById("quiz-empty").classList.add("hidden");
  document.getElementById("quiz-loading").classList.add("hidden");
  document.getElementById("quiz-body").classList.remove("hidden");

  const form = document.getElementById("quiz-form");
  form.innerHTML = quiz
    .map((q, i) => {
      const opts = q.options
        .map(
          (opt, j) => `
            <label class="quiz-option">
              <input type="radio" name="q${i}" value="${j}" />
              <span>${escapeHtml(opt)}</span>
            </label>`,
        )
        .join("");
      return `
        <fieldset>
          <legend class="mb-2 text-sm font-medium">${i + 1}. ${escapeHtml(q.q)}</legend>
          <div class="space-y-2">${opts}</div>
        </fieldset>`;
    })
    .join("");
}

// ---------- chat ----------

async function onSendChat(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = (input.value || "").trim();
  if (!msg) return;
  input.value = "";

  // Remove empty placeholder if present.
  const empty = document.querySelector(".chat-empty");
  if (empty) empty.remove();

  appendBubble("user", msg);
  const placeholder = appendBubble("ai", "");
  const answerSpan = placeholder.querySelector(".bubble-text");

  try {
    await streamSSE(
      "/api/courses/" + encodeURIComponent(COURSE.course_id) + "/chat",
      { message: msg },
      (event, data) => {
        if (event === "route") {
          const chip = document.createElement("div");
          chip.className = "route-chip " + data.route;
          chip.textContent = "router → " + data.route;
          placeholder.prepend(chip);
          if (data.route === "unclear") placeholder.querySelector(".bubble").classList.add("clarify");
        } else if (event === "token") {
          answerSpan.textContent += data.text;
          autoScrollChat();
        } else if (event === "error") {
          answerSpan.textContent = "(error: " + data.message + ")";
        }
      },
    );
  } catch {
    answerSpan.textContent = "(stream failed)";
  }
}

function autoScrollChat() {
  const root = document.getElementById("chat-messages");
  root.scrollTop = root.scrollHeight;
}

function appendBubble(role, initialText) {
  const root = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "flex flex-col " + (role === "user" ? "items-end" : "items-start");
  wrap.innerHTML = `<div class="bubble bubble-${role}"><span class="bubble-text">${escapeHtml(initialText)}</span></div>`;
  root.appendChild(wrap);
  autoScrollChat();
  return wrap;
}

// ---------- quiz grading ----------

async function onSubmitQuiz() {
  const form = document.getElementById("quiz-form");
  const quiz = COURSE.quiz || [];
  const answers = [];
  for (let i = 0; i < quiz.length; i++) {
    const sel = form.querySelector(`input[name="q${i}"]:checked`);
    answers.push(sel ? Number(sel.value) : -1);
  }
  if (answers.some((a) => a < 0)) {
    alert("Please answer every question first.");
    return;
  }

  const res = await fetch(
    "/api/courses/" + encodeURIComponent(COURSE.course_id) + "/quiz/grade",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }) },
  );
  if (!res.ok) { alert("Failed to grade quiz."); return; }
  const data = await res.json();

  const out = document.getElementById("quiz-result");
  out.classList.remove("hidden");
  const pct = Math.round((data.score / data.total) * 100);
  out.innerHTML = `
    <div class="mb-4 rounded-xl bg-gradient-to-br from-indigo-50 to-violet-50 p-4 border border-indigo-100">
      <div class="text-xs font-semibold uppercase tracking-wider text-indigo-600">Your score</div>
      <div class="mt-1 text-2xl font-bold text-slate-900">${data.score} / ${data.total} <span class="text-sm font-medium text-slate-500">(${pct}%)</span></div>
    </div>
    <ol class="space-y-2 text-sm">
      ${data.feedback
        .map((f, i) => {
          const q = quiz[i];
          const correct = q.options[f.correct_idx];
          return `
            <li class="${f.correct ? "quiz-feedback-correct" : "quiz-feedback-wrong"}">
              <div class="font-medium text-slate-900">${i + 1}. ${escapeHtml(q.q)}</div>
              <div class="mt-1 text-xs ${f.correct ? "text-emerald-700" : "text-rose-700"}">${f.correct ? "✓ Correct" : "✗ Incorrect"} · Answer: <b>${escapeHtml(correct)}</b></div>
              <div class="mt-1 text-xs text-slate-600">${escapeHtml(f.explanation)}</div>
            </li>`;
        })
        .join("")}
    </ol>
  `;
}

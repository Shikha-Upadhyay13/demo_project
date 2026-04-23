// AdaptivAI Mini — vanilla JS.
// Entry points (one per HTML page):
//   renderLoginPage()    — login.html
//   renderHomePage()     — index.html (hero + recent courses)
//   renderSectionPage()  — catalog.html, my-courses.html, bookmarks.html
//   renderCoursePage()   — course.html

// ========================================================================
// User / bookmark / owned-courses state in localStorage
// ========================================================================

const USER_KEY = "adaptivai:user";
const OWNED_KEY = "adaptivai:owned";
const BOOKMARKS_KEY = "adaptivai:bookmarks";
const AVATAR_EMOJIS = ["🦊","🐼","🦄","🐙","🐸","🦁","🐯","🐵","🐨","🦉","🐺","🐢","🐲","🦖","🐳","🦜"];

function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); }
  catch { return null; }
}
function setUser(u) { localStorage.setItem(USER_KEY, JSON.stringify(u)); }
function logout() { localStorage.removeItem(USER_KEY); window.location.href = "/login"; }

function getOwned() {
  try { return JSON.parse(localStorage.getItem(OWNED_KEY) || "[]"); }
  catch { return []; }
}
function addOwned(courseId) {
  const set = new Set(getOwned());
  set.add(courseId);
  localStorage.setItem(OWNED_KEY, JSON.stringify([...set]));
}

function getBookmarks() {
  try { return JSON.parse(localStorage.getItem(BOOKMARKS_KEY) || "[]"); }
  catch { return []; }
}
function toggleBookmark(courseId) {
  const set = new Set(getBookmarks());
  if (set.has(courseId)) set.delete(courseId);
  else set.add(courseId);
  localStorage.setItem(BOOKMARKS_KEY, JSON.stringify([...set]));
  return set.has(courseId);
}
function isBookmarked(courseId) { return getBookmarks().includes(courseId); }

// ========================================================================
// SHARED SSE + HTML utils
// ========================================================================

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

// ========================================================================
// Topic theming (unchanged visual identity)
// ========================================================================

const TOPIC_ICONS = [
  { kw: ["docker", "container"], emoji: "🐳" },
  { kw: ["react", "jsx", "hook"], emoji: "⚛️" },
  { kw: ["python", "decorator", "django", "flask"], emoji: "🐍" },
  { kw: ["kubernetes", "k8s", "pod", "helm"], emoji: "☸️" },
  { kw: ["git", "rebase", "merge"], emoji: "🌿" },
  { kw: ["graphql", "apollo"], emoji: "🔗" },
  { kw: ["rust", "cargo"], emoji: "🦀" },
  { kw: ["go ", "golang"], emoji: "🐹" },
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
function themeFor(topic) {
  const t = (topic || "").toLowerCase();
  const entry = TOPIC_ICONS.find((e) => e.kw.some((k) => t.includes(k)));
  const emoji = entry ? entry.emoji : "✨";
  return { emoji };
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

// ========================================================================
// SHELL (sidebar + topbar) — used by home / section / course pages
// ========================================================================

const NAV = [
  { slug: "home",       label: "Home",         href: "/",           icon: "M3 12l9-9 9 9M5 10v10a1 1 0 001 1h3m10-11v10a1 1 0 01-1 1h-3m-6 0v-6a1 1 0 011-1h2a1 1 0 011 1v6m-4 0h4" },
  { slug: "catalog",    label: "Catalog",      href: "/catalog",    icon: "M4 6h16M4 12h16M4 18h7" },
  { slug: "my-courses", label: "My courses",   href: "/my-courses", icon: "M5 13l4 4L19 7" },
  { slug: "bookmarks",  label: "Bookmarks",    href: "/bookmarks",  icon: "M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" },
];

function renderSidebar(activeSlug) {
  const slot = document.getElementById("sidebar-slot");
  if (!slot) return;
  slot.outerHTML = `
    <aside class="sidebar hidden w-64 shrink-0 md:flex md:flex-col">
      <div class="sidebar-header">
        <a href="/" class="sidebar-brand-row">
          <span class="brand-mark">A</span>
          <div class="leading-tight">
            <div class="text-sm font-semibold">AdaptivAI</div>
            <div class="text-[10px] uppercase tracking-widest text-slate-400">mini</div>
          </div>
        </a>
      </div>
      <nav class="sidebar-nav">
        <div class="sidebar-section-label">Learn</div>
        ${NAV.map((n) => `
          <a class="nav-item ${n.slug === activeSlug ? "nav-item-active" : ""}" href="${n.href}">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${n.icon}"/></svg>
            ${n.label}
          </a>
        `).join("")}
      </nav>
      <div class="sidebar-footer">
        <div class="sidebar-status">
          <div class="sidebar-status-row"><span class="pulse-dot"></span><b>All systems up</b></div>
          <div class="sidebar-status-row">v0.1 · agent-generated courses</div>
        </div>
      </div>
    </aside>
  `;
}

function renderTopbar(opts = {}) {
  const slot = document.getElementById("topbar-slot");
  if (!slot) return;
  const user = getUser();
  const showSearch = opts.search !== false;

  slot.outerHTML = `
    <header class="topbar">
      ${showSearch ? `
        <form id="topbar-form" class="max-w-xl flex-1">
          <div class="search-pill">
            <svg class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.3-4.3m0 0A7.5 7.5 0 103.5 10.5a7.5 7.5 0 0013.2 6.2z"/></svg>
            <input name="topic" placeholder="Generate a new course..." class="search-input" />
            <kbd class="search-kbd">↵</kbd>
          </div>
        </form>
      ` : `<div class="flex-1"></div>`}

      <div class="hidden items-center gap-2 text-xs text-slate-500 md:flex">
        <span class="pulse-dot"></span>
        Agent online
      </div>

      ${user ? `
        <button id="user-chip" class="user-chip">
          <span class="user-avatar">${user.avatar || "👤"}</span>
          <span class="hidden sm:inline">${escapeHtml(user.name || "You")}</span>
          <svg class="h-3 w-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
        </button>
      ` : `
        <a href="/login" class="user-chip">
          <span class="user-avatar">👤</span>
          <span class="hidden sm:inline">Sign in</span>
        </a>
      `}
    </header>
  `;

  // Wire topbar search (submits to home page generation if not there).
  const form = document.getElementById("topbar-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const topic = (form.querySelector('input[name="topic"]').value || "").trim();
      if (!topic) return;
      if (location.pathname === "/") {
        // Let home page handler take over.
        startGeneration(topic);
      } else {
        location.href = "/?topic=" + encodeURIComponent(topic);
      }
    });
  }

  // User menu.
  const chip = document.getElementById("user-chip");
  if (chip && user) chip.addEventListener("click", (e) => { e.stopPropagation(); openUserMenu(chip); });
}

function openUserMenu(anchor) {
  closeUserMenu();
  const user = getUser();
  const menu = document.createElement("div");
  menu.className = "user-menu";
  menu.id = "user-menu";
  menu.innerHTML = `
    <div class="user-menu-header">
      <div class="flex items-center gap-3">
        <span class="user-avatar" style="width:36px;height:36px;font-size:18px;">${user.avatar || "👤"}</span>
        <div>
          <div class="text-sm font-semibold text-slate-900">${escapeHtml(user.name || "You")}</div>
          <div class="text-[11px] text-slate-500">${escapeHtml(user.email || "")}</div>
        </div>
      </div>
    </div>
    <a href="/my-courses" class="user-menu-item">
      <svg class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
      My courses
    </a>
    <a href="/bookmarks" class="user-menu-item">
      <svg class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
      Bookmarks
    </a>
    <button id="logout-btn" class="user-menu-item user-menu-item-danger">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
      Sign out
    </button>
  `;
  document.body.appendChild(menu);
  menu.querySelector("#logout-btn").addEventListener("click", logout);
  // Close on outside click.
  setTimeout(() => document.addEventListener("click", closeUserMenu, { once: true }), 0);
}
function closeUserMenu() {
  const m = document.getElementById("user-menu");
  if (m) m.remove();
}

// ========================================================================
// LOGIN PAGE
// ========================================================================

function renderLoginPage() {
  // If already logged in, forward to home.
  if (getUser()) { window.location.href = "/"; return; }

  const picker = document.getElementById("avatar-picker");
  let selected = AVATAR_EMOJIS[0];
  picker.innerHTML = AVATAR_EMOJIS
    .map((e) => `<button type="button" class="avatar-option ${e === selected ? "selected" : ""}" data-emoji="${e}">${e}</button>`)
    .join("");
  picker.addEventListener("click", (e) => {
    const btn = e.target.closest(".avatar-option");
    if (!btn) return;
    selected = btn.dataset.emoji;
    picker.querySelectorAll(".avatar-option").forEach((b) => b.classList.toggle("selected", b === btn));
  });

  document.getElementById("login-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = (document.getElementById("login-name").value || "").trim();
    const email = (document.getElementById("login-email").value || "").trim();
    if (!name || !email) return;
    setUser({ name, email, avatar: selected, signedInAt: new Date().toISOString() });
    window.location.href = "/";
  });

  document.getElementById("guest-btn").addEventListener("click", () => {
    setUser({ name: "Guest", email: "", avatar: "👤", guest: true, signedInAt: new Date().toISOString() });
    window.location.href = "/";
  });
}

// ========================================================================
// CARD RENDERING
// ========================================================================

function courseCardHtml(c, opts = {}) {
  const when = c.created_at ? timeAgo(c.created_at) : "";
  const { emoji } = themeFor(c.topic);
  const bookmarked = isBookmarked(c.course_id);
  const showBookmark = opts.bookmark !== false;
  return `
    <div class="relative">
      ${showBookmark ? `
        <button class="bookmark-btn ${bookmarked ? "bookmarked" : ""}" data-bookmark="${c.course_id}" title="${bookmarked ? "Remove bookmark" : "Bookmark"}">
          <svg class="h-4 w-4" fill="${bookmarked ? "currentColor" : "none"}" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
          </svg>
        </button>
      ` : ""}
      <a href="/course/${encodeURIComponent(c.course_id)}" class="course-card">
        <div class="course-card-header">
          <span class="course-card-emoji">${emoji}</span>
        </div>
        <div class="course-card-body">
          <div class="text-[10px] font-semibold uppercase tracking-widest text-stone-400">Course</div>
          <div class="mt-1 course-card-topic">${escapeHtml(c.topic)}</div>
          <div class="course-card-meta">
            <span>${c.video_count} video${c.video_count === 1 ? "" : "s"} · ${escapeHtml(when)}</span>
            <span class="course-card-cta">View →</span>
          </div>
        </div>
      </a>
    </div>
  `;
}

function wireBookmarkButtons(containerId) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-bookmark]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const id = btn.dataset.bookmark;
    const nowOn = toggleBookmark(id);
    btn.classList.toggle("bookmarked", nowOn);
    btn.querySelector("svg").setAttribute("fill", nowOn ? "currentColor" : "none");
  });
}

// ========================================================================
// HOME PAGE
// ========================================================================

async function renderHomePage() {
  renderSidebar("home");
  renderTopbar({ search: true });

  // If URL has ?topic=..., kick off generation immediately (used by topbar search from other pages).
  const params = new URLSearchParams(location.search);
  const queued = params.get("topic");

  const grid = document.getElementById("catalog-grid");
  const empty = document.getElementById("catalog-empty");
  try {
    const res = await fetch("/api/catalog");
    const courses = await res.json();
    if (!courses.length) {
      empty.classList.remove("hidden");
    } else {
      empty.classList.add("hidden");
      grid.innerHTML = courses.slice(0, 9).map((c) => courseCardHtml(c)).join("");
      wireBookmarkButtons("catalog-grid");
    }
  } catch {
    empty.textContent = "Failed to load catalog.";
    empty.classList.remove("hidden");
  }

  document.getElementById("hero-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = e.target.querySelector('input[name="topic"]');
    startGeneration((input.value || "").trim());
  });
  document.querySelectorAll("[data-chip]").forEach((btn) => {
    btn.addEventListener("click", () => startGeneration(btn.dataset.chip));
  });

  if (queued) {
    document.querySelector('#hero-form input[name="topic"]').value = queued;
    startGeneration(queued);
  }
}

async function startGeneration(topic) {
  topic = (topic || "").trim();
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
        addOwned(data.course_id);
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
// SECTION PAGES — catalog / my-courses / bookmarks
// ========================================================================

async function renderSectionPage({ section }) {
  renderSidebar(section);
  renderTopbar({ search: true });

  const grid = document.getElementById("catalog-grid");
  const empty = document.getElementById("catalog-empty");
  const count = document.getElementById("section-count");
  const filterInput = document.getElementById("filter-input");
  const sortSelect = document.getElementById("sort-select");

  let allCourses = [];
  try {
    const res = await fetch("/api/catalog");
    allCourses = await res.json();
  } catch {
    empty.textContent = "Failed to load courses.";
    empty.classList.remove("hidden");
    return;
  }

  // Filter by section.
  let sectionCourses;
  if (section === "my-courses") {
    const owned = new Set(getOwned());
    sectionCourses = allCourses.filter((c) => owned.has(c.course_id));
  } else if (section === "bookmarks") {
    const bm = new Set(getBookmarks());
    sectionCourses = allCourses.filter((c) => bm.has(c.course_id));
  } else {
    sectionCourses = allCourses;
  }

  function render() {
    let list = sectionCourses.slice();
    const q = (filterInput.value || "").toLowerCase().trim();
    if (q) list = list.filter((c) => c.topic.toLowerCase().includes(q));

    const sort = sortSelect.value;
    list.sort((a, b) => {
      if (sort === "newest") return new Date(b.created_at) - new Date(a.created_at);
      if (sort === "oldest") return new Date(a.created_at) - new Date(b.created_at);
      if (sort === "az") return a.topic.localeCompare(b.topic);
      if (sort === "za") return b.topic.localeCompare(a.topic);
      if (sort === "videos") return (b.video_count || 0) - (a.video_count || 0);
      return 0;
    });

    count.textContent = `${list.length} course${list.length === 1 ? "" : "s"}`;

    if (!list.length) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
    } else {
      empty.classList.add("hidden");
      grid.innerHTML = list.map((c) => courseCardHtml(c)).join("");
      wireBookmarkButtons("catalog-grid");
    }
  }

  filterInput.addEventListener("input", render);
  sortSelect.addEventListener("change", render);
  render();
}

// ========================================================================
// COURSE PAGE
// ========================================================================

let COURSE = null;

async function renderCoursePage() {
  renderSidebar("home");
  renderTopbar({ search: true });

  const courseId = decodeURIComponent(location.pathname.split("/").pop());
  const res = await fetch("/api/courses/" + encodeURIComponent(courseId));
  if (!res.ok) {
    document.getElementById("course-title").textContent = "Course not found";
    return;
  }
  COURSE = await res.json();

  const { emoji } = themeFor(COURSE.topic);

  document.getElementById("course-topic").textContent = COURSE.topic;
  document.getElementById("course-title").innerHTML =
    `<span style="font-size: 0.85em; margin-right: 10px;">${emoji}</span>${escapeHtml(COURSE.topic)}`;
  document.getElementById("course-video-count").textContent =
    `${(COURSE.videos || []).length} videos`;
  document.getElementById("course-created").textContent = timeAgo(COURSE.created_at);

  const header = document.querySelector(".course-header");
  if (header) {
    const bookmarked = isBookmarked(COURSE.course_id);
    const actions = document.createElement("div");
    actions.className = "course-header-actions";
    actions.innerHTML = `
      <button id="header-bookmark" class="header-action ${bookmarked ? "bookmarked" : ""}">
        <svg class="h-3 w-3" fill="${bookmarked ? "currentColor" : "none"}" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
        <span class="bookmark-label">${bookmarked ? "Bookmarked" : "Bookmark"}</span>
      </button>
    `;
    header.appendChild(actions);
    document.getElementById("header-bookmark").addEventListener("click", () => {
      const nowOn = toggleBookmark(COURSE.course_id);
      const btn = document.getElementById("header-bookmark");
      btn.classList.toggle("bookmarked", nowOn);
      btn.querySelector("svg").setAttribute("fill", nowOn ? "currentColor" : "none");
      btn.querySelector(".bookmark-label").textContent = nowOn ? "Bookmarked" : "Bookmark";
    });
  }

  renderVideos(COURSE.videos || []);

  if (COURSE.summary) showSummary(COURSE.summary);
  if ((COURSE.quiz || []).length) showQuiz(COURSE.quiz);

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  document.getElementById("gen-summary-btn").addEventListener("click", () => generateSummary());
  document.getElementById("gen-quiz-btn").addEventListener("click", () => generateQuiz());

  document.getElementById("chat-form").addEventListener("submit", onSendChat);
  document.getElementById("quiz-submit").addEventListener("click", onSubmitQuiz);

  // Wire example-prompt chips in chat empty state.
  document.querySelectorAll("[data-suggest]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById("chat-input");
      input.value = btn.dataset.suggest;
      document.getElementById("chat-form").requestSubmit();
    });
  });

  // Delegate clicks on citation chips → scroll + highlight the source video.
  document.getElementById("chat-messages").addEventListener("click", (e) => {
    const chip = e.target.closest(".cite-chip");
    if (!chip) return;
    const idx = Number(chip.dataset.videoIdx);
    focusVideo(idx);
  });
}

function focusVideo(idx) {
  const card = document.querySelector(`[data-video-index="${idx}"]`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("is-cited");
  setTimeout(() => card.classList.remove("is-cited"), 1600);
}

function renderVideos(videos) {
  const transcripts = COURSE.transcripts || [];
  const root = document.getElementById("videos");
  root.innerHTML = videos
    .map((v, i) => {
      const transcript = transcripts[i] || "";
      const formatted = formatTranscriptForDisplay(transcript);
      return `
        <article class="video-card" data-video-index="${i}">
          <div class="aspect-video w-full bg-black">
            <iframe src="https://www.youtube.com/embed/${escapeHtml(v.id)}" title="${escapeHtml(v.title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
          </div>
          <div class="p-4">
            <div class="text-[11px] font-medium uppercase tracking-wider text-stone-400">Video ${i + 1} · ${escapeHtml(v.channel || "")}</div>
            <div class="mt-1.5 font-medium text-[15px]">${escapeHtml(v.title)}</div>
            <details class="mt-3 text-sm">
              <summary class="inline-flex items-center gap-1.5 text-indigo-700 text-xs font-medium">
                <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                Show transcript
              </summary>
              <div class="transcript-block" data-transcript-raw="${escapeHtml(transcript)}">${escapeHtml(formatted)}</div>
              <div class="transcript-actions">
                <button class="transcript-copy" data-copy-transcript="${i}">
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-2M8 5a2 2 0 002 2h4a2 2 0 002-2M8 5a2 2 0 012-2h4a2 2 0 012 2m0 0h2a2 2 0 012 2v3"/></svg>
                  Copy
                </button>
              </div>
            </details>
          </div>
        </article>
      `;
    })
    .join("");

  root.querySelectorAll("[data-copy-transcript]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = Number(btn.dataset.copyTranscript);
      const raw = (COURSE.transcripts || [])[idx] || "";
      try {
        await navigator.clipboard.writeText(raw);
        const prev = btn.innerHTML;
        btn.innerHTML = "<span>Copied ✓</span>";
        setTimeout(() => { btn.innerHTML = prev; }, 1200);
      } catch {}
    });
  });
}

// Format a raw YouTube caption dump into readable paragraphs.
// Captions are usually one short phrase per line with no punctuation;
// group ~8 lines into a paragraph for display.
function formatTranscriptForDisplay(raw) {
  if (!raw) return "";
  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const paragraphs = [];
  let chunk = [];
  for (const line of lines) {
    chunk.push(line);
    if (chunk.length >= 8) {
      paragraphs.push(chunk.join(" "));
      chunk = [];
    }
  }
  if (chunk.length) paragraphs.push(chunk.join(" "));
  return paragraphs.join("\n\n");
}

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("tab-active", b.dataset.tab === tab);
  });
  document.querySelectorAll("[data-tab-panel]").forEach((p) => {
    const show = p.dataset.tabPanel === tab;
    p.classList.toggle("hidden", !show);
    if (p.dataset.tabPanel === "chat" && show) p.classList.add("chat-wrap");
  });
}

async function generateSummary() {
  document.getElementById("summary-empty").classList.add("hidden");
  document.getElementById("summary-loading").classList.remove("hidden");
  try {
    const res = await fetch("/api/courses/" + encodeURIComponent(COURSE.course_id) + "/generate-summary", { method: "POST" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    COURSE.summary = data.summary;
    showSummary(data.summary);
  } catch {
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

async function generateQuiz() {
  document.getElementById("quiz-empty").classList.add("hidden");
  document.getElementById("quiz-loading").classList.remove("hidden");
  try {
    const res = await fetch("/api/courses/" + encodeURIComponent(COURSE.course_id) + "/generate-quiz", { method: "POST" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    COURSE.quiz = data.quiz;
    showQuiz(data.quiz);
  } catch {
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
        .map((opt, j) => `
          <label class="quiz-option">
            <input type="radio" name="q${i}" value="${j}" />
            <span>${escapeHtml(opt)}</span>
          </label>`)
        .join("");
      return `
        <fieldset>
          <legend class="mb-2 text-sm font-medium">${i + 1}. ${escapeHtml(q.q)}</legend>
          <div class="space-y-2">${opts}</div>
        </fieldset>`;
    })
    .join("");
}

async function onSendChat(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = (input.value || "").trim();
  if (!msg) return;
  input.value = "";
  const empty = document.querySelector(".chat-empty");
  if (empty) empty.remove();

  appendBubble("user", msg);
  const placeholder = appendBubble("ai", "", { typing: true });
  const bubble = placeholder.querySelector(".bubble");
  const answerSpan = placeholder.querySelector(".bubble-text");
  let typingRemoved = false;
  let rawText = "";

  const removeTyping = () => {
    if (typingRemoved) return;
    const dots = placeholder.querySelector(".typing-dots");
    if (dots) dots.remove();
    typingRemoved = true;
  };

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
          if (data.route === "unclear") bubble.classList.add("clarify");
        } else if (event === "token") {
          removeTyping();
          rawText += data.text;
          answerSpan.textContent = rawText;
          autoScrollChat();
        } else if (event === "error") {
          removeTyping();
          answerSpan.textContent = "(error: " + data.message + ")";
        }
      },
    );
    removeTyping();
    // Post-process citations on the finalized text.
    if (rawText) answerSpan.innerHTML = renderCitationChips(rawText);
  } catch {
    removeTyping();
    answerSpan.textContent = "(stream failed)";
  }
}

function renderCitationChips(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(/\[Video (\d+)\]/g, (_, n) => {
    return `<button class="cite-chip" data-video-idx="${Number(n) - 1}">Video ${n}</button>`;
  });
}

function autoScrollChat() {
  const root = document.getElementById("chat-messages");
  root.scrollTop = root.scrollHeight;
}
function appendBubble(role, initialText, opts = {}) {
  const root = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "flex flex-col " + (role === "user" ? "items-end" : "items-start");
  const content = opts.typing
    ? `<span class="typing-dots"><span></span><span></span><span></span></span><span class="bubble-text"></span>`
    : `<span class="bubble-text">${escapeHtml(initialText)}</span>`;
  wrap.innerHTML = `<div class="bubble bubble-${role}">${content}</div>`;
  root.appendChild(wrap);
  autoScrollChat();
  return wrap;
}

async function onSubmitQuiz() {
  const form = document.getElementById("quiz-form");
  const quiz = COURSE.quiz || [];
  const answers = [];
  for (let i = 0; i < quiz.length; i++) {
    const sel = form.querySelector(`input[name="q${i}"]:checked`);
    answers.push(sel ? Number(sel.value) : -1);
  }
  if (answers.some((a) => a < 0)) { alert("Please answer every question first."); return; }

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
    <div class="mb-4 rounded-xl p-4 border" style="background: var(--accent-soft); border-color: transparent;">
      <div class="text-xs font-semibold uppercase tracking-wider" style="color: var(--accent);">Your score</div>
      <div class="mt-1 text-2xl font-semibold text-stone-900">${data.score} / ${data.total} <span class="text-sm font-medium text-stone-500">(${pct}%)</span></div>
    </div>
    <ol class="space-y-3 text-sm">
      ${data.feedback
        .map((f, i) => {
          const q = quiz[i];
          const correct = q.options[f.correct_idx];
          return `
            <li class="${f.correct ? "quiz-feedback-correct" : "quiz-feedback-wrong"}">
              <div class="font-medium text-stone-900">${i + 1}. ${escapeHtml(q.q)}</div>
              <div class="mt-1 text-xs ${f.correct ? "text-emerald-700" : "text-rose-700"}">${f.correct ? "✓ Correct" : "✗ Incorrect"} · Answer: <b>${escapeHtml(correct)}</b></div>
              <div class="mt-1 text-xs text-stone-600">${escapeHtml(f.explanation)}</div>
            </li>`;
        })
        .join("")}
    </ol>
  `;
}

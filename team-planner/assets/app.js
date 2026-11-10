(function () {
  "use strict";

  var PLAN = window.PLAN;
  var TEAM_PASSWORD = "123456";
  var KEY_USER = "tp.user";
  var KEY_DAY = "tp.day";
  var KEY_LOCAL = "tp.progress.local";
  var app = document.getElementById("app");

  var people = {};
  PLAN.people.forEach(function (p) { people[p.id] = p; });

  var state = {
    user: readJSON(KEY_USER),
    day: parseInt(localStorage.getItem(KEY_DAY) || "1", 10),
    view: "all",
    ownerFilter: "all",
    open: {},
    progress: {},
    shared: null,
    pollTimer: null
  };
  if (!(state.day >= 1 && state.day <= PLAN.days.length)) state.day = 1;

  // ------------------------------------------------------------------ helpers
  function readJSON(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; }
  }
  function esc(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function initial(name) { return name.charAt(0).toUpperCase(); }
  function pct(a, b) { return b ? Math.round((a / b) * 100) : 0; }
  function toast(message) {
    var el = document.getElementById("toast");
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toast.t);
    toast.t = setTimeout(function () { el.classList.remove("show"); }, 1800);
  }
  var CHECK_SVG = '<svg viewBox="0 0 16 16" fill="none"><path d="M3 8.5l3 3 7-7" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHEVRON = '<svg viewBox="0 0 12 12" fill="none"><path d="M2.5 4.5L6 8l3.5-3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  var PY_KEYWORDS = "def|class|return|if|elif|else|for|in|while|import|from|as|with|try|except|finally|raise|not|and|or|is|None|True|False|lambda|yield|pass|continue|break|global|assert|del";
  var PY_TOKENS = new RegExp(
    "(#[^\\n]*)" +
    "|((?:[rRbBfF]{1,2})?(?:\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*'))" +
    "|(@[A-Za-z_][\\w.]*)" +
    "|\\b(" + PY_KEYWORDS + ")\\b" +
    "|\\b(\\d+(?:\\.\\d+)?)\\b", "g");
  var SH_TOKENS = /(#[^\n]*)|('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")|\b(git|python|cd|mkdir|rm|printf|cat)\b/g;

  function highlight(code, lang) {
    var pattern = lang === "sh" ? SH_TOKENS : PY_TOKENS;
    var out = "", last = 0, m;
    pattern.lastIndex = 0;
    while ((m = pattern.exec(code)) !== null) {
      out += esc(code.slice(last, m.index));
      var cls = m[1] ? "tk-c" : m[2] ? "tk-s" : lang === "sh" ? "tk-k" : m[3] ? "tk-d" : m[4] ? "tk-k" : "tk-n";
      out += '<span class="' + cls + '">' + esc(m[0]) + "</span>";
      last = pattern.lastIndex;
      if (m[0].length === 0) pattern.lastIndex++;
    }
    return out + esc(code.slice(last));
  }

  function copyText(text, button) {
    function done() {
      if (button) {
        var old = button.getAttribute("data-label") || button.textContent;
        button.setAttribute("data-label", old);
        button.textContent = "Copied";
        button.classList.add("copied");
        setTimeout(function () { button.textContent = old; button.classList.remove("copied"); }, 1500);
      }
      toast("Copied to clipboard");
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed"; area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (e) { toast("Select the text and copy it manually"); }
      document.body.removeChild(area);
    }
  }

  var clipboard = {};
  var clipId = 0;
  function codeBlock(code, lang, label, short) {
    var id = "c" + (++clipId);
    clipboard[id] = code;
    var lines = code.split("\n").length;
    return '<div class="code-wrap"><div class="code-bar"><span>' + esc(label) + " · " + lines + (lines === 1 ? " line" : " lines") +
      '</span><button class="btn-copy" data-copy="' + id + '">Copy</button></div>' +
      '<pre class="code' + (short ? " short" : "") + '"><code>' + highlight(code, lang) + "</code></pre></div>";
  }

  // ------------------------------------------------------------------ progress
  function totals(filterFn) {
    var done = 0, all = 0;
    Object.keys(PLAN.files).forEach(function (path) {
      var f = PLAN.files[path];
      if (filterFn && !filterFn(f, path)) return;
      all++;
      if (state.progress[path]) done++;
    });
    return { done: done, all: all };
  }

  function loadProgress() {
    return fetch("/api/progress", { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("status " + r.status);
        return r.json();
      })
      .then(function (data) {
        state.shared = true;
        state.progress = data.done || {};
      })
      .catch(function () {
        state.shared = false;
        state.progress = readJSON(KEY_LOCAL) || {};
      });
  }

  function setProgress(path, value) {
    var file = PLAN.files[path];
    if (!file || !state.user || file.owner !== state.user.id) return;
    state.progress[path] = value;
    render();
    if (state.shared === false) {
      localStorage.setItem(KEY_LOCAL, JSON.stringify(state.progress));
      return;
    }
    fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: state.user.id, password: state.user.password, path: path, done: value })
    }).then(function (r) {
      if (r.status === 503) {
        state.shared = false;
        localStorage.setItem(KEY_LOCAL, JSON.stringify(state.progress));
        render();
        return;
      }
      if (!r.ok) throw new Error("status " + r.status);
      toast(value ? "Marked done · +1 point" : "Marked not done");
    }).catch(function () {
      state.progress[path] = !value;
      render();
      toast("Could not save - check your connection");
    });
  }

  function startPolling() {
    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(function () {
      if (document.hidden || state.shared !== true) return;
      loadProgress().then(render);
    }, 15000);
  }

  // ------------------------------------------------------------------ sign in
  function renderSignIn(error) {
    app.innerHTML =
      '<div class="signin">' +
      '<section class="signin-brand">' +
      '<div class="brand-mark"><span class="brand-square">TP</span>Team Planner</div>' +
      "<div><h1>Build PhaseWise AI, one day at a time.</h1>" +
      "<p>Daily tasks, the exact files to paste, the commands to push and what to show in review - for every member of the team, in one place.</p></div>" +
      '<div class="signin-roles">' + PLAN.people.map(function (p) { return "<span>" + esc(p.area) + "</span>"; }).join("") + "</div>" +
      "</section>" +
      '<section class="signin-form-wrap"><form class="signin-card" id="signin-form" autocomplete="on">' +
      "<h2>Sign in</h2><p class=\"sub\">Use your first name and the team password.</p>" +
      '<label class="field"><span>Username</span><input name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required></label>' +
      '<label class="field"><span>Password</span><input name="password" type="password" autocomplete="current-password" required></label>' +
      '<div class="form-error">' + (error ? esc(error) : "") + "</div>" +
      '<button class="btn btn-primary btn-block" type="submit">Sign in</button>' +
      '<p class="signin-hint">Team: ' + PLAN.people.map(function (p) { return p.id; }).join(", ") + "</p>" +
      "</form></section></div>";
    var form = document.getElementById("signin-form");
    form.username.focus();
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var username = form.username.value.trim().toLowerCase();
      var password = form.password.value;
      if (!people[username] || password !== TEAM_PASSWORD) {
        renderSignIn("Username or password is not correct");
        return;
      }
      state.user = { id: username, password: password };
      localStorage.setItem(KEY_USER, JSON.stringify(state.user));
      state.view = "mine";
      boot();
    });
  }

  // ------------------------------------------------------------------ app
  function nav() {
    var me = people[state.user.id];
    return '<header class="nav"><div class="nav-inner">' +
      '<div class="brand-mark"><span class="brand-square">TP</span>Team Planner</div>' +
      '<div class="nav-right"><div class="user-chip"><span class="avatar" style="background:' + me.colour + '">' + initial(me.name) + "</span>" +
      '<span class="who"><b>' + esc(me.name) + "</b><small>" + esc(me.area) + (me.lead ? " · Team lead" : "") + "</small></span></div>" +
      '<button class="btn btn-small" data-action="signout">Sign out</button></div></div></header>';
  }

  function hero() {
    var t = totals();
    var mine = totals(function (f) { return f.owner === state.user.id; });
    var today = totals(function (f) { return f.day === state.day; });
    return '<section class="hero">' +
      '<div class="card hero-main"><span class="eyebrow">' + esc(PLAN.project.org) + "</span>" +
      "<h1>" + esc(PLAN.project.name) + "</h1><p>" + esc(PLAN.project.summary) + "</p></div>" +
      '<div class="card hero-stats"><div><span class="eyebrow">Team progress</span>' +
      '<div class="big-number" style="margin-top:8px">' + t.done + " <small>of " + t.all + " files · " + pct(t.done, t.all) + "%</small></div></div>" +
      '<div class="bar"><i style="width:' + pct(t.done, t.all) + '%"></i></div>' +
      '<div class="mini-stats"><div><b>' + mine.done + "/" + mine.all + "</b><span>Your points</span></div>" +
      "<div><b>" + today.done + "/" + today.all + "</b><span>Day " + state.day + " files</span></div>" +
      "<div><b>" + PLAN.days.length + "</b><span>Days planned</span></div></div></div></section>";
  }

  function team() {
    return '<section class="section"><div class="section-head"><div><h2>The team</h2><p>Who owns what. Every file is one point.</p></div></div>' +
      '<div class="team-grid">' + PLAN.people.map(function (p) {
        var t = totals(function (f) { return f.owner === p.id; });
        return '<div class="card member' + (p.id === state.user.id ? " me" : "") + '">' +
          '<div class="member-top"><span class="avatar lg" style="background:' + p.colour + '">' + initial(p.name) + "</span>" +
          "<div><b>" + esc(p.name) + '</b><div class="tags"><span class="tag area" style="color:' + p.colour + '">' + esc(p.area) + "</span>" +
          (p.lead ? '<span class="tag lead">Lead</span>' : "") + "</div></div></div>" +
          "<p>" + esc(p.focus) + "</p>" +
          '<div class="bar"><i style="width:' + pct(t.done, t.all) + "%;background:" + p.colour + '"></i></div>' +
          '<div class="member-foot"><span>' + t.done + " of " + t.all + " points</span><span>" + pct(t.done, t.all) + "%</span></div></div>";
      }).join("") + "</div></section>";
  }

  function dayTabs() {
    return '<div class="days">' + PLAN.days.map(function (d) {
      var t = totals(function (f) { return f.day === d.n; });
      return '<button class="day-tab' + (d.n === state.day ? " on" : "") + '" data-day="' + d.n + '">' +
        '<span class="day-n">Day ' + d.n + '</span><span class="day-sub">' + esc(d.title) + "</span>" +
        '<div class="bar"><i style="width:' + pct(t.done, t.all) + '%"></i></div>' +
        '<span class="day-count">' + t.done + " / " + t.all + " files</span></button>";
    }).join("") + "</div>";
  }

  function brief(day) {
    return '<div class="card brief"><div><span class="eyebrow">Day ' + day.n + " brief</span><h3>" + esc(day.title) + "</h3>" +
      "<p>" + esc(day.goal) + "</p>" + (day.order ? '<div class="order">' + esc(day.order) + "</div>" : "") +
      '<div style="margin-top:14px">' + codeBlock(day.check, "sh", "End-of-day check (after the merge)", true) + "</div></div>" +
      '<div><span class="eyebrow">Every day, in this order</span><div class="flow" style="margin-top:10px">' +
      PLAN.flow.map(function (step, i) { return '<div class="flow-step"><i>' + (i + 1) + "</i><span>" + esc(step) + "</span></div>"; }).join("") +
      "</div></div></div>";
  }

  function fileItem(file, ownerId) {
    var done = !!state.progress[file.path];
    var mine = state.user.id === ownerId;
    var open = !!state.open[file.path];
    return '<div class="file' + (done ? " done" : "") + (open ? " open" : "") + '">' +
      '<div class="file-row">' +
      '<button class="check' + (done ? " on" : "") + '" data-check="' + esc(file.path) + '"' + (mine ? "" : " disabled") +
      ' title="' + (mine ? (done ? "Mark as not done" : "Mark as done") : "Only " + esc(people[ownerId].name) + " can change this") + '" aria-label="Done">' + CHECK_SVG + "</button>" +
      '<span class="file-path">' + esc(file.path) + "</span><span class=\"pt\">1 pt</span>" +
      '<button class="toggle" data-open="' + esc(file.path) + '">' + (open ? "Hide code" : "Show code") + " " + CHEVRON + "</button></div>" +
      '<div class="file-detail"><p class="explain">' + esc(file.explain) + "</p>" +
      (open ? codeBlock(file.code, "py", file.path) : "") + "</div></div>";
  }

  function taskCard(day, task) {
    var p = people[task.owner];
    var mine = p.id === state.user.id;
    var t = { done: 0, all: task.files.length };
    task.files.forEach(function (f) { if (state.progress[f.path]) t.done++; });
    return '<article class="card task' + (mine ? " me" : "") + '">' +
      '<div class="task-head"><div class="left"><span class="avatar" style="background:' + p.colour + '">' + initial(p.name) + "</span>" +
      "<div><b>" + esc(p.name) + (mine ? " (you)" : "") + "</b><small>" + esc(p.area) + " · " + esc(task.summary) + "</small></div></div>" +
      '<div class="right">' + (t.all ? '<div class="bar"><i style="width:' + pct(t.done, t.all) + "%;background:" + p.colour + '"></i></div>' : "") +
      '<span class="score">' + t.done + " <small>/ " + t.all + " pts</small></span></div></div>" +
      '<div class="task-body">' +
      (task.files.length ? task.files.map(function (f) { return fileItem(f, p.id); }).join("") :
        '<div class="empty-note">No new files today - this task is the end-to-end run below.</div>') +
      '<div class="blocks">' +
      '<div class="block"><h4>' + (task.files.length ? "Push to your branch" : "Before you start") + "</h4>" + codeBlock(task.commands, "sh", "terminal · Project folder", true) + "</div>" +
      '<div class="block"><h4>Show in review</h4>' + codeBlock(task.demo, "sh", "demo", true) +
      "<p>" + esc(task.show) + "</p></div></div></div></article>";
  }

  function planner() {
    var day = PLAN.days[state.day - 1];
    var tasks = day.tasks.filter(function (task) { return state.view === "all" || task.owner === state.user.id; });
    return '<section class="section" id="planner"><div class="section-head"><div><h2>Daily planner</h2>' +
      "<p>Pick a day. Tick a file when it is pasted, pushed and merged - only the owner can tick it.</p></div>" +
      '<div class="toolbar"><div class="segmented"><button data-view="mine" class="' + (state.view === "mine" ? "on" : "") + '">My tasks</button>' +
      '<button data-view="all" class="' + (state.view === "all" ? "on" : "") + '">Everyone</button></div></div></div>' +
      (state.shared === false ? '<div class="banner">Shared progress is not connected yet, so ticks are saved in this browser only. Connect Upstash Redis in Vercel (see README) to share them with the team.</div>' : "") +
      dayTabs() + brief(day) + '<div class="tasks">' + tasks.map(function (task) { return taskCard(day, task); }).join("") + "</div></section>";
  }

  function ownership() {
    var rows = Object.keys(PLAN.files).filter(function (path) {
      return state.ownerFilter === "all" || PLAN.files[path].owner === state.ownerFilter;
    }).sort();
    return '<section class="section"><div class="section-head"><div><h2>File ownership</h2><p>All ' + Object.keys(PLAN.files).length +
      " files of the project, who writes each and on which day.</p></div>" +
      '<div class="own-filter"><button class="chip-btn' + (state.ownerFilter === "all" ? " on" : "") + '" data-owner="all">Everyone</button>' +
      PLAN.people.map(function (p) {
        return '<button class="chip-btn' + (state.ownerFilter === p.id ? " on" : "") + '" data-owner="' + p.id + '">' + esc(p.name) + "</button>";
      }).join("") + "</div></div>" +
      '<div class="card" style="overflow-x:auto"><table class="own-table"><thead><tr><th>File</th><th>Owner</th><th>Area</th><th>Day</th><th>Status</th></tr></thead><tbody>' +
      rows.map(function (path) {
        var f = PLAN.files[path], p = people[f.owner];
        return '<tr><td class="mono">' + esc(path) + '</td><td><span class="owner"><span class="dot" style="background:' + p.colour + '"></span>' + esc(p.name) + "</span></td>" +
          "<td>" + esc(p.area) + "</td><td>Day " + f.day + "</td><td>" +
          (state.progress[path] ? '<span class="status-done">Done</span>' : '<span class="status-todo">To do</span>') + "</td></tr>";
      }).join("") + "</tbody></table></div></section>";
  }

  function faq() {
    return '<section class="section"><div class="section-head"><div><h2>Branches, pull requests and main</h2><p>How the five branches stay in step.</p></div></div>' +
      '<div class="card faq"><div><h3>Do we need to pull main before pushing?</h3>' + PLAN.faq.answer.map(function (para) { return "<p>" + esc(para) + "</p>"; }).join("") + "</div>" +
      "<div><h3>The lead's merge routine</h3><ol>" + PLAN.faq.lead.map(function (step) { return "<li>" + esc(step) + "</li>"; }).join("") + "</ol>" +
      '<div style="margin-top:14px">' + codeBlock(PLAN.faq.syncCommands, "sh", "every member, start of each day", true) + "</div></div></div></section>";
  }

  function render() {
    if (!state.user || !people[state.user.id]) { renderSignIn(); return; }
    clipboard = {}; clipId = 0;
    var scroll = window.scrollY;
    app.innerHTML = nav() + "<main>" + hero() + team() + planner() + ownership() + faq() +
      "<footer>PhaseWise AI · Team Planner</footer></main>";
    window.scrollTo(0, scroll);
  }

  app.addEventListener("click", function (event) {
    var target = event.target.closest("[data-copy],[data-check],[data-open],[data-day],[data-view],[data-owner],[data-action]");
    if (!target) return;
    if (target.hasAttribute("data-copy")) { copyText(clipboard[target.getAttribute("data-copy")] || "", target); return; }
    if (target.hasAttribute("data-check")) {
      if (target.disabled) return;
      var path = target.getAttribute("data-check");
      setProgress(path, !state.progress[path]);
      return;
    }
    if (target.hasAttribute("data-open")) {
      var p = target.getAttribute("data-open");
      state.open[p] = !state.open[p];
      render();
      return;
    }
    if (target.hasAttribute("data-day")) {
      state.day = parseInt(target.getAttribute("data-day"), 10);
      localStorage.setItem(KEY_DAY, String(state.day));
      render();
      return;
    }
    if (target.hasAttribute("data-view")) { state.view = target.getAttribute("data-view"); render(); return; }
    if (target.hasAttribute("data-owner")) { state.ownerFilter = target.getAttribute("data-owner"); render(); return; }
    if (target.getAttribute("data-action") === "signout") {
      localStorage.removeItem(KEY_USER);
      state.user = null;
      clearInterval(state.pollTimer);
      renderSignIn();
    }
  });

  function boot() {
    if (!state.user || !people[state.user.id]) { renderSignIn(); return; }
    app.innerHTML = nav() + '<main><div class="card" style="padding:28px">Loading the plan...</div></main>';
    loadProgress().then(function () { render(); startPolling(); });
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && state.user && state.shared) loadProgress().then(render);
  });

  boot();
})();

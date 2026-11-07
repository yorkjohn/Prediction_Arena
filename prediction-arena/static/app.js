/* Prediction Arena - participant client (no framework, no build step). */
(function () {
  "use strict";

  const I = {
    zh: {
      sub: "ICDM Youth · 二元预测互动",
      demo: "真实市场题库：参考概率为公开历史数据的事前快照；各平台 API 展示许可仍待人工核实（方案 §10.3）。",
      homeTitle: "预测不是猜 YES 或 NO",
      homeBody: "面对一个已经发生、但结果未必为你所知的事件，先给出你有多大把握，再与参考概率比较，最后看结果并用 Brier Score 检验这份把握。",
      nickname: "给自己起个名字（用于排行榜）",
      nicknamePh: "例如：预测者 A",
      startWarmup: "开始练手（3 题，不计分）",
      board: "查看排行榜",
      warmup: "练手", practice: "不计分 · 提交后立即揭晓",
      next: "下一题", toCategory: "进入实战",
      category: "选择题材", categoryHint: "从该类别随机抽 5 道题，每人独立抽取",
      random: "随机类别",
      challenge: "实战", submitting: "提交中…",
      submitLock: "提交并锁定",
      yesLabel: "YES 的定义",
      result: "本局结果", brier: "平均 Brier Score", hit: "Hit Rate", rank: "我的排名",
      myPrediction: "我的预测", real: "真实结果", ref: "参考概率", bs: "本题得分",
      leaderboard: "统一排行榜", leaderHint: "排名仅为现场趣味挑战，不代表严格公平的预测能力比较",
      yes: "YES", no: "NO", neutral: "中性",
      demoTag: "演示值",
      again: "再来一局", home: "返回首页",
      warmupNote: "练手预测不写入正式成绩，也不进入排行榜。",
      resultNote: "每人只有 5 道实战题，Brier Score 是本次游戏成绩，不能据此认定长期预测能力。",
      netErr: "连接失败：请确认与组织者笔记本在同一 Wi-Fi，或稍后重试。",
      pending: "本局 5 题已全部提交，正在获取结果…",
      retry: "重新获取结果",
      cats: { sports: "体育", esports: "电竞", ai: "AI 与科技", business: "商业与生活", world: "国际与社会" }
    },
    en: {
      sub: "ICDM Youth · binary forecasting game",
      demo: "REAL MARKET BANK: benchmarks are pre-event snapshots from public historical data; display licensing is pending manual review.",
      homeTitle: "Forecasting is not guessing YES or NO",
      homeBody: "You see a past event frozen before its outcome. State how confident you are, compare with a reference probability, then reveal the result and score your confidence with the Brier Score.",
      nickname: "Pick a name (for the leaderboard)",
      nicknamePh: "e.g. Forecaster A",
      startWarmup: "Warm-up (3 questions, not scored)",
      board: "Leaderboard",
      warmup: "Warm-up", practice: "Not scored · revealed right after you submit",
      next: "Next", toCategory: "Start challenge",
      category: "Choose a topic", categoryHint: "5 questions drawn at random, independently for each player",
      random: "Random topic",
      challenge: "Challenge", submitting: "Submitting…",
      submitLock: "Submit and lock",
      yesLabel: "YES means",
      result: "Your result", brier: "Mean Brier Score", hit: "Hit Rate", rank: "Your rank",
      myPrediction: "You said", real: "Outcome", ref: "Reference", bs: "Brier",
      leaderboard: "Overall leaderboard", leaderHint: "A fun on-site score only — not a fair measure of forecasting skill",
      yes: "YES", no: "NO", neutral: "Neutral",
      demoTag: "demo value",
      again: "Play again", home: "Home",
      warmupNote: "Warm-up answers are not recorded and never enter the leaderboard.",
      resultNote: "Five questions only. This score says nothing about long-run calibration.",
      netErr: "Connection failed: make sure you are on the same Wi-Fi as the organizer's notebook, then retry.",
      pending: "All five answers are in. Loading your result…",
      retry: "Retry result",
      cats: { sports: "Sports", esports: "Esports", ai: "AI & Tech", business: "Business & Life", world: "World & Society" }
    }
  };

  const CATS = ["sports", "esports", "ai", "business", "world"];
  const $ = (id) => document.getElementById(id);
  const appEl = $("app");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function clientId() {
    let v = localStorage.getItem("arena_cid");
    if (!v) {
      v = "c_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 10);
      localStorage.setItem("arena_cid", v);
    }
    return v;
  }

  const S = {
    lang: localStorage.getItem("arena_lang") === "en" ? "en" : "zh",
    cid: clientId(),
    nickname: localStorage.getItem("arena_nick") || "",
    view: "home",
    warmup: [], wi: 0, warmupAnswer: null,
    sessionId: null, questions: [], qi: 0, answers: [],
    result: null, board: [], p: 50, busy: false, error: null
  };

  function T() { return I[S.lang]; }
  function field(q, base) {
    const en = q[base + "_en"];
    return S.lang === "en" && en ? en : (q[base + "_zh"] || "");
  }
  function catName(k) { return T().cats[k] || k; }

  async function api(path, body) {
    const init = body
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : { method: "GET" };
    const res = await fetch(path, init);
    const data = await res.json().catch(() => ({ ok: false, error: "bad response" }));
    if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
    return data;
  }

  function msg(text) {
    S.error = text;
    const el = $("msg");
    if (el) { el.textContent = text; el.className = "notice err"; }
  }
  function clearMsg() {
    S.error = null;
    const el = $("msg");
    if (el) el.className = "notice err hidden";
  }

  async function guard(fn) {
    if (S.busy) return;
    S.busy = true;
    clearMsg();
    try { await fn(); }
    catch (e) { msg(T().netErr + " (" + esc(e.message) + ")"); }
    finally { S.busy = false; render(); }
  }

  function avatar(name, color) {
    const ch = (name || "?").trim().charAt(0).toUpperCase();
    return '<span class="avatar" style="background:' + esc(color || "#6ab7ff") + '">' + esc(ch) + "</span>";
  }

  function banner() {
    // Disclosure copy lives in index.html: it describes the real-market bank
    // and must not be overwritten by language toggles.
    $("brandSub").textContent = T().sub;
    $("btnZh").className = S.lang === "zh" ? "on" : "";
    $("btnEn").className = S.lang === "en" ? "on" : "";
  }

  // Error must survive re-render, otherwise a Wi-Fi drop looks like a silent freeze.
  function shell(inner) {
    return '<div id="msg" class="notice err' + (S.error ? "" : " hidden") + '">' +
      esc(S.error || "") + "</div>" + inner;
  }

  function viewHome() {
    return shell(
      '<div class="card">' +
        "<h1>" + esc(T().homeTitle) + "</h1>" +
        "<p>" + esc(T().homeBody) + "</p>" +
        '<label class="muted" for="nick">' + esc(T().nickname) + "</label>" +
        '<input id="nick" type="text" maxlength="20" placeholder="' + esc(T().nicknamePh) + '" value="' + esc(S.nickname) + '">' +
        '<button class="btn" type="button" onclick="arena.startWarmup()">' + esc(T().startWarmup) + "</button>" +
        '<button class="btn ghost" type="button" onclick="arena.leaderboard()">' + esc(T().board) + "</button>" +
      "</div>" +
      '<p class="tiny">' + esc(T().leaderHint) + "</p>"
    );
  }

  function slider() {
    return '<div class="slider-row">' +
      '<input type="range" min="0" max="100" step="1" value="' + S.p + '" oninput="arena.setP(this.value)">' +
      '<span class="pval" id="pval">' + S.p + "%</span></div>" +
      '<div class="scale"><span>0% · ' + esc(T().no) + '</span><span>50% · ' + esc(T().neutral) + '</span><span>' + esc(T().yes) + " · 100%</span></div>";
  }

  function questionCard(q, meta) {
    return '<div class="card">' +
      '<div class="qmeta">' + esc(meta) + "</div>" +
      '<div class="qtitle">' + esc(field(q, "title")) + "</div>" +
      (field(q, "context") ? '<div class="qcontext">' + esc(field(q, "context")) + "</div>" : "") +
      '<div class="define"><b>' + esc(T().yesLabel) + "：</b>" + esc(field(q, "yes")) + "</div>" +
      slider() +
      '<button class="btn" id="submitBtn" type="button" onclick="arena.' + (S.view === "warmup" ? "answerWarmup" : "answerReal") + '()">' +
        esc(T().submitLock) + "</button>" +
      "</div>";
  }

  function progress(cur, total) {
    let h = '<div class="progress">';
    for (let i = 0; i < total; i++) {
      h += '<i class="' + (i < cur ? "done" : i === cur ? "current" : "") + '"></i>';
    }
    return h + "</div>";
  }

  function viewWarmup() {
    const q = S.warmup[S.wi];
    if (!q) return shell('<div class="card muted">…</div>');
    let h = progress(S.wi, S.warmup.length) +
      '<p class="muted">' + esc(T().warmup) + " · " + esc(T().practice) + " · " + (S.wi + 1) + "/" + S.warmup.length + "</p>";
    if (S.warmupAnswer) {
      h += '<div class="explain">' +
        "<b>" + esc(T().real) + "：" + (S.warmupAnswer.outcome ? T().yes : T().no) + "</b> · " +
        "Brier " + S.warmupAnswer.brier.toFixed(3) + "<br>" + esc(S.warmupAnswer.explain) +
        "</div>" +
        '<button class="btn" type="button" onclick="arena.nextWarmup()">' +
          esc(S.wi + 1 < S.warmup.length ? T().next : T().toCategory) + "</button>";
    } else {
      h += questionCard(q, T().warmup + " " + (S.wi + 1) + "/" + S.warmup.length);
    }
    h += '<p class="tiny" style="margin-top:14px">' + esc(T().warmupNote) + "</p>";
    return shell(h);
  }

  function viewCategory() {
    let h = '<div class="card"><h2>' + esc(T().category) + "</h2>" +
      '<p class="muted">' + esc(T().categoryHint) + "</p>" + '<div class="grid">';
    for (const c of CATS) {
      h += '<button class="btn secondary" type="button" onclick="arena.startReal(\'' + c + '\')">' + esc(catName(c)) + "</button>";
    }
    h += '<button class="btn secondary wide" type="button" onclick="arena.startReal(\'random\')">' + esc(T().random) + "</button>";
    h += "</div></div>";
    return shell(h);
  }

  function viewChallenge() {
    const q = S.questions[S.qi];
    if (!q) {
      // Fifth answer landed but the result request failed (Wi-Fi blip).
      return shell('<div class="card"><p>' + esc(T().pending) + "</p>" +
        '<button class="btn" type="button" onclick="arena.retryResult()">' + esc(T().retry) + "</button></div>");
    }
    return shell(
      progress(S.qi, S.questions.length) +
      '<p class="muted">' + esc(T().challenge) + " · " + catName(q.category) + " · " + (S.qi + 1) + "/" + S.questions.length + "</p>" +
      questionCard(q, (S.qi + 1) + "/" + S.questions.length)
    );
  }

  function viewResult() {
    const r = S.result;
    if (!r) return shell('<div class="card muted">…</div>');
    let h = '<div class="card"><h2>' + esc(T().result) + "</h2>" +
      '<div class="metrics">' +
        '<div class="metric"><b>' + r.avg_brier.toFixed(3) + "</b><span>" + esc(T().brier) + "</span></div>" +
        '<div class="metric"><b>' + (r.hit_rate == null ? "—" : Math.round(r.hit_rate * 100) + "%") + "</b><span>" + esc(T().hit) + "</span></div>" +
        '<div class="metric"><b>' + (r.rank == null ? "—" : "#" + r.rank) + "</b><span>" + esc(T().rank) + "</span></div>" +
      "</div>" +
      "<h3>" + esc(T().myPrediction) + " / " + esc(T().real) + " / " + esc(T().ref) + "</h3>" +
      "<table><thead><tr><th>#</th><th>" + esc(T().real) + "</th><th class=\"num\">" + esc(T().myPrediction) +
        '</th><th class="num">' + esc(T().ref) + '</th><th class="num">' + esc(T().bs) + "</th></tr></thead><tbody>";
    r.details.forEach((d, i) => {
      h += "<tr><td>" + (i + 1) + "</td><td>" +
        '<span class="tag ' + (d.outcome ? "yes" : "no") + '">' + (d.outcome ? T().yes : T().no) + "</span></td>" +
        '<td class="num">' + Math.round(d.p_yes * 100) + "%</td>" +
        '<td class="num">' + (d.benchmark_probability == null
            ? "—" : Math.round(d.benchmark_probability * 100) + "%") +
          (d.benchmark_verified
            ? ' <span class="tag">' + esc(d.benchmark_source || "market") + "</span>"
            : ' <span class="tag demo">' + esc(T().demoTag) + "</span>") + "</td>" +
        '<td class="num">' + d.brier.toFixed(3) + "</td></tr>";
    });
    h += "</tbody></table>";
    h += '<p class="tiny" style="margin-top:14px">' + esc(T().resultNote) + "</p></div>";
    h += boardCard(r.leaderboard);
    h += '<div class="card">' +
      '<button class="btn" type="button" onclick="arena.playAgain()">' + esc(T().again) + "</button>" +
      '<button class="btn ghost" type="button" onclick="arena.goHome()">' + esc(T().home) + "</button></div>";
    return shell(h);
  }

  function boardCard(rows) {
    let h = '<div class="card"><h2>' + esc(T().leaderboard) + "</h2>" +
      '<p class="muted">' + esc(T().leaderHint) + "</p>";
    if (!rows || !rows.length) {
      h += '<p class="muted">—</p>';
    } else {
      h += '<table><thead><tr><th>#</th><th>' + (S.lang === "zh" ? "参与者" : "Player") +
        '</th><th class="num">Brier</th><th class="num">Hit</th></tr></thead><tbody>';
      rows.forEach((b) => {
        h += '<tr class="' + (b.session_id === S.sessionId ? "me" : "") + '"><td>' + b.rank + "</td><td>" +
          avatar(b.nickname, b.avatar_color) + esc(b.nickname) + "</td>" +
          '<td class="num">' + b.brier.toFixed(3) + "</td>" +
          '<td class="num">' + (b.hit_rate == null ? "—" : Math.round(b.hit_rate * 100) + "%") + "</td></tr>";
      });
      h += "</tbody></table>";
    }
    return h + "</div>";
  }

  function viewBoard() {
    return shell(boardCard(S.board) +
      '<div class="card"><button class="btn ghost" type="button" onclick="arena.goHome()">' + esc(T().home) + "</button></div>");
  }

  function render() {
    banner();
    let html;
    switch (S.view) {
      case "warmup": html = viewWarmup(); break;
      case "category": html = viewCategory(); break;
      case "challenge": html = viewChallenge(); break;
      case "result": html = viewResult(); break;
      case "board": html = viewBoard(); break;
      default: html = viewHome();
    }
    appEl.innerHTML = html;
  }

  const arena = {
    setLang(lang) {
      const input = $("nick");
      if (input) {
        S.nickname = input.value.trim().slice(0, 20);
        localStorage.setItem("arena_nick", S.nickname);
      }
      S.lang = lang;
      localStorage.setItem("arena_lang", lang);
      render();
    },
    setP(v) {
      S.p = Number(v);
      const el = $("pval");
      if (el) el.textContent = S.p + "%";
    },
    async join() {
      const input = $("nick");
      S.nickname = (input ? input.value : S.nickname).trim().slice(0, 20);
      localStorage.setItem("arena_nick", S.nickname);
      await api("/api/join", { client_id: S.cid, nickname: S.nickname });
    },
    startWarmup: () => guard(async () => {
      await arena.join();
      const d = await api("/api/questions/warmup");
      S.warmup = d.questions;
      S.wi = 0; S.warmupAnswer = null; S.p = 50;
      S.view = "warmup";
    }),
    answerWarmup: () => guard(async () => {
      const q = S.warmup[S.wi];
      S.warmupAnswer = await api("/api/warmup/answer", {
        question_id: q.id, p_yes: S.p, lang: S.lang
      });
    }),
    nextWarmup: () => guard(async () => {
      if (S.wi + 1 < S.warmup.length) {
        S.wi += 1; S.warmupAnswer = null; S.p = 50;
      } else {
        S.view = "category";
      }
    }),
    startReal: (category) => guard(async () => {
      const d = await api("/api/session/start", { client_id: S.cid, category: category });
      S.sessionId = d.session_id;
      sessionStorage.setItem("arena_sid", String(d.session_id));
      S.questions = d.questions;
      S.qi = 0; S.answers = []; S.p = 50; S.result = null;
      S.view = "challenge";
    }),
    answerReal: () => guard(async () => {
      const q = S.questions[S.qi];
      await api("/api/predictions", {
        client_id: S.cid, session_id: S.sessionId,
        question_id: q.id, p_yes: S.p
      });
      S.answers.push({ id: q.id, p: S.p });
      S.qi += 1; S.p = 50;
      if (S.qi >= S.questions.length) {
        S.result = await api("/api/session/" + S.sessionId + "/result?client_id=" + encodeURIComponent(S.cid));
        S.view = "result";
      }
    }),
    retryResult: () => guard(async () => {
      S.result = await api("/api/session/" + S.sessionId + "/result?client_id=" + encodeURIComponent(S.cid));
      S.view = "result";
    }),
    leaderboard: () => guard(async () => {
      S.board = (await api("/api/leaderboard")).leaderboard;
      S.view = "board";
    }),
    playAgain: () => guard(async () => {
      S.sessionId = null; S.questions = []; S.qi = 0; S.answers = []; S.result = null;
      sessionStorage.removeItem("arena_sid");
      S.view = "category";
    }),
    goHome: () => guard(async () => { S.view = "home"; })
  };

  // WeChat can kill the page on a background switch. Restore the in-flight
  // session instead of silently dropping the player's five locked answers.
  async function resume() {
    const sid = Number(sessionStorage.getItem("arena_sid") || 0);
    if (!sid) { render(); return; }
    try {
      const q = "/api/session/" + sid + "/questions?client_id=" + encodeURIComponent(S.cid);
      const d = await api(q);
      S.sessionId = sid;
      S.questions = d.questions;
      const done = new Set(d.answered);
      let idx = -1;
      for (let i = 0; i < d.questions.length; i++) {
        if (!done.has(d.questions[i].id)) { idx = i; break; }
      }
      S.qi = idx < 0 ? d.questions.length : idx;
      if (d.completed || S.qi >= d.questions.length) {
        S.result = await api("/api/session/" + sid + "/result?client_id=" + encodeURIComponent(S.cid));
        S.view = "result";
      } else {
        S.view = "challenge";
      }
    } catch (e) {
      sessionStorage.removeItem("arena_sid");
      S.view = "home";
    }
    render();
  }

  window.arena = arena;
  $("btnZh").addEventListener("click", () => arena.setLang("zh"));
  $("btnEn").addEventListener("click", () => arena.setLang("en"));
  banner();
  appEl.innerHTML = '<div class="card muted">…</div>';
  resume();
})();

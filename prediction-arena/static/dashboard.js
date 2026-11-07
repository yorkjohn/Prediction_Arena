/* Organizer dashboard: anonymous aggregates + unified leaderboard, bilingual.
   Polls /api/dashboard and /api/leaderboard every 3 seconds. Language is shared
   with the participant page via localStorage key "arena_lang".
*/
(function () {
  "use strict";

  const I = {
    zh: {
      sub: "组织者匿名看板 · 每 3 秒刷新",
      confTag: "组织者视图",
      disclosure: "150 道真实市场题 · 参考概率为公开事前快照；看板只显示匿名聚合数据。",
      exportBtn: "导出成绩 CSV（仅本机）",
      connecting: "连接中…",
      live: "LIVE · 每 3 秒刷新",
      offline: "连接中断 · 重试中",
      cards: ["参与人数", "已开局数", "已完成局数", "总提交数"],
      progressTitle: "完成进度",
      progressNote: "已完成 / 已开局",
      avgNote: "群体平均 YES 概率",
      boardTitle: "统一排行榜",
      boardHint: "按平均 Brier Score 升序，仅显示完成 5 题的局。",
      boardHead: ["#", "参与者", "Brier", "Hit"],
      catTitle: "各类别参与局数",
      qTitle: "每道题的匿名平均 YES 概率",
      qHead: ["题目", "提交人数", "平均 YES", "分布"],
      qNote: "只统计真正回答过该题的参与者；不同用户抽到不同题目。",
      emptyCat: "暂无数据",
      emptyQ: "暂无提交",
      emptyBoard: "暂无完成局数",
      updated: "最近更新",
      foot: "仅显示匿名聚合数据 · Northeast Yucai School · Shenyang Aerospace University",
      cats: {
        sports: "体育", esports: "电竞", ai: "AI 与科技",
        business: "商业与生活", world: "国际与社会", random: "随机类别"
      }
    },
    en: {
      sub: "Organizer dashboard · refreshes every 3s",
      confTag: "Organizer View",
      disclosure: "150 real-market questions · public pre-event snapshots; anonymous aggregates only.",
      exportBtn: "Export results CSV (this notebook only)",
      connecting: "Connecting…",
      live: "LIVE · refresh 3s",
      offline: "Disconnected · retrying",
      cards: ["Participants", "Sessions started", "Sessions completed", "Total predictions"],
      progressTitle: "Completion",
      progressNote: "Completed / started",
      avgNote: "Crowd mean YES",
      boardTitle: "Overall leaderboard",
      boardHint: "Sorted by mean Brier Score; only sessions with all 5 answers.",
      boardHead: ["#", "Player", "Brier", "Hit"],
      catTitle: "Sessions by topic",
      qTitle: "Anonymous mean YES probability per question",
      qHead: ["Question", "Answers", "Mean YES", "Distribution"],
      qNote: "Only players who actually answered that question; different players draw different questions.",
      emptyCat: "No data yet",
      emptyQ: "No submissions yet",
      emptyBoard: "No completed sessions yet",
      updated: "Last updated",
      foot: "Anonymous aggregates only · Northeast Yucai School · Shenyang Aerospace University",
      cats: {
        sports: "Sports", esports: "Esports", ai: "AI & Tech",
        business: "Business & Life", world: "World & Society", random: "Random topic"
      }
    }
  };

  const $ = (id) => document.getElementById(id);
  const T = () => I[lang];
  let lang = localStorage.getItem("arena_lang") === "en" ? "en" : "zh";
  let last = null;
  let board = [];
  let online = false;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function setStatus(ok, text) {
    $("statusDot").className = "dot" + (ok ? "" : " off");
    $("statusText").textContent = text;
  }

  function applyStatic() {
    const t = T();
    $("brandSub").textContent = t.sub;
    $("confTag").textContent = t.confTag;
    $("dashBanner").textContent = t.disclosure;
    $("exportBtn").textContent = t.exportBtn;
    $("progressTitle").textContent = t.progressTitle;
    $("boardTitle").textContent = t.boardTitle;
    $("boardHint").textContent = t.boardHint;
    $("catTitle").textContent = t.catTitle;
    $("qTitle").textContent = t.qTitle;
    $("qNote").textContent = t.qNote;
    $("footNote").textContent = t.foot;
    $("btnZh").className = lang === "zh" ? "on" : "";
    $("btnEn").className = lang === "en" ? "on" : "";
    $("boardHead").innerHTML =
      "<tr><th>" + esc(t.boardHead[0]) + "</th><th>" + esc(t.boardHead[1]) +
      '</th><th class="num">' + esc(t.boardHead[2]) +
      '</th><th class="num">' + esc(t.boardHead[3]) + "</th></tr>";
    $("qHead").innerHTML =
      "<tr><th>" + esc(t.qHead[0]) + '</th><th class="num">' + esc(t.qHead[1]) +
      '</th><th class="num">' + esc(t.qHead[2]) + "</th><th>" + esc(t.qHead[3]) + "</th></tr>";
    setStatus(online, online ? t.live : t.connecting);
  }

  function render(d, rows) {
    const t = T();
    const qs = d.per_question || [];
    const submissions = qs.reduce((a, q) => a + q.count, 0);
    const started = d.started_sessions || 0;
    const completed = d.completed_sessions || 0;
    const rate = started ? Math.round((completed / started) * 100) : 0;
    const avg = submissions
      ? qs.reduce((a, q) => a + q.avg_p * q.count, 0) / submissions
      : null;

    const metrics = [d.total_participants, started, completed, submissions];
    $("cards").innerHTML = metrics.map((v, i) =>
      '<div class="metric"><b>' + v + "</b><span>" + esc(t.cards[i]) + "</span></div>"
    ).join("");

    $("progress").innerHTML =
      '<div class="progress-lg"><i style="width:' + rate + '%"></i></div>' +
      '<p class="muted">' + esc(t.progressNote) + " · <b>" + rate + "%</b>" +
      (avg == null ? "" : " · " + esc(t.avgNote) + " <b>" + Math.round(avg * 100) + "%</b>") +
      "</p>";

    $("boardRows").innerHTML = rows.length
      ? rows.map((b) =>
          "<tr><td>" + b.rank + "</td><td>" +
          '<span class="avatar" style="background:' + esc(b.avatar_color || "#6ab7ff") + '">' +
          esc(String(b.nickname || "?").trim().charAt(0).toUpperCase()) + "</span>" +
          esc(b.nickname) + "</td>" +
          '<td class="num">' + Number(b.brier).toFixed(3) + "</td>" +
          '<td class="num">' + (b.hit_rate == null ? "—" : Math.round(b.hit_rate * 100) + "%") +
          "</td></tr>"
        ).join("")
      : '<tr><td colspan="4" class="muted">' + esc(t.emptyBoard) + "</td></tr>";

    const cats = Object.entries(d.by_category || {});
    $("cat").innerHTML = cats.length
      ? cats.map(([k, n]) =>
          '<span class="tag" style="margin:0 8px 8px 0;display:inline-block;padding:5px 12px;font-size:13px">' +
          esc(t.cats[k] || k) + " · " + n + "</span>").join("")
      : '<span class="muted">' + esc(t.emptyCat) + "</span>";

    $("rows").innerHTML = qs.length
      ? qs.map((q) =>
          "<tr><td>" + esc(q.question_id) + " · " +
          esc(lang === "en" ? (q.title_en || q.title) : q.title) + "</td>" +
          '<td class="num">' + q.count + "</td>" +
          '<td class="num">' + Math.round(q.avg_p * 100) + "%</td>" +
          '<td><div class="bar"><i style="width:' + Math.round(q.avg_p * 100) + '%"></i></div></td></tr>'
        ).join("")
      : '<tr><td colspan="4" class="muted">' + esc(t.emptyQ) + "</td></tr>";

    $("updated").textContent = t.updated + " · " +
      new Date().toLocaleTimeString(lang === "en" ? "en-GB" : "zh-CN");
  }

  async function tick() {
    try {
      const [a, b] = await Promise.all([
        fetch("/api/dashboard", { cache: "no-store" }),
        fetch("/api/leaderboard", { cache: "no-store" })
      ]);
      if (!a.ok || !b.ok) throw new Error("HTTP " + a.status + "/" + b.status);
      const d = await a.json();
      const lb = await b.json();
      if (!d.ok || !lb.ok) throw new Error("bad payload");
      last = d;
      board = lb.leaderboard || [];
      online = true;
      render(last, board);
      setStatus(true, T().live);
    } catch (e) {
      online = false;
      setStatus(false, T().offline);
    }
  }

  function setLang(l) {
    lang = l;
    localStorage.setItem("arena_lang", l);
    applyStatic();
    if (last) render(last, board);
    else tick();
  }

  $("btnZh").addEventListener("click", () => setLang("zh"));
  $("btnEn").addEventListener("click", () => setLang("en"));

  applyStatic();
  tick();
  setInterval(tick, 3000);
})();

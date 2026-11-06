/* Organizer dashboard: anonymous aggregates only, polled every 3 seconds. */
(function () {
  "use strict";

  const CATS = {
    sports: "体育", esports: "电竞", ai: "AI 与科技",
    business: "商业与生活", world: "国际与社会", random: "随机类别"
  };
  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function setStatus(ok, text) {
    $("statusDot").className = "dot" + (ok ? "" : " off");
    $("statusText").textContent = text;
  }

  function render(d) {
    $("cards").innerHTML =
      '<div class="metric"><b>' + d.total_participants + "</b><span>参与人数</span></div>" +
      '<div class="metric"><b>' + d.started_sessions + "</b><span>已开局数</span></div>" +
      '<div class="metric"><b>' + d.completed_sessions + "</b><span>已完成局数</span></div>" +
      '<div class="metric"><b>' + d.per_question.length + "</b><span>被回答的题目数</span></div>";

    const cats = Object.entries(d.by_category || {});
    $("cat").innerHTML = cats.length
      ? cats.map(([k, n]) =>
          '<span class="tag" style="margin:0 8px 8px 0;display:inline-block;padding:5px 12px;font-size:13px">' +
          esc(CATS[k] || k) + " · " + n + "</span>").join("")
      : '<span class="muted">暂无数据</span>';

    $("rows").innerHTML = d.per_question.length
      ? d.per_question.map((q) =>
          "<tr><td>" + esc(q.question_id) + " · " + esc(q.title) + "</td>" +
          '<td class="num">' + q.count + "</td>" +
          '<td class="num">' + Math.round(q.avg_p * 100) + "%</td>" +
          '<td><div class="bar"><i style="width:' + Math.round(q.avg_p * 100) + '%"></i></div></td></tr>'
        ).join("")
      : '<tr><td colspan="4" class="muted">暂无提交</td></tr>';

    $("updated").textContent = "最近更新：" + new Date().toLocaleTimeString("zh-CN") +
      " · 只显示匿名聚合数据，不显示个人昵称或单人预测";
    setStatus(true, "LIVE · 每 3 秒刷新");
  }

  async function tick() {
    try {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const d = await res.json();
      if (!d.ok) throw new Error(d.error || "bad payload");
      render(d);
    } catch (e) {
      setStatus(false, "连接中断 · 重试中");
    }
  }

  tick();
  setInterval(tick, 3000);
})();

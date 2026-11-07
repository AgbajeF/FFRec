"""Write docs/data.json and the static, mobile-first docs/index.html."""
import html
import json
import os

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>__TITLE__</title>
<style>
:root{
  --bg:#f6f7f9; --card:#ffffff; --text:#14171c; --muted:#5d6673; --line:#e3e6ea;
  --yellow:#f2c200; --yellow-text:#3b2f00; --green:#1f9d55; --blue:#2563eb; --orange:#ea6a12;
  --red:#d92d20; --red-bg:#fdecea; --fa:#e7f6ec; --fa-text:#13693a; --wv:#efeafd; --wv-text:#5b3cc4;
  --tag:#eef1f5; --up:#13693a; --down:#b42318; --news:#b54708; --news-bg:#fff4e5;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1115; --card:#1a1d23; --text:#f1f3f5; --muted:#a1a9b5; --line:#2b3038;
    --yellow-text:#2b2200; --red-bg:#3a1512; --fa:#123222; --fa-text:#7fe0a6; --wv:#251d45; --wv-text:#c4b5fd;
    --tag:#252a32; --up:#7fe0a6; --down:#ff9b8f; --news:#ffb35c; --news-bg:#3a2810;
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:18px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:640px;margin:0 auto;padding:16px 16px 48px}
.badge{display:inline-block;font-weight:800;font-size:17px;letter-spacing:.02em;padding:10px 14px;border-radius:12px;color:#fff}
.badge.yellow{background:var(--yellow);color:var(--yellow-text)} .badge.green{background:var(--green)}
.badge.blue{background:var(--blue)} .badge.orange{background:var(--orange)}
.sub{margin:10px 0 0;color:var(--muted);font-size:16px}
.countdown{margin:4px 0 0;font-size:20px;font-weight:700}
.alert{margin:16px 0 0;background:var(--red-bg);border:2px solid var(--red);color:var(--text);border-radius:14px;padding:14px 16px;font-weight:700;font-size:18px}
.alert b{color:var(--red)}
.notice{margin:12px 0 0;color:var(--muted);font-size:15px}
.tabs{display:flex;gap:8px;overflow-x:auto;margin:18px -16px 4px;padding:2px 16px 6px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;min-width:56px;min-height:44px;padding:0 16px;border-radius:22px;border:1px solid var(--line);background:var(--card);color:var(--text);font-weight:600;font-size:16px;line-height:44px;font-family:inherit;cursor:pointer}
.tab[aria-pressed=true]{background:var(--text);color:var(--bg);border-color:var(--text)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:12px 0}
.top{display:flex;gap:12px;align-items:flex-start}
.rank{flex:0 0 40px;height:40px;border-radius:50%;background:var(--tag);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px}
.who{flex:1;min-width:0}
.name{font-size:21px;font-weight:800;line-height:1.2}
.meta{color:var(--muted);font-size:16px;margin-top:2px}
.inj{color:var(--red);font-weight:700}
.pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.pill{font-size:14px;font-weight:700;padding:4px 10px;border-radius:999px;background:var(--tag)}
.pill.fa{background:var(--fa);color:var(--fa-text)} .pill.waivers{background:var(--wv);color:var(--wv-text)}
.pill.new{background:var(--blue);color:#fff} .pill.up{color:var(--up)} .pill.down{color:var(--down)}
.pill.news{background:var(--news-bg);color:var(--news)}
.reason{margin:12px 0 0;font-size:18px}
.row{margin:10px 0 0;font-size:16px;color:var(--muted)} .row strong{color:var(--text)}
.more-btn,.stats-btn{min-height:44px;border:0;background:none;color:var(--blue);font-weight:600;font-size:16px;font-family:inherit;padding:8px 0;cursor:pointer}
.stats{margin-top:6px;font-size:15px;color:var(--muted)}
.stats div{padding:6px 0;border-top:1px solid var(--line)}
.see-more{display:block;width:100%;margin:8px 0;min-height:52px;border-radius:14px;border:1px solid var(--line);background:var(--card);color:var(--text);font-weight:700;font-size:17px;font-family:inherit;cursor:pointer}
.empty{color:var(--muted);text-align:center;padding:24px 0}
.views{display:flex;gap:6px;margin:14px 0 0;background:var(--tag);border-radius:14px;padding:4px}
.view{flex:1;min-height:44px;border:0;border-radius:11px;background:none;color:var(--text);font-weight:700;font-size:16px;font-family:inherit;cursor:pointer}
.view[aria-pressed=true]{background:var(--card);box-shadow:0 1px 3px rgba(0,0,0,.15)}
h2{font-size:19px;margin:24px 0 4px}
.hint{color:var(--muted);font-size:15px;margin:0 0 8px}
.side{margin:8px 0 0;font-size:17px} .side b{display:inline-block;min-width:74px;color:var(--muted);font-weight:600;font-size:15px}
.pill.good{background:var(--fa);color:var(--fa-text)} .pill.bad{background:var(--red-bg);color:var(--down)}
select{width:100%;min-height:48px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--text);font:inherit;font-size:17px;padding:0 12px}
.pick-list{display:flex;flex-direction:column;gap:6px;margin-top:8px}
.pick{display:flex;justify-content:space-between;align-items:center;gap:8px;min-height:44px;padding:8px 12px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--text);font:inherit;font-size:16px;text-align:left;cursor:pointer}
.pick[aria-pressed=true]{border-color:var(--blue);box-shadow:inset 0 0 0 1px var(--blue);background:var(--wv)}
.pick small{color:var(--muted);font-size:14px;white-space:nowrap}
.result{position:sticky;bottom:8px;z-index:1}
.result .card{box-shadow:0 4px 16px rgba(0,0,0,.18)}
.verdict{font-size:20px;font-weight:800}
.ss-row{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--line)}
.ss-row:first-of-type{border-top:0;padding-top:4px}
.slot{flex:0 0 44px;min-height:32px;border-radius:10px;background:var(--tag);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px}
.ss-who{flex:1;min-width:0}
.ss-name{font-size:18px;font-weight:800;line-height:1.25}
.ss-meta{color:var(--muted);font-size:15px;margin-top:2px}
.ss-pts{flex:0 0 auto;max-width:96px;text-align:right;font-weight:800;font-size:19px;line-height:1.2}
.ss-pts small{display:block;color:var(--muted);font-weight:600;font-size:13px;white-space:nowrap}
.ss-pts .up{color:var(--up)} .ss-pts .down{color:var(--down)}
.ss-row .pill{white-space:nowrap}
.ss-row .pills{margin-top:6px}
.ss-row .row{margin-top:6px;font-size:15px}
.game{padding:10px 0;border-top:1px solid var(--line);font-size:16px}
.game:first-of-type{border-top:0;padding-top:0}
.game .ss-meta{font-size:14px}
.game.mine{font-weight:600}
.todo{font-size:18px;font-weight:700;margin:0}
.todo + .todo{margin-top:6px}
.wk{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px;font-variant-numeric:tabular-nums}
.wk th{color:var(--muted);font-weight:600;text-align:right;padding:4px 2px;border-bottom:1px solid var(--line)}
.wk td{text-align:right;padding:5px 2px;border-bottom:1px solid var(--line)}
.wk th:first-child,.wk td:first-child{text-align:left}
.wk tr:last-child td{border-bottom:0}
.wk .dim{color:var(--muted)}
.wk .hi{color:var(--up);font-weight:700} .wk .lo{color:var(--down);font-weight:700}
.try{min-height:40px;margin-top:8px;padding:0 14px;border-radius:12px;border:1px solid var(--blue);background:none;color:var(--blue);font:inherit;font-size:15px;font-weight:700;cursor:pointer}
footer{margin-top:28px;color:var(--muted);font-size:13px;text-align:center}
</style>
</head>
<body>
<main>
  <div id="badge" class="badge"></div>
  <p class="sub" id="updated"></p>
  <p class="countdown" id="countdown"></p>
  <div id="alert"></div>
  <div class="views" id="views" role="group" aria-label="Section">
    <button class="view" data-view="waivers" aria-pressed="true">Waivers</button>
    <button class="view" data-view="startsit" aria-pressed="false">Start/Sit</button>
    <button class="view" data-view="trends" aria-pressed="false">Trends</button>
    <button class="view" data-view="trades" aria-pressed="false">Trades</button>
  </div>
  <div id="waiverView">
    <div id="notices"></div>
    <nav class="tabs" id="tabs" aria-label="Position filter"></nav>
    <section id="top"></section>
    <button class="see-more" id="seeMore" hidden></button>
    <section id="rest" hidden></section>
  </div>
  <div id="startView" hidden></div>
  <div id="trendView" hidden></div>
  <div id="tradeView" hidden></div>
  <footer id="foot"></footer>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

$('badge').textContent = D.badge.text;
$('badge').className = 'badge ' + D.badge.color;
$('updated').textContent = 'Updated ' + D.generated_et + ' · Week ' + D.week + (D.team_name ? ' · ' + D.team_name : '');

function dur(ms){
  const m = Math.max(0, Math.round(ms / 60000));
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
  if (d) return d + 'd ' + h + 'h';
  if (h) return h + 'h ' + mm + 'm';
  return mm + 'm';
}
function tick(){
  const now = Date.now();
  const t = (D.countdown || []).find(c => Date.parse(c.iso) > now);
  $('countdown').textContent = t ? t.label + ' ' + dur(Date.parse(t.iso) - now)
    : (D.mode === 'waiver' ? 'Waivers have run. A new list is coming.' : 'All games this week have started.');
}
tick(); setInterval(tick, 30000);

if (D.alert) {
  const t = esc(D.alert.text).replace(/^(Your [^.]*\.)/, '<b>$1</b>');
  $('alert').innerHTML = '<div class="alert" role="alert">' + t + '</div>';
}
if (D.notices && D.notices.length) {
  $('notices').innerHTML = D.notices.map(n => '<p class="notice">ⓘ ' + esc(n) + '</p>').join('');
}

function ago(iso){
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  if (m < 60) return Math.max(1, m) + 'm ago';
  if (m < 1440) return Math.round(m / 60) + 'h ago';
  return Math.round(m / 1440) + 'd ago';
}

function card(p, n){
  const tags = (p.tags || []).map(t => '<span class="pill ' + t.kind + '">' + esc(t.text) + '</span>').join('');
  const news = p.news_iso ? '<span class="pill news">NEWS · ' + ago(p.news_iso) + '</span>' : '';
  const inj = p.injury ? ' · <span class="inj">' + esc(p.injury) + '</span>' : '';
  const s = p.stats || {};
  const wk = (s.weeks || []).map(w => '<div>Week ' + w.week + ': <strong>' + w.pts + ' pts</strong>' +
     (w.snap != null ? ' · ' + w.snap + '% snaps' : '') + (w.targets ? ' · ' + w.targets + ' tgt' : '') +
     (w.carries ? ' · ' + w.carries + ' car' : '') + (w.rz ? ' · ' + w.rz + ' red zone' : '') + '</div>').join('');
  const extra = [
    s.proj != null ? 'Projection: <strong>' + s.proj + ' pts</strong>' : null,
    s.opponent ? 'Next: <strong>' + esc(s.opponent) + '</strong>' : null,
    s.adds_24h ? 'Sleeper adds (24h): <strong>' + s.adds_24h.toLocaleString() + '</strong>' : null,
  ].filter(Boolean).map(x => '<div>' + x + '</div>').join('');
  return '<article class="card">' +
    '<div class="top"><div class="rank">' + n + '</div><div class="who">' +
      '<div class="name">' + esc(p.name) + '</div>' +
      '<div class="meta">' + esc(p.pos) + ' · ' + esc(p.team) + inj + '</div></div></div>' +
    '<div class="pills"><span class="pill ' + p.availability + '">' + esc(p.availability === 'fa' ? 'Free agent' : 'On waivers') + '</span>' + tags + news + '</div>' +
    '<p class="reason">' + esc(p.reason) + '</p>' +
    (p.availability === 'fa' ? '' : '<p class="row">' + esc(p.availability_label) + '</p>') +
    (p.drop ? '<p class="row">Drop: <strong>' + esc(p.drop) + '</strong></p>' : '') +
    '<p class="row"><strong>' + esc(p.advice) + '</strong></p>' +
    '<button class="stats-btn" aria-expanded="false">Show stats</button>' +
    '<div class="stats" hidden>' + (wk || '<div>No recent games.</div>') + extra + '</div>' +
  '</article>';
}

const positions = ['All'].concat(['QB','RB','WR','TE','K','DEF'].filter(x => D.picks.some(p => p.pos === x)),
  [...new Set(D.picks.map(p => p.pos))].filter(x => !['QB','RB','WR','TE','K','DEF'].includes(x)));
let pos = 'All', expanded = false;
let view = 'waivers';
try {
  const h = new URLSearchParams(location.hash.slice(1));
  pos = h.get('pos') || 'All';
  view = ['trades', 'startsit', 'trends'].includes(h.get('view')) ? h.get('view') : 'waivers';
} catch (e) {}
function saveHash(){ try { history.replaceState(null, '', '#' + (view !== 'waivers' ? 'view=' + view : 'pos=' + pos)); } catch (e) {} }
if (!positions.includes(pos)) pos = 'All';

function render(){
  $('tabs').innerHTML = positions.map(x => '<button class="tab" aria-pressed="' + (x === pos) + '" data-pos="' + x + '">' + x + '</button>').join('');
  const list = pos === 'All' ? D.picks.filter(p => p.rank) : D.picks.filter(p => p.pos === pos);
  const top = list.slice(0, 5), rest = list.slice(5, 20);
  $('top').innerHTML = top.length ? top.map((p, i) => card(p, i + 1)).join('') : '<p class="empty">No one worth adding here right now.</p>';
  $('rest').innerHTML = rest.map((p, i) => card(p, i + 6)).join('');
  $('seeMore').hidden = !rest.length;
  $('rest').hidden = !expanded || !rest.length;
  $('seeMore').textContent = expanded ? 'Show fewer' : 'See ' + rest.length + ' more';
}
document.addEventListener('click', e => {
  const t = e.target.closest('button');
  if (!t) return;
  if (t.dataset.view) { view = t.dataset.view; saveHash(); showView(); }
  else if (t.dataset.pos) { pos = t.dataset.pos; expanded = false; saveHash(); render(); }
  else if (t.dataset.give || t.dataset.get) { toggleTrade(t); }
  else if (t.dataset.tpos) { trendPos = t.dataset.tpos; renderTrends(); }
  else if (t.dataset.buy) { tryBuy(t.dataset.buy, +t.dataset.rid); }
  else if (t.dataset.open != null) { openSuggestion(+t.dataset.open); }
  else if (t.id === 'seeMore') { expanded = !expanded; render(); }
  else if (t.classList.contains('stats-btn')) {
    const box = t.nextElementSibling, open = box.hidden;
    box.hidden = !open; t.setAttribute('aria-expanded', open); t.textContent = open ? 'Hide stats' : 'Show stats';
  }
});
render();
__TRADES_JS__
showView();
$('foot').textContent = (D.league_name || '') + ' · Stats through week ' + D.stats_week;
})();
</script>
</body>
</html>
"""

TRENDS_JS = r"""// ---------------------------------------------------------------- trends
const TR = D.trends;
let trendPos = 'All';
const COLS = {
  QB: [['pts','Pts'],['xpts','xPts'],['snap','Snap%'],['car','Car'],['rz','RZ']],
  RB: [['pts','Pts'],['xpts','xPts'],['snap','Snap%'],['car','Car'],['tgt','Tgt'],['rz','RZ']],
  WR: [['pts','Pts'],['xpts','xPts'],['snap','Snap%'],['tgt','Tgt'],['tgt_share','Tgt%'],['air','Air'],['rz','RZ']],
};
COLS.TE = COLS.WR;
function weekTable(r){
  const cols = COLS[r.pos];
  let h = '<table class="wk"><thead><tr><th>Wk</th>' + cols.map(c => '<th>' + c[1] + '</th>').join('') + '</tr></thead><tbody>';
  h += r.weeks.slice().reverse().map(w => {
    if (!w.played) return '<tr><td>' + w.week + '</td><td class="dim" colspan="' + cols.length + '" style="text-align:left">Did not play</td></tr>';
    return '<tr><td>' + w.week + '</td>' + cols.map(c => {
      let v = w[c[0]], cls = '';
      if (c[0] === 'pts' && w.xpts != null) cls = w.pts >= w.xpts + 4 ? 'hi' : w.pts <= w.xpts - 4 ? 'lo' : '';
      if (c[0] === 'xpts') cls = 'dim';
      return '<td class="' + cls + '">' + (v == null ? '–' : v) + '</td>';
    }).join('') + '</tr>';
  }).join('');
  return h + '</tbody></table>';
}
function trendCard(r){
  const s = r.season;
  const arrow = r.trend === 'up' ? '<span class="pill good">▲ Role growing</span>' : r.trend === 'down' ? '<span class="pill bad">▼ Role shrinking</span>' : '';
  const lk = s && s.label !== 'Too early' ? '<span class="pill ' + esc(s.kind) + '">' + esc(s.label) + '</span>' : '';
  const line = s ? '<p class="row">Season: <strong>' + s.pts + '</strong> pts a game vs <strong>' + s.xpts + '</strong> expected (' +
      (s.diff > 0 ? '+' : '') + s.diff + ') over ' + s.games + ' game' + (s.games > 1 ? 's' : '') + '.</p><p class="row">' + esc(s.text) + '</p>' : '';
  return '<article class="card"><div class="ss-name">' + esc(r.name) + (r.injury ? ' <span class="inj">' + esc(r.injury) + '</span>' : '') + '</div>' +
    '<div class="ss-meta">' + esc(r.pos + ' · ' + r.team) + '</div>' +
    ((arrow || lk) ? '<div class="pills">' + arrow + lk + '</div>' : '') + line + weekTable(r) + '</article>';
}
function luckRow(r, buy){
  return '<div class="ss-row"><div class="ss-who"><div class="ss-name">' + esc(r.name) + '</div>' +
    '<div class="ss-meta">' + esc(r.pos + ' · ' + r.team + (buy ? ' · ' + r.owner : '')) + '</div>' +
    '<p class="row">' + r.pts + ' pts a game on ' + r.xpts + ' expected over ' + r.games + ' games</p>' +
    (buy && T ? '<button class="try" data-buy="' + esc(r.player_id) + '" data-rid="' + r.roster_id + '">Try a trade</button>' : '') +
    '</div><div class="ss-pts">' + (r.diff > 0 ? '+' : '') + r.diff + '<small>pts a game</small></div></div>';
}
function tryBuy(pid, rid){
  tradeWith = rid; give = new Set(); get = new Set([pid]);
  view = 'trades'; saveHash(); showView();
  $('analyzer').scrollIntoView({behavior: 'smooth'});
}
function renderTrends(){
  const box = $('trendView');
  if (!TR) { box.innerHTML = '<p class="empty">Trends are unavailable right now. They\'ll be back on the next update.</p>'; return; }
  let h = '';
  if (TR.sell_high.length) h += '<h2>Sell high</h2><p class="hint">Your players scoring well above what their usage is worth. Expect them to cool off.</p><div class="card">' + TR.sell_high.map(r => luckRow(r, false)).join('') + '</div>';
  if (TR.buy_low.length) h += '<h2>Buy low around your league</h2><p class="hint">Players on other teams with a strong role who are scoring well below it. Their managers may sell cheap.</p><div class="card">' + TR.buy_low.map(r => luckRow(r, true)).join('') + '</div>';
  const posList = ['All'].concat(['QB','RB','WR','TE'].filter(p => TR.players.some(r => r.pos === p)));
  h += '<h2>Your players</h2><p class="hint">Last ' + TR.weeks.length + ' weeks, newest first. xPts is what an average player would score with the same targets, carries and field position, so the gap is mostly touchdown luck. Snap% is share of offensive snaps, Tgt% share of team targets, Air is air yards and RZ is red-zone targets plus carries.</p>';
  h += '<nav class="tabs">' + posList.map(p => '<button class="tab" aria-pressed="' + (p === trendPos) + '" data-tpos="' + p + '">' + p + '</button>').join('') + '</nav>';
  const list = TR.players.filter(r => trendPos === 'All' || r.pos === trendPos);
  h += list.length ? list.map(trendCard).join('') : '<p class="empty">No players here.</p>';
  h += '<p class="notice">Usage: Sleeper and nflverse. Expected points: ffverse ffopportunity' + (TR.ep_through ? ', through week ' + TR.ep_through : '') + '.</p>';
  box.innerHTML = h;
}
"""

STARTSIT_JS = r"""// ---------------------------------------------------------------- start/sit
const S = D.start_sit;
function ssPts(r){
  if (r.bye || r.adj == null) return '<div class="ss-pts">' + (r.bye ? 'BYE' : '–') + '</div>';
  const d = r.delta ? ' <span class="' + (r.delta > 0 ? 'up' : 'down') + '">' + (r.delta > 0 ? '+' : '') + r.delta.toFixed(1) + '</span>' : '';
  return '<div class="ss-pts">' + r.adj.toFixed(1) + '<small>proj ' + r.proj.toFixed(1) + d + '</small></div>';
}
function ssLine(r){
  const bits = [];
  if (r.total != null) bits.push('O/U <strong>' + r.total + '</strong>');
  if (r.spread) bits.push(esc(r.spread));
  if (r.implied != null) bits.push('Team total <strong>' + r.implied + '</strong>' + (r.implied_rank ? ' (#' + r.implied_rank + ')' : ''));
  const out = [];
  if (bits.length) out.push('<p class="row">' + bits.join(' · ') + '</p>');
  if (r.weather) out.push('<p class="row">' + esc(r.weather) + '</p>');
  if (r.close_call) out.push('<p class="row"><strong>' + esc(r.close_call) + '</strong></p>');
  return out.join('');
}
function ssRow(r, label){
  if (!r.name) return '<div class="ss-row"><div class="slot">' + esc(label) + '</div><div class="ss-who"><div class="ss-name">Empty</div><div class="ss-meta">No healthy player for this slot.</div></div></div>';
  const flags = (r.flags || []).map(f => '<span class="pill ' + esc(f.kind) + '">' + esc(f.text) + '</span>').join('') +
    (r.locked ? '<span class="pill">Locked</span>' : '');
  const meta = [r.pos + ' · ' + r.team, r.opp, r.kickoff_et].filter(Boolean).map(esc).join(' · ');
  return '<div class="ss-row"><div class="slot">' + esc(label) + '</div><div class="ss-who">' +
    '<div class="ss-name">' + esc(r.name) + (r.injury && !r.bye ? ' <span class="inj">' + esc(r.injury) + '</span>' : '') + '</div>' +
    '<div class="ss-meta">' + meta + '</div>' + (flags ? '<div class="pills">' + flags + '</div>' : '') + ssLine(r) +
    '</div>' + ssPts(r) + '</div>';
}
function renderStartSit(){
  const box = $('startView');
  if (!S) { box.innerHTML = '<p class="empty">Start/Sit is unavailable right now. It\'ll be back on the next update.</p>'; return; }
  let h = '<div class="card">';
  if (S.start.length || S.sit.length) {
    h += '<p class="todo">Change in Sleeper:</p>';
    if (S.start.length) h += '<p class="row">Start <strong>' + S.start.map(esc).join(', ') + '</strong></p>';
    if (S.sit.length) h += '<p class="row">Bench <strong>' + S.sit.map(esc).join(', ') + '</strong></p>';
  } else {
    h += '<p class="todo">Your Sleeper lineup already matches the best one.</p>';
  }
  if (S.empty_slots) h += '<p class="row" style="color:var(--red)"><strong>You have ' + S.empty_slots + ' empty starting slot' + (S.empty_slots > 1 ? 's' : '') + ' in Sleeper.</strong></p>';
  h += '</div>';
  h += '<h2>Best lineup</h2><p class="hint">Big number: Sleeper projection adjusted for Vegas team totals, spreads and game-time weather. Green or red shows how much the adjustment moved it.</p>';
  h += '<div class="card">' + S.lineup.map(r => ssRow(r, ({SUPER_FLEX: 'SF', REC_FLEX: 'W/T', WRRB_FLEX: 'W/R', IDP_FLEX: 'IDP'})[r.slot] || r.slot)).join('') + '</div>';
  if (S.bench.length) h += '<h2>Bench</h2><div class="card">' + S.bench.map(r => ssRow(r, 'BN')).join('') + '</div>';
  if (S.games.length) {
    h += '<h2>Games by over/under</h2><p class="hint">Higher totals mean more points to go around. Your players are listed under each game.</p><div class="card">';
    h += S.games.map(g => {
      const imp = g.away_implied != null ? g.away + ' ' + g.away_implied + ', ' + g.home + ' ' + g.home_implied : null;
      const meta = [g.kickoff_et, g.spread, imp ? 'Team totals: ' + imp : null, g.weather].filter(Boolean).map(esc).join(' · ');
      return '<div class="game' + (g.mine.length ? ' mine' : '') + '"><div><strong>' + esc(g.away) + ' @ ' + esc(g.home) + '</strong>' +
        (g.total != null ? ' · O/U ' + g.total : '') + '</div><div class="ss-meta">' + meta + '</div>' +
        (g.mine.length ? '<div class="ss-meta">Yours: ' + g.mine.map(esc).join(', ') + '</div>' : '') + '</div>';
    }).join('') + '</div>';
  }
  h += '<p class="notice">Lines: ' + esc(S.lines_source || 'unavailable this week') + '. Weather: ' +
    (S.has_weather ? 'Open-Meteo forecast for the middle of each outdoor game.' : 'shown within 7 days of kickoff.') + '</p>';
  box.innerHTML = h;
}
"""

TRADES_JS = r"""// ---------------------------------------------------------------- trades
const T = D.trades;
let tradeWith = null, give = new Set(), get = new Set();

function showView(){
  document.querySelectorAll('.view').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === view));
  $('waiverView').hidden = view !== 'waivers';
  $('tradeView').hidden = view !== 'trades';
  $('startView').hidden = view !== 'startsit';
  $('trendView').hidden = view !== 'trends';
  if (view === 'trends') renderTrends();
  if (view === 'trades') renderTrades();
  if (view === 'startsit') renderStartSit();
}

const byId = {};
if (T) T.teams.forEach(t => t.players.forEach(p => { byId[p.id] = p; }));
const val = id => (byId[id] || {}).value || 0;
const nm = id => (byId[id] || {}).name || id;
const team = rid => T.teams.find(t => t.roster_id === rid);
const ids = t => t.players.map(p => p.id);

// Same math as ffwaiver/trades.py, so the analyzer matches the suggestions.
function bestLineup(pids){
  const order = T.slots.map((s, i) => i).sort((a, b) => T.slot_elig[T.slots[a]].length - T.slot_elig[T.slots[b]].length);
  const st = new Set();
  order.forEach(i => {
    const elig = T.slot_elig[T.slots[i]];
    let best = null;
    pids.forEach(p => { if (!st.has(p) && elig.includes((byId[p] || {}).pos) && (best === null || val(p) > val(best))) best = p; });
    if (best !== null) st.add(best);
  });
  return st;
}
function teamScore(pids){
  const st = bestLineup(pids);
  let total = 0; st.forEach(p => { total += val(p); });
  const bench = pids.filter(p => !st.has(p) && !['K', 'DEF'].includes((byId[p] || {}).pos)).map(val).sort((a, b) => b - a).slice(0, T.bench_n);
  return {total: total + T.bench_w * bench.reduce((a, b) => a + b, 0), st};
}
function afterTrade(pids, out, inc){
  let nw = pids.filter(p => !out.includes(p)).concat(inc);
  const extra = nw.length - pids.length;
  if (extra > 0) {
    const st = bestLineup(nw);
    const drop = new Set(nw.filter(p => !st.has(p) && !inc.includes(p)).sort((a, b) => val(a) - val(b)).slice(0, extra));
    nw = nw.filter(p => !drop.has(p));
  }
  return nw;
}
function pkg(pids){ return Math.round(pids.map(val).sort((a, b) => b - a).reduce((s, v, i) => s + v * Math.pow(T.decay, i), 0)); }
function sideImpact(pids, out, inc){
  const b = teamScore(pids), nw = afterTrade(pids, out, inc), a = teamScore(nw);
  return {pct: Math.round(1000 * (a.total - b.total) / (b.total || 1)) / 10,
          starts: inc.filter(p => a.st.has(p)), dropped: pids.filter(p => !out.includes(p) && !nw.includes(p))};
}
function analyze(myP, thP, g, r){
  const gv = pkg(g), rv = pkg(r), top = Math.max(gv, rv) || 1, pct = Math.round(100 * (rv - gv) / top);
  const text = Math.abs(pct) <= T.fair_pct ? 'Fair trade' : pct > 0 ? 'You win this trade' : "You'd be overpaying";
  return {gv, rv, pct, text, me: sideImpact(myP, g, r), them: sideImpact(thP, r, g)};
}

const signed = x => (x > 0 ? '+' : '') + x + '%';
const kind = x => x > 0 ? 'good' : x < 0 ? 'bad' : '';

function suggestionCard(s, i){
  return '<article class="card"><div class="name">With ' + esc(s.team) + '</div>' +
    '<p class="side"><b>You give</b> ' + esc(s.give_names.join(' + ')) + '</p>' +
    '<p class="side"><b>You get</b> ' + esc(s.get_names.join(' + ')) + '</p>' +
    '<div class="pills"><span class="pill">' + esc(s.verdict) + '</span>' +
    '<span class="pill ' + kind(s.my_delta_pct) + '">Your lineup ' + signed(s.my_delta_pct) + '</span>' +
    '<span class="pill ' + kind(s.their_delta_pct) + '">Theirs ' + signed(s.their_delta_pct) + '</span></div>' +
    '<p class="reason">' + esc(s.reason) + '</p>' +
    '<button class="more-btn" data-open="' + i + '">Open in analyzer</button></article>';
}

function pickRow(p, key, on){
  const inj = p.inj ? ' · <span class="inj">' + esc(p.inj) + '</span>' : '';
  return '<button class="pick" data-' + key + '="' + esc(p.id) + '" aria-pressed="' + on + '"><span><strong>' + esc(p.name) +
    '</strong> <small>' + esc(p.pos || '') + ' · ' + esc(p.team) + '</small>' + inj + '</span><small>' +
    (p.value ? p.value.toLocaleString() : '-') + '</small></button>';
}

function analyzerResult(){
  if (!give.size && !get.size) return '<div class="card"><p class="hint" style="margin:0">Tap players on both sides to see who wins the trade.</p></div>';
  const me = team(T.my_roster_id), th = team(tradeWith);
  const a = analyze(ids(me), ids(th), [...give], [...get]);
  const starts = a.me.starts.length ? '<p class="row">Would start for you: <strong>' + esc(a.me.starts.map(nm).join(', ')) + '</strong></p>' : '';
  const drop = a.me.dropped.length ? '<p class="row">You\'d need to drop: <strong>' + esc(a.me.dropped.map(nm).join(', ')) + '</strong></p>' : '';
  return '<div class="card"><div class="verdict">' + esc(a.text) + '</div>' +
    '<p class="row">You give <strong>' + a.gv.toLocaleString() + '</strong> · You get <strong>' + a.rv.toLocaleString() + '</strong> (' + signed(a.pct) + ' value)</p>' +
    '<div class="pills"><span class="pill ' + kind(a.me.pct) + '">Your lineup ' + signed(a.me.pct) + '</span>' +
    '<span class="pill ' + kind(a.them.pct) + '">Their lineup ' + signed(a.them.pct) + '</span></div>' + starts + drop +
    (a.them.pct < 0 && a.pct > 0 ? '<p class="row">This hurts their team, so expect a no.</p>' : '') + '</div>';
}

function renderTrades(){
  const box = $('tradeView');
  if (!T) { box.innerHTML = '<p class="empty">Trade values are unavailable right now. They\'ll be back on the next update.</p>'; return; }
  if (tradeWith === null) tradeWith = (T.teams.find(t => t.roster_id !== T.my_roster_id) || {}).roster_id;
  const me = team(T.my_roster_id), th = team(tradeWith);
  let h = (T.notices || []).map(n => '<p class="notice">ⓘ ' + esc(n) + '</p>').join('');
  h += '<h2>Suggested trades</h2><p class="hint">Trades that make your starting lineup better without hurting theirs, at fair value.</p>';
  h += T.suggestions.length ? T.suggestions.map(suggestionCard).join('') : '<p class="empty">No trades that clearly help both teams right now.</p>';
  h += '<h2 id="analyzer">Trade analyzer</h2><select id="tradeWith" aria-label="Trade with">' +
    T.teams.filter(t => t.roster_id !== T.my_roster_id).map(t => '<option value="' + t.roster_id + '"' + (t.roster_id === tradeWith ? ' selected' : '') + '>Trade with ' + esc(t.name) + '</option>').join('') + '</select>';
  h += '<h2>You give</h2><div class="pick-list">' + me.players.map(p => pickRow(p, 'give', give.has(p.id))).join('') + '</div>';
  h += '<h2>You get</h2><div class="pick-list">' + th.players.map(p => pickRow(p, 'get', get.has(p.id))).join('') + '</div>';
  h += '<div class="result" id="result">' + analyzerResult() + '</div>';
  if (T.recent && T.recent.length) {
    h += '<h2>Recent trades in your league</h2>' + T.recent.map(r => '<article class="card"><div class="meta">Week ' + r.week + '</div>' +
      r.sides.map(s => '<p class="side"><b>' + esc(s.team) + '</b> got ' + esc(s.got.join(', ') || 'nothing') + '</p>').join('') +
      '<p class="row"><strong>' + esc(r.summary) + '</strong></p></article>').join('');
  }
  h += '<p class="notice">Values: ' + esc(T.source) + '. Higher is better; a top-5 player is about 9,000.</p>';
  box.innerHTML = h;
  $('tradeWith').onchange = e => { tradeWith = +e.target.value; get.clear(); renderTrades(); };
}

function toggleTrade(t){
  const set = t.dataset.give ? give : get, id = t.dataset.give || t.dataset.get;
  set.has(id) ? set.delete(id) : set.add(id);
  t.setAttribute('aria-pressed', set.has(id));
  $('result').innerHTML = analyzerResult();
}

function openSuggestion(i){
  const s = T.suggestions[i];
  tradeWith = s.roster_id; give = new Set(s.give); get = new Set(s.get);
  renderTrades();
  $('analyzer').scrollIntoView({behavior: 'smooth'});
}
"""
TEMPLATE = TEMPLATE.replace("__TRADES_JS__", TRADES_JS + STARTSIT_JS + TRENDS_JS)


def write(data, docs_dir):
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "data.json"), "w") as f:
        json.dump(data, f, indent=1, default=str)
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    page = TEMPLATE.replace("__TITLE__", html.escape(f"Waiver Wire · Week {data['week']}")) \
                   .replace("__DATA__", payload)
    with open(os.path.join(docs_dir, "index.html"), "w") as f:
        f.write(page)
    # Disable Jekyll so GitHub Pages serves files as-is.
    open(os.path.join(docs_dir, ".nojekyll"), "w").close()

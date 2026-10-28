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
    <button class="view" data-view="trades" aria-pressed="false">Trades</button>
  </div>
  <div id="waiverView">
    <div id="notices"></div>
    <nav class="tabs" id="tabs" aria-label="Position filter"></nav>
    <section id="top"></section>
    <button class="see-more" id="seeMore" hidden></button>
    <section id="rest" hidden></section>
  </div>
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
  view = h.get('view') === 'trades' ? 'trades' : 'waivers';
} catch (e) {}
function saveHash(){ try { history.replaceState(null, '', '#' + (view === 'trades' ? 'view=trades' : 'pos=' + pos)); } catch (e) {} }
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

TRADES_JS = r"""// ---------------------------------------------------------------- trades
const T = D.trades;
let tradeWith = null, give = new Set(), get = new Set();

function showView(){
  document.querySelectorAll('.view').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === view));
  $('waiverView').hidden = view !== 'waivers';
  $('tradeView').hidden = view !== 'trades';
  if (view === 'trades') renderTrades();
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
TEMPLATE = TEMPLATE.replace("__TRADES_JS__", TRADES_JS)


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

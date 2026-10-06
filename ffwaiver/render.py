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
footer{margin-top:28px;color:var(--muted);font-size:13px;text-align:center}
</style>
</head>
<body>
<main>
  <div id="badge" class="badge"></div>
  <p class="sub" id="updated"></p>
  <p class="countdown" id="countdown"></p>
  <div id="alert"></div>
  <div id="notices"></div>
  <nav class="tabs" id="tabs" aria-label="Position filter"></nav>
  <section id="top"></section>
  <button class="see-more" id="seeMore" hidden></button>
  <section id="rest" hidden></section>
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
try { pos = new URLSearchParams(location.hash.slice(1)).get('pos') || 'All'; } catch (e) {}
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
  if (t.dataset.pos) { pos = t.dataset.pos; expanded = false; try { history.replaceState(null, '', '#pos=' + pos); } catch (e) {} render(); }
  else if (t.id === 'seeMore') { expanded = !expanded; render(); }
  else if (t.classList.contains('stats-btn')) {
    const box = t.nextElementSibling, open = box.hidden;
    box.hidden = !open; t.setAttribute('aria-expanded', open); t.textContent = open ? 'Hide stats' : 'Show stats';
  }
});
render();
$('foot').textContent = (D.league_name || '') + ' · Stats through week ' + D.stats_week;
})();
</script>
</body>
</html>
"""


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

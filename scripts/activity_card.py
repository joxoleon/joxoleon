"""Render a static "<year> in numbers" card from the GitHub contribution calendar.

Writes <out>/activity-dark.svg and <out>/activity-light.svg. Counts include private contributions
when the profile shows them. Run by .github/workflows/profile-assets.yml every day.

Env: GH_TOKEN (any token that can read public profile data), GH_USER, OUT_DIR (default dist).
"""
import calendar
import datetime as dt
import json
import os
import urllib.request

USER = os.environ.get("GH_USER", "joxoleon")
OUT = os.environ.get("OUT_DIR", "dist")
TOKEN = os.environ["GH_TOKEN"]

today = dt.datetime.now(dt.timezone.utc).date()
year = today.year
query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) { contributionsCollection(from: $from, to: $to) {
    contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }"""
variables = {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{today.isoformat()}T23:59:59Z"}
req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps({"query": query, "variables": variables}).encode(),
    headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-card"},
)
data = json.load(urllib.request.urlopen(req, timeout=30))
weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
days = sorted(
    (d["date"], d["contributionCount"])
    for w in weeks
    for d in w["contributionDays"]
    if f"{year}-01-01" <= d["date"] <= today.isoformat()
)
if not days:
    raise SystemExit("no contribution data returned")

total = sum(c for _, c in days)
active = sum(1 for _, c in days if c > 0)
busiest_date, busiest = max(days, key=lambda x: (x[1], x[0]))
months = [0] * 12
for d, c in days:
    months[int(d[5:7]) - 1] += c
best_month_idx = max(range(12), key=lambda i: months[i])
longest = run = 0
for _, c in days:
    run = run + 1 if c > 0 else 0
    longest = max(longest, run)
current = 0
for i, (d, c) in enumerate(reversed(days)):
    if c > 0:
        current += 1
    elif i == 0:
        continue  # today may not have contributions yet
    else:
        break


def fmt(n):
    return f"{n:,}"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{calendar.month_abbr[d.month]} {d.day}"


stats = [
    (fmt(total), "contributions", f"Jan 1 to {short_date(days[-1][0])}"),
    (fmt(active), "active days", f"of {len(days)} so far"),
    (fmt(busiest), "busiest day", short_date(busiest_date)),
    (fmt(months[best_month_idx]), "best month", calendar.month_name[best_month_idx + 1]),
    (fmt(longest), "longest streak", f"current: {current} days"),
]

THEMES = {
    "dark": dict(title="#E6EDF3", fg="#C9D1D9", muted="#8B949E", accent="#58A6FF", rule="#30363D", empty="#21262D"),
    "light": dict(title="#1F2328", fg="#1F2328", muted="#656D76", accent="#0969DA", rule="#D0D7DE", empty="#EAEEF2"),
}
W, H = 880, 340
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def render(t):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         '<defs><linearGradient id="bar" x1="0" y1="1" x2="0" y2="0">'
         '<stop offset="0" stop-color="#1F6FEB"/><stop offset="1" stop-color="#7F52FF"/></linearGradient></defs>',
         f'<text x="{W/2}" y="30" text-anchor="middle" font-size="18" font-weight="600" fill="{t["title"]}">{year} in numbers</text>']
    col = W / len(stats)
    for i, (big, label, sub) in enumerate(stats):
        x = col * i + col / 2
        o.append(f'<text x="{x}" y="84" text-anchor="middle" font-size="30" font-weight="700" fill="{t["accent"]}">{big}</text>')
        o.append(f'<text x="{x}" y="108" text-anchor="middle" font-size="13" font-weight="600" fill="{t["fg"]}">{label}</text>')
        o.append(f'<text x="{x}" y="126" text-anchor="middle" font-size="11" fill="{t["muted"]}">{sub}</text>')
    o.append(f'<line x1="40" y1="148" x2="{W-40}" y2="148" stroke="{t["rule"]}" stroke-width="1"/>')
    o.append(f'<text x="40" y="172" font-size="11" fill="{t["muted"]}">Contributions per month</text>')
    top, base = 196, 304
    slot = (W - 80) / 12
    peak = max(months) or 1
    current_month = today.month
    for i in range(12):
        cx = 40 + slot * i + slot / 2
        bw = slot * 0.56
        if i + 1 <= current_month:
            h = max(2, (base - top) * months[i] / peak)
            o.append(f'<rect x="{cx-bw/2:.1f}" y="{base-h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="url(#bar)"/>')
            o.append(f'<text x="{cx:.1f}" y="{base-h-6:.1f}" text-anchor="middle" font-size="11" fill="{t["fg"]}">{fmt(months[i])}</text>')
        else:
            o.append(f'<rect x="{cx-bw/2:.1f}" y="{base-2}" width="{bw:.1f}" height="2" rx="1" fill="{t["empty"]}"/>')
        o.append(f'<text x="{cx:.1f}" y="{base+18}" text-anchor="middle" font-size="11" fill="{t["muted"]}">{calendar.month_abbr[i+1]}</text>')
    o.append("</svg>")
    return "\n".join(o)


os.makedirs(OUT, exist_ok=True)
for name, theme in THEMES.items():
    with open(os.path.join(OUT, f"activity-{name}.svg"), "w", encoding="utf-8") as f:
        f.write(render(theme))
print(f"{year}: {total} contributions, {active}/{len(days)} active days, busiest {busiest} on {busiest_date}, "
      f"best month {calendar.month_name[best_month_idx+1]} ({months[best_month_idx]}), longest streak {longest}, current {current}")

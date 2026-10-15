import json, urllib.request, sys, time
from concurrent.futures import ThreadPoolExecutor

def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as ex:
            last = ex; time.sleep(1.5*(i+1))
    raise last

teams = {}
games = []
for wk in range(6, 19):
    sb = get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week={wk}')
    for e in sb.get('events', []):
        comp = e['competitions'][0]
        home = away = None
        for c in comp['competitors']:
            t = c['team']
            teams[t['id']] = {'id': t['id'], 'abbr': t['abbreviation'], 'name': t['displayName'],
                              'color': t.get('color','333333'), 'logo': t.get('logo','')}
            if c['homeAway'] == 'home': home = t['id']
            else: away = t['id']
        odds = (comp.get('odds') or [{}])[0]
        games.append({'week': wk, 'id': e['id'], 'date': e['date'], 'home': home, 'away': away,
                      'ml_h': ((odds.get('homeTeamOdds') or {}).get('moneyLine')),
                      'ml_a': ((odds.get('awayTeamOdds') or {}).get('moneyLine'))})
print('schedule loaded:', len(games), 'games,', len(teams), 'teams', file=sys.stderr)

def implied(ml):
    if ml is None: return None
    return (-ml)/((-ml)+100) if ml < 0 else 100/(ml+100)

def fetch_pred(g):
    try:
        p = get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{g['id']}/competitions/{g['id']}/predictor?lang=en&region=us", tries=3)
        def gp(side):
            for s in p[side]['statistics']:
                if s['name'] == 'gameProjection': return round(s['value'], 1)
        h, a = gp('homeTeam'), gp('awayTeam')
        if h is not None and a is not None:
            tot = h + a
            return round(h/tot*100, 1), round(a/tot*100, 1), 'ESPN Predictor'
    except Exception as ex:
        print('pred fail', g['id'], type(ex).__name__, file=sys.stderr)
    ih, ia = implied(g['ml_h']), implied(g['ml_a'])
    if ih and ia:
        tot = ih + ia
        return round(ih/tot*100, 1), round(ia/tot*100, 1), 'Moneyline implied'
    return 50.0, 50.0, 'No data'

with ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(fetch_pred, games))
for g, (h, a, src) in zip(games, results):
    g['homeWP'], g['awayWP'], g['src'] = h, a, src
    del g['ml_h'], g['ml_a']

out = {'teams': teams, 'games': games, 'weeks': list(range(6, 19)), 'currentWeek': 6,
       'generatedAt': 'October 15, 2026'}
json.dump(out, open('/tmp/nfl-data.json', 'w'))
srcs = {}
for g in games: srcs[g['src']] = srcs.get(g['src'], 0) + 1
print('teams:', len(teams), 'games:', len(games), 'sources:', srcs)

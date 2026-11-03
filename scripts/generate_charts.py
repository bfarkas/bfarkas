#!/usr/bin/env python3
"""Render public GitHub contribution data as theme-aware workshop charts."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.request

OUT = Path(__file__).resolve().parents[1] / 'assets' / 'generated'
QUERY = '''query($login:String!) { user(login:$login) { contributionsCollection { contributionCalendar { totalContributions weeks { contributionDays { contributionCount contributionLevel date } } } } } }'''
THEMES = {
    'dark': dict(bg='#201b3a', frame='#65538e', text='#f2dda7', muted='#c6b5d6', empty='#443b5b', colors=['#443b5b', '#51447c', '#7863a3', '#a68bc1', '#f2bd6b']),
    'light': dict(bg='#fbefd7', frame='#a97a52', text='#45343b', muted='#69504c', empty='#e7d4b8', colors=['#e7d4b8', '#c3d2a0', '#8cb075', '#638d64', '#426c59']),
}

def text(x, y, value, size=14, color=None):
    return f'<text x="{x}" y="{y}" fill="{color or "currentColor"}" font-family="monospace" font-size="{size}">{value}</text>'

def wrap(content, theme, height, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" role="img" aria-label="{title}">'
            f'<title>{title}</title><rect width="720" height="{height}" fill="{theme["bg"]}"/>'
            f'<path d="M4 4H716V{height-4}H4Z" fill="none" stroke="{theme["frame"]}" stroke-width="4"/>'
            f'<g color="{theme["text"]}">{content}</g></svg>')

def placeholder(theme, name):
    body = text(24, 35, name, 17) + text(24, 66, 'Awaiting the first GitHub Actions update.', 13, theme['muted'])
    return wrap(body, theme, 90, name)

def charts(calendar, theme):
    weeks = calendar['weeks'][-53:]
    levels = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2, 'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
    body = text(22, 30, 'THE ADVENTURE LOG', 17)
    body += text(22, 50, f'{calendar["totalContributions"]} contributions in the last year', 12, theme['muted'])
    totals = [0] * 7
    for x, week in enumerate(weeks):
        for day in week['contributionDays']:
            d = dt.date.fromisoformat(day['date'])
            weekday = (d.weekday() + 1) % 7
            totals[weekday] += day['contributionCount']
            color = theme['colors'][levels[day['contributionLevel']]]
            body += f'<rect x="{24+x*12}" y="{66+weekday*12}" width="9" height="9" fill="{color}"/>'
    body += text(24, 170, 'LESS', 11, theme['muted'])
    for i, color in enumerate(theme['colors']):
        body += f'<rect x="{67+i*13}" y="160" width="9" height="9" fill="{color}"/>'
    body += text(138, 170, 'MORE', 11, theme['muted'])
    calendar_svg = wrap(body, theme, 185, 'The adventure log: contributions over the last year')
    body = text(22, 30, 'WORKSHOP RHYTHM', 17)
    body += text(22, 49, 'Contributions by weekday over the last year', 12, theme['muted'])
    max_total = max(totals, default=0)
    for i, (label, value) in enumerate(zip(['SUN','MON','TUE','WED','THU','FRI','SAT'], totals)):
        x = 29 + i * 98
        height = round(value / max_total * 75) if max_total else 0
        body += f'<rect x="{x}" y="{143-height}" width="48" height="{height}" fill="{theme["colors"][3]}"/>'
        body += text(x, 158, label, 12, theme['muted'])
        body += text(x, 139-height, str(value), 12)
    rhythm_svg = wrap(body, theme, 175, 'Workshop rhythm: contributions by weekday')
    return calendar_svg, rhythm_svg

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--placeholder' in sys.argv:
        for name, theme in THEMES.items():
            for filename, title in [('adventure-log','THE ADVENTURE LOG'), ('workshop-rhythm','WORKSHOP RHYTHM')]:
                (OUT / f'{filename}-{name}.svg').write_text(placeholder(theme, title))
        return
    token = os.environ['GITHUB_TOKEN']
    request = urllib.request.Request('https://api.github.com/graphql', data=json.dumps({'query': QUERY, 'variables': {'login': 'bfarkas'}}).encode(), headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'bfarkas-profile'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get('errors') or not data.get('data', {}).get('user'):
        raise RuntimeError(f'GitHub GraphQL failed: {data.get("errors", "user not found")}')
    calendar = data['data']['user']['contributionsCollection']['contributionCalendar']
    for name, theme in THEMES.items():
        for filename, svg in zip(['adventure-log', 'workshop-rhythm'], charts(calendar, theme)):
            (OUT / f'{filename}-{name}.svg').write_text(svg)

if __name__ == '__main__':
    main()

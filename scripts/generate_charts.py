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
    'dark': dict(bg='#15132b', frame='#df8c61', text='#fff4cf', muted='#d6c9e8', colors=['#35334d', '#4d8aa3', '#69bcb0', '#c5db7e', '#ffd36b'], shadow='#0b0a1a'),
    'light': dict(bg='#fff3d6', frame='#df8c61', text='#332537', muted='#514050', colors=['#e0cfb4', '#46778e', '#35806f', '#608c34', '#a85c18'], shadow='#e5d2af'),
}

# A compact 5×7 bitmap alphabet, drawn as SVG paths so GitHub needs no font file.
GLYPHS = {
    'A':'01110/10001/10001/11111/10001/10001/10001',
    'B':'11110/10001/10001/11110/10001/10001/11110',
    'C':'01111/10000/10000/10000/10000/10000/01111',
    'D':'11110/10001/10001/10001/10001/10001/11110',
    'E':'11111/10000/10000/11110/10000/10000/11111',
    'F':'11111/10000/10000/11110/10000/10000/10000',
    'G':'01111/10000/10000/10111/10001/10001/01111',
    'H':'10001/10001/10001/11111/10001/10001/10001',
    'I':'11111/00100/00100/00100/00100/00100/11111',
    'J':'00111/00010/00010/00010/10010/10010/01100',
    'K':'10001/10010/10100/11000/10100/10010/10001',
    'L':'10000/10000/10000/10000/10000/10000/11111',
    'M':'10001/11011/10101/10101/10001/10001/10001',
    'N':'10001/11001/10101/10011/10001/10001/10001',
    'O':'01110/10001/10001/10001/10001/10001/01110',
    'P':'11110/10001/10001/11110/10000/10000/10000',
    'Q':'01110/10001/10001/10001/10101/10010/01101',
    'R':'11110/10001/10001/11110/10100/10010/10001',
    'S':'01111/10000/10000/01110/00001/00001/11110',
    'T':'11111/00100/00100/00100/00100/00100/00100',
    'U':'10001/10001/10001/10001/10001/10001/01110',
    'V':'10001/10001/10001/10001/10001/01010/00100',
    'W':'10001/10001/10001/10101/10101/10101/01010',
    'X':'10001/10001/01010/00100/01010/10001/10001',
    'Y':'10001/10001/01010/00100/00100/00100/00100',
    'Z':'11111/00001/00010/00100/01000/10000/11111',
    '0':'01110/10001/10011/10101/11001/10001/01110',
    '1':'00100/01100/00100/00100/00100/00100/01110',
    '2':'01110/10001/00001/00010/00100/01000/11111',
    '3':'11110/00001/00001/01110/00001/00001/11110',
    '4':'00010/00110/01010/10010/11111/00010/00010',
    '5':'11111/10000/10000/11110/00001/00001/11110',
    '6':'01110/10000/10000/11110/10001/10001/01110',
    '7':'11111/00001/00010/00100/01000/01000/01000',
    '8':'01110/10001/10001/01110/10001/10001/01110',
    '9':'01110/10001/10001/01111/00001/00001/01110',
    '.':'00000/00000/00000/00000/00000/00110/00110',
    ' ':'00000/00000/00000/00000/00000/00000/00000',
}


def text(x, y, value, size=14, color=None):
    # Join every glyph's pixels into one path; shared edges cannot develop seams.
    scale = 2 if size >= 17 else 1.5
    pixels = []
    for col, character in enumerate(str(value).upper()):
        if character not in GLYPHS:
            raise ValueError(f'Unsupported pixel-font character: {character!r}')
        for row, line in enumerate(GLYPHS[character].split('/')):
            for bit, pixel in enumerate(line):
                if pixel == '1':
                    px = x + (col * 6 + bit) * scale
                    py = y - 7 * scale + row * scale
                    pixels.append(f'M{px:g} {py:g}h{scale:g}v{scale:g}h-{scale:g}z')
    return f'<path fill="{color or "currentColor"}" d="{"".join(pixels)}"/>'

def wrap(content, theme, height, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" shape-rendering="crispEdges" role="img" aria-label="{title}">'
            f'<title>{title}</title><rect width="720" height="{height}" fill="{theme["bg"]}"/>'
            f'<path d="M6 0H714V2H718V6H720V{height-6}H718V{height-2}H714V{height}H6V{height-2}H2V{height-6}H0V6H2V2H6Z M6 4H4V6H4V{height-6}H6V{height-4}H714V{height-6}H716V6H714V4Z" fill="{theme["frame"]}" fill-rule="evenodd"/>'
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
            weekday = day.get('weekday')
            if weekday is None:
                weekday = (dt.date.fromisoformat(day['date']).weekday() + 1) % 7
            totals[weekday] += day.get('contributionCount', 0)
            color = theme['colors'][levels[day['contributionLevel']]]
            px, py = 24 + x * 12, 66 + weekday * 12
            body += f'<rect x="{px}" y="{py}" width="10" height="10" fill="{theme["shadow"]}"/><rect x="{px}" y="{py}" width="8" height="8" fill="{color}"/>'
    body += text(24, 170, 'LESS', 11, theme['muted'])
    for i, color in enumerate(theme['colors']):
        body += f'<rect x="{67+i*13}" y="160" width="9" height="9" fill="{color}"/>'
    body += text(138, 170, 'MORE', 11, theme['muted'])
    calendar_svg = wrap(body, theme, 185, 'The adventure log: contributions over the last year')
    body = text(22, 30, 'WORKSHOP RHYTHM', 17)
    body += text(22, 49, 'Contributions by weekday over the last year', 12, theme['muted'])
    totals = calendar.get('weekdayTotals', totals)
    max_total = max(totals, default=0)
    for i, (label, value) in enumerate(zip(['SUN','MON','TUE','WED','THU','FRI','SAT'], totals)):
        x = 29 + i * 98
        height = round(value / max_total * 75) if max_total else 0
        body += f'<rect x="{x}" y="{143-height}" width="48" height="{height}" fill="{theme["colors"][2]}"/>'
        if height:
            body += f'<rect x="{x}" y="{143-height}" width="48" height="{min(4,height)}" fill="{theme["colors"][4]}"/>'
        body += text(x, 158, label, 12, theme['muted'])
        body += text(x, 139-height, str(value), 12)
    rhythm_svg = wrap(body, theme, 175, 'Workshop rhythm: contributions by weekday')
    return calendar_svg, rhythm_svg

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--placeholder' in sys.argv:
        for name, theme in THEMES.items():
            for filename, title in [('adventure-log-thin','THE ADVENTURE LOG'), ('workshop-rhythm-thin','WORKSHOP RHYTHM')]:
                (OUT / f'{filename}-{name}.svg').write_text(placeholder(theme, title))
        return
    if '--snapshot' in sys.argv:
        calendar = json.loads(Path(sys.argv[sys.argv.index('--snapshot') + 1]).read_text())
        for name, theme in THEMES.items():
            for filename, svg in zip(['adventure-log-thin', 'workshop-rhythm-thin'], charts(calendar, theme)):
                (OUT / f'{filename}-{name}.svg').write_text(svg)
        return
    token = os.environ['GITHUB_TOKEN']
    request = urllib.request.Request('https://api.github.com/graphql', data=json.dumps({'query': QUERY, 'variables': {'login': 'bfarkas'}}).encode(), headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'bfarkas-profile'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get('errors') or not data.get('data', {}).get('user'):
        raise RuntimeError(f'GitHub GraphQL failed: {data.get("errors", "user not found")}')
    calendar = data['data']['user']['contributionsCollection']['contributionCalendar']
    for name, theme in THEMES.items():
        for filename, svg in zip(['adventure-log-thin', 'workshop-rhythm-thin'], charts(calendar, theme)):
            (OUT / f'{filename}-{name}.svg').write_text(svg)

if __name__ == '__main__':
    main()

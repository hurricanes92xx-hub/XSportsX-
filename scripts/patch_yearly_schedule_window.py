#!/usr/bin/env python3
from pathlib import Path

p = Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt')
s = p.read_text(encoding='utf-8')
old = 'val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(30);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(8)'
new = 'val today=LocalDate.now(ZoneId.systemDefault());val end=today.plusDays(370);val dates="${today.format(DateTimeFormatter.BASIC_ISO_DATE)}-${end.format(DateTimeFormatter.BASIC_ISO_DATE)}";val limiter=Semaphore(8)'
if old in s:
    p.write_text(s.replace(old, new, 1), encoding='utf-8')
    print('schedule window expanded to current + next season horizon')
elif 'today.plusDays(370)' in s:
    print('schedule window already expanded; nothing to patch')
else:
    raise SystemExit('schedule window pattern not found and expected 370-day window is absent')

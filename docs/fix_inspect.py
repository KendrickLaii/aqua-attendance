# -*- coding: utf-8 -*-
import re
from pathlib import Path

p = Path(r'C:\Users\Kendrick\Documents\GitHub\juku-attendance\docs\程式碼審查.md')
raw = p.read_bytes()
newline = '\r\n' if b'\r\n' in raw else '\n'
lines = raw.decode('utf-8').splitlines()

def is_heading(line):
    return re.match(r'^#{1,6}\s+\S', line) is not None

def is_hr(line):
    return re.match(r'^(?:---|\*\*\*|- - -)\s*$', line) is not None

def is_list_item(line):
    return re.match(r'^[ \t]*(?:[-*+]|\d+[.)])\s', line) is not None

converted = []
converted.append('# 程式碼審查紀錄')

for line in lines:
    m = re.match(r'^\*\*(問題\d+[：:][^*]+?)\*\*\s*$', line)
    if m:
        converted.append(f'##### {m.group(1)}')
        continue
    m2 = re.match(r'^\*\*(問題\d+[：:][^*]+?)\*\*(.*)$', line)
    if m2:
        title_text = m2.group(1).rstrip()
        tail = m2.group(2)
        converted.append(f'##### {title_text}')
        if tail.strip():
            converted.append(tail)
        continue
    m3 = re.match(r'^\*\*([^*]+?)\*\*\s*$', line)
    if m3:
        converted.append(f'#### {m3.group(1)}')
        continue
    converted.append(line)

out = []
for i, line in enumerate(converted):
    prev_out = out[-1] if out else None
    next_line = converted[i + 1] if i + 1 < len(converted) else None

    if is_heading(line):
        if prev_out is not None and prev_out.strip() != '':
            out.append('')
        out.append(line)
        if next_line is not None and next_line.strip() != '':
            out.append('')
    elif is_hr(line):
        if prev_out is not None and prev_out.strip() != '':
            out.append('')
        out.append(line)
        if next_line is not None and next_line.strip() != '':
            out.append('')
    elif is_list_item(line):
        if prev_out is not None and prev_out.strip() != '' and not is_list_item(prev_out):
            out.append('')
        out.append(line)
        if next_line is not None and next_line.strip() != '' and not is_list_item(next_line):
            out.append('')
    else:
        if prev_out is not None and is_list_item(prev_out) and line.strip() != '':
            out.append('')
        out.append(line)

final = []
prev_blank = False
for line in out:
    if line.strip() == '':
        if not prev_blank:
            final.append(line)
        prev_blank = True
    else:
        final.append(line)
        prev_blank = False

if final and final[-1].strip() != '':
    final.append('')

print('out first 12:')
for i,l in enumerate(out[:12]):
    print(i, ascii(l))
print('final first 12:')
for i,l in enumerate(final[:12]):
    print(i, ascii(l))

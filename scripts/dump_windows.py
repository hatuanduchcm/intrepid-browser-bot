"""Utility to list top-level windows and optionally dump control identifiers.

Run with:
    python -m scripts.dump_windows

It writes `assets/windows_list.txt` and `assets/control_tree.txt` (if a title match is provided).
"""
from pywinauto import Desktop
from pathlib import Path
import sys

out_dir = Path(__file__).resolve().parents[1] / 'assets'
out_dir.mkdir(parents=True, exist_ok=True)

def main():
    d = Desktop(backend='uia')
    wins = d.windows()
    lines = []
    for w in wins:
        try:
            title = w.window_text()
        except Exception:
            title = '<no-title>'
        lines.append(f"HWND={w.handle} | title={title}")

    (out_dir / 'windows_list.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('Wrote', out_dir / 'windows_list.txt')

    # optional: if user passed a substring, dump control identifiers for first matching window
    if len(sys.argv) > 1:
        match = sys.argv[1].lower()
        for w in wins:
            try:
                title = w.window_text() or ''
            except Exception:
                title = ''
            if match in title.lower():
                print('Dumping control identifiers for:', title)
                try:
                    with open(out_dir / 'control_tree.txt', 'w', encoding='utf-8') as fh:
                        w.print_control_identifiers(filename=str(out_dir / 'control_tree.txt'))
                except Exception as e:
                    print('Failed to dump control identifiers:', e)
                return
        print('No window matched', match)

if __name__ == '__main__':
    main()

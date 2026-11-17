"""本地草稿流演练入口：自启临时环回站点，演练并输出人工复核移交记录。

用法：
    python -m app.drill_cli                 # 演练目录中的全部摊位
    python -m app.drill_cli stall-01        # 只演练指定身份
    python -m app.drill_cli -o handoffs     # 指定移交记录目录
"""
import argparse
import threading
from pathlib import Path

from .site import DATA, start_server
from .drill import run_draft_drill
from .handoff import write_handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description='摊位申报草稿流本地演练（不提交正式申请）')
    parser.add_argument('item_id', nargs='?', help='只演练指定摊位身份；缺省演练全部')
    parser.add_argument('-o', '--output', default='handoffs', help='移交记录输出目录')
    args = parser.parse_args(argv)

    if args.item_id:
        targets = [args.item_id]
        known = {item['id'] for item in DATA['items']}
        if args.item_id not in known:
            parser.error(f'未知摊位身份：{args.item_id}；可选 {sorted(known)}')
    else:
        targets = [item['id'] for item in DATA['items']]

    server = start_server()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f'http://127.0.0.1:{server.server_port}/'
    written = []
    try:
        for item_id in targets:
            result = run_draft_drill(origin, item_id)
            paths = write_handoff(Path(args.output), result)
            written.append(paths)
            handoff = paths['handoff']
            mismatches = [row for row in handoff['consistency'] if row['verdict'] == 'mismatch']
            print(f'[{item_id}] 正式申请结论：{handoff["submission_conclusion"]}；'
                  f'一致性 {len(handoff["consistency"])} 项，'
                  f'其中预期内不一致 {len(mismatches)} 项、拦截 '
                  f'{sum(1 for row in handoff["consistency"] if row["verdict"] == "blocked_by_validation")} 项')
            print(f'  移交记录：{paths["markdown"]}')
            print(f'  原始轨迹：{paths["json"]}')
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
    return written


if __name__ == '__main__':
    main()

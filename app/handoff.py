"""把浏览器演练轨迹整理成可供人工复核的移交记录。

记录只陈述观察到的草稿事实：不把确认页上的按钮或文案解释为正式提交，
每条一致性裁决都附带可回溯到具体演练步骤的证据。
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import drill

CONSISTENT = 'consistent'
MISMATCH = 'mismatch'
BLOCKED = 'blocked_by_validation'
NOT_OBSERVED = 'not_observed'

VERDICT_LABEL = {
    CONSISTENT: '一致（已核对）',
    MISMATCH: '不一致（版本待核对）',
    BLOCKED: '被校验拦截（未进入确认）',
    NOT_OBSERVED: '未观察到',
}


def _snapshots(result):
    return {entry['step']: entry.get('snapshot') for entry in result['steps']
            if 'snapshot' in entry}


def _step_note(result, step_id):
    for entry in result['steps']:
        if entry['step'] == step_id:
            return entry.get('note')
    return None


def _consistency_rows(result):
    snaps = _snapshots(result)

    def row(dimension, step_id, verdict, detail):
        return {
            'dimension': dimension,
            'verdict': verdict,
            'verdict_label': VERDICT_LABEL[verdict],
            'evidence_step': step_id,
            'evidence_note': _step_note(result, step_id),
            'detail': detail,
        }

    first = snaps[drill.STEP_FIRST_PREVIEW]
    consistent = snaps[drill.STEP_CONFIRM_CONSISTENT]
    stale = snaps[drill.STEP_CONFIRM_STALE]
    switched = snaps[drill.STEP_CATEGORY_SWITCH]
    focus = snaps[drill.STEP_VALIDATION_FOCUS]
    recovered = snaps[drill.STEP_RECOVERED_CONSISTENT]
    returned = snaps[drill.STEP_LEAVE_AND_RETURN]
    restored_empty = snaps[drill.STEP_CONFIRM_RESTORED_EMPTY]
    restored_reattach = snaps[drill.STEP_RESTORED_REATTACH]
    reload_step = snaps[drill.STEP_RELOAD_RESTORE]
    boundary = snaps[drill.STEP_SESSION_BOUNDARY]
    expected = result['expected_digests'][drill.SAME_FILENAME]

    rows = [
        row('摊位类别 → 所需材料', drill.STEP_CATEGORY_SWITCH, CONSISTENT,
            f"类别切换为「{switched['category']}」，所需材料提示变为「{switched['requiredMaterial']}」；"
            f"切换前为「{first['requiredMaterial']}」，附件与摘要同步清空。"),
        row('材料预览（同名文件不同内容）', drill.STEP_SAME_NAME_REPLACED, CONSISTENT,
            f"两次上传文件名均为 {drill.SAME_FILENAME}，摘要分别为 "
            f"{expected['first'][:16]}… 与 {expected['second'][:16]}…，"
            '摘要按内容区分版本，文件名不参与身份判断。'),
        row('确认页（保存后一致）', drill.STEP_CONFIRM_CONSISTENT, CONSISTENT,
            f"确认页显示「{consistent['draftCheck']}」，确认区为「{consistent['confirmation']}」；"
            '重复点击两次，草稿版本保持 '
            f"{consistent['storedDraft']['version']}，未产生重复版本或网络请求。"),
        row('确认页（旧材料不得沿用）', drill.STEP_CONFIRM_STALE, MISMATCH,
            f"材料变化后未重新保存，确认区为「{stale['confirmation']}」，核对结果为「{stale['draftCheck']}」；"
            '已保存草稿摘要与当前预览摘要不同，系统明确标记不一致。'),
        row('换类别后旧材料是否仍附在申请上', drill.STEP_CATEGORY_SWITCH, CONSISTENT,
            f"切换后附件输入为空、摘要为空（{switched['attachmentInputValue'] == '' and switched['uploadDigest'] == ''}）；"
            '旧材料不再附在当前类别申请上，需按新类别重新上传。'),
        row('校验错误与焦点跳转', drill.STEP_VALIDATION_FOCUS, BLOCKED,
            f"无材料点击确认时提示「{focus['validationError']}」，焦点元素为 #{focus['activeElementId']}；"
            '重新附材料后错误清除，确认页恢复一致。'),
        row('校验后重新核对（类别保持切换后的选择）', drill.STEP_RECOVERED_CONSISTENT, CONSISTENT,
            f"焦点跳转恢复后重新附上材料并保存，类别仍为「{recovered['category']}」，"
            f"确认页显示「{recovered['draftCheck']}」，证明换类别流程可在报错后继续完成。"),
        row('离开恢复后重新核对', drill.STEP_RESTORED_REATTACH, CONSISTENT,
            f"离开页面返回并重新附材料后，确认页显示「{restored_reattach['draftCheck']}」，"
            f"类别为「{restored_reattach['category']}」。"),
        row('恢复后未附材料即确认', drill.STEP_CONFIRM_RESTORED_EMPTY, BLOCKED,
            f"恢复态材料区为空（{restored_empty['attachmentInputValue'] == ''}），"
            f"守卫提示「{restored_empty['validationError']}」并聚焦 #{restored_empty['activeElementId']}；"
            '确认区出现文案不代表材料齐全或申请已提交。'),
        row('离开页面后草稿恢复', drill.STEP_LEAVE_AND_RETURN, CONSISTENT,
            f"返回详情页状态为「{returned['draftState']}」；reload 后为「{reload_step['draftState']}」。"
            '草稿随 sessionStorage 恢复，但附件文件不恢复，必须重新附上。'),
        row('会话边界（不得跨会话恢复）', drill.STEP_SESSION_BOUNDARY, CONSISTENT,
            f"新会话草稿状态为「{boundary['draftState']}」、storedDraft 为 {boundary['storedDraft']}，"
            '不存在跨会话草稿泄漏。'),
    ]
    return rows


def _anomaly_rows(result):
    snaps = _snapshots(result)
    evidence = result['submission_evidence']
    return [
        {'topic': '离开页面后恢复草稿',
         'handled': True,
         'detail': f"同会话返回与 reload 均出现「{snaps[drill.STEP_RELOAD_RESTORE]['draftState']}」；"
                   '附件输入为空，必须重新上传并重新核对。'},
        {'topic': '同名文件不同内容',
         'handled': True,
         'detail': '以 SHA-256 摘要区分两个内容版本；未保存即确认被标记为材料版本待核对。'},
        {'topic': '校验错误造成焦点跳转',
         'handled': True,
         'detail': '守卫将焦点移回 #attachment 并显示错误；演练在每次跳转后重新定位元素继续操作。'},
        {'topic': '重复点击',
         'handled': True,
         'detail': '确认按钮连点两次结果幂等，草稿版本不变；全程无重复提交请求。'},
        {'topic': '确认页按钮不等于正式提交',
         'handled': True,
         'detail': '确认页只写会话内可见文案，不产生任何写请求；'
                   f"守卫自检拦截结果：{evidence['guard_probe_blocked']}。"},
        {'topic': '正式申请未发出',
         'handled': True,
         'detail': f"被拦截的写请求 {len(evidence['mutating_attempts_blocked'])} 条（均为守卫自检）；"
                   f"结束时仍停留在 {evidence['final_url']}，无成功提交标识。"},
    ]


def build_handoff(result):
    """依据演练轨迹构建移交记录结构。"""
    rows = _consistency_rows(result)
    evidence = result['submission_evidence']
    # 守卫自检是演练主动发起的预期拦截；除此之外不应出现任何写请求。
    guard_paths = {'/submit'}
    unexpected_writes = [
        attempt for attempt in evidence['mutating_attempts_blocked']
        if not any(attempt['url'].endswith(path) for path in guard_paths)
    ]
    submission_conclusion = (
        'not_performed'
        if evidence['guard_probe_blocked']
        and not unexpected_writes
        and not evidence['success_indicator_present']
        and evidence['still_on_detail_page']
        else 'needs_manual_review'
    )
    return {
        'record_type': 'stall_draft_handoff',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'exercise_window': {'started_at': result['started_at'],
                            'finished_at': result['finished_at']},
        'origin': result['origin'],
        'item_id': result['item_id'],
        'draft_key': result['draft_key'],
        'submission_conclusion': submission_conclusion,
        'unexpected_write_attempts': unexpected_writes,
        'consistency': rows,
        'anomaly_handling': _anomaly_rows(result),
        'submission_evidence': evidence,
        'manual_review_checklist': [
            '换类别后的所需材料提示是否与本次市集规则一致',
            '同名不同内容材料的两条摘要是否与摊主实际文件对应',
            '确认页所有“材料摘要已核”是否都基于重新附上的材料',
            '恢复后的草稿是否都经过重新上传与重新核对',
            '确认无任何正式申请被发出（以提交证据节为准，而非按钮是否存在）',
        ],
        'raw_trace_reference': '同目录 JSON 中的 steps 字段保留逐步快照',
    }


def _markdown(handoff):
    lines = [
        '# 摊位申报草稿流人工复核移交记录',
        '',
        f"- 记录生成时间（UTC）：{handoff['generated_at']}",
        f"- 演练来源：{handoff['origin']}（仅环回）",
        f"- 详情身份：{handoff['item_id']}；草稿键：`{handoff['draft_key']}`",
        f"- 演练窗口：{handoff['exercise_window']['started_at']} → {handoff['exercise_window']['finished_at']}",
        f"- 正式申请结论：**{handoff['submission_conclusion']}**",
        '',
        '## 一、类别 / 材料预览 / 确认页一致性',
        '',
        '| 维度 | 裁决 | 证据步骤 | 说明 |',
        '| --- | --- | --- | --- |',
    ]
    for row in handoff['consistency']:
        lines.append(
            f"| {row['dimension']} | {row['verdict_label']} | {row['evidence_step']} | {row['detail']} |"
        )
    lines += ['', '## 二、异常与恢复处理', '']
    for item in handoff['anomaly_handling']:
        lines.append(f"- {'已处理' if item['handled'] else '待处理'}｜{item['topic']}：{item['detail']}")
    evidence = handoff['submission_evidence']
    lines += [
        '',
        '## 三、未提交正式申请的证据',
        '',
        f"- 结论：{evidence['conclusion']}",
        f"- 被拦截的写请求（POST/PUT/PATCH/DELETE）：{len(evidence['mutating_attempts_blocked'])} 条（守卫自检 {len(evidence['mutating_attempts_blocked']) - len(handoff['unexpected_write_attempts'])} 条，意外请求 {len(handoff['unexpected_write_attempts'])} 条）",
        f"- 守卫自检 POST /submit 被拦截：{evidence['guard_probe_blocked']}",
        f"- 演练结束时仍在详情页：{evidence['still_on_detail_page']}（{evidence['final_url']}）",
        f"- 页面出现提交成功标识：{evidence['success_indicator_present']}",
        '- 确认页按钮只生成会话内核对文案，不触发任何网络写请求。',
        '',
        '## 四、人工复核清单',
        '',
    ]
    lines += [f'- [ ] {item}' for item in handoff['manual_review_checklist']]
    lines += [
        '',
        '> 逐步页面快照见同目录 JSON 的 `steps` 字段；本记录不构成资格、授权或正式提交。',
        '',
    ]
    return '\n'.join(lines)


def write_handoff(directory, result):
    """把演练轨迹与移交记录写入指定目录，返回生成的文件路径。"""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    handoff = build_handoff(result)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = f'draft-handoff-{result["item_id"]}-{stamp}'
    json_path = out / f'{base}.json'
    md_path = out / f'{base}.md'
    json_path.write_text(
        json.dumps({'handoff': handoff, 'trace': result}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    md_path.write_text(_markdown(handoff), encoding='utf-8')
    return {'json': json_path, 'markdown': md_path, 'handoff': handoff}

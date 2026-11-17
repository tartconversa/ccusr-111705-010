"""浏览器草稿流演练。

硬约束：
- 只允许 http 环回来源；
- 拦截一切 POST/PUT/PATCH/DELETE，正式申请请求不可能离开浏览器；
- 全程只读 sessionStorage 与页面可见输出，不调用任何业务提交接口；
- 每个关键动作后留快照，供人工复核类别、材料预览与确认页的一致性。
"""
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

LOOPBACK_HOSTS = ('127.0.0.1', 'localhost')
BLOCKED_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')
DRAFT_KEY_TEMPLATE = 'stall-draft:{item_id}'

SAME_FILENAME = 'draft.txt'
FIRST_CONTENT = b'first material bytes'
SECOND_CONTENT = b'second material bytes with same filename'

# 演练步骤标识，移交记录构建器按这些标识取快照。
STEP_OPEN = 'open_detail'
STEP_FIRST_PREVIEW = 'first_preview'
STEP_DRAFT_SAVED = 'draft_saved'
STEP_CONFIRM_CONSISTENT = 'confirm_consistent'
STEP_SAME_NAME_REPLACED = 'same_name_replaced'
STEP_CONFIRM_STALE = 'confirm_stale_draft'
STEP_CATEGORY_SWITCH = 'category_switched'
STEP_VALIDATION_FOCUS = 'validation_focus_jump'
STEP_REATTACH_AFTER_FOCUS = 'reattach_after_focus'
STEP_RECOVERED_CONSISTENT = 'recovered_consistent'
STEP_LEAVE_AND_RETURN = 'leave_and_return'
STEP_CONFIRM_RESTORED_EMPTY = 'confirm_restored_without_material'
STEP_RESTORED_REATTACH = 'restored_reattach'
STEP_RELOAD_RESTORE = 'reload_restore'
STEP_SESSION_BOUNDARY = 'new_session_no_restore'
STEP_SUBMISSION_GUARD_PROBE = 'submission_guard_probe'


def require_loopback(origin):
    parts = urlsplit(origin)
    if parts.scheme != 'http' or parts.hostname not in LOOPBACK_HOSTS:
        raise ValueError('只允许本地演练来源（http + 环回地址）')


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _snapshot(page, draft_key):
    """读取当前页面全部可复核状态；只读，不改变页面。"""
    return page.evaluate(
        """([key]) => {
          const stored = JSON.parse(sessionStorage.getItem(key) || 'null');
          const active = document.activeElement;
          return {
            url: location.href,
            mainKey: document.querySelector('main').getAttribute('data-key'),
            category: document.querySelector('#category').value,
            requiredMaterial: document.querySelector('#material-requirement').textContent,
            attachmentName: document.querySelector('#attachment').files[0]?.name || null,
            attachmentInputValue: document.querySelector('#attachment').value,
            uploadDigest: document.querySelector('#upload-digest').textContent,
            draftState: document.querySelector('#draft-state').textContent,
            confirmation: document.querySelector('#confirmation').textContent,
            draftCheck: document.querySelector('#draft-check').textContent,
            validationError: document.querySelector('#validation-error').textContent,
            activeElementId: active ? active.id : null,
            storedDraft: stored,
          };
        }""",
        [draft_key],
    )


def _record(steps, step_id, label, page, draft_key, note=None):
    entry = {'step': step_id, 'label': label, 'snapshot': _snapshot(page, draft_key)}
    if note:
        entry['note'] = note
    steps.append(entry)
    return entry


def run_draft_drill(origin, item_id):
    """在环回门户上走完整草稿流，返回可供人工复核的演练轨迹。"""
    require_loopback(origin)
    started_at = datetime.now(timezone.utc).isoformat()
    draft_key = DRAFT_KEY_TEMPLATE.format(item_id=item_id)
    expected_first = sha256_hex(FIRST_CONTENT)
    expected_second = sha256_hex(SECOND_CONTENT)
    steps = []
    mutating_attempts = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()

            def handle_route(route):
                request = route.request
                if request.method in BLOCKED_METHODS:
                    mutating_attempts.append({'method': request.method, 'url': request.url})
                    route.abort()
                else:
                    route.continue_()

            page.route('**/*', handle_route)

            # 1. 从目录卡片进入详情，先核身份再操作。
            page.goto(origin, wait_until='domcontentloaded')
            card = page.locator(f'.card[data-key="{item_id}"]')
            if card.count() != 1:
                raise ValueError('目录卡片身份不唯一或不存在')
            card.locator('a').click()
            page.wait_for_selector(f'main[data-key="{item_id}"]')
            if page.locator('main').get_attribute('data-key') != item_id:
                raise ValueError('详情页身份与目录卡片不一致')
            _record(steps, STEP_OPEN, '从目录卡片进入详情页', page, draft_key)

            # 2. 首次上传材料并核对 SHA-256 摘要。
            page.locator('#attachment').set_input_files(
                {'name': SAME_FILENAME, 'mimeType': 'text/plain', 'buffer': FIRST_CONTENT}
            )
            page.wait_for_function(
                "(hex) => document.querySelector('#upload-digest').textContent.endsWith(hex)",
                arg=expected_first,
            )
            first = _record(steps, STEP_FIRST_PREVIEW, '首次上传材料，上传预览出现摘要', page, draft_key)
            assert first['snapshot']['uploadDigest'].endswith(expected_first)

            # 3. 保存演练草稿（仅写 sessionStorage）。
            page.locator('#draft').click()
            page.wait_for_function(
                "() => document.querySelector('#draft-state').textContent.includes('草稿：')"
            )
            saved = _record(steps, STEP_DRAFT_SAVED, '保存演练草稿', page, draft_key)
            assert saved['snapshot']['storedDraft'] is not None
            version_after_save = saved['snapshot']['storedDraft']['version']

            # 4. 重复点击确认按钮：结果必须幂等，版本不得跳动，且不产生任何请求。
            page.locator('#confirm').click()
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.querySelector('#draft-check').textContent.includes('材料摘要已核')"
            )
            consistent = _record(
                steps, STEP_CONFIRM_CONSISTENT, '重复点击查看确认页（幂等核对）', page, draft_key,
                note='连续两次点击确认按钮，验证不产生重复版本或重复请求',
            )
            assert consistent['snapshot']['storedDraft']['version'] == version_after_save
            assert consistent['snapshot']['draftCheck'].endswith('材料摘要已核')

            # 5. 同名文件不同内容：文件名相同，摘要必须变化。
            page.locator('#attachment').set_input_files(
                {'name': SAME_FILENAME, 'mimeType': 'text/plain', 'buffer': SECOND_CONTENT}
            )
            page.wait_for_function(
                "(hex) => document.querySelector('#upload-digest').textContent.endsWith(hex)",
                arg=expected_second,
            )
            replaced = _record(
                steps, STEP_SAME_NAME_REPLACED, '同名文件不同内容重新上传', page, draft_key,
                note='文件名不变，内容变化后摘要应区分两个材料版本',
            )
            assert replaced['snapshot']['attachmentName'] == SAME_FILENAME
            assert replaced['snapshot']['uploadDigest'].endswith(expected_second)
            assert not replaced['snapshot']['uploadDigest'].endswith(expected_first)

            # 6. 未重新保存就查看确认页：确认页必须标出草稿已变化，而不是沿用旧材料。
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.querySelector('#draft-check').textContent.includes('材料版本待核对')"
            )
            stale = _record(
                steps, STEP_CONFIRM_STALE, '材料变化后未保存即查看确认页', page, draft_key,
                note='确认页应明确提示版本待核对，旧材料不得被当作新申请材料',
            )
            assert '草稿已变化' in stale['snapshot']['confirmation']
            assert '材料版本待核对' in stale['snapshot']['draftCheck']
            assert stale['snapshot']['storedDraft']['digest'] != \
                stale['snapshot']['uploadDigest']

            # 7. 换类别：所需材料提示变化，附件与摘要被清空，旧材料不再附在当前申请上。
            page.locator('#category').select_option('食饮')
            page.wait_for_function(
                "() => document.querySelector('#material-requirement').textContent.includes('安全说明')"
            )
            switched = _record(
                steps, STEP_CATEGORY_SWITCH, '切换摊位类别', page, draft_key,
                note='类别变化后所需材料提示更新，附件输入与摘要被清空',
            )
            assert switched['snapshot']['requiredMaterial'] != \
                first['snapshot']['requiredMaterial']
            assert switched['snapshot']['attachmentInputValue'] == ''
            assert switched['snapshot']['uploadDigest'] == ''

            # 8. 无材料查看确认页：校验失败，焦点跳回上传框，错误可见。
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.activeElement && document.activeElement.id === 'attachment' "
                "&& document.querySelector('#validation-error').textContent !== ''"
            )
            focus_step = _record(
                steps, STEP_VALIDATION_FOCUS, '缺材料触发校验错误与焦点跳转', page, draft_key,
                note='焦点被移回材料上传框；随后重新定位元素继续操作，不依赖跳转前句柄',
            )
            assert focus_step['snapshot']['activeElementId'] == 'attachment'
            assert focus_step['snapshot']['validationError']

            # 9. 焦点跳转后重新附材料，校验错误应清除，再保存、再确认恢复一致。
            page.locator('#attachment').set_input_files(
                {'name': SAME_FILENAME, 'mimeType': 'text/plain', 'buffer': FIRST_CONTENT}
            )
            page.wait_for_function(
                "(hex) => document.querySelector('#upload-digest').textContent.endsWith(hex)",
                arg=expected_first,
            )
            reattach = _record(steps, STEP_REATTACH_AFTER_FOCUS, '焦点跳转后重新附上材料', page, draft_key)
            assert reattach['snapshot']['validationError'] == ''
            page.locator('#draft').click()
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.querySelector('#draft-check').textContent.includes('材料摘要已核')"
            )
            recovered = _record(
                steps, STEP_RECOVERED_CONSISTENT, '焦点恢复后重新保存，确认页恢复一致', page, draft_key,
            )
            assert '材料摘要已核' in recovered['snapshot']['draftCheck']

            # 10. 离开页面再从目录返回：草稿恢复提示出现，但材料必须重新附上。
            page.goto(origin, wait_until='domcontentloaded')
            page.locator(f'.card[data-key="{item_id}"] a').click()
            page.wait_for_selector(f'main[data-key="{item_id}"]')
            returned = _record(
                steps, STEP_LEAVE_AND_RETURN, '离开页面后从目录返回', page, draft_key,
            )
            assert '草稿已恢复' in returned['snapshot']['draftState']
            assert returned['snapshot']['attachmentInputValue'] == ''
            assert returned['snapshot']['uploadDigest'] == ''

            # 11. 恢复态直接确认：仍因缺材料被拦下——确认文案存在不代表材料齐全或已提交。
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.activeElement && document.activeElement.id === 'attachment'"
            )
            restored_empty = _record(
                steps, STEP_CONFIRM_RESTORED_EMPTY, '恢复草稿后未重新附材料即确认', page, draft_key,
                note='即使确认区出现待人工确认文案，材料守卫仍拦截，不能据此认定已提交',
            )
            assert restored_empty['snapshot']['activeElementId'] == 'attachment'
            assert restored_empty['snapshot']['validationError']

            # 12. 重新附上与已保存草稿相同内容，摘要重新对齐，确认页恢复一致。
            page.locator('#attachment').set_input_files(
                {'name': SAME_FILENAME, 'mimeType': 'text/plain', 'buffer': FIRST_CONTENT}
            )
            page.wait_for_function(
                "(hex) => document.querySelector('#upload-digest').textContent.endsWith(hex)",
                arg=expected_first,
            )
            page.locator('#confirm').click()
            page.wait_for_function(
                "() => document.querySelector('#draft-check').textContent.includes('材料摘要已核')"
            )
            restored_reattach = _record(
                steps, STEP_RESTORED_REATTACH, '恢复后重新附材料并核对一致', page, draft_key,
            )
            assert '材料摘要已核' in restored_reattach['snapshot']['draftCheck']

            # 13. 再以 reload 方式离开/恢复一次，记录同一恢复机制。
            page.reload()
            page.wait_for_selector(f'main[data-key="{item_id}"]')
            page.wait_for_function(
                "() => document.querySelector('#draft-state').textContent.includes('草稿已恢复')"
            )
            _record(steps, STEP_RELOAD_RESTORE, 'reload 后草稿再次恢复', page, draft_key)

            # 14. 会话边界：新会话没有 sessionStorage，不得凭空恢复他人草稿。
            second_context = browser.new_context()
            try:
                fresh_page = second_context.new_page()
                fresh_page.route('**/*', handle_route)
                fresh_page.goto(
                    f'{origin.rstrip("/")}/detail?id={item_id}', wait_until='domcontentloaded'
                )
                fresh_page.wait_for_selector(f'main[data-key="{item_id}"]')
                boundary = _record(
                    steps, STEP_SESSION_BOUNDARY, '新会话打开同一详情页', fresh_page,
                    DRAFT_KEY_TEMPLATE.format(item_id=item_id),
                    note='sessionStorage 不跨会话，新会话无草稿可恢复',
                )
                assert boundary['snapshot']['draftState'] == ''
                assert boundary['snapshot']['storedDraft'] is None
            finally:
                second_context.close()

            # 15. 提交守卫自检：页面上下文主动发起一次 POST，应被路由拦截且无成功响应。
            guard_probe = page.evaluate(
                """async () => {
                  try {
                    const response = await fetch('/submit', {method: 'POST', body: 'guard-probe'});
                    return {blocked: false, status: response.status};
                  } catch (error) {
                    return {blocked: true, error: String(error)};
                  }
                }"""
            )
            probe_step = {
                'step': STEP_SUBMISSION_GUARD_PROBE,
                'label': '正式提交守卫自检（POST /submit 应被拦截）',
                'probe': guard_probe,
            }
            steps.append(probe_step)
            assert guard_probe['blocked'] is True

            body_text = page.locator('body').inner_text()
            finished_at = datetime.now(timezone.utc).isoformat()
            return {
                'origin': origin,
                'item_id': item_id,
                'draft_key': draft_key,
                'started_at': started_at,
                'finished_at': finished_at,
                'headless': True,
                'steps': steps,
                'expected_digests': {
                    SAME_FILENAME: {'first': expected_first, 'second': expected_second},
                },
                'submission_evidence': {
                    'conclusion': 'not_performed',
                    'mutating_attempts_blocked': list(mutating_attempts),
                    'final_url': page.url,
                    'still_on_detail_page': item_id in page.url and '/detail' in page.url,
                    'success_indicator_present': any(
                        word in body_text for word in ('提交成功', '已提交', '申请成功')
                    ),
                    'guard_probe_blocked': guard_probe['blocked'],
                },
            }
        finally:
            browser.close()

"""市集摊位申报的浏览器草稿移交：目录卡片既有数据约定。"""
import re

def interpret_card(item):
    parts = item['summary'].split(' · ', 1)
    if len(parts) != 2:
        raise ValueError('卡片摘要格式无效')
    condition, observation = parts
    found = re.fullmatch(r"(?P<amount>草稿)", observation)
    if not found:
        raise ValueError('卡片状态未识别')
    amount = found.group('amount')
    return {'kind': 'application', 'identity': item['id'], 'condition': condition, 'draft_state': observation, 'state': int(amount) if amount.isdigit() else amount}

def interpret_entry(catalog_fact, signal):
    if signal['application'] != catalog_fact['identity']:
        raise ValueError('application identity mismatch')
    return {'business_key': f"{signal['application']}:{signal['category']}", 'category': signal['category'], 'draft': signal['draft']}

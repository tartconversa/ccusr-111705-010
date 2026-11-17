"""Candidate review of observed entry facts, never a completed transaction."""

def review_entries(entries):
    handoffs = []
    for entry in entries:
        detail = entry['detail_fact']
        handoffs.append({'draft_key': detail['business_key'], 'directory_draft': entry['catalog_fact']['draft_state'],
                         'attachment_digest': None, 'submission': 'not_performed'})
    return handoffs

import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from study_planner import plan_study


def goal(mode='exam'):
    return {'mode': mode, 'front_language': 'en', 'explanation_language': 'pt-BR', 'reference': 'Synthetic blueprint v1',
        'topics': [{'id': 'routing', 'terms': ['OSPF', 'RIP'], 'weight': 1}, {'id': 'switching', 'terms': ['VLAN', 'trunk'], 'weight': 1}]}


def test_cluster_topics_with_evidence_and_abstain_on_ties():
    cards = [{'id': 1, 'text': 'OSPF priority'}, {'id': 2, 'text': 'VLAN trunk'}, {'id': 3, 'text': 'OSPF VLAN'}, {'id': 4, 'text': 'unrelated'}]
    result = plan_study(cards, goal())
    assert result['clusters']['routing'][0]['id'] == 1
    assert result['clusters']['routing'][0]['matched_terms'] == ['ospf']
    assert {r['reason'] for r in result['unclassified']} == {'ambiguous_topics', 'no_match'}


def test_language_and_exam_scope_are_explicit():
    g = goal(); del g['reference']
    with pytest.raises(ValueError): plan_study([], g)
    cards = [{'id': 1, 'text': 'OSPF', 'front_language': 'de'}]
    assert plan_study(cards, goal())['unclassified'][0]['reason'] == 'language_metadata_mismatch'
    g = goal('language'); del g['front_language']
    with pytest.raises(ValueError): plan_study([], g)


def test_due_first_then_weighted_topic_fairness_without_mutating_input():
    cards = [{'id': i, 'text': 'OSPF' if i < 4 else 'VLAN', 'due': i == 5} for i in range(1, 7)]
    result = plan_study(cards, goal(), 6)
    assert result['suggested_queue'][0]['id'] == 5
    assert len({r['topic'] for r in result['suggested_queue'][:3]}) == 2
    assert cards[0] == {'id': 1, 'text': 'OSPF', 'due': False}


def test_terms_are_literal_and_script_text_cannot_control_routing():
    g = goal(); g['topics'][0]['terms'] = ['IP']
    result = plan_study([{'id': 1, 'text': '<script>IP</script> RIP'}], g)
    assert result['unclassified'][0]['reason'] == 'no_match'


@pytest.mark.parametrize('weight', [float('nan'), float('inf'), True, -1, 0])
def test_invalid_weights_are_rejected(weight):
    g = goal(); g['topics'][0]['weight'] = weight
    with pytest.raises(ValueError): plan_study([], g)


def test_missing_topics_reported_as_coverage_gaps_and_bad_metadata_rejected():
    result = plan_study([{'id': 1, 'text': 'OSPF'}], goal())
    assert result['uncovered_topics'] == ['switching']
    with pytest.raises(ValueError): plan_study([{'id': 1, 'text': 'OSPF', 'due': 'yes'}], goal())
    g = goal(); g['topics'][0]['terms'] = ['<script>topic</script>']
    with pytest.raises(ValueError): plan_study([], g)

"""Motor de evidencia para v4-evidencias.
Detecta conflictos por tipo de campo, evita falsos conflictos por ausencia,
y previene que hechos conflictivos lleguen al LLM como datos definitivos.
"""
import json
from pathlib import Path
from functools import lru_cache
from typing import List, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

FIELD_POLICIES = {
    'schedule': 'exclusive_scalar',
    'duration': 'exclusive_scalar',
    'departure_time': 'exclusive_scalar',
    'official_price': 'exclusive_scalar',
    'price_pen': 'exclusive_scalar',
    'exchange_rate': 'exclusive_scalar',
    'includes': 'additive_set',
    'excludes': 'additive_set',
    'stops': 'additive_set',
    'route': 'additive_set',
    'services': 'additive_set',
    'transport_options': 'additive_set',
    'phone': 'multi_value',
    'email': 'multi_value',
    'address': 'exclusive_or_multi',
    'confirmed_product': 'existence',
}

SCALAR_NORMALIZE = {
    'schedule': lambda v: v.strip().replace(' ', ''),
    'duration': lambda v: v.strip().lower(),
}

@lru_cache(maxsize=1)
def _load_facts():
    path = ROOT / 'data' / 'evidence_facts.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return [Fact(f) for f in data['facts']]

@lru_cache(maxsize=1)
def _load_conflicts():
    path = ROOT / 'data' / 'conflicts.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return data['conflicts']

@lru_cache(maxsize=1)
def _load_catalog():
    path = ROOT / 'data' / 'tours_catalog.json'
    return json.loads(path.read_text(encoding='utf-8'))

class Fact:
    def __init__(self, raw: dict):
        self.fact_id = raw['fact_id']
        self.entity_id = raw['entity_id']
        self.field = raw['field']
        self.item = raw.get('item')
        self.value = raw['value']
        self.source_id = raw['source_id']
        self.source_page = raw.get('source_page')
        self.evidence_status = raw.get('evidence_status', 'confirmed')
        self.note = raw.get('note')

    def to_dict(self):
        d = {
            'fact_id': self.fact_id,
            'entity_id': self.entity_id,
            'field': self.field,
            'item': self.item,
            'value': self.value,
            'source_id': self.source_id,
            'source_page': self.source_page,
            'evidence_status': self.evidence_status,
        }
        if self.note:
            d['note'] = self.note
        return d


def get_facts(entity_id: str, field: str = None) -> List[Fact]:
    facts = _load_facts()
    result = [f for f in facts if f.entity_id == entity_id]
    if field:
        result = [f for f in result if f.field == field]
    return result


def get_facts_by_source(entity_id: str, source_id: str) -> List[Fact]:
    return [f for f in _load_facts() if f.entity_id == entity_id and f.source_id == source_id]


def detect_conflicts(entity_id: str, field: str = None) -> List[dict]:
    facts = get_facts(entity_id, field)
    if not facts:
        return []

    existing_conflicts = [c for c in _load_conflicts() if c['entity_id'] == entity_id]
    if field:
        existing_conflicts = [c for c in existing_conflicts if c['field'] == field]

    fields_to_check = set(f.field for f in facts)
    if field:
        fields_to_check = {field}

    auto_conflicts = []
    for fld in fields_to_check:
        fld_facts = [f for f in facts if f.field == fld]
        policy = FIELD_POLICIES.get(fld, 'additive_set')

        if policy == 'exclusive_scalar':
            conflict = _detect_scalar_conflict(fld, fld_facts)
            if conflict:
                auto_conflicts.append(conflict)

        elif policy == 'additive_set':
            conflict = _detect_set_conflict(entity_id, fld)
            if conflict:
                auto_conflicts.append(conflict)

        elif policy == 'existence':
            values_by_source = {}
            for f in fld_facts:
                if f.source_id not in values_by_source:
                    values_by_source[f.source_id] = f.value
            true_sources = [s for s, v in values_by_source.items() if v is True]
            false_sources = [s for s, v in values_by_source.items() if v is False]
            if true_sources and false_sources:
                auto_conflicts.append({
                    'conflict_id': f'auto-conf-{entity_id}-{fld}',
                    'entity_id': entity_id,
                    'field': fld,
                    'policy': 'existence',
                    'source_a': {'source_id': true_sources[0], 'value': True},
                    'source_b': {'source_id': false_sources[0], 'value': False},
                    'needs_confirmation': True,
                    'note': f'Una fuente confirma existencia, otra niega.'
                })

    result = list(existing_conflicts)
    for conflict in auto_conflicts:
        if not any(c['field'] == conflict['field'] and c.get('source_a', {}).get('item') == conflict.get('source_a', {}).get('item') for c in result):
            result.append(conflict)
    return result


def _detect_scalar_conflict(field: str, facts: List[Fact]) -> Optional[dict]:
    normalize = SCALAR_NORMALIZE.get(field, lambda v: v.strip().lower() if isinstance(v, str) else v)

    by_source = {}
    for f in facts:
        if f.source_id not in by_source:
            by_source[f.source_id] = f

    sources = list(by_source.keys())
    if len(sources) < 2:
        return None

    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            a, b = by_source[sources[i]], by_source[sources[j]]
            norm_a = normalize(a.value)
            norm_b = normalize(b.value)
            if norm_a != norm_b:
                return {
                    'conflict_id': f'auto-conf-{a.entity_id}-{field}-{a.source_id}-{b.source_id}',
                    'entity_id': a.entity_id,
                    'field': field,
                    'policy': 'exclusive_scalar',
                    'source_a': {'source_id': a.source_id, 'source_page': a.source_page, 'value': a.value},
                    'source_b': {'source_id': b.source_id, 'source_page': b.source_page, 'value': b.value},
                    'needs_confirmation': True,
                    'note': f'Valores escalares incompatibles entre {a.source_id} y {b.source_id}.'
                }
    return None


def _detect_set_conflict(entity_id: str, field: str) -> Optional[dict]:
    includes = {(f.item, f.source_id) for f in get_facts(entity_id, 'includes') if f.value is True}
    excludes = {(f.item, f.source_id) for f in get_facts(entity_id, 'excludes') if f.value is True}

    if field in {'includes', 'excludes'}:
        for item, src_ex in excludes:
            for _, src_in in includes:
                if item == _ and src_in != src_ex:
                    return {
                        'conflict_id': f'auto-conf-{entity_id}-inc-exc-{item}',
                        'entity_id': entity_id,
                        'field': 'includes_vs_excludes',
                        'policy': 'additive_set',
                        'source_a': {'source_id': src_in, 'item': item, 'value': 'includes'},
                        'source_b': {'source_id': src_ex, 'item': item, 'value': 'excludes'},
                        'needs_confirmation': True,
                        'note': f'Item "{item}" incluido en una fuente y excluido en otra.'
                    }
    return None


def is_product_confirmed(entity_id: str) -> bool:
    facts = get_facts(entity_id, 'confirmed_product')
    return any(f.value is True for f in facts)


def get_confirmed_products() -> List[dict]:
    catalog = _load_catalog()
    return [t for t in catalog['tours'] if t.get('confirmed_product')]


def build_context_for_entity(entity_id: str) -> str:
    conflicts = detect_conflicts(entity_id)
    conflict_fields = set(c['field'] for c in conflicts)

    facts = get_facts(entity_id)
    consolidated = {}
    for f in facts:
        key = (f.field, f.item)
        if key not in consolidated:
            consolidated[key] = []
        consolidated[key].append(f)

    lines = []
    for (field, item), fact_list in consolidated.items():
        if field in conflict_fields or (field in {'includes','excludes'} and 'includes_vs_excludes' in conflict_fields):
            continue

        sources = sorted(set(f.source_id for f in fact_list))
        source_str = '+'.join(sources)

        if item:
            lines.append(f"- {field}/{item}: confirmado por {source_str}")
        else:
            val = fact_list[0].value
            if isinstance(val, bool):
                lines.append(f"- {field}: {'sí' if val else 'no'} (fuente: {source_str})")
            else:
                for fact in fact_list:
                    lines.append(f"- {field}: {fact.value} (fuente: {fact.source_id}, página: {fact.source_page})")

    if conflicts:
        lines.append("")
        lines.append("CONFLICTOS PENDIENTES DE CONFIRMACIÓN:")
        for c in conflicts:
            src_a = c['source_a']
            src_b = c['source_b']
            val_a = src_a.get('value', '?')
            val_b = src_b.get('value', '?')
            lines.append(f"- {c['field']}: difiere entre {src_a['source_id']} y {src_b['source_id']}. No proporcionar un valor vigente; confirmar con agencia.")

    return '\n'.join(lines)


def build_context_for_question(entity_id: str, question_fields: List[str] = None) -> Tuple[str, bool]:
    conflicts = detect_conflicts(entity_id)
    if question_fields:
        relevant_conflicts = [c for c in conflicts if c['field'] in question_fields]
    else:
        relevant_conflicts = conflicts

    if relevant_conflicts:
        conflict = relevant_conflicts[0]
        src_a = conflict['source_a']
        src_b = conflict['source_b']
        val_a = src_a.get('value', '?')
        val_b = src_b.get('value', '?')
        response = (
            f"Los materiales de la agencia muestran información diferente sobre {conflict['field']}. "
            f"Es necesario confirmar el dato vigente con la agencia."
        )
        return response, True

    context = build_context_for_entity(entity_id)
    return context, False


def get_listing() -> str:
    products = get_confirmed_products()
    lines = []
    for p in products:
        name = p['name']
        schedule_status = p.get('schedule_status', 'unknown')
        if schedule_status == 'conflict':
            lines.append(f"- {name}: horario por confirmar (conflictos entre fuentes)")
        elif schedule_status == 'confirmed':
            lines.append(f"- {name}")
        else:
            lines.append(f"- {name}")
    return '\n'.join(lines)


def get_includes(entity_id: str) -> str:
    facts = get_facts(entity_id, 'includes')
    if not facts:
        return "Información de inclusiones no disponible."

    items = {}
    for f in facts:
        if f.item not in items:
            items[f.item] = []
        items[f.item].append(f.source_id)

    conflicts = detect_conflicts(entity_id, 'includes')
    conflict_items = set()
    for c in conflicts:
        if 'item' in c.get('source_a', {}):
            conflict_items.add(c['source_a']['item'])

    lines = []
    for item, sources in sorted(items.items()):
        source_str = '+'.join(sorted(set(sources)))
        if item in conflict_items:
            lines.append(f"- {item}: por confirmar (conflicto entre fuentes)")
        else:
            lines.append(f"- {item} (fuente: {source_str})")

    return '\n'.join(lines)


def get_route(entity_id: str) -> str:
    facts = get_facts(entity_id, 'stops')
    if not facts:
        return "Información de ruta no disponible."

    stops_by_source = {}
    for f in facts:
        if f.source_id not in stops_by_source:
            stops_by_source[f.source_id] = []
        stops_by_source[f.source_id].append(f.item)

    all_stops = []
    for f in facts:
        if f.item not in [s[0] for s in all_stops]:
            all_stops.append((f.item, [f.source_id]))
        else:
            for i, (stop, srcs) in enumerate(all_stops):
                if stop == f.item and f.source_id not in srcs:
                    all_stops[i] = (stop, srcs + [f.source_id])

    lines = []
    for item, sources in all_stops:
        source_str = '+'.join(sorted(sources))
        lines.append(f"- {item} (fuente: {source_str})")

    return '\n'.join(lines)


def get_all_conflicts() -> List[dict]:
    return _load_conflicts()


def get_complementary() -> List[dict]:
    path = ROOT / 'data' / 'conflicts.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return data.get('complementary_information', [])


def stats() -> dict:
    facts = _load_facts()
    entities = set(f.entity_id for f in facts)
    by_source = {}
    for f in facts:
        by_source.setdefault(f.source_id, []).append(f)

    return {
        'total_facts': len(facts),
        'total_entities': len(entities),
        'facts_by_source': {s: len(fs) for s, fs in by_source.items()},
        'confirmed_products': len(get_confirmed_products()),
        'conflicts': len(get_all_conflicts()),
    }

from opentargets_pharmgkb.ontology_apis import get_chebi_iri, get_efo_iri


def test_get_chebi_iri():
    # Exactly one exact match
    assert get_chebi_iri('morphine') == 'http://purl.obolibrary.org/obo/CHEBI_17303'

    # Multiple results but none that exactly match
    assert get_chebi_iri('fluorouracil') is None


def test_get_efo_iri(mappings):
    # Exactly one high-confidence match
    assert get_efo_iri('Lymphoma', mappings) == 'http://purl.obolibrary.org/obo/MONDO_0005062'

    # No high-confidence matches
    assert get_efo_iri('neoplasms', mappings) is None

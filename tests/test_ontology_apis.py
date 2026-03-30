from unittest.mock import patch

from cmat.trait_mapping.trait import Trait, OntologyEntry

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


def test_get_efo_iri_cache(mappings):
    with patch('opentargets_pharmgkb.ontology_apis.process_trait') as m_process_trait:
        # Caches result of process_trait
        finished_trait = Trait('test trait name', None, None)
        finished_trait.finished_mapping_set = {OntologyEntry('http://example.com/test', 'test')}
        m_process_trait.return_value = finished_trait

        get_efo_iri('test trait name', mappings)
        assert m_process_trait.call_count == 1
        m_process_trait.reset_mock()
        get_efo_iri('test trait name', mappings)
        assert m_process_trait.call_count == 0

        # Also caches when no mapping found
        finished_trait.finished_mapping_set = set()
        m_process_trait.reset_mock()
        get_efo_iri('something else', mappings)
        assert m_process_trait.call_count == 1
        m_process_trait.reset_mock()
        get_efo_iri('something else', mappings)
        assert m_process_trait.call_count == 0

import os

import pytest
from cmat.trait_mapping.utils import load_ontology_mapping

from opentargets_pharmgkb.variant_coordinates import Fasta

resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
fasta_path = os.path.join(resources_dir, 'chr21.fa')
mappings_path = os.path.join(resources_dir, 'latest_mappings.tsv')


@pytest.fixture
def fasta():
    return Fasta(fasta_path)


@pytest.fixture
def mappings():
    return load_ontology_mapping(mappings_path)[0]

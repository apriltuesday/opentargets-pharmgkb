import re

import pandas as pd

from opentargets_pharmgkb.pandas_utils import split_and_explode_column

ID_COL_NAME = 'Clinical Annotation ID'
GENOTYPE_ALLELE_COL_NAME = 'Genotype/Allele'
VAR_ID_COL_NAME = 'Variant Annotation ID'
EFFECT_COL_NAME = 'effect_term'
OBJECT_COL_NAME = 'object_term'
ASSOC_COL_NAME = 'Is/Is Not associated'
DOE_COL_NAME = 'Direction of effect'
BASE_ALLELE_COL_NAME = 'Alleles'
COMPARISON_COL_NAME = 'Comparison Allele(s) or Genotype(s)'


def merge_variant_annotation_tables(var_drug_table, var_pheno_table):
    """
    Return a single dataframe with selected columns from each variant annotation table.

    :param var_drug_table: variant drug annotation table
    :param var_pheno_table: variant phenotype annotation table
    :return: unified variant annotation dataframe
    """
    # Select relevant columns
    # TODO confirm which columns we want to include, and whether to include functional assay evidence
    drug_df = var_drug_table[[
        'Variant Annotation ID', 'PMID', 'Sentence', 'Alleles', 'Is/Is Not associated',
        'Direction of effect', 'PD/PK terms', 'Drug(s)',
        'Comparison Allele(s) or Genotype(s)'
    ]]
    phenotype_df = var_pheno_table[[
        'Variant Annotation ID', 'PMID', 'Sentence', 'Alleles', 'Is/Is Not associated',
        'Direction of effect', 'Side effect/efficacy/other', 'Phenotype',
        'Comparison Allele(s) or Genotype(s)'
    ]]
    # Rename differing columns so we can concat
    drug_df = drug_df.rename(columns={'PD/PK terms': EFFECT_COL_NAME, 'Drug(s)': OBJECT_COL_NAME})
    phenotype_df = phenotype_df.rename(columns={'Side effect/efficacy/other': EFFECT_COL_NAME,
                                                'Phenotype': OBJECT_COL_NAME})
    # Strip type annotation (disease, side effect, etc.) from phenotype column - we might use this later but not now
    phenotype_df[OBJECT_COL_NAME] = phenotype_df[OBJECT_COL_NAME].dropna().apply(
        lambda p: p.split(':')[1] if ':' in p else p)
    return pd.concat((drug_df, phenotype_df))


def get_variant_annotations(clinical_alleles_df, clinical_evidence_df, var_annotations_df):
    """
    Main method for getting associations between clinical annotations and variant annotations.

    :param clinical_alleles_df: clinical annotation alleles dataframe
    :param clinical_evidence_df: clinical evidence dataframe, used to link clinical annotations and variant annotations
    :param var_annotations_df: variant annotation dataframe
    :return: dataframe describing associations between clinical annotations alleles and variant annotations
    """
    caid_to_vaid = {
        caid: clinical_evidence_df[clinical_evidence_df[ID_COL_NAME] == caid]['Evidence ID'].to_list()
        for caid in clinical_evidence_df[ID_COL_NAME]
    }
    results = {}
    for caid, vaids in caid_to_vaid.items():
        clinical_alleles_for_caid = clinical_alleles_df[clinical_alleles_df[ID_COL_NAME] == caid][[
            ID_COL_NAME, GENOTYPE_ALLELE_COL_NAME
        ]]
        variant_ann_for_caid = var_annotations_df[var_annotations_df[VAR_ID_COL_NAME].isin(vaids)]
        # Filter for positive associations only
        variant_ann_for_caid = variant_ann_for_caid[
            variant_ann_for_caid[ASSOC_COL_NAME].str.lower() == 'associated with'
        ]
        results[caid] = associate_annotations_with_alleles(variant_ann_for_caid, clinical_alleles_for_caid)

    # Re-assemble results into a single dataframe
    final_dfs = []
    for caid, df in results.items():
        new_df = df[[
            GENOTYPE_ALLELE_COL_NAME, 'PMID', 'Sentence', BASE_ALLELE_COL_NAME,
            DOE_COL_NAME, EFFECT_COL_NAME, OBJECT_COL_NAME, COMPARISON_COL_NAME
        ]].groupby(GENOTYPE_ALLELE_COL_NAME, as_index=False).aggregate(list)
        new_df[ID_COL_NAME] = caid
        final_dfs.append(new_df)
    return pd.concat(final_dfs)


def associate_annotations_with_alleles(annotation_df, clinical_alleles_df):
    """
    Associate variant annotations with clinical annotation alleles, using the algorithm described here:
    https://docs.google.com/document/d/1YYNMLArt0FNFUEFLieMDm1p5NHSfJheddnPUocy8pGM/edit?usp=sharing

    :param annotation_df: variant annotation dataframe, filtered to only contain one clinical annotation ID
    :param clinical_alleles_df: clinical annotation alleles dataframe, filtered to contain one CAID
    :return: dataframe merging annotation_df and clinical_alleles_df based on the computed associations
    """
    # Split on +
    split_ann_df = split_and_explode_column(annotation_df, BASE_ALLELE_COL_NAME, 'split_alleles_1', sep='\+')
    # Split on /
    split_ann_df = split_and_explode_column(split_ann_df, 'split_alleles_1', 'split_alleles_2', sep='/')
    # Get alleles from clinical annotations - same logic as for getting ids
    split_clin_df = clinical_alleles_df.assign(
        parsed_genotype=clinical_alleles_df[GENOTYPE_ALLELE_COL_NAME].apply(simple_parse_genotype))
    split_clin_df = split_clin_df.explode('parsed_genotype').reset_index(drop=True)

    # Match by +-split and /-split
    merged_df = pd.merge(split_clin_df, split_ann_df, how='outer', left_on=GENOTYPE_ALLELE_COL_NAME,
                         right_on='split_alleles_1')
    merged_df_2 = pd.merge(split_clin_df, split_ann_df, how='outer', left_on='parsed_genotype',
                           right_on='split_alleles_2')
    # TODO match also on comparison genotype/allele

    # If a genotype in a clinical annotation doesn't have evidence, want this listed with nan's
    all_results = []
    for caid, genotype, parsed_genotype in split_clin_df.itertuples(index=False):
        # Rows that matched on genotype
        rows_first_match = merged_df[
            (merged_df[GENOTYPE_ALLELE_COL_NAME] == genotype) & (merged_df['parsed_genotype'] == parsed_genotype) & (
                ~merged_df[VAR_ID_COL_NAME].isna())]
        # Rows that matched on parsed genotype
        rows_second_match = merged_df_2[
            (merged_df_2[GENOTYPE_ALLELE_COL_NAME] == genotype) & (merged_df_2['parsed_genotype'] == parsed_genotype) & (
                ~merged_df_2[VAR_ID_COL_NAME].isna())]

        # If neither matches, add with nan's
        if rows_first_match.empty and rows_second_match.empty:
            all_results.append(merged_df[(merged_df[GENOTYPE_ALLELE_COL_NAME] == genotype) & (
                        merged_df['parsed_genotype'] == parsed_genotype)])
        else:
            all_results.extend([rows_first_match, rows_second_match])

    # Might associate the same variant annotation with a genotype/allele multiple times, so need to drop duplicates
    final_result = pd.concat(all_results).drop_duplicates(subset=[GENOTYPE_ALLELE_COL_NAME, VAR_ID_COL_NAME])

    # TODO This part is only useful for counts, think about whether we need it
    # If _no_ part of a variant annotation is associated with any clinical annotation, want this listed with nan's
    # for idx, row in split_ann_df.iterrows():
    #     vaid = row[VAR_ID_COL_NAME]
    #     alleles = row[BASE_ALLELE_COL_NAME]
    #     split_1 = row['split_alleles_1']
    #     split_2 = row['split_alleles_2']
    #     results_with_vaid = final_result[final_result[VAR_ID_COL_NAME] == vaid]
    #     if results_with_vaid.empty:
    #         final_result = pd.concat((final_result,
    #                                   merged_df[(merged_df[VAR_ID_COL_NAME] == vaid) & (
    #                                               merged_df[BASE_ALLELE_COL_NAME] == alleles) &
    #                                             (merged_df['split_alleles_1'] == split_1) & (
    #                                                         merged_df['split_alleles_2'] == split_2)]
    #                                   ))
    return final_result


def simple_parse_genotype(genotype_string):
    """
    Parse PGKB string representations of genotypes into alleles. Note this is simpler than the one in
    variant_coordinates.py as it does not need to compute precise variant coordinates, just parse string
    representations of alleles to use for matching.
    """
    alleles = [genotype_string]

    # SNPs
    if len(genotype_string) == 2 and '*' not in genotype_string:
        alleles = [genotype_string[0], genotype_string[1]]

    # others (indels, repeats, star alleles)
    m = re.match('([^/]+)/([^/]+)', genotype_string, re.IGNORECASE)
    if m:
        alleles = [m.group(1), m.group(2)]

    return alleles

# -*- coding: utf-8 -*-
"""Passage des tableaux et sections aux parcours et étapes.

Aucun résultat n'avait encore été saisi : les cas, leur historique et leurs
identifiants XML sont supprimés, et la mise à jour les recrée rattachés aux
étapes, avec les nouvelles références (RMP, RLP, RMCB, RCB).

Les colonnes tableau_id, section_id et section_sequence sont retirées ici, avant
le chargement des données : sinon leur contrainte NOT NULL ferait échouer la
création des nouveaux cas. Les tables des tableaux et des sections sont
supprimées par Odoo en fin de mise à jour, leurs modèles n'existant plus.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DELETE FROM nkezefuu_recette_echange")
    cr.execute("DELETE FROM nkezefuu_recette_cas")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'nkezefuu_recette'
           AND model IN ('nkezefuu.recette.cas', 'nkezefuu.recette.section', 'nkezefuu.recette.tableau')
    """)
    cr.execute("""
        ALTER TABLE nkezefuu_recette_cas
            DROP COLUMN IF EXISTS tableau_id,
            DROP COLUMN IF EXISTS section_id,
            DROP COLUMN IF EXISTS section_sequence
    """)

# -*- coding: utf-8 -*-
"""Passage des cas de recette aux versions de l'application.

Chaque cas appartient désormais à une version, et la version de l'application
n'est plus saisie à chaque résultat. Aucun résultat réel n'avait encore été
enregistré : les cas et leur historique sont supprimés avec leurs identifiants
XML, et la mise à jour les recrée dans la version 0.0.1, déclarée par
data/recette_versions.xml.

Les colonnes version_apk des cas et des échanges, qui n'ont plus de champ, sont
retirées : Odoo ne supprime pas lui-même les colonnes des champs disparus.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DELETE FROM nkezefuu_recette_echange")
    cr.execute("DELETE FROM nkezefuu_recette_cas")
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'nkezefuu_recette'
           AND model = 'nkezefuu.recette.cas'
    """)
    cr.execute("ALTER TABLE nkezefuu_recette_cas DROP COLUMN IF EXISTS version_apk")
    cr.execute("ALTER TABLE nkezefuu_recette_echange DROP COLUMN IF EXISTS version_apk")

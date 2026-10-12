# -*- coding: utf-8 -*-

from odoo import fields, models


class RecetteTableau(models.Model):
    """Un tableau de recette, l'équivalent d'un onglet du classeur (Mes prêts,
    Comptes bancaires). Un modèle plutôt qu'une sélection figée : ajouter un tableau
    plus tard ne demande pas de recoder."""
    _name = 'nkezefuu.recette.tableau'
    _description = 'Tableau de recette'
    _order = 'sequence, id'

    name = fields.Char(string='Nom', required=True)
    # Utilisé dans les routes : /api/recette/tableaux/<code>
    code = fields.Char(string='Code', required=True)
    # Préfixe de la référence des cas : PR-025, CB-007
    prefixe = fields.Char(string='Préfixe', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    description = fields.Text(string='Description')
    section_ids = fields.One2many('nkezefuu.recette.section', 'tableau_id', string='Sections')
    cas_ids = fields.One2many('nkezefuu.recette.cas', 'tableau_id', string='Cas')

    # Odoo 19 n'applique plus _sql_constraints (ignoré avec un simple avertissement).
    _code_unique = models.Constraint('unique(code)', 'Ce code de tableau est déjà utilisé.')
    _prefixe_unique = models.Constraint('unique(prefixe)', 'Ce préfixe est déjà utilisé par un autre tableau.')

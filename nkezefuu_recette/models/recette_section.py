# -*- coding: utf-8 -*-

from odoo import fields, models


class RecetteSection(models.Model):
    """Une ligne de titre du tableau, comme « 1. Ouvrir l'écran Mes prêts »."""
    _name = 'nkezefuu.recette.section'
    _description = 'Section de recette'
    _order = 'tableau_id, sequence, id'

    tableau_id = fields.Many2one('nkezefuu.recette.tableau', string='Tableau', required=True,
                                 ondelete='restrict', index=True)
    name = fields.Char(string='Titre', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    cas_ids = fields.One2many('nkezefuu.recette.cas', 'section_id', string='Cas')

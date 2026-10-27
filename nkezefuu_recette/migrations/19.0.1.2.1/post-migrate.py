# -*- coding: utf-8 -*-
"""Un cas bloqué attend désormais le développeur, et non plus le testeur.

« Action attendue de » est un champ calculé stocké : changer sa règle ne
recalcule pas les cas existants. Seuls les cas bloqués sans réponse du
développeur changent ; après sa réponse, la règle n'a pas bougé.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE nkezefuu_recette_cas
           SET balle = 'developer'
         WHERE resultat = 'blocked'
           AND dernier_acteur IS DISTINCT FROM 'developer'
           AND balle IS DISTINCT FROM 'developer'
    """)
    _logger.info("Cas bloqués passés au développeur : %s", cr.rowcount)

# nkezefuu-management

Modules de la plateforme de suivi des produits de la coopérative NKEZEFUU
(`management.nkezefuu.com`), sur une instance Odoo 19 dédiée, indépendante de la
production de la coopérative.

| Module | Rôle |
|---|---|
| `nkezefuu_recette` | recette fonctionnelle de l'application mobile |

## nkezefuu_recette

Module Odoo 19 de recette fonctionnelle de l'application mobile NKEZEFUU.

Les cas de test, leurs résultats et la discussion entre le testeur et le développeur
mobile sont enregistrés dans Odoo, et manipulés uniquement par API depuis le site
`apps-docs.nkezefuu.com` (entrée « Recette »). Le module n'a volontairement ni vue
ni menu.

Il ne dépend que de `base`, et gère lui-même ses jetons de connexion.

## Profils

| Profil | Ce qu'il peut faire |
|---|---|
| Testeur | poser un résultat, commenter, ajouter un cas |
| Admin testeur | tout ce que fait le testeur, plus modifier le texte d'un cas, archiver, gérer sections et tableaux |
| Développeur mobile | poser une suite, commenter, ajouter un cas (un compte portail suffit) |

Chaque profil est attribué explicitement, administrateurs compris : le statut
d'administrateur système ne donne par lui-même aucun accès à la recette.

Les profils vivent dans deux privilèges distincts, « Profil de recette » (Testeur
puis Admin testeur, qui s'excluent) et « Développement mobile ». Un même compte peut
donc être à la fois Admin testeur et Développeur mobile, ce qui est utile pendant la
mise au point.

## Données initiales

`data/recette_donnees.xml`, en `noupdate="1"` : 2 tableaux (Mes prêts, Comptes
bancaires), 12 sections, 125 cas. Ils sont créés à l'installation et jamais réécrits
ensuite : ce qui est corrigé depuis le site survit aux mises à jour, et un cas ajouté
plus tard dans ce fichier est créé à la mise à jour suivante sans toucher aux autres.

On archive un cas devenu inutile, on ne le supprime pas.

## Routes

Toutes sous `/api/recette`, jeton Bearer, réponse HTTP 200 avec le vrai résultat dans
`customstatus`. Toute création ou modification renvoie l'objet complet.

| Route | Rôle |
|---|---|
| `POST /login` | identifiant et mot de passe contre une paire de jetons |
| `POST /refresh` | nouvelle paire contre le jeton de renouvellement |
| `POST /logout` | révoque la paire du jeton d'accès |
| `GET /moi` | l'utilisateur connecté (nom, identifiant) et ses profils |
| `POST /moi/mot-de-passe` | changer son mot de passe ; révoque les autres connexions et renvoie une nouvelle paire |
| `GET /tableaux` | les tableaux et leurs compteurs |
| `POST /tableaux` | créer un tableau (admin testeur) |
| `GET /tableaux/{code}` | le tableau complet ; filtres `balle=moi`, `resultat=ko,regression`, `archives=1` |
| `POST /sections`, `POST /sections/{id}/update` | gérer les sections (admin testeur) |
| `POST /cas` | ajouter un cas |
| `GET /cas/{id}` | une ligne avec sa discussion |
| `POST /cas/{id}/update` | corriger le texte (admin testeur) |
| `POST /cas/{id}/archive`, `/unarchive` | archiver, restaurer (admin testeur) |
| `POST /cas/{id}/resultat` | le testeur pose un résultat |
| `POST /cas/{id}/reponse` | le développeur pose une suite |
| `POST /cas/{id}/commentaire` | message libre |

Une connexion produit un jeton d'accès valable 8 heures (`token`) et un jeton de
renouvellement valable 30 jours (`refresh_token`). Quand une route répond 401, appeler
`/refresh` avec le jeton de renouvellement : il est consommé et remplacé par une
nouvelle paire, et ne peut pas être rejoué. Seules les empreintes des jetons sont
stockées en base. Un compte archivé perd ses accès immédiatement.

`/moi/mot-de-passe` attend `ancien_mot_de_passe` et `nouveau_mot_de_passe` (8 caractères
au moins, différent de l'actuel). Il passe par la même protection contre les essais en
rafale que la connexion (`customstatus` 429 pendant le délai d'attente). Un mot de
passe actuel faux renvoie 400, et non 401, pour que le site ne le prenne pas pour une
session expirée. En cas de succès, toutes les paires du compte sont révoquées et la
réponse est la session complète, comme `/login` : le site remplace ses jetons.

## Déploiement

L'instance suit l'organisation des autres Odoo du serveur : un répertoire par
instance, avec ses propres sources, son venv, sa conf, sa base et son service.

| Élément | Valeur |
|---|---|
| Domaine | `management.nkezefuu.com` |
| Répertoire | `/opt/nkezefuu/management/` |
| Sources Odoo 19 | `/opt/nkezefuu/management/odoo/` |
| Venv | `/opt/nkezefuu/management/venv/` |
| Clone de ce dépôt | `/opt/nkezefuu/management/nkezefuu-management/` |
| Conf | `/etc/nkezefuu-management.conf` |
| Base | `management` |
| Port | 8075 |
| Service systemd | `nkezefuu-management` |

Un seul environnement : chaque push sur `master` est contrôlé (compilation du Python,
validité des XML et du CSV des droits, présence des fichiers du manifeste), puis
déployé dans le clone ci-dessus, et le service est redémarré. Si le contrôle échoue,
rien n'est déployé.

Secrets requis, les mêmes que pour `nkezefuu-addons` : `VPS_HOST`, `VPS_USER`,
`VPS_SSH_PRIVATE_KEY`.

Le pipeline ne met pas le module à jour. Après un changement de modèle, de droits ou
de données :

```bash
sudo systemctl stop nkezefuu-management
sudo -u odoo /opt/nkezefuu/management/venv/bin/python3 \
    /opt/nkezefuu/management/odoo/odoo-bin \
    -c /etc/nkezefuu-management.conf -d management \
    -u nkezefuu_recette --stop-after-init
sudo systemctl start nkezefuu-management
```

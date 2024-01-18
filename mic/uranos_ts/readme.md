Lien Uranos-Timesheet
=====================

Installation
------------

* Installer pymssql  (pip install pymssql)

Uranos TS
---------

Ce module gère 3 liens avec Timesheet.

Synchronisation des contacts
----------------------------

Cette partie applique dans Timesheet les changements aux Partners/Users.

* synchroniser Contact (11 champs)
* synchroniser RoleEmployee (4 champs)
* champ Last Action Date - pour savoir si le client nous a contacté récemment


Gestion des tâches
------------------

Cette partie permet la création des Work TS depuis la vue tâche.

* bouton Create/bind Request - crée une nouvelle requête (le rebind est perdu?)
* bouton Create TS Event - si un événement pour cette tâche est ouvert, écrase l'heure de fin,
sinon en crée un nouveau et marque la progression du Followup (si unique)
* bouton Close Request - ferme la tâche et tous ses Followup
* bouton Unbind Request - coupe le lien Odoo-TS (pour corriger certaines erreurs)
* champ Request Status (admin seulement) - statut sous Timesheet
* champ Total (admin seulement) - somme des billing_time
* Section Sprint : Calculer automatiquement le nombre d'heure lié à une tâche.


Rapports Timesheet
------------------

Cette partie permet de faire le suivi de la facturation et l'analyse du temps passé sur les tâches.

* import des tables Request, Event, Billing, Followup et intermédiaires
* création de l'apps Uranos Timesheet pour afficher ces modèles
* regroupement par département
* écran de supervision qui affiche les erreurs de durée, similaire à TS


Détails techniques
------------------

Les champs password / database pour se connecter à MSSQL/Timesheet ne peuvent être modifiés
que par le fichier de configuration sous les entrées ts_password / ts_database.

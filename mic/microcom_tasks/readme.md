Microcom Tasks
====================

Ce module modifie la gestion de projet pour les besoins de Microcom.

Etats Kanban
------------

On ajoute Approval à ProjectTask.kanban_state pour les tâches bloquées
en attente d'approbation.

Ceci implique l'ajout du champ legend_approved, du CSS, et un correctif au widget.


Tâches
------

Changement au modèle Task:

* champ description - nécessaire pour uranos_ts
* champ priority_microcom - les 5 étoiles
* champ max_hours  - inutilisé
* champ planned_hours - durée planifiée au sprint
* vue Tree (plusieurs colonnes ajoutées)
* Contrôle de qualité
    * Un nouvel onglet est ajouté sur la tâche contenant la liste des actions à faire avant de remettre la "Pull Request"
    * Il y a un écran dans la configuration pour ajouter des items au "Check list"


Détails techniques
------------------

Le cron Patch Task Priority transfer la priorité anciennement placée dans `priority`.
Cette opération ne doit pas être migrée en v15.

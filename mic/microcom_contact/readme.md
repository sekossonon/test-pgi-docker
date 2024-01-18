Microcom Contact
================

Ce module modifie la gestion des partenaires pour les besoins de Microcom.

Champs permanents de Timesheet
------------------------------

Certains champs de Timesheet doivent survivre si la gestion du temps
utilise un nouvel outil.

Pour Partner (Contact dans TS):
* warning - sert dans Timesheet
* bill_to_id - sert dans Timesheet
* security_level - sert dans Timesheet (?)
* pk_contact - clef étrangère vers Timesheet
* min_billing_time - sert dans Timesheet
* is_company - mettre le défaut à True

Pour User (RoleEmployee dans TS):
* privilege - sert dans Timesheet
* contact_group - sert dans Timesheet
* clearance_level - sert dans Timesheet

Gestion du code client
----------------------

Le champ ref contient le code client.
Les recherches doivent retourner en priorité les partenaires
ayant un code similaire avant les noms similaires.

* ref doit être unique (la comptabilité Access le suppose)
* le display_name est ajusté
* la recherche passe par une requête SQL explicite pour trier les résultats

Ces changements sont appliqués à Users aussi.


Détails techniques
------------------

* La recherche utilise `unaccent` si installé.
* Un filtre sur le numéro de téléphone et de cellulaire a été ajouté au contact.

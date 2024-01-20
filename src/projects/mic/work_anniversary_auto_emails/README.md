Work Anniversary Emails
=======================

This module sends emails to remind employees of someone's hire date anniversary

Automatically sends a 'Work Anniversary' email to specific predetermined employees
in the company when it is someone's hire date anniversary thirty (30) days before
the current day. If there are n employees that share a common hire date (year is not 
considered), a single email will be sent mentioning every one of those n employees.
Emails are created and sent to the email queue automatically everyday at 6 AM, 
through a cron job.

The email template is located with the others templates which are located
in Settings / Technical / Email / Templates. Developer mode must be activated
in order to access this menu.

The reminder scheduled action can be suspended from the Automation menu.


Version française
=================

Envoi de courriel
-----------------

Ce module envoi des courriels pour rappeler les années de services des employés.

Un courriel est envoyé à chaque jour où il y a un ou plusieurs
utilisateurs actifs dont l'anniversaire d'embauche arrive dans
30 jours. Un seul courriel contenant tous les fêtés sera envoyé.

Seul un manager peut entrer la date d'embauche, laquelle se trouve
dans l'onglet d'information personnelle du partenaire.

Le courriel-modèle Work Anniversary Reminder se trouve avec les autres
templates dans Settings / Technical / Email / Templates, il faut activer
le mode développeur pour y accéder.

L'action planifiée du même nom permet de suspendre l'envoi du courriel.


Contributors
------------

* Marc-Etienne Dery <med@microcom.ca>
* Stephane Le Cornec <slc@microcom.ca>
* Marc-Etienne Leblanc <mel@microcom.ca>
* Eric Lemire <el@microcom.ca>


Maintainer
----------

This module is maintained by Microcom.

<img src="static/description/MICROCOM.png" width="500">

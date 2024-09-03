#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import configparser
from modules.OptionParser_doc import OptionParser_doc

# Constantes
NOM_SCRIPT = "bftp.py"
ConfigFile = 'bftp.ini'
RunningFile = 'bftp_run.ini'

def analyse_conf():
    """Pour analyser/initialiser le paramétrage
    (à l'aide du module ConfigParser)"""
    config = configparser.RawConfigParser(allow_no_value=True)
    config.read_file(open(ConfigFile))
    param = config.items("blindftp")
    for key, val in param:
        if config.has_option("blindftp", key):
            param = config.get("blindftp", key)
    return param

def analyse_options():
    """Pour analyser les options de ligne de commande.
    (à l'aide du module optparse)"""

    parseur = OptionParser_doc(usage="%prog [options] <fichier ou repertoire>")
    parseur.doc = __doc__

    parseur.add_option("-e", "--envoi", action="store_true", dest="envoi_fichier",
        default=False, help="Envoyer le fichier")
    parseur.add_option("-s", "--synchro", action="store_true", dest="synchro_arbo",
        default=False, help="Synchroniser l'arborescence")
    parseur.add_option("-S", "--Synchro", action="store_true", dest="synchro_arbo_stricte",
        default=False, help="Synchroniser l'arborescence avec suppression")
    parseur.add_option("-r", "--reception", action="store_true", dest="recevoir",
        default=False, help="Recevoir des fichiers dans le repertoire indique")
    parseur.add_option("-a", dest="adresse", default="localhost",
        help="Adresse destination: Adresse IP ou nom de machine")
    parseur.add_option("-p", dest="port_UDP",
        help="Port UDP", type="int", default=36016)
    parseur.add_option("-l", dest="debit",
        help="Limite du debit (Kbps)", type="int", default=8000)
    parseur.add_option("-d", "--debug", action="store_true", dest="debug",
        default=False, help="Mode Debug")
    parseur.add_option("-b", "--boucle", dest="boucle", action="store", type="int", default=None,
                    help="Envoyer en boucle (optionnel: nombre d'envois)")
    parseur.add_option("-P", dest="pause",
        help="Pause entre 2 boucles (en secondes)", type="int", default=300)
    parseur.add_option("-c", "--continue", action="store_true", dest="reprise",
        default=False, help="Fichier de reprise a chaud")

    (options, args) = parseur.parse_args(sys.argv[1:])
    
    # Vérification des actions
    nb_actions = sum([options.envoi_fichier, options.synchro_arbo, options.synchro_arbo_stricte, options.recevoir])
    if nb_actions != 1:
        parseur.error(f"Vous devez indiquer une et une seule action. ({NOM_SCRIPT} -h pour l'aide complete)")
    if len(args) != 1:
        parseur.error(f"Vous devez indiquer un et un seul fichier/repertoire. ({NOM_SCRIPT} -h pour l'aide complete)")
    
    return (options, args)

def Save_ConfTrace():
    """Pour sauvegarder le paramétrage courant"""
    # TODO: Implémenter cette fonction
    pass
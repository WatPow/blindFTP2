#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import os
from plx import str_lat1, print_console

def debug(message):
    if MODE_DEBUG:
        print_console("DEBUG: " + message)

def str_ajuste(chaine, longueur=79):
    """Ajuste une chaîne à une longueur donnée."""
    if len(chaine) > longueur:
        return chaine[:longueur-3] + "..."
    return chaine.ljust(longueur)

def mtime2str(date_fichier):
    """Convertit une date de fichier en chaîne de caractères."""
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(date_fichier))

def chemin_interdit(chemin):
    """Vérifie si un chemin est interdit."""
    for ext in IgnoreExtensions:
        if chemin.endswith(ext):
            return True
    return False

def augmenter_priorite():
    """Augmente la priorité du processus."""
    try:
        os.nice(-20)
    except:
        print("Impossible d'augmenter la priorité du processus:")
        print("Il est conseillé de le lancer en tant que root pour obtenir les meilleures performances.")

# Variables globales (à déplacer plus tard dans un fichier de configuration)
MODE_DEBUG = False
IgnoreExtensions = ('.part', '.tmp', '.ut', '.dlm')
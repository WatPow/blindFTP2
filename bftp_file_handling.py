#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import tempfile
import logging
import io
from path import Path
import xfl

from bftp_utils import debug, str_ajuste, mtime2str, chemin_interdit
from modules import TabBits, TraitEncours

class Fichier:
    """Classe représentant un fichier en cours de réception."""

    def __init__(self, paquet):
        self.nom_fichier = paquet.nom_fichier
        self.date_fichier = paquet.date_fichier
        self.taille_fichier = paquet.taille_fichier
        self.nb_paquets = paquet.nb_paquets
        self.fichier_dest = CHEMIN_DEST / self.nom_fichier
        self.fichier_temp = tempfile.NamedTemporaryFile(prefix='BFTP_')
        self.paquets_recus = TabBits.TabBits(self.nb_paquets)
        self.est_termine = False
        self.crc32 = paquet.crc32
        self.termine = False

    def annuler_reception(self):
        if isinstance(self.fichier_temp, io.IOBase):
            if not self.fichier_temp.closed:
                self.fichier_temp.close()

    def recopier_destination(self):
        # Implémentation de la méthode recopier_destination
        pass

    def traiter_paquet(self, paquet):
        # Implémentation de la méthode traiter_paquet
        pass

    def est_complet(self):
        return self.paquets_recus.nb_true == self.nb_paquets

def synchro_arbo(cible):
    """Synchronise l'arborescence."""
    # Implémentation de la fonction synchro_arbo
    pass

def initialiser_fichier_reprise(cible, options):
    """Initialise le fichier de reprise."""
    print("Lecture/construction du fichier de reprise")
    XFLFile_id = False
    working = TraitEncours.TraitEnCours()
    working.StartIte()
    if options.reprise:
        XFLFile = "BFTPsynchro.xml"
        XFLFileBak = "BFTPsynchro.bak"
    else:
        XFLFile_id, XFLFile = tempfile.mkstemp(prefix='BFTP_', suffix='.xml')
    DRef = xfl.DirTree()
    if XFLFile_id:
        debug(f"Fichier de reprise de la session : {XFLFile}")
        DRef.read_disk(cible, working.AffCar)
    else:
        debug(f"Lecture du fichier de reprise : {XFLFile}")
        try:
            DRef.read_file(XFLFile)
        except:
            DRef.read_disk(cible, working.AffCar)
    
    return XFLFile_id, XFLFile, XFLFileBak, DRef

# Variables globales (à déplacer plus tard dans un fichier de configuration)
CHEMIN_DEST = None
OFFLINEDELAY = 86400*7
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
----------------------------------------------------------------------------
XFL Reset
----------------------------------------------------------------------------

Auteur:
- Laurent VILLEMIN (LV) - Laurent.villemin(a)laposte.net

"""

try:
    import bftp
except ImportError:
    raise ImportError("Le module blindftp n'est pas accessible: Voir https://adullact.net/projects/blindftp/")
try:
    import modules.TraitEncours as TraitEncours
except ImportError:
    raise ImportError("Le module TraitEncours n'est pas accessible: Voir https://adullact.net/projects/blindftp/")
try:
    import xfl
except ImportError:
    raise ImportError("le module XFL n'est pas installé: voir http://www.decalage.info/python/xfl")
import datetime, time, re
import os

XFLFile="BFTPsynchro.xml"

def Saisie(Libelle, DefValue):
    """
    Saisie d'une valeur avec proposition par défaut
    """
    question = Libelle + '? [' + str(DefValue) + '] '
    val=input(question)
    if val == '':
        return(DefValue)
    else:
        return(val)

def InputResetDate():
    """
    Saisie de la date et heure d'incident - préinitialisation à Now - 1 jour
    """
    print("Initialisation sur date incident. \n  Saisie de la date et heure de rupture du lien diode :")
    Incident=datetime.datetime.now()-datetime.timedelta(days=1)

    aaaa= Saisie('    Annee  ', Incident.year)
    mmm = Saisie('    Mois   ', Incident.month)
    dd  = Saisie('    Jour   ', Incident.day)
    hh  = Saisie('    Heure  ', Incident.hour)
    mm  = Saisie('    Minute ', Incident.minute)

    pattern = '%Y-%m-%d %H:%M:%S'
    MyDate="%d-%02d-%02d %02d:%02d:00" %(int(aaaa), int(mmm) , int(dd), int(hh), int(mm))
    epoch = int(time.mktime(time.strptime(MyDate, pattern)))
    bftp.debug("date_initialisation       = %s" % bftp.mtime2str(epoch))
    return(epoch)

def resetbyDate(ResetDate):
    """
    Initialisation des émissions au sein du fichier XML postérieur à une date
    Coté bas penser à automatiser la génération d'un fichier timestamp au sein de
    l'arborescence synchronisée afin d'identifier facilement l'heure de non transmission
    """
    DRef = xfl.DirTree()
    DRef.read_file(XFLFile)
    DRef.pathdict()
    NbFile=0
    NbReinitFile=0
    for myfile in DRef.dict:
        if(DRef.dict[myfile].tag == xfl.TAG_FILE):
            NbFile+=1
            if float(DRef.dict[myfile].get(bftp.ATTR_LASTSEND)) > ResetDate:
                NbReinitFile+=1
                print("        %s \n" % myfile)
                for attr in (bftp.ATTR_LASTSEND, bftp.ATTR_NBSEND):
                    DRef.dict[myfile].set(attr, str(0))
    bftp.debug('Initialisation de %d fichier(s) sur %d.' % (NbReinitFile,  NbFile))
    if NbReinitFile > 0:
        DRef.write_file(XFLFile)

def resetbyRegexp(expr):
    """
    Initialisation des émissions au sein du fichier XML selon un motif regexp
    Consulter le howto regexp python pour maitriser la syntaxe
    Quelques exemples
        .* : tous les fichiers
        .*\.txt$ : tous les fichiers d'extension ".txt"
        monrep/.* : tous les fichiers contenus dans monrep
    """
    DRef = xfl.DirTree()
    DRef.read_file(XFLFile)
    DRef.pathdict()
    NbFile=0
    NbReinitFile=0
    motif=re.compile(expr)
    for myfile in DRef.dict:
        if(DRef.dict[myfile].tag == xfl.TAG_FILE):
            NbFile+=1
            res=motif.match(str(myfile))
            if res!=None:
                NbFile+=1
                NbReinitFile+=1
                print("        %s" % myfile)
                for attr in (bftp.ATTR_LASTSEND, bftp.ATTR_NBSEND):
                    DRef.dict[myfile].set(attr, str(0))
    bftp.debug('Initialisation de %d fichier(s) sur %d.' % (NbReinitFile,  NbFile))
    if NbReinitFile > 0:
        DRef.write_file(XFLFile)

def resetbyDiff(path):
    """
    Initialisation des émissions au sein du fichier XML en comparant l'arborescence de réception
    Mode opératoire :
        Le fichier XML de reprise est transmis coté haut.
        Ce fichier est comparé à l'arborescence de réception
        Tous les fichiers déclarés émis et non reçus sont réinitialisés
        Importer le fichier XML modifié sur le guichet bas et relancer blindftp
    """
    DRef  = xfl.DirTree()
    DHaut = xfl.DirTree()
    MonAff=TraitEncours.TraitEnCours()
    MonAff.StartIte()
    DRef.read_file(XFLFile)
    DHaut.read_disk(path, None, MonAff.AffCar)
    same, different, only1, only2 = xfl.compare_DT(DRef, DHaut)
    NbReinitFile=0
    for myfile in sorted(different + only1):
        if(DRef.dict[myfile].tag == xfl.TAG_FILE):
            NbReinitFile+=1
            print("        %s" % myfile)
            for attr in (bftp.ATTR_LASTSEND, bftp.ATTR_NBSEND):
                DRef.dict[myfile].set(attr, str(0))
    bftp.debug('Initialisation de %d fichier(s)' % NbReinitFile)
    if NbReinitFile > 0:
        DRef.write_file(XFLFile)


def resetbyPath(path):
    """
    Initialisation des émissions au sein du fichier XML selon un chemin
    """
    DRef = xfl.DirTree()
    DRef.read_file(XFLFile)
    DRef.pathdict()
    if path in DRef.dict:
        for attr in (bftp.ATTR_LASTSEND, bftp.ATTR_NBSEND):
            DRef.dict[path].set(attr, str(0))
        DRef.write_file(XFLFile)
    else:
        print('Erreur : Chemin inexistant')


#--- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":
    methode=Saisie('Methode d initialisation utilisee ? \n1 : par date \n2 : par chemin du fichier \n3 : par analyse arborescence \n4 : par expression reguliere ', '1')
    if methode == '1':
        MyResetDate=InputResetDate()
        resetbyDate(MyResetDate)
    if methode == '2':
        path=Saisie('Chemin fichier ', '/chemin/vers/fichier.txt')
        resetbyPath(path)
    if methode == '3':
        path=Saisie('Chemin arborescence de reception ', "/chemin/vers/reception")
        resetbyDiff(path)
    if methode == '4':
        print("HowTo des expressions regulieres disponible à l'URL http://www.python.org/doc/howto/")
        regexp=Saisie('Expression reguliere ', ".*\.txt$")
        resetbyRegexp(regexp)


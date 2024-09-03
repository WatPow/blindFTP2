#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
XFL - XML File List v0.06 2008-02-06 - Philippe Lagadec
"""

#--- IMPORTS ------------------------------------------------------------------
import sys, time, os

# module path pour manipuler facilement les fichiers et répertoires :
try:
    from path import Path
except ImportError:
    raise ImportError("Le module path n'est pas installé : "
                      "voir http://www.jorendorff.com/articles/python/path/")

# ElementTree pour le XML pythonique :
try:
    import xml.etree.ElementTree as ET
except ImportError:
    raise ImportError("Le module ElementTree n'est pas installé : "
                      "voir http://effbot.org/zone/element-index.htm")

#--- CONSTANTES ----------------------------------------------------------------

# Balises XML
TAG_DIRTREE = "dirtree"
TAG_DIR     = "dir"
TAG_FILE    = "file"

# Attributs XML
ATTR_NAME  = "name"
ATTR_TIME  = "time"
ATTR_MTIME = "mtime"
ATTR_SIZE  = "size"
ATTR_OWNER = "owner"

#--- CLASSES ------------------------------------------------------------------

class DirTree:
    """
    Classe représentant une arborescence de répertoires et fichiers,
    qui peut être écrite ou lue depuis un fichier XML.
    """

    def __init__(self, rootpath=""):
        """
        Constructeur DirTree.
        """
        self.rootpath = Path(rootpath)

    def read_disk(self, rootpath=None, callback_dir=None, callback_file=None):
        """
        Pour lire le DirTree depuis le disque.
        """
        # création de l'ElementTree racine :
        self.et = ET.Element(TAG_DIRTREE)
        if rootpath:
            self.rootpath = Path(rootpath)
        # attribut name = rootpath
        self.et.set(ATTR_NAME, str(self.rootpath))
        # attribut time = heure du scan
        self.et.set(ATTR_TIME, str(time.time()))
        try:
            self._scan_dir(self.rootpath, self.et, callback_dir, callback_file)
        except:
            print(" Erreur : impossible de scanner le répertoire %s " % self.rootpath)

    def _scan_dir(self, dir, parent, callback_dir=None, callback_file=None):
        """
        Pour scanner un répertoire sur le disque (scan récursif).
        (ceci est une méthode privée)
        """
        if callback_dir:
            callback_dir(dir, parent)
        for f in dir.files():
            e = ET.SubElement(parent, TAG_FILE)
            e.set(ATTR_NAME, f.name)
            e.set(ATTR_SIZE, str(f.getsize()))
            e.set(ATTR_MTIME, str(f.getmtime()))
            try:
                e.set(ATTR_OWNER, f.get_owner())
            except:
                pass
            if callback_file:
                callback_file(f, e)
        for d in dir.dirs():
            e = ET.SubElement(parent, TAG_DIR)
            e.set(ATTR_NAME, d.name)
            try:
                self._scan_dir(d, e, callback_dir, callback_file)
            except:
                print("Erreur : impossible de scanner le sous-répertoire %s " % d)

    def write_file(self, filename, encoding="utf-8"):
        """
        Pour écrire le DirTree dans un fichier XML.
        """
        tree = ET.ElementTree(self.et)
        tree.write(filename, encoding=encoding)

    def read_file(self, filename):
        """
        Pour lire le DirTree depuis un fichier XML.
        """
        tree = ET.parse(filename)
        self.et = tree.getroot()
        self.rootpath = self.et.get(ATTR_NAME)

    def pathdict(self):
        """
        Pour créer un dictionnaire qui indexe tous les objets par leurs chemins.
        """
        self.dict = {}
        self._pathdict_dir(Path(""), self.et)

    def _pathdict_dir(self, base, et):
        """
        (méthode privée)
        """
        dirs = et.findall(TAG_DIR)
        for d in dirs:
            dpath = base / d.get(ATTR_NAME)
            self.dict[dpath] = d
            self._pathdict_dir(dpath, d)
        files = et.findall(TAG_FILE)
        for f in files:
            fpath = base / f.get(ATTR_NAME)
            self.dict[fpath] = f


#--- FONCTIONS ----------------------------------------------------------------

def compare_files(et1, et2):
    """
    Pour comparer deux fichiers ou répertoires.
    Renvoie True si les informations des fichiers/répertoires sont identiques,
    False sinon.
    """
    if et1.tag != et2.tag:
        return False
    if et1.tag == TAG_DIR:
        if et1.get(ATTR_NAME) != et2.get(ATTR_NAME):
            return False
        else:
            return True
    elif et1.tag == TAG_FILE:
        if et1.get(ATTR_NAME) != et2.get(ATTR_NAME):
            return False
        if et1.get(ATTR_SIZE) != et2.get(ATTR_SIZE):
            return False
        if et1.get(ATTR_MTIME) != et2.get(ATTR_MTIME):
            return False
        else:
            return True
    else:
        raise TypeError

def compare_DT(dirTree1, dirTree2):
    """
    Pour comparer deux DirTrees, et rapporter quels fichiers ont changé.
    Renvoie un tuple de 4 listes de chemins : fichiers identiques, fichiers différents,
    fichiers uniquement dans dt1, fichiers uniquement dans dt2.
    """
    same = []
    different = []
    only1 = []
    only2 = []
    dirTree1.pathdict()
    dirTree2.pathdict()
    paths1 = list(dirTree1.dict.keys())
    paths2 = list(dirTree2.dict.keys())
    for p in paths1:
        if p in paths2:
            # le chemin est dans les 2 DT, nous devons comparer les infos du fichier
            f1 = dirTree1.dict[p]
            f2 = dirTree2.dict[p]
            if compare_files(f1, f2):
                # les fichiers/répertoires sont identiques
                same.append(p)
            else:
                different.append(p)
            paths2.remove(p)
        else:
            only1.append(p)
    # maintenant paths2 devrait contenir uniquement les fichiers et répertoires qui n'étaient pas dans paths1
    only2 = paths2
    return same, different, only1, only2

def callback_dir_print(dir, element):
    """
    Fonction de callback exemple pour afficher le chemin du répertoire.
    """
    print(dir)

def callback_dir_print2(dir, element):
    """
    Fonction de callback exemple pour afficher le chemin du répertoire.
    """
    lg = len(str(dir))
    if lg > 75:
        l1 = (75 - 3)//2
        l2 = 75 - l1 - 3
        pathdir = str(dir)[0:l1]+"..."+str(dir)[lg-l2:lg]
    else:
        pathdir = str(dir) + (75-lg)*" "
    print(" %s\r" % pathdir, end='')

def callback_file_print(file, element):
    """
    Fonction de callback exemple pour afficher le chemin du fichier.
    """
    print(" - " + str(file))



#--- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print(__doc__)
        print("usage: python %s <root path> <xml file> [previous xml file]" % os.path.basename(sys.argv[0]))
        sys.exit(1)
    d = DirTree()
    d.read_disk(sys.argv[1], callback_dir_print, callback_file_print)
    d.write_file(sys.argv[2])
    if len(sys.argv)>3:
        d2 = DirTree()
        d2.read_file(sys.argv[3])
        same, different, only1, only2 = compare_DT(d, d2)
        print("\nIDENTIQUES:")
        for f in sorted(same):
            print("  "+str(f))
        print("\nDIFFÉRENTS:")
        for f in sorted(different):
            print("  "+str(f))
        print("\nNOUVEAUX:")
        for f in sorted(only1):
            print("  "+str(f))
        print("\nSUPPRIMÉS:")
        for f in sorted(only2):
            print("  "+str(f))


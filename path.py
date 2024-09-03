# -*- coding: utf-8 -*-

""" path.py - Un objet représentant un chemin vers un fichier ou un répertoire.

Exemple:

from path import Path
d = Path('/home/guido/bin')
for f in d.files('*.py'):
    f.chmod(0o755)

Ce module nécessite Python 3.2 ou ultérieur.


URL:     http://www.jorendorff.com/articles/python/path
Auteur:  Jason Orendorff <jason.orendorff@gmail.com> (et autres - voir l'url !)
Date:    9 Mar 2007
"""


import sys, warnings, os, fnmatch, glob, shutil, codecs
import hashlib

__version__ = '2.2'
__all__ = ['Path']

# Support spécifique à la plateforme pour path.owner
try:
    import pwd
except ImportError:
    pwd = None

# Support pré-2.3. Les noms de fichiers Unicode sont-ils pris en charge ?
_base = str
_getcwd = os.getcwd

# Support universel des nouvelles lignes
_textmode = 'r'


class TreeWalkWarning(Warning):
    pass

class Path(_base):
    """ Représente un chemin de système de fichiers.

    Pour la documentation des méthodes individuelles, consultez leurs
    homologues dans os.path.
    """

    # --- Méthodes Python spéciales.

    def __repr__(self):
        return 'Path(%s)' % _base.__repr__(self)

    # L'ajout d'un chemin et d'une chaîne donne un chemin.
    def __add__(self, more):
        try:
            resultStr = _base.__add__(self, more)
        except TypeError:  #Bogue Python
            resultStr = NotImplemented
        if resultStr is NotImplemented:
            return resultStr
        return self.__class__(resultStr)

    def __radd__(self, other):
        if isinstance(other, str):
            return self.__class__(other.__add__(self))
        else:
            return NotImplemented

    # L'opérateur / joint les chemins.
    def __truediv__(self, rel):
        """ fp.__truediv__(rel) == fp / rel == fp.joinpath(rel)

        Joint deux composants de chemin, en ajoutant un caractère séparateur si
        nécessaire.
        """
        return self.__class__(os.path.join(self, rel))

    __div__ = __truediv__

    @classmethod
    def getcwd(cls):
        """ Renvoie le répertoire de travail actuel sous forme d'objet path. """
        return cls(_getcwd())


    # --- Opérations sur les chaînes de chemin.

    isabs = os.path.isabs
    def abspath(self):       return self.__class__(os.path.abspath(self))
    def normcase(self):      return self.__class__(os.path.normcase(self))
    def normpath(self):      return self.__class__(os.path.normpath(self))
    def realpath(self):      return self.__class__(os.path.realpath(self))
    def expanduser(self):    return self.__class__(os.path.expanduser(self))
    def expandvars(self):    return self.__class__(os.path.expandvars(self))
    def dirname(self):       return self.__class__(os.path.dirname(self))
    basename = os.path.basename

    def expand(self):
        """ Nettoie un nom de fichier en appelant expandvars(),
        expanduser(), et normpath() dessus.

        C'est généralement tout ce qui est nécessaire pour nettoyer un nom de fichier
        lu à partir d'un fichier de configuration, par exemple.
        """
        return self.expandvars().expanduser().normpath()

    def _get_namebase(self):
        base, ext = os.path.splitext(self.name)
        return base

    def _get_ext(self):
        f, ext = os.path.splitext(_base(self))
        return ext

    def _get_drive(self):
        drive, r = os.path.splitdrive(self)
        return self.__class__(drive)

    parent = property(
        dirname, None, None,
        """ Le répertoire parent de ce chemin, sous forme de nouvel objet path.

        Par exemple, Path('/usr/local/lib/libpython.so').parent == Path('/usr/local/lib')
        """)

    name = property(
        basename, None, None,
        """ Le nom de ce fichier ou répertoire sans le chemin complet.

        Par exemple, Path('/usr/local/lib/libpython.so').name == 'libpython.so'
        """)

    namebase = property(
        _get_namebase, None, None,
        """ Identique à path.name, mais avec une extension de fichier supprimée.

        Par exemple, Path('/home/guido/python.tar.gz').name     == 'python.tar.gz',
        mais          Path('/home/guido/python.tar.gz').namebase == 'python.tar'
        """)

    ext = property(
        _get_ext, None, None,
        """ L'extension du fichier, par exemple '.py'. """)

    drive = property(
        _get_drive, None, None,
        """ Le spécificateur de lecteur, par exemple 'C:'.
        Ceci est toujours vide sur les systèmes qui n'utilisent pas de spécificateurs de lecteur.
        """)

    def splitpath(self):
        """ p.splitpath() -> Renvoie (p.parent, p.name). """
        parent, child = os.path.split(self)
        return self.__class__(parent), child

    def splitdrive(self):
        """ p.splitdrive() -> Renvoie (p.drive, <le reste de p>).

        Sépare le spécificateur de lecteur de ce chemin. S'il n'y a
        pas de spécificateur de lecteur, p.drive est vide, donc la valeur de retour
        est simplement (Path(''), p). C'est toujours le cas sous Unix.
        """
        drive, rel = os.path.splitdrive(self)
        return self.__class__(drive), rel

    def splitext(self):
        """ p.splitext() -> Renvoie (p.stripext(), p.ext).

        Sépare l'extension du nom de fichier de ce chemin et renvoie
        les deux parties. L'une ou l'autre partie peut être vide.

        L'extension est tout ce qui va de '.' à la fin du
        dernier segment de chemin. Cela a la propriété que si
        (a, b) == p.splitext(), alors a + b == p.
        """
        filename, ext = os.path.splitext(self)
        return self.__class__(filename), ext

    def stripext(self):
        """ p.stripext() -> Supprime une extension de fichier du chemin.

        Par exemple, Path('/home/guido/python.tar.gz').stripext()
        renvoie Path('/home/guido/python.tar').
        """
        return self.splitext()[0]

    if hasattr(os.path, 'splitunc'):
        def splitunc(self):
            unc, rest = os.path.splitunc(self)
            return self.__class__(unc), rest

        def _get_uncshare(self):
            unc, r = os.path.splitunc(self)
            return self.__class__(unc)

        uncshare = property(
            _get_uncshare, None, None,
            """ Le point de montage UNC pour ce chemin.
            Ceci est vide pour les chemins sur les lecteurs locaux. """)

    def joinpath(self, *args):
        """ Joint deux ou plusieurs composants de chemin, en ajoutant un caractère
        séparateur (os.sep) si nécessaire. Renvoie un nouvel objet
        path.
        """
        return self.__class__(os.path.join(self, *args))

    def splitall(self):
        r""" Renvoie une liste des composants de chemin dans ce chemin.

        Le premier élément de la liste sera un chemin. Sa valeur sera
        soit os.curdir, os.pardir, vide, ou le répertoire racine de
        ce chemin (par exemple, '/' ou 'C:\\').  Les autres éléments de
        la liste seront des chaînes.

        path.Path.joinpath(*result) donnera le chemin d'origine.
        """
        parts = []
        loc = self
        while loc != os.curdir and loc != os.pardir:
            prev = loc
            loc, child = prev.splitpath()
            if loc == prev:
                break
            parts.append(child)
        parts.append(loc)
        parts.reverse()
        return parts

    def relpath(self):
        """ Renvoie ce chemin comme un chemin relatif,
        basé sur le répertoire de travail actuel.
        """
        cwd = self.__class__(os.getcwd())
        return cwd.relpathto(self)

    def relpathto(self, dest):
        """ Renvoie un chemin relatif de self à dest.

        S'il n'y a pas de chemin relatif de self à dest, par exemple s'ils
        résident sur des lecteurs différents sous Windows, alors cela renvoie
        dest.abspath().
        """
        origin = self.abspath()
        dest = self.__class__(dest).abspath()

        orig_list = origin.normcase().splitall()
        # Ne pas normaliser dest ! Nous voulons préserver la casse.
        dest_list = dest.splitall()

        if orig_list[0] != os.path.normcase(dest_list[0]):
            # Impossible d'y arriver à partir d'ici.
            return dest

        # Trouver l'endroit où les deux chemins commencent à différer.
        i = 0
        for start_seg, dest_seg in zip(orig_list, dest_list):
            if start_seg != os.path.normcase(dest_seg):
                break
            i += 1

        # Maintenant i est le point où les deux chemins divergent.
        # Il faut un certain nombre de "os.pardir" pour remonter
        # de l'origine au point de divergence.
        segments = [os.pardir] * (len(orig_list) - i)
        # Il faut ajouter la partie divergente de dest_list.
        segments += dest_list[i:]
        if len(segments) == 0:
            # S'ils sont identiques par hasard, utiliser os.curdir.
            relpath = os.curdir
        else:
            relpath = os.path.join(*segments)
        return self.__class__(relpath)

    # --- Listage, recherche, parcours et correspondance

    def listdir(self, pattern=None):
        """ D.listdir() -> Liste des éléments dans ce répertoire.

        Utilisez D.files() ou D.dirs() à la place si vous voulez une liste
        de seulement les fichiers ou seulement les sous-répertoires.

        Les éléments de la liste sont des objets path.

        Avec l'argument optionnel 'pattern', cela ne liste
        que les éléments dont les noms correspondent au motif donné.
        """
        names = os.listdir(self)
        if pattern is not None:
            names = fnmatch.filter(names, pattern)
        return [self / child for child in names]

    def dirs(self, pattern=None):
        """ D.dirs() -> Liste des sous-répertoires de ce répertoire.

        Les éléments de la liste sont des objets path.
        Cela ne parcourt pas récursivement les sous-répertoires
        (mais voir path.walkdirs).

        Avec l'argument optionnel 'pattern', cela ne liste
        que les répertoires dont les noms correspondent au motif donné. Par
        exemple, d.dirs('build-*').
        """
        return [p for p in self.listdir(pattern) if p.isdir()]

    def files(self, pattern=None):
        """ D.files() -> Liste des fichiers dans ce répertoire.

        Les éléments de la liste sont des objets path.
        Cela ne parcourt pas les sous-répertoires (voir path.walkfiles).

        Avec l'argument optionnel 'pattern', cela ne liste
        que les fichiers dont les noms correspondent au motif donné. Par exemple,
        d.files('*.pyc').
        """

        return [p for p in self.listdir(pattern) if p.isfile()]

    def walk(self, pattern=None, errors='strict'):
        """ D.walk() -> itérateur sur les fichiers et sous-répertoires, récursivement.

        L'itérateur produit des objets path nommant chaque élément enfant de
        ce répertoire et ses descendants. Cela nécessite que
        D.isdir().

        Cela effectue un parcours en profondeur de l'arborescence du répertoire.
        Chaque répertoire est renvoyé juste avant tous ses enfants.

        L'argument errors= contrôle le comportement lorsqu'une
        erreur se produit. La valeur par défaut est 'strict', qui provoque une
        exception. Les autres valeurs autorisées sont 'warn', qui
        signale l'erreur via warnings.warn(), et 'ignore'.
        """
        if errors not in ('strict', 'warn', 'ignore'):
            raise ValueError("paramètre errors invalide")

        try:
            childList = self.listdir()
        except Exception:
            if errors == 'ignore':
                return
            elif errors == 'warn':
                warnings.warn(
                    "Impossible de lister le répertoire '{}': {}".format(
                        self, sys.exc_info()[1]),
                    TreeWalkWarning)
                return
            else:
                raise

        for child in childList:
            if pattern is None or child.fnmatch(pattern):
                yield child
            try:
                isdir = child.isdir()
            except Exception:
                if errors == 'ignore':
                    isdir = False
                elif errors == 'warn':
                    warnings.warn(
                        "Impossible d'accéder à '{}': {}".format(
                            child, sys.exc_info()[1]),
                        TreeWalkWarning)
                    isdir = False
                else:
                    raise

            if isdir:
                for item in child.walk(pattern, errors):
                    yield item

    def walkdirs(self, pattern=None, errors='strict'):
        """ D.walkdirs() -> itérateur sur les sous-répertoires, récursivement.

        Avec l'argument optionnel 'pattern', cela ne produit que
        les répertoires dont les noms correspondent au motif donné. Par
        exemple, mydir.walkdirs('*test') ne produit que les répertoires
        dont les noms se terminent par 'test'.

        L'argument errors= contrôle le comportement lorsqu'une
        erreur se produit. La valeur par défaut est 'strict', qui provoque une
        exception. Les autres valeurs autorisées sont 'warn', qui
        signale l'erreur via warnings.warn(), et 'ignore'.
        """
        if errors not in ('strict', 'warn', 'ignore'):
            raise ValueError("paramètre errors invalide")

        try:
            dirs = self.dirs()
        except Exception:
            if errors == 'ignore':
                return
            elif errors == 'warn':
                warnings.warn(
                    "Impossible de lister le répertoire '{}': {}".format(
                        self, sys.exc_info()[1]),
                    TreeWalkWarning)
                return
            else:
                raise

        for child in dirs:
            if pattern is None or child.fnmatch(pattern):
                yield child
            for subsubdir in child.walkdirs(pattern, errors):
                yield subsubdir

    def walkfiles(self, pattern=None, errors='strict'):
        """ D.walkfiles() -> itérateur sur les fichiers dans D, récursivement.

        L'argument optionnel, pattern, limite les résultats aux fichiers
        dont les noms correspondent au motif. Par exemple,
        mydir.walkfiles('*.tmp') ne produit que les fichiers avec l'extension .tmp.
        """
        if errors not in ('strict', 'warn', 'ignore'):
            raise ValueError("paramètre errors invalide")

        try:
            childList = self.listdir()
        except Exception:
            if errors == 'ignore':
                return
            elif errors == 'warn':
                warnings.warn(
                    "Impossible de lister le répertoire '{}': {}".format(
                        self, sys.exc_info()[1]),
                    TreeWalkWarning)
                return
            else:
                raise

        for child in childList:
            try:
                isfile = child.isfile()
                isdir = not isfile and child.isdir()
            except:
                if errors == 'ignore':
                    continue
                elif errors == 'warn':
                    warnings.warn(
                        "Impossible d'accéder à '{}': {}".format(
                            self, sys.exc_info()[1]),
                        TreeWalkWarning)
                    continue
                else:
                    raise

            if isfile:
                if pattern is None or child.fnmatch(pattern):
                    yield child
            elif isdir:
                for f in child.walkfiles(pattern, errors):
                    yield f

    def fnmatch(self, pattern):
        """ Renvoie True si self.name correspond au motif donné.

        pattern - Un motif de nom de fichier avec des caractères génériques,
            par exemple '*.py'.
        """
        return fnmatch.fnmatch(self.name, pattern)

    def glob(self, pattern):
        """ Renvoie une liste d'objets path qui correspondent au motif.

        pattern - un chemin relatif à ce répertoire, avec des caractères génériques.

        Par exemple, path('/users').glob('*/bin/*') renvoie une liste
        de tous les fichiers que les utilisateurs ont dans leurs répertoires bin.
        """
        cls = self.__class__
        return [cls(s) for s in glob.glob(str(self / pattern))]


    # --- Lecture ou écriture d'un fichier entier en une fois.

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        """ Ouvre ce fichier. Renvoie un objet fichier. """
        return open(self, mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    def bytes(self):
        """ Ouvre ce fichier, lit tous les octets, les renvoie sous forme de chaîne. """
        with self.open('rb') as f:
            return f.read()

    def write_bytes(self, data, append=False):
        """ Ouvre ce fichier et écrit les octets donnés.

        Le comportement par défaut est d'écraser tout fichier existant.
        Appelez p.write_bytes(bytes, append=True) pour ajouter à la place.
        """
        mode = 'ab' if append else 'wb'
        with self.open(mode) as f:
            f.write(data)

    def text(self, encoding=None, errors='strict'):
        """ Ouvre ce fichier, le lit et renvoie le contenu sous forme de chaîne.

        Paramètres optionnels :

        encoding - L'encodage Unicode (ou jeu de caractères) du
            fichier. Si présent, le contenu du fichier est
            décodé et renvoyé comme un objet unicode ; sinon
            il est renvoyé comme une chaîne de 8 bits.
        errors - Comment gérer les erreurs Unicode ; voir help(str.decode)
            pour les options. La valeur par défaut est 'strict'.
        """
        with self.open('r', encoding=encoding, errors=errors) as f:
            return f.read()

    def write_text(self, text, encoding=None, errors='strict', linesep=os.linesep, append=False):
        """ Écrit le texte donné dans ce fichier.

        Le comportement par défaut est d'écraser tout fichier existant ;
        pour ajouter à la place, utilisez l'argument 'append=True'.

        Il y a deux différences entre path.write_text() et
        path.write_bytes() : la gestion des sauts de ligne et la gestion Unicode.
        Voir ci-dessous.

        Paramètres :

          - text - str/unicode - Le texte à écrire.

          - encoding - str - L'encodage Unicode qui sera utilisé.
            Ceci est ignoré si 'text' n'est pas une chaîne Unicode.

          - errors - str - Comment gérer les erreurs d'encodage Unicode.
            La valeur par défaut est 'strict'. Voir help(str.encode) pour les
            options. Ceci est ignoré si 'text' n'est pas une chaîne Unicode.

          - linesep - argument mot-clé - str/unicode - La séquence de
            caractères à utiliser pour marquer la fin de ligne. La valeur par défaut est
            os.linesep. Vous pouvez aussi spécifier None ; cela signifie de
            laisser tous les sauts de ligne tels qu'ils sont dans 'text'.

          - append - argument mot-clé - bool - Spécifie quoi faire si
            le fichier existe déjà (True : ajouter à la fin ;
            False : l'écraser). La valeur par défaut est False.

        --- Gestion des sauts de ligne.

        write_text() convertit toutes les séquences standard de fin de ligne
        ('\\n', '\\r', et '\\r\\n') en séquence de fin de ligne par défaut de votre plateforme
        (voir os.linesep ; sur Windows, par exemple, le
        marqueur de fin de ligne est '\\r\\n').

        Si vous n'aimez pas la valeur par défaut de votre plateforme, vous pouvez la remplacer
        en utilisant l'argument 'linesep='. Si vous voulez spécifiquement que
        write_text() préserve les sauts de ligne tels quels, utilisez 'linesep=None'.

        Cela s'applique au texte Unicode de la même manière qu'au texte 8 bits, sauf
        qu'il y a trois séquences Unicode standard supplémentaires de fin de ligne :
        u'\\x85', u'\\r\\x85', et u'\\u2028'.

        (C'est légèrement différent de quand vous ouvrez un fichier pour
        écriture avec fopen(filename, "w") en C ou open(filename, 'w')
        en Python.)


        --- Unicode

        Si 'text' n'est pas Unicode, alors à part la gestion des sauts de ligne, les
        octets sont écrits tels quels dans le fichier. Les arguments 'encoding' et
        'errors' ne sont pas utilisés et doivent être omis.

        Si 'text' est Unicode, il est d'abord converti en octets en utilisant
        l'encodage spécifié (ou l'encodage par défaut si 'encoding'
        n'est pas spécifié). L'argument 'errors' s'applique uniquement à cette
        conversion.

        """
        mode = 'a' if append else 'w'
        with self.open(mode, encoding=encoding, errors=errors, newline=linesep) as f:
            f.write(text)

    def lines(self, encoding=None, errors='strict', retain=True):
        """ Ouvre ce fichier, lit toutes les lignes, les renvoie dans une liste.

        Arguments optionnels :
            encoding - L'encodage Unicode (ou jeu de caractères) du
                fichier. La valeur par défaut est None, ce qui signifie que le contenu
                du fichier est lu comme des caractères 8 bits et renvoyé
                comme une liste d'objets str (non-Unicode).
            errors - Comment gérer les erreurs Unicode ; voir help(str.decode)
                pour les options. La valeur par défaut est 'strict'
            retain - Si vrai, conserve les caractères de saut de ligne ; mais tous les
                combinaisons de caractères de saut de ligne ('\\r', '\\n', '\\r\\n') sont
                traduites en '\\n'. Si faux, les caractères de saut de ligne sont
                supprimés. La valeur par défaut est True.
        """
        with self.open('r', encoding=encoding, errors=errors) as f:
            return f.readlines() if retain else [line.rstrip('\\r\\n') for line in f]

    def write_lines(self, lines, encoding=None, errors='strict',
                    linesep=os.linesep, append=False):
        """ Écrit les lignes de texte données dans ce fichier.

        Par défaut, cela écrase tout fichier existant à ce chemin.

        Cela met une séquence de saut de ligne spécifique à la plateforme sur chaque ligne.
        Voir 'linesep' ci-dessous.

        lines - Une liste de chaînes.

        encoding - Un encodage Unicode à utiliser. Cela s'applique uniquement si
            'lines' contient des chaînes Unicode.

        errors - Comment gérer les erreurs dans l'encodage Unicode. Cela
            s'applique également uniquement aux chaînes Unicode.

        linesep - La fin de ligne souhaitée. Cette fin de ligne est
            appliquée à chaque ligne. Si une ligne a déjà une
            fin de ligne standard ('\\r', '\\n', '\\r\\n', u'\\x85',
            u'\\r\\x85', u'\\u2028'), celle-ci sera supprimée et
            celle-ci sera utilisée à la place. La valeur par défaut est os.linesep,
            qui dépend de la plateforme ('\\r\\n' sur Windows, '\\n' sur
            Unix, etc.) Spécifiez None pour écrire les lignes telles quelles,
            comme file.writelines().

        Utilisez l'argument mot-clé append=True pour ajouter des lignes au
        fichier. La valeur par défaut est d'écraser le fichier. Attention :
        Lorsque vous utilisez ceci avec des données Unicode, si l'encodage des
        données existantes dans le fichier est différent de l'encodage
        que vous spécifiez avec le paramètre encoding=, le résultat est
        des données à encodage mixte, ce qui peut vraiment confondre quelqu'un essayant
        de lire le fichier plus tard.
        """
        mode = 'a' if append else 'w'
        with self.open(mode, encoding=encoding, errors=errors, newline=linesep) as f:
            f.writelines(lines)

    def read_md5(self):
        """ Calcule le hachage md5 pour ce fichier.

        Cela lit le fichier entier.
        """
        import hashlib
        m = hashlib.md5()
        with self.open('rb') as f:
            while True:
                d = f.read(8192)
                if not d:
                    break
                m.update(d)
        return m.digest()

    # --- Méthodes pour interroger le système de fichiers.

    exists = os.path.exists
    isdir = os.path.isdir
    isfile = os.path.isfile
    islink = os.path.islink
    ismount = os.path.ismount

    if hasattr(os.path, 'samefile'):
        samefile = os.path.samefile

    getatime = os.path.getatime
    atime = property(
        getatime, None, None,
        """ Heure du dernier accès au fichier. """)

    getmtime = os.path.getmtime
    mtime = property(
        getmtime, None, None,
        """ Heure de la dernière modification du fichier. """)

    if hasattr(os.path, 'getctime'):
        getctime = os.path.getctime
        ctime = property(
            getctime, None, None,
            """ Heure de création du fichier. """)

    getsize = os.path.getsize
    size = property(
        getsize, None, None,
        """ Taille du fichier, en octets. """)

    if hasattr(os, 'access'):
        def access(self, mode):
            """ Renvoie vrai si l'utilisateur actuel a accès à ce chemin.

            mode - Une des constantes os.F_OK, os.R_OK, os.W_OK, os.X_OK
            """
            return os.access(self, mode)

    def stat(self):
        """ Effectue un appel système stat() sur ce chemin. """
        return os.stat(self)

    def lstat(self):
        """ Comme path.stat(), mais ne suit pas les liens symboliques. """
        return os.lstat(self)

    def get_owner(self):
        """ Renvoie le nom du propriétaire de ce fichier ou répertoire.

        Ceci suit les liens symboliques.
        """
        if pwd is None:
            raise NotImplementedError("path.owner n'est pas implémenté sur cette plateforme.")
        st = self.stat()
        return pwd.getpwuid(st.st_uid).pw_name

    owner = property(
        get_owner, None, None,
        """ Nom du propriétaire de ce fichier ou répertoire. """)

    if hasattr(os, 'statvfs'):
        def statvfs(self):
            """ Effectue un appel système statvfs() sur ce chemin. """
            return os.statvfs(self)

    if hasattr(os, 'pathconf'):
        def pathconf(self, name):
            return os.pathconf(self, name)


    # --- Opérations de modification sur les fichiers et répertoires

    def utime(self, times):
        """ Définit les temps d'accès et de modification de ce fichier. """
        os.utime(self, times)

    def chmod(self, mode):
        os.chmod(self, mode)

    if hasattr(os, 'chown'):
        def chown(self, uid, gid):
            os.chown(self, uid, gid)

    def rename(self, new):
        os.rename(self, new)

    def renames(self, new):
        os.renames(self, new)


    # --- Opérations de création/suppression sur les répertoires

    def mkdir(self, mode=0o777):
        os.mkdir(self, mode)

    def makedirs(self, mode=0o777):
        os.makedirs(self, mode)

    def rmdir(self):
        os.rmdir(self)

    def removedirs(self):
        os.removedirs(self)


    # --- Opérations de modification sur les fichiers

    def touch(self):
        """ Définit les temps d'accès/modification de ce fichier à l'heure actuelle.
        Crée le fichier s'il n'existe pas.
        """
        fd = os.open(self, os.O_WRONLY | os.O_CREAT, 0o666)
        os.close(fd)
        os.utime(self, None)

    def remove(self):
        os.remove(self)

    def unlink(self):
        os.unlink(self)


    # --- Liens

    if hasattr(os, 'link'):
        def link(self, newpath):
            """ Crée un lien dur à 'newpath', pointant vers ce fichier. """
            os.link(self, newpath)

    if hasattr(os, 'symlink'):
        def symlink(self, newlink):
            """ Crée un lien symbolique à 'newlink', pointant ici. """
            os.symlink(self, newlink)

    if hasattr(os, 'readlink'):
        def readlink(self):
            """ Renvoie le chemin vers lequel ce lien symbolique pointe.

            Le résultat peut être un chemin absolu ou relatif.
            """
            return self.__class__(os.readlink(self))

        def readlinkabs(self):
            """ Renvoie le chemin vers lequel ce lien symbolique pointe.

            Le résultat est toujours un chemin absolu.
            """
            p = self.readlink()
            if p.isabs():
                return p
            else:
                return (self.parent / p).abspath()


    # --- Fonctions de haut niveau de shutil

    copyfile = shutil.copyfile
    copymode = shutil.copymode
    copystat = shutil.copystat
    copy = shutil.copy
    copy2 = shutil.copy2
    copytree = shutil.copytree
    if hasattr(shutil, 'move'):
        move = shutil.move
    rmtree = shutil.rmtree


    # --- Fonctions spéciales de os

    if hasattr(os, 'chroot'):
        def chroot(self):
            os.chroot(self)

    if hasattr(os, 'startfile'):
        def startfile(self):
            os.startfile(self)


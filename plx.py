#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
plx - Python portability layer extensions

v0.16 2023-05-24 Updated for Python 3 compatibility

This module contains several small useful functions to extend Python features,
especially to improve portability on Windows and Unix.

Project website: http://www.decalage.info/python/plx

License: CeCILL (open-source GPL compatible), see source code for details.
         http://www.cecill.info
"""

__version__ = '0.16'
__date__    = '2023-05-24'
__author__  = 'Philippe Lagadec'


#--- IMPORTS ------------------------------------------------------------------

import os, os.path, sys, urllib.request, urllib.parse, urllib.error, importlib.util, webbrowser, threading, signal
from subprocess import *
try:
    import pwd
except ImportError:
    pass

#--- CONSTANTES ----------------------------------------------------------------

# CONSOLE :
# codec utilisé pour l'affichage console :
CODEC_CONSOLE = 'utf-8'

# POUR POPEN_TIMER :
# Délai par défaut pour un processus lancé par Popen_timer (secondes)
POPEN_TIMEOUT = 60
# Code de sortie pour un processus tué par Popen_timer s'il atteint le délai :
# Sur Unix c'est la valeur du signal SIGKILL (-9) utilisé pour tuer le
# processus (valeur négative) :
EXIT_KILL_PTIMER = -signal.SIGKILL
# Paramètre par défaut pour Popen_Timer :
# Sur Unix ce paramètre n'est pas utilisé :
CF_CREATE_NO_WINDOW = 0


#--- VARIABLES GLOBALES ---------------------------------------------------------


#=== FONCTIONS ================================================================

def unistr(string, errors='strict', default_codec='latin_1'):
    """
    Pour convertir n'importe quelle chaîne (unicode ou str 8 bits) en chaîne Unicode.
    Si string est str, elle sera convertie en utilisant le codec spécifié (Latin-1
    par défaut). Une chaîne unicode est renvoyée inchangée.
    Tout autre objet est converti en utilisant str(object).

    @param string: chaîne ou objet à convertir
    @type  string: str, unicode, ou tout objet
    @param errors: voir la doc Python pour str()
    @type  errors: str
    @return: chaîne convertie
    @rtype: str
    """
    if isinstance(string, str):
        return string
    else:
        return str(string, default_codec, errors)


def str_lat1(string, errors='strict'):
    """
    Pour convertir n'importe quelle chaîne (unicode ou str 8 bits) en chaîne str "Latin-1".
    Si string est str, elle est renvoyée inchangée.
    Tout autre objet est converti en utilisant str(object).

    @param string: chaîne ou objet à convertir
    @type  string: str, unicode, ou tout objet
    @param errors: voir la doc Python pour str()
    @type  errors: str
    @return: chaîne convertie
    @rtype: str
    """
    if isinstance(string, str):
        return string.encode('latin_1', errors)
    elif isinstance(string, bytes):
        return string
    else:
        return str(string)


def str_console(string, errors='strict', initial_encoding='latin_1'):
    """
    Pour convertir n'importe quelle chaîne (unicode ou str 8 bits) en chaîne str avec un
    encodage adapté à l'affichage console ("CP850" sur Windows, "UTF-8" sur Linux
    ou MacOSX, ...).
    Si string est str, elle est d'abord décodée en utilisant initial_encoding ("Latin-1" par
    défaut). Tout autre objet est d'abord converti en utilisant str(object).

    @param string: chaîne ou objet à convertir
    @type  string: str, unicode, ou tout objet
    @param errors: voir la doc Python pour str()
    @type  errors: str
    @return: chaîne convertie
    @rtype: str
    """
    ustring = unistr(string, errors, initial_encoding)
    return ustring.encode(CODEC_CONSOLE, errors)


def print_console(string, errors='strict', initial_encoding='latin_1'):
    """
    Pour afficher n'importe quelle chaîne (unicode ou str 8 bits) sur la console avec un
    encodage adapté ("CP850" sur Windows, "UTF-8" sur Linux ou MacOSX, ...).
    Si string est str, elle est d'abord décodée en utilisant initial_encoding ("Latin-1" par
    défaut). Tout autre objet est d'abord converti en utilisant str(object).

    @param string: chaîne ou objet à convertir
    @type  string: str, unicode, ou tout objet
    @param errors: voir la doc Python pour str()
    @type  errors: str
    @return: chaîne convertie
    @rtype: str
    """
    print(str_console(string, errors, initial_encoding).decode(CODEC_CONSOLE))

def get_username(with_domain=False):
    """
    Renvoie le nom d'utilisateur de l'utilisateur actuellement connecté.
    Fonctionne uniquement sur les systèmes Unix.
    Si with_domain=True, renvoie le nom d'utilisateur sous la forme "utilisateur@machine".
    """
    uid = os.getuid()
    username = pwd.getpwuid(uid)[0]
    if with_domain:
        return f"{username}@{os.uname()[1]}"
    else:
        return username


def main_is_frozen():
    """
    Pour déterminer si le script est lancé depuis l'interpréteur ou s'il
    s'agit d'un exécutable compilé avec py2exe.
    Voir http://www.py2exe.org/index.cgi/HowToDetermineIfRunningFromExe
    """
    return (hasattr(sys, "frozen") # nouveau py2exe
        or hasattr(sys, "importers") # ancien py2exe
        or importlib.util.find_spec("__main__") is not None) # tools/freeze


def get_main_dir():
    """
    Pour déterminer le répertoire où se trouve le script principal.
    Fonctionne s'il est lancé depuis l'interpréteur ou s'il s'agit d'un exécutable
    compilé avec py2exe.
    Voir http://www.py2exe.org/index.cgi/HowToDetermineIfRunningFromExe
    """
    if main_is_frozen():
        # script compilé avec py2exe :
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # sinon le script est sys.argv[0]
        return os.path.dirname(os.path.abspath(sys.argv[0]))


def display_html_file(htmlfile_abspath):
    """
    Fonction pour afficher un fichier HTML local dans le navigateur web par défaut.
    Utilise webbrowser.open() avec une URL de fichier.
    htmlfile_abspath doit être un chemin absolu.
    """
    # Utiliser webbrowser.open avec une URL de fichier :
    file_url = 'file://' + urllib.parse.quote(htmlfile_abspath)
    webbrowser.open(file_url)

def calc_dirsize(dirpath):
    """
    calcule la taille totale de tous les fichiers dans le répertoire et ses sous-répertoires.
    """
    size = 0
    for root, dirs, files in os.walk(dirpath):
        for filename in files:
            size += os.path.getsize(os.path.join(root, filename))
    return size


#------------------------------------------------------------------------------
# KILL_PROCESS
#---------------------
def kill_process(process, log=None):
    """
    Pour tuer un processus lancé par Popen_timer, si le délai est atteint
    (POPEN_TIMEOUT). Cette fonction est appelée par un objet threading.Timer.
    Le processus se termine et renvoie EXIT_KILL_PTIMER comme code d'erreur.

    process: objet processus, tel que créé par Popen.
    log: module de journalisation optionnel pour enregistrer les messages de débogage et d'erreur éventuels.
         (peut être le module de journalisation standard, ou tout objet compatible avec
         les méthodes exception et debug)
    """
    # Toute la sortie du processus est journalisée au niveau debug, MAIS seulement si stdout
    # et stderr ont été définis comme "PIPE" lors de l'appel à Popen_timer :
    if process.stdout and log:
        log.debug("Affichage du processus :")
        log.debug(process.stdout.read())
    if process.stderr and log:
        log.debug(process.stderr.read())
    try:
        os.kill(process.pid, signal.SIGKILL)
        if log:
            log.debug("Processus PID=%d tué." % process.pid)
    except:
        if log:
            # journaliser ou afficher l'exception complète :
            log.exception("Impossible de tuer le processus PID=%d." % process.pid)
        # lever l'exception
        raise


#------------------------------------------------------------------------------
# POPEN_TIMER
#---------------------
def Popen_timer(args, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                creationflags=CF_CREATE_NO_WINDOW,
                timeout=POPEN_TIMEOUT, log=None):
    """
    Pour lancer un processus avec Popen, avec un délai d'attente (voir POPEN_TIMEOUT).
    Si le délai est atteint, le processus est tué et renvoie EXIT_KILL_PTIMER.
    Voir l'aide du module subprocess de la bibliothèque standard Python pour les options de Popen.

    @param args: processus à lancer et arguments (liste ou chaîne)
    @param timeout: temps d'exécution maximum pour le processus
    @param creationflags: paramètres pour CreateProcess sur Windows
    @param log: module de journalisation optionnel pour enregistrer les messages de débogage et d'erreur éventuels.
         (peut être le module de journalisation standard, ou tout objet compatible avec
         les méthodes exception et debug)
    """
    # le processus est lancé avec Popen pour cacher son affichage :
    process = Popen(args, stdin=stdin, stdout=stdout, stderr=stderr,
                    creationflags=creationflags)
    # TODO: gérer l'exception OSError ?
    if log:
        log.debug("Processus lancé, PID = %d" % process.pid)
    # Timer pour tuer le processus si le délai est atteint :
    timer = threading.Timer(timeout, kill_process, args=[process, log])
    timer.start()
    if log:
        log.debug("Timer démarré : %d secondes..." % timeout)
    result_process = process.wait()
    # si le processus s'est terminé avant le délai, le timer est annulé :
    timer.cancel()
    if log:
        log.debug("Code de sortie renvoyé par le processus : %d" % result_process)
    return result_process


def _test_Popen_timer():
    """
    tests pour Popen_timer
    """
    print('Tests pour Popen_timer:')
    print('1) une commande rapide qui se termine normalement avant le délai')
    cmd1 = ['/bin/sh', '-c', 'ls /etc']
    print('cmd1 = ' + repr(cmd1))
    print('Popen_timer (cmd1)...')
    res = Popen_timer(cmd1)
    if res == 0:
        print('OK, code de sortie = 0')
    else:
        print('NOK, code de sortie = %d au lieu de 0' % res)
    print('')

    timeout = 3
    print('2) une commande longue qui atteint le délai (%d s)' % timeout)
    cmd2 = ['/bin/sh', '-c', 'read']
    print('cmd2 = ' + repr(cmd2))
    print('Popen_timer (cmd2, timeout=%d)...' % timeout)
    res = Popen_timer(cmd2, stdin=None, stdout=None, stderr=None,
        timeout=timeout)
    if res == EXIT_KILL_PTIMER:
        print('OK, code de sortie = EXIT_KILL_PTIMER (%d)' % res)
    else:
        print('NOK, code de sortie = %d au lieu de EXIT_KILL_PTIMER (%d)' % (res,
            EXIT_KILL_PTIMER))
    print('')

    # mêmes tests avec la journalisation activée :
    import logging
    logging.basicConfig(level=logging.DEBUG)
    print('3) une commande rapide qui se termine normalement avant le délai + LOG')
    print('cmd1 = ' + repr(cmd1))
    print('Popen_timer (cmd1)...')
    res = Popen_timer(cmd1, log=logging)
    if res == 0:
        print('OK, code de sortie = 0')
    else:
        print('NOK, code de sortie = %d au lieu de 0' % res)
    print('')

    timeout = 3
    print('4) une commande longue qui atteint le délai (%d s)' % timeout)
    print('cmd2 = ' + repr(cmd2))
    print('Popen_timer (cmd2, timeout=%d)...' % timeout)
    res = Popen_timer(cmd2, stdin=None, stdout=None, stderr=None,
        timeout=timeout, log=logging)
    if res == EXIT_KILL_PTIMER:
        print('OK, code de sortie = EXIT_KILL_PTIMER (%d)' % res)
    else:
        print('NOK, code de sortie = %d au lieu de EXIT_KILL_PTIMER (%d)' % (res,
            EXIT_KILL_PTIMER))
    print('')


#=== MAIN =====================================================================

if __name__ == "__main__":
    print(__doc__)
    # Quelques tests :
    print('-'*79)
    print('Tests pour le module "%s" :' % __file__)
    print('-'*79)
    print('')

    print("get_username()                 =", get_username())
    print("get_username(with_domain=True) =", get_username(with_domain=True))
    print('')

    print("main_is_frozen() =", main_is_frozen())
    print("get_main_dir()   =", get_main_dir())
    print('')

    print('Test des fonctions str et console:')
    str_accents = 'éèêëàâäôöùûüç'
    ustr_accents = 'éèêëàâäôöùûüç'
    assert isinstance(unistr(str_accents), str)
    print_console(str_accents)
    print_console(ustr_accents)
    print_console(str_lat1(ustr_accents))
    print_console(unistr(str_accents))
    print_console(unistr(ustr_accents))
    print('')

    # Test Popen_timer:
    _test_Popen_timer()
    print('')

    print("Tests pour display_html_file:")
    filename = 'test_plx.html'
    print("devrait maintenant ouvrir %s dans le navigateur par défaut." % filename)
    try:
        input('Appuyez sur Entrée pour lancer le navigateur... (ou Ctrl+C pour arrêter)')
        with open(filename, 'w') as f:
            f.write('<html><body>Test plx.<b>display_html_file</b></body></html>')
        display_html_file(os.path.abspath(filename))
        os.remove(filename)
    except KeyboardInterrupt:
        print('\narrêté.')
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#=== IMPORTS ==================================================================
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
import sys, socket, struct, time, os, os.path, tempfile, traceback
import xml.etree.ElementTree as ET
import io
import binascii
import threading
import configparser
import ctypes

# path.py module import
try:
    from path import Path as path
except:
    raise ImportError("the path module is not installed:"
        " see http://www.jorendorff.com/articles/python/path/"
        " or http://pypi.python.org/pypi/path.py/ (if first URL is down)")

# XFL - Python module to create and compare file lists in XML
try:
    import xfl
except:
    raise ImportError("the XFL module is not installed:"
        " see http://www.decalage.info/python/xfl")

# plx - portability layer extension
try:
    from plx import str_lat1, print_console
except:
    raise ImportError('the plx module is not installed:'
        ' see http://www.decalage.info/en/python/plx')

# internal modules
from bftp_config import analyse_options
from bftp_utils import debug, str_ajuste, mtime2str, chemin_interdit, augmenter_priorite
from modules.OptionParser_doc import *
import modules.TabBits as TabBits, modules.Console as Console
import modules.TraitEncours as TraitEncours


#=== CONSTANTES ===============================================================

# Network Packet Max size
TAILLE_PAQUET = 65500

RACINE_TEMP = "temp"    # Tempfile root

MAX_NOM_FICHIER = 1024  # Max length for the filename field

HB_DELAY = 10 # Default time between two Heartbeat

# en synchro stricte durée de rétention
# un fichier disparu/effacé sur le guichet bas est effacé coté haut après ce délai
OFFLINEDELAY = 86400*7 # 86400 vaut 1 jour

FORMAT_ENTETE = "!iiQQiiiiQQi"
# Correction bug 557 : taille du format diffère selon les OS
TAILLE_ENTETE = struct.calcsize(FORMAT_ENTETE)

# Types de paquets:
PAQUET_FICHIER      = 0  # File
PAQUET_REPERTOIRE   = 1  # Directory (not yet use)
PAQUET_HEARTBEAT    = 10 # HeartBeat
PAQUET_DELETEFile   = 16 # File Delete

# Complement d'attributs à XFL
ATTR_CRC = "crc" 			            # File CRC
ATTR_NBSEND = "NbSend"		        	# Number of send
ATTR_LASTVIEW = "LastView"	        	# Last View Date
ATTR_LASTSEND = "LastSend"	        	# Last Send Date

#=== Valeurs à traiter au sein du fichier .ini in fine ========================
MinFileRedundancy = 5

#=== VARIABLES GLOBALES =======================================================

# pour stocker les options (cf. analyse_options)
# options parameters
global options
options = None

# dictionnaire des fichiers en cours de réception
# receiving files dictionnary
global fichiers
fichiers = {}

# pour mesurer les stats de reception:

stats = None

#------------------------------------------------------------------------------
# EXIT_AIDE : Display Help in case of error
#-------------------

def exit_aide():
    "Affiche un texte d'aide en cas d'erreur."

    # on affiche la docstring (en début de ce fichier) qui contient l'aide.
    print(__doc__)
    sys.exit(1)


#------------------------------------------------------------------------------
# classe STATS
#-------------------

class Stats:
    """classe permettant de calculer des statistiques sur les transferts."""

    def __init__(self):
        """Constructeur d'objet Stats."""
        self.num_session = -1
        self.num_paquet_attendu = 0
        self.nb_paquets_perdus = 0

    def ajouter_paquet(self, paquet):
        """pour mettre à jour les stats en fonction du paquet."""
        # on vérifie si on est toujours dans la même session, sinon RAZ
        if paquet.num_session != self.num_session:
            self.num_session = paquet.num_session
            self.num_paquet_attendu = 0
            self.nb_paquets_perdus = 0
        # a-t-on perdu des paquets ?
        if paquet.num_paquet_session != self.num_paquet_attendu:
            self.nb_paquets_perdus += paquet.num_paquet_session - self.num_paquet_attendu
        self.num_paquet_attendu = paquet.num_paquet_session + 1

    def taux_perte(self):
        """calcule le taux de paquets perdus, en pourcentage"""
        # num_paquet_attendu correspond au nombre de paquets envoyés de la session
        if self.num_paquet_attendu > 0:
            taux = (100 * self.nb_paquets_perdus) // self.num_paquet_attendu
        else:
            taux = 0
        return taux

    def print_stats(self):
        """affiche les stats"""
        print('Taux de perte: {}%, paquets perdus: {}/{}'.format(self.taux_perte(),
            self.nb_paquets_perdus, self.num_paquet_attendu))

#------------------------------------------------------------------------------
# classe FICHIER
#-------------------
class Fichier:
    """classe représentant un fichier en cours de réception."""

    def __init__(self, paquet):
        """Constructeur d'objet Fichier.

        paquet: objet paquet contenant les infos du fichier."""

        self.nom_fichier = paquet.nom_fichier
        self.date_fichier = paquet.date_fichier
        self.taille_fichier = paquet.taille_fichier
        self.nb_paquets = paquet.nb_paquets
        # chemin du fichier destination
        self.fichier_dest = CHEMIN_DEST / self.nom_fichier
        # on crée le fichier temporaire (objet file):
        self.fichier_temp = tempfile.NamedTemporaryFile(prefix='BFTP_')
        self.paquets_recus = TabBits.TabBits(self.nb_paquets)
        #print('Reception du fichier "{}"...'.format(self.nom_fichier))
        self.est_termine = False    # flag indiquant une réception complète
        self.crc32 = paquet.crc32 # CRC32 du fichier
        self.termine = False  # Nouveau flag pour indiquer si le fichier a été traité complètement

    def annuler_reception(self):
        "pour annuler la réception d'un fichier en cours."
        # on ferme et on supprime le fichier temporaire
        # seulement s'il est effectivement ouvert
        # (sinon à l'initialisation c'est un entier)
        if isinstance(self.fichier_temp, io.IOBase):
            if not self.fichier_temp.closed:
                self.fichier_temp.close()
        # d'après la doc de tempfile, le fichier est automatiquement supprimé
        #os.remove(self.nom_temp)

    def recopier_destination(self):
        logging.info(f"Début de recopier_destination pour {self.nom_fichier}")
        "pour recopier le fichier à destination une fois qu'il est terminé."
        print('OK, fichier termine.')
        logging.info(f'Recopie du fichier "{self.nom_fichier}" vers la destination.')
        
        # créer le chemin destination si besoin avec makedirs
        chemin_dest = self.fichier_dest.dirname()
        if not os.path.exists(chemin_dest):
            chemin_dest.makedirs()
        elif not os.path.isdir(chemin_dest):
            chemin_dest.remove()
            chemin_dest.mkdir()
        
        # recopier le fichier temporaire au bon endroit
        
        try:
            # on revient au début du fichier temporaire
            self.fichier_temp.seek(0)
            
            with open(self.fichier_dest, 'wb') as f_dest:
                # on démarre le calcul de CRC32
                crc32 = 0
                while True:
                    buffer = self.fichier_temp.read(16384)
                    if not buffer:
                        break
                    f_dest.write(buffer)
                    # poursuite du calcul de CRC32
                    crc32 = binascii.crc32(buffer, crc32)
            
            # vérifier si la taille obtenue est correcte
            taille_obtenue = self.fichier_dest.getsize()
            if taille_obtenue != self.taille_fichier:
                logging.error(f"Taille du fichier incorrecte: attendu {self.taille_fichier}, obtenu {taille_obtenue}")
                raise IOError('taille du fichier incorrecte.')
            
            # vérifier si le checksum CRC32 est correct
            logging.info(f"CRC32 calculé: {crc32 & 0xFFFFFFFF:08X}, CRC32 attendu: {self.crc32 & 0xFFFFFFFF:08X}")
            if (crc32 & 0xFFFFFFFF) != (self.crc32 & 0xFFFFFFFF):
                logging.error(f"Contrôle d'intégrité incorrect pour le fichier: {self.nom_fichier}")
                raise IOError("controle d'integrite incorrect.")
            
            # mettre à jour la date de modif: tuple (atime,mtime)
            self.fichier_dest.utime((self.date_fichier, self.date_fichier))
            
            # fermer le fichier temporaire
            self.fichier_temp.close()
            
            # d'après la doc de tempfile, le fichier est automatiquement supprimé
            self.fichier_en_cours = False
            
            # Affichage de fin de traitement
            logging.info(f'Fichier "{self.nom_fichier}" recu en entier, recopie a destination terminée.')
            
            # Marquer le fichier comme terminé
            self.termine = True
            
            # dans ce cas on retire le fichier du dictionnaire
            self.est_termine = True
            del fichiers[self.nom_fichier]
        
        except IOError as e:
            logging.error(f"Erreur lors de la recopie du fichier {self.nom_fichier}: {e}")
            # Vous pouvez ajouter ici d'autres actions à effectuer en cas d'erreur
            raise  # On relève l'exception pour la gestion d'erreur au niveau supérieur
        except Exception as e:
            logging.error(f"Erreur inattendue lors de la recopie du fichier {self.nom_fichier}: {e}")
            raise
        logging.info(f"Fin de recopier_destination pour {self.nom_fichier}")

    def traiter_paquet(self, paquet):
        """Traite un paquet reçu pour ce fichier."""
        logging.info(f"Début du traitement du paquet pour {self.nom_fichier}, offset: {paquet.offset}")
        
        if self.termine:
            logging.info(f"Fichier {self.nom_fichier} déjà terminé, paquet ignoré")
            return
        
        # Vérifier si le paquet est dans les limites du fichier
        if paquet.offset + paquet.taille_donnees > self.taille_fichier:
            logging.error(f"Paquet hors limites pour {self.nom_fichier}: offset {paquet.offset}, taille {paquet.taille_donnees}, taille fichier {self.taille_fichier}")
            return
        
        # Vérifier si le paquet n'a pas déjà été reçu
        if self.paquets_recus.get(paquet.num_paquet):
            logging.info(f"Paquet {paquet.num_paquet} déjà reçu pour {self.nom_fichier}, ignoré")
            return
        
        # Écrire les données du paquet dans le fichier temporaire
        self.fichier_temp.seek(paquet.offset)
        self.fichier_temp.write(paquet.donnees)
        self.fichier_temp.flush()
        
        # Marquer le paquet comme reçu
        self.paquets_recus.set(paquet.num_paquet, True)
        
        logging.info(f"Paquet {paquet.num_paquet} traité pour {self.nom_fichier}, {self.paquets_recus.nb_true} paquets reçus sur {self.nb_paquets}")
        
        # Vérifier si le fichier est complet
        if self.est_complet():
            logging.info(f"Fichier {self.nom_fichier} complet, lancement de la recopie")
            try:
                self.recopier_destination()
            except Exception as e:
                logging.error(f"Erreur lors de la recopie de {self.nom_fichier}: {e}")
                traceback.print_exc()
        else:
            paquets_manquants = self.nb_paquets - self.paquets_recus.nb_true
            logging.info(f"Fichier {self.nom_fichier} incomplet, {paquets_manquants} paquets manquants")

    def est_complet(self):
        """Vérifie si tous les paquets du fichier ont été reçus."""
        return self.paquets_recus.nb_true == self.nb_paquets

#------------------------------------------------------------------------------
# classe PAQUET
#-------------------
class Paquet:
    """classe représentant un paquet BFTP, permettant la construction et le
    décodage du paquet."""

    def test_method(self):
        print("La méthode test_method fonctionne.")

    def __init__(self):
        "Constructeur d'objet Paquet BFTP."
        # on initialise les infos contenues dans l'entête du paquet
        self.type_paquet = PAQUET_FICHIER
        self.longueur_nom = 0
        self.taille_donnees = 0
        self.offset = 0
        self.num_paquet = 0
        self.nom_fichier = ""
        self.nb_paquets = 0
        self.taille_fichier = 0
        self.date_fichier = 0
        self.donnees = b""
        self.fichier_en_cours = ""
        self.num_session = -1
        self.num_paquet_session = -1

    def decoder(self, paquet):
        "Pour décoder un paquet BFTP."
        taille_attendue = struct.calcsize(FORMAT_ENTETE)
        if len(paquet) < taille_attendue:
            raise ValueError(f"Taille du paquet insuffisante : {len(paquet)} octets reçus, {taille_attendue} attendus")
        
        entete = paquet[0:TAILLE_ENTETE]
        (
            self.type_paquet,
            self.longueur_nom,
            self.taille_donnees,
            self.offset,
            self.num_session,
            self.num_paquet_session,
            self.num_paquet,
            self.nb_paquets,
            self.taille_fichier,
            self.date_fichier,
            self.crc32
        ) = struct.unpack(FORMAT_ENTETE, entete)
        if self.type_paquet not in [PAQUET_FICHIER, PAQUET_HEARTBEAT, PAQUET_DELETEFile]:
            raise ValueError('type de paquet incorrect')
        if self.type_paquet == PAQUET_FICHIER:
            if self.longueur_nom > MAX_NOM_FICHIER:
                raise ValueError('nom de fichier trop long')
            if self.offset + self.taille_donnees > self.taille_fichier:
                raise ValueError('offset ou taille des donnees incorrects')
            self.nom_fichier = paquet[TAILLE_ENTETE : TAILLE_ENTETE + self.longueur_nom]
            # conversion en utf-8 pour éviter problèmes dûs aux accents
            self.nom_fichier = self.nom_fichier.decode('utf-8', 'strict')
            if chemin_interdit(self.nom_fichier):
                logging.error('nom de fichier ou de chemin incorrect: {}'.format(self.nom_fichier))
                raise ValueError('nom de fichier ou de chemin incorrect')
            taille_entete_complete = TAILLE_ENTETE + self.longueur_nom
            if self.taille_donnees != len(paquet) - taille_entete_complete:
                raise ValueError('taille de donnees incorrecte')
            self.donnees = paquet[taille_entete_complete:len(paquet)]
            # on mesure les stats, et on les affiche tous les 100 paquets
            stats.ajouter_paquet(self)
            # est-ce que le fichier est en cours de réception ?
            if self.nom_fichier in fichiers:
                f = fichiers[self.nom_fichier]
                # on vérifie si le fichier n'a pas changé:
                if f.date_fichier != self.date_fichier \
                or f.taille_fichier != self.taille_fichier \
                or f.crc32 != self.crc32:
                    # on commence par annuler la réception en cours:
                    f.annuler_reception()
                    del fichiers[self.nom_fichier]
                    # puis on recrée un nouvel objet fichier d'après les infos du paquet:
                    self.nouveau_fichier()
                else:
                    if self.fichier_en_cours != self.nom_fichier:
                        # on change de fichier
                        msg = 'Suite de "{}"...'.format(self.nom_fichier)
                        heure = time.strftime('%d/%m %H:%M ')
                        # Vérifier si un NL est nécessaire ou non
                        Console.Print_temp(msg, NL=True)
                        logging.info(msg)
                        self.fichier_en_cours = self.nom_fichier
                    f.traiter_paquet(self)
            else:
                # est-ce que le fichier existe déjà sur le disque ?
                fichier_dest = CHEMIN_DEST / self.nom_fichier
                # si la date et la taille du fichier n'ont pas changé,
                # inutile de recréer le fichier, on l'ignore:
                if  fichier_dest.exists() \
                and fichier_dest.getsize() == self.taille_fichier \
                and fichier_dest.getmtime() == self.date_fichier:
                    msg = 'Fichier deja recu: {}'.format(self.nom_fichier)
                    Console.Print_temp(msg)
                    sys.stdout.flush()
                else:
                    # sinon on crée un nouvel objet fichier d'après les infos du paquet:
                    self.nouveau_fichier()
        elif self.type_paquet == PAQUET_HEARTBEAT:
            HeartBeat.check_heartbeat(HB_recus, self.num_session, self.num_paquet_session, self.num_paquet)
        elif self.type_paquet == PAQUET_DELETEFile:
            self.nom_fichier = paquet[TAILLE_ENTETE : TAILLE_ENTETE + self.longueur_nom]
            self.nom_fichier = self.nom_fichier.decode('utf-8', 'strict')
            fichier_dest = CHEMIN_DEST / self.nom_fichier
            # Test pour bloquer en présence de caracteres joker ou autres
            if chemin_interdit(self.nom_fichier):
                msg = 'Notification pour effacement suspecte "{}"...'.format(self.nom_fichier)
                Console.Print_temp(msg, NL=True)
                logging.error(msg)
            else:
                msg = 'Effacement de "{}"...'.format(self.nom_fichier)
                if fichier_dest.is_file():
                    try:
                        os.remove(fichier_dest)
                    except OSError:
                        msg = 'Echec effacement de "{}"...'.format(self.nom_fichier)
                        logging.warning(msg)
                    Console.Print_temp(msg, NL=True)
                    # log à supprimer après qualif.
                    logging.info(msg)
                if fichier_dest.is_dir():
                    # TODO Supression de dossier vide à coder coté bas (émission)
                    logging.info("suppression de dossier")
                    try:
                        os.rmdir(fichier_dest)
                    except OSError:
                        msg = 'Echec de effacement de "{}"...'.format(self.nom_fichier)
                        Console.Print_temp(msg, NL=True)
                        logging.warning(msg)

    def nouveau_fichier(self):
        "pour débuter la réception d'un nouveau fichier."
        msg = 'Reception de "{}"...'.format(self.nom_fichier)
        heure = time.strftime('%d/%m %H:%M ')
        #msg = str_ajuste(msg)+'\r'
        #print_oem(heure + msg)
        Console.Print_temp(msg, NL=True)
        logging.info(msg)
        self.fichier_en_cours = self.nom_fichier
        # on crée un nouvel objet fichier d'après les infos du paquet:
        nouveau_fichier = Fichier(self)
        fichiers[self.nom_fichier] = nouveau_fichier
        nouveau_fichier.traiter_paquet(self)

    def construire(self):
        "pour construire un paquet BFTP à partir des paramètres. (non implémenté)"
        raise NotImplementedError

print("Contenu de la classe Paquet:")
print(Paquet.__dict__)





#------------------------------------------------------------------------------
# HeartBeat - dépendant de la classe de paquet
#---------------
class HeartBeat:
    """ Generate and check HeartBeat BFTP packet

        A session is a heartbeat sequence.
        A heartbeat is a simple packet with a timestamp (Session Id + sequence
        number) to identify if the link (physical and logical) is up or down

        The session Id will identify a restart
        The sequence number will identify lost paquet

        Because time synchronisation betwen emission/reception computer isn't garantee,
        timestamp can't be check in absolute.
        """

    # TODO :
    # Add HB from reception to emission in broadcast to detect bi-directional link

    def __init__(self):
        #Variables locales
        self.hb_delay=HB_DELAY
        self.hb_numsession=0
        self.hb_numpaquet=0
        self.hb_timeout=time.time()+1.25*(self.hb_delay)

    def newsession(self):
        """ initiate values for a new session """
        self.hb_numsession=int(time.time())
        self.hb_numpaquet=0
        return(self.hb_numsession, self.hb_numpaquet)

    def incsession(self):
        """ increment values in a existing session """
        self.hb_numpaquet+=1
        self.hb_timeout=time.time()+(self.hb_delay)
        return(self.hb_numpaquet, self.hb_timeout)

    def print_heartbeat(self):
        """ Print internal values of heartbeat """
        print("----- Current HeartBeart -----")
        print("Session ID      : {} ".format(self.hb_numsession))
        print("Seq             : {} ".format(self.hb_numpaquet))
        print("Delay           : {} ".format(self.hb_delay))
        print("Current Session : {} ".format(mtime2str(self.hb_numsession)))
        print("Next Timeout    : {} ".format(mtime2str(self.hb_timeout)))
        print("----- ------------------ -----")

    def check_heartbeat(self, num_session, num_paquet, delay):
        """ Check and diagnostic last received heartbeat paquet """
        msg=None
        #self.print_heartbeat()
        # new session identification (session restart)
        if self.hb_numsession != num_session:
                if num_paquet==0 :
                    msg = 'HeartBeat : emission redemarree'
                    logging.info(msg)
                # lost packet in a new session (reception start was too late)
                else:
                    # TODO : vérifier cas du redemarrage de la reception (valeurs locales à 0)
                    if (self.hb_numpaquet==0 and self.hb_numsession==0):
                        msg = 'HeartBeat : reception redemaree'
                        logging.info(msg)
                    else:
                        msg = 'HeartBeat : emission redemaree, perte de {} paquet(s)'.format(num_paquet)
                        logging.warning(msg)
                # Set correct num_session
                self.hb_numsession=num_session
        # lost packet identification
        else:
            hb_lost=num_paquet-self.hb_numpaquet-1
            if bool(hb_lost) :
                msg = 'HeartBeat : perte de {} paquet(s)'.format(hb_lost)
                logging.warning(msg)
        # Set new values
        self.hb_numpaquet=num_paquet
        self.hb_timeout=time.time()+1.5*(delay)
        if msg != None:
            Console.Print_temp(msg, NL=True)
            sys.stdout.flush()


    def checktimer_heartbeat(self):
        "Timer to send alarm if no heartbeat are received"
        #self.print_heartbeat()
        Nbretard=0
        while True:
            if self.hb_timeout < time.time():
                Nbretard+=1
                delta=time.time()-self.hb_timeout
                msg = 'HeartBeat : Reception en attente ( {} ) '.format(self.hb_numpaquet)
                Console.Print_temp(msg, NL=False)
                sys.stdout.flush()
                time.sleep(self.hb_delay-1)
                if Nbretard%10==0:
                    msg = 'HeartBeat : Retard de reception ( {} ) - {} '.format(self.hb_numpaquet, Nbretard//10)
                    logging.warning(msg)
                    Console.Print_temp(msg, NL=True)
            else:
                Nbretard=0
            time.sleep(1)

    def Th_checktimeout_heartbeatT(self):
        """ thead to send heartbeat """
        Sendheartbeat=threading.Thread(target=self.checktimer_heartbeat)
        Sendheartbeat.start()


    def send_heartbeat(self, message=None, num_session=None, num_paquet=None):
        """ Send a heartbeat packet """
        # un HeartBeat est un paquet court donnant un timestamp qui pourra être vérifié à la réception
        # on donne un numero de session afin de tracer coté haut une relance du guichet bas
        # num paquet permet de tracer les iterations au sein d'une session

        # Affectation statique pour tests et qualification du mod
        if num_session is None:
            num_session = self.hb_numsession
        if num_paquet is None:
            num_paquet = self.hb_numpaquet
        if message is None:
            message = "HeartBeat"
        taille_donnees = len(message)
        #self.print_heartbeat()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # on commence par packer l'entete:
        entete = struct.pack(FORMAT_ENTETE,
            PAQUET_HEARTBEAT,
            0,
            taille_donnees,
            0,
            num_session,
            num_paquet,
            self.hb_delay,
            1,
            0,
            0,
            0
            )
        paquet = entete + message.encode('utf-8')
        s.sendto(paquet, (HOST, PORT))
        s.close()

    def envoyer_Boucleheartbeat(self):
        """A loop to send heartbeat sequence every X seconds"""
        self.newsession()
        while True:
            self.send_heartbeat()
            self.incsession()
            time.sleep(self.hb_delay)


    def Th_envoyer_BoucleheartbeatT(self):
        """ thead to send heartbeat """
        Sendheartbeat = threading.Thread(target=self.envoyer_Boucleheartbeat)
        Sendheartbeat.start()

#------------------------------------------------------------------------------
# LimiteurDebit
#-------------------

class LimiteurDebit:
    "pour controler le débit d'envoi de données."

    def __init__(self, debit):
        """contructeur de classe LimiteurDebit.

        debit : débit maximum autorisé, en Kbps."""
        # débit en Kbps converti en octets/s
        self.debit_max = debit*1000/8
        # on stocke le temps de départ
        self.temps_debut = time.time()
        # nombre d'octets déjà transférés
        self.octets_envoyes = 0

    def depart_chrono(self):
        "pour (re)démarrer la mesure du débit."
        self.temps_debut = time.time()
        self.octets_envoyes = 0

    def ajouter_donnees(self, octets):
        "pour ajouter un nombre d'octets envoyés."
        self.octets_envoyes += octets

    def temps_total(self):
        "donne le temps total de mesure."
        return (time.time() - self.temps_debut)

    def debit_moyen(self):
        "donne le débit moyen mesuré, en octets/s."
        temps_total = self.temps_total()
        if temps_total == 0: return 0   # pour éviter division par zéro
        debit_moyen = self.octets_envoyes / temps_total
        return debit_moyen

    def limiter_debit(self):
        "pour faire une pause afin de respecter le débit maximum."
        # on fait des petites pauses (10 ms) tant que le débit est trop élevé:
        while self.debit_moyen() > self.debit_max:
            time.sleep(0.01)
        # méthode alternative qui ne fonctionne pas très bien
        # (donne souvent des temps de pause négatifs !)
#       temps_total = self.temps_total()
#       debit_moyen = self.debit_moyen()
#       # si on dépasse le débit max, on calcule la pause:
#       if debit_moyen > self.debit_max:
#           pause = self.octets_envoyes/self.debit_max - temps_total
#           if pause>0:
#               time.sleep(pause)


#------------------------------------------------------------------------------
# RECEVOIR
#-------------------
def recevoir(repertoire):
    """Pour recevoir les paquets UDP BFTP contenant les fichiers, et stocker
    les fichiers reçus dans le répertoire indiqué en paramètre."""

    global CHEMIN_DEST
    CHEMIN_DEST = path(repertoire)
    logging.info(f"Démarrage de la réception dans le répertoire : {CHEMIN_DEST}")
    print(f'Les fichiers seront recus dans le repertoire "{str_lat1(CHEMIN_DEST.abspath(),errors="replace")}".')
    print(f'En ecoute sur le port UDP {PORT}...')
    print('(taper Ctrl+Pause pour quitter)')
    p = Paquet()
    print(f"Type de p: {type(p)}")
    print(f"Méthodes de p: {dir(p)}")
    try:
        p.test_method()
    except AttributeError:
        print("La méthode test_method n'existe pas.")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    while True:
        try:
            paquet, emetteur = s.recvfrom(TAILLE_PAQUET)
            logging.info(f"Paquet reçu de {emetteur}")
            if not paquet: 
                continue
            if len(paquet) < struct.calcsize(FORMAT_ENTETE):
                msg = f"Paquet trop petit reçu de {emetteur}: {len(paquet)} octets"
                print(msg)
                logging.warning(msg)
                continue
            try:
                p.decoder(paquet)
                logging.info(f"Type de paquet reçu : {p.type_paquet}")
                if p.type_paquet == PAQUET_FICHIER:
                    print(f"Fichier reçu : {p.nom_fichier}")
                    logging.info(f"Traitement du paquet fichier : {p.nom_fichier}")
                    if p.nom_fichier in fichiers:
                        f = fichiers[p.nom_fichier]
                    else:
                        f = Fichier(p)
                        fichiers[p.nom_fichier] = f
                    f.traiter_paquet(p)
                elif p.type_paquet == PAQUET_HEARTBEAT:
                    print("Paquet heartbeat reçu")
                    logging.info("Paquet heartbeat reçu")
                    HeartBeat.check_heartbeat(HB_recus, p.num_session, p.num_paquet_session, p.num_paquet)
                elif p.type_paquet == PAQUET_DELETEFile:
                    print("Paquet de suppression reçu")
                    logging.info(f"Paquet de suppression reçu pour : {p.nom_fichier}")
                    # Traitement du paquet de suppression
                    fichier_dest = CHEMIN_DEST / p.nom_fichier
                    if fichier_dest.exists():
                        try:
                            if fichier_dest.is_file():
                                os.remove(fichier_dest)
                            elif fichier_dest.is_dir():
                                os.rmdir(fichier_dest)
                            logging.info(f"Fichier/dossier supprimé : {p.nom_fichier}")
                        except OSError as e:
                            logging.error(f"Erreur lors de la suppression de {p.nom_fichier}: {e}")
                    else:
                        logging.warning(f"Fichier/dossier à supprimer non trouvé : {p.nom_fichier}")
                else:
                    print(f"Type de paquet inconnu : {p.type_paquet}")
                    logging.warning(f"Type de paquet inconnu reçu : {p.type_paquet}")
            except struct.error as e:
                msg = f"Erreur lors du décodage d'un paquet: {e}"
                print(msg)
                logging.error(msg)
                continue
            except ValueError as e:
                msg = f"Erreur de valeur lors du décodage d'un paquet: {e}"
                print(msg)
                logging.error(msg)
                continue
            except AttributeError as e:
                msg = f"Erreur d'attribut lors du décodage d'un paquet: {e}"
                print(msg)
                logging.error(msg)
                print(f"Type de p lors de l'erreur: {type(p)}")
                print(f"Méthodes de p lors de l'erreur: {dir(p)}")
                continue
            except Exception as e:
                msg = f"Erreur inattendue lors du décodage d'un paquet: {e}"
                print(msg)
                traceback.print_exc()
                logging.error(msg)
                continue
        except socket.error as e:
            msg = f"Erreur de socket: {e}"
            print(msg)
            logging.error(msg)
        except Exception as e:
            msg = f"Erreur inattendue dans la boucle principale: {e}"
            print(msg)
            traceback.print_exc()
            logging.error(msg)
            logging.debug(f"Traceback: {traceback.format_exc()}")

    s.close()


#------------------------------------------------------------------------------
# CalcCRC
#-------------------
def CalcCRC(fichier):
    """Calcul du CRC32 du fichier."""

    debug(f'Calcul de CRC32 pour "{fichier}"...')
    MonAff = TraitEncours.TraitEnCours()
    MonAff.StartIte()
    chaine = f" Calcul CRC32 {fichier}"
    MonAff.NewChaine(chaine, truncate=True)
    try:
        with open(fichier, 'rb') as f:
            buffer = f.read(16384)
            # on démarre le calcul de CRC32:
            crc32 = binascii.crc32(buffer)
            while buffer:
                buffer = f.read(16384)
                # poursuite du calcul de CRC32:
                crc32 = binascii.crc32(buffer, crc32)
                MonAff.AffLigneBlink()
        debug(f"CRC32 = {crc32:08X}")
    except IOError:
        #print "Erreur : CRC32 Ouverture impossible de %s" %fichier
        crc32 = 0
    return crc32

#------------------------------------------------------------------------------
# SendDeleteFileMessage
#-------------------
def SendDeleteFileMessage(fichier):
    """ Emet un message de suppression du fichier coté haut
    """
    # Doit on ajouter des éléments de Dref (taille/date) pour consolider l'ordre à la reception ?
    debug("Sending DeleteFileMessage...")
    nom_fichier = str(fichier).encode('utf-8')
    taille = len(nom_fichier)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # on commence par packer l'entete:
    entete = struct.pack(
        FORMAT_ENTETE,
        PAQUET_DELETEFile,
        taille,
        taille,
        0,
        0,
        0,
        0,
        1,
        0,
        0,
        0
        )
    paquet = entete + nom_fichier
    s.sendto(paquet, (HOST, PORT))
    s.close()

#------------------------------------------------------------------------------
# ENVOYER
#-------------------

def envoyer(fichier_source, fichier_dest, limiteur_debit=None, num_session=None,
    num_paquet_session=None, crc=None):
    """Pour émettre un fichier en paquets UDP BFTP.

    fichier_source : chemin du fichier source sur le disque local
    fichier_dest   : chemin relatif du fichier dans le répertoire destination
    limiteur_debit : pour limiter le débit d'envoi
    num_session    : numéro de session
    num_paquet_session : compteur de paquets
    """

    msg = f"Envoi du fichier {fichier_source}..."
    Console.Print_temp(msg, NL=True)
    logging.info(msg)
    if num_session is None:
        num_session = int(time.time())
        num_paquet_session = 0
    debug(f"num_session         = {num_session}")
    debug(f"num_paquet_session  = {num_paquet_session}")
    debug(f"fichier destination = {fichier_dest}")
    nom_fichier_dest = str(fichier_dest).encode('utf-8')
    longueur_nom = len(nom_fichier_dest)
    debug(f"longueur_nom = {longueur_nom}")
    if longueur_nom > MAX_NOM_FICHIER:
        raise ValueError
    if os.path.isfile(str(fichier_source)):
        taille_fichier = os.path.getsize(str(fichier_source))
        date_fichier = int(os.path.getmtime(str(fichier_source)))
        debug(f"taille_fichier = {taille_fichier}")
        debug(f"date_fichier = {mtime2str(date_fichier)}")
        # calcul de CRC32
        if crc is None:
            crc32 = CalcCRC(str(fichier_source))
        else:
            crc32 = crc
    else:
        raise FileNotFoundError(f"Le fichier source {fichier_source} n'existe pas ou n'est pas un fichier.")
    # taille restant pour les données dans un paquet normal
    taille_donnees_max = TAILLE_PAQUET - TAILLE_ENTETE - longueur_nom
    debug(f"taille_donnees_max = {taille_donnees_max}")
    nb_paquets = (taille_fichier + taille_donnees_max - 1) // taille_donnees_max
    if nb_paquets == 0:
        # si le fichier est vide, il faut quand même envoyer un paquet
        nb_paquets = 1
    debug(f"nb_paquets = {nb_paquets}")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reste_a_envoyer = taille_fichier
    try:
        with open(str(fichier_source), 'rb') as f:
            if limiteur_debit is None:
                # si aucun limiteur fourni, on en initialise un:
                limiteur_debit = LimiteurDebit(options.debit)
            limiteur_debit.depart_chrono()
            for num_paquet in range(nb_paquets):
                # on fait une pause si besoin pour limiter le débit
                limiteur_debit.limiter_debit()
                if reste_a_envoyer > taille_donnees_max:
                    taille_donnees = taille_donnees_max
                else:
                    taille_donnees = reste_a_envoyer
                reste_a_envoyer -= taille_donnees
                offset = f.tell()
                donnees = f.read(taille_donnees)
                
                # Conversion explicite de tous les arguments
                paquet_fichier = ctypes.c_int(int(PAQUET_FICHIER)).value
                longueur_nom = ctypes.c_int(int(longueur_nom)).value
                taille_donnees = ctypes.c_int(int(taille_donnees)).value
                offset = ctypes.c_uint64(int(offset)).value
                num_session = ctypes.c_uint64(int(num_session)).value
                num_paquet_session = ctypes.c_int(int(num_paquet_session)).value
                num_paquet = ctypes.c_int(int(num_paquet)).value
                nb_paquets = ctypes.c_int(int(nb_paquets)).value
                taille_fichier = ctypes.c_uint64(int(taille_fichier)).value
                date_fichier = ctypes.c_uint64(int(date_fichier)).value
                crc32 = ctypes.c_int(int(crc32)).value

                # Conversion en entiers non signés 64 bits si nécessaire
                if offset > 2**31 - 1:
                    offset = ctypes.c_uint64(offset).value
                if taille_fichier > 2**31 - 1:
                    taille_fichier = ctypes.c_uint64(taille_fichier).value
                if date_fichier > 2**31 - 1:
                    date_fichier = ctypes.c_uint64(date_fichier).value

                # Affichage des valeurs pour le débogage
                debug(f"FORMAT_ENTETE: {FORMAT_ENTETE}")
                debug(f"paquet_fichier: {paquet_fichier} ({type(paquet_fichier)})")
                debug(f"longueur_nom: {longueur_nom} ({type(longueur_nom)})")
                debug(f"taille_donnees: {taille_donnees} ({type(taille_donnees)})")
                debug(f"offset: {offset} ({type(offset)})")
                debug(f"num_session: {num_session} ({type(num_session)})")
                debug(f"num_paquet_session: {num_paquet_session} ({type(num_paquet_session)})")
                debug(f"num_paquet: {num_paquet} ({type(num_paquet)})")
                debug(f"nb_paquets: {nb_paquets} ({type(nb_paquets)})")
                debug(f"taille_fichier: {taille_fichier} ({type(taille_fichier)})")
                debug(f"date_fichier: {date_fichier} ({type(date_fichier)})")
                debug(f"crc32: {crc32} ({type(crc32)})")

                # Vérification des limites pour les entiers signés 32 bits
                for name, value in [('paquet_fichier', paquet_fichier), ('longueur_nom', longueur_nom), 
                                    ('taille_donnees', taille_donnees), ('num_paquet_session', num_paquet_session), 
                                    ('num_paquet', num_paquet), ('nb_paquets', nb_paquets), ('crc32', crc32)]:
                    if not (-2147483648 <= value <= 2147483647):
                        raise ValueError(f"{name} ({value}) est en dehors des limites d'un entier signé 32 bits")

                # Appel à struct.pack avec les valeurs converties
                entete = struct.pack(
                    FORMAT_ENTETE,
                    paquet_fichier,
                    longueur_nom,
                    taille_donnees,
                    offset,
                    num_session,
                    num_paquet_session,
                    num_paquet,
                    nb_paquets,
                    taille_fichier,
                    date_fichier,
                    crc32
                )
                print(f"Type de paquet envoyé : {PAQUET_FICHIER}")
                paquet = entete + nom_fichier_dest + donnees
                s.sendto(paquet, (HOST, PORT))
                num_paquet_session += 1
                limiteur_debit.ajouter_donnees(len(paquet))
                #debug("debit moyen = %d" % limiteur_debit.debit_moyen())
                #time.sleep(0.3)
                pourcent = 100*(num_paquet+1)/nb_paquets
                # affichage du pourcentage: la virgule évite un retour chariot
                print(f"{pourcent:.0f}%\r", end='', flush=True)
        print(f"transfert en {limiteur_debit.temps_total():.3f} secondes - debit moyen {limiteur_debit.debit_moyen()*8/1000:.0f} Kbps")
    except IOError:
        msg = f"Ouverture du fichier {fichier_source}..."
        print("Erreur : " + msg)
        logging.error(msg)
        num_paquet_session = -1
    s.close()
    return num_paquet_session


#------------------------------------------------------------------------------
# SortDictBy
#-----------------
def sortDictBy(nslist, key):
    """
    Tri d'un dictionnaire sur un champ
    """
    return sorted(nslist, key=lambda x: x[key])

#------------------------------------------------------------------------------
# SYNCHRO_ARBO
#-------------------
def synchro_arbo(repertoire):
    """
    Synchroniser une arborescence en envoyant regulierement tous les
    fichiers.
    """
    XFLFile_id = None
    logging.info(f'Synchronisation du repertoire "{str_lat1(repertoire, errors="replace")}"')

    # on utilise un objet LimiteurDebit global pour tout le transfert:
    limiteur_debit = LimiteurDebit(options.debit)

    # TODO : Distinguer le traitement d'une arborescence locale / distante
    if (0):
        logging.info("Traitement d'une arborescence locale")
        # TODO : Traitement Local des donnnées :
        #            - utiliser wath_directory pour détecter le besoin l'émission
    else:
        logging.info("Traitement d'une arborescence distante")
        # Traitement distant des donnnées :
        #     Boucle 1 : Analyse et priorisation des fichiers
        AllFileSendMax = False
        # test pour affichage d'un motif cyclique
        monaff = TraitEncours.TraitEnCours()
        monaff.StartIte()
        iteration_count = 0
        while not AllFileSendMax and (options.boucle is None or iteration_count < options.boucle):
            iteration_count += 1
            logging.info(f"Début de l'itération {iteration_count}")
            logging.info(f"{mtime2str(time.time())} - Scrutation arborescence")
            Dscrutation = xfl.DirTree()
            if MODE_DEBUG:
                Dscrutation.read_disk(repertoire, xfl.callback_dir_print)
            else:
                Dscrutation.read_disk(repertoire, None, monaff.AffCar)
            logging.info(f"{mtime2str(time.time())} - Analyse arborescence")
            same, different, only1, only2 = xfl.compare_DT(Dscrutation, DRef)
            logging.info(f"{mtime2str(time.time())} - Traitement des fichiers supprimes")
            logging.debug("\n========== Supprimes ========== ")
            for f in sorted(only2, reverse=True):
                logging.debug(f"S  {f}")
                monaff.AffCar()
                DeletionNeeded=False
                parent, myfile=f.splitpath()
                if(DRef.dict[f].tag == xfl.TAG_DIR):
                    # Vérifier la présence de fils (dir / file)
                    if not(bool(DRef.dict[f].getchildren())): DeletionNeeded=True
                if(DRef.dict[f].tag == xfl.TAG_FILE):
                    LastView=DRef.dict[f].get(ATTR_LASTVIEW)
                    NbSend=DRef.dict[f].get(ATTR_NBSEND)
                    if LastView == None: LastView=0
                    # Si Disparu depuis X jours ; on notifie la suppression
                    if (time.time() - (float(LastView) + OffLineDelay)) > 0:
                        if (NbSend == None): NbSend=-10
                        else:
                            if (NbSend >= 0):
                                NbSend=-1
                        for attr in (ATTR_LASTSEND, ATTR_CRC):
                            DRef.dict[f].set(attr, str(0))
                        if options.synchro_arbo_stricte:
                            SendDeleteFileMessage(f)
                        NbSend-=1
                        if NbSend > -10:
                            DRef.dict[f].set(ATTR_NBSEND, str(NbSend))
                        else:
                            DeletionNeeded=True
                if DeletionNeeded:
                    logging.debug("****** Suppression")
                    if parent == '':
                        DRef.et.remove(DRef.dict[f])
                    else:
                        DRef.dict[parent].remove(DRef.dict[f])
            logging.info(f"{mtime2str(time.time())} - Traitement des nouveaux fichiers")
            logging.debug("\n========== Nouveaux  ========== ")
            RefreshDictNeeded=False
            for f in sorted(only1):
                monaff.AffCar()
                logging.debug(f"N  {f}")
                parent, myfile=f.splitpath()
                index=0
                if parent == '':
                    newET = ET.SubElement(DRef.et, Dscrutation.dict[f].tag)
                    index=len(DRef.et)-1
                    if (Dscrutation.dict[f].tag == xfl.TAG_FILE):
                        RefreshDictNeeded=True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            DRef.et[index].set(attr, Dscrutation.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            DRef.et[index].set(attr, str(0))
                        DRef.et[index].set(ATTR_LASTVIEW, Dscrutation.et.get(xfl.ATTR_TIME))
                    else:
                        DRef.et[index].set(xfl.ATTR_NAME, Dscrutation.dict[f].get(xfl.ATTR_NAME))
                else:
                    newET = ET.SubElement(DRef.dict[parent], Dscrutation.dict[f].tag)
                    index=len(DRef.dict[parent])-1
                    if (Dscrutation.dict[f].tag == xfl.TAG_FILE):
                        RefreshDictNeeded=True
                        for attr in (xfl.ATTR_NAME, xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                            DRef.dict[parent][index].set(attr, Dscrutation.dict[f].get(attr))
                        for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                            DRef.dict[parent][index].set(attr, str(0))
                        DRef.dict[parent][index].set(ATTR_LASTVIEW, (Dscrutation.et.get(xfl.ATTR_TIME)))
                    else:
                        DRef.dict[parent][index].set(xfl.ATTR_NAME, Dscrutation.dict[f].get(xfl.ATTR_NAME))
                if (Dscrutation.dict[f].tag == xfl.TAG_DIR):
                    DRef.pathdict()
                    RefreshDict=False
            if RefreshDictNeeded:
                DRef.pathdict()
            logging.info(f"{mtime2str(time.time())} - Traitement des fichiers modifies")
            logging.debug("\n========== Differents  ========== ")
            for f in different:
                monaff.AffCar()
                logging.debug(f"D  {f}")
                if (Dscrutation.dict[f].tag == xfl.TAG_FILE):
                    for attr in (xfl.ATTR_MTIME, xfl.ATTR_SIZE):
                        DRef.dict[f].set(attr, Dscrutation.dict[f].get(attr))
                    for attr in (ATTR_LASTSEND, ATTR_CRC, ATTR_NBSEND):
                        DRef.dict[f].set(attr, str(0))
                    DRef.dict[f].set(ATTR_LASTVIEW, (Dscrutation.et.get(xfl.ATTR_TIME)))
            logging.info(f"{mtime2str(time.time())} - Traitement des fichiers identiques")
            logging.debug("\n========== Identiques ========== ")
            for f in same:
                monaff.AffCar()
                logging.debug(f"I  {f}")
                if (Dscrutation.dict[f].tag == xfl.TAG_FILE):
                    DRef.dict[f].set(ATTR_LASTVIEW, (Dscrutation.et.get(xfl.ATTR_TIME)))
            logging.info(f"{mtime2str(time.time())} - Sauvegarde du fichier de reprise")
            DRef.et.set(xfl.ATTR_TIME, str(time.time()))
            if XFLFile == "BFTPsynchro.xml":
                if os.path.isfile(XFLFile):
                    try:
                        os.rename(XFLFile,XFLFileBak)
                    except:
                        os.remove(XFLFileBak)
                        os.rename(XFLFile,XFLFileBak)
            DRef.write_file(XFLFile)
            logging.info(f"{mtime2str(time.time())} - Selection des fichiers les moins emis")
            FileToSend=[]
            for f in DRef.dict:
                if (DRef.dict[f].tag == xfl.TAG_FILE):
                    nbsend = DRef.dict[f].get(ATTR_NBSEND)
                    FileToSend.append({'file':f, 'iteration':int(nbsend) if nbsend is not None else 0})
            logging.info(f"{mtime2str(time.time())} - Selection des fichiers a emettre")
            FileToSend=sortDictBy(FileToSend, 'iteration')
            logging.info(f"Nombre de fichiers a synchroniser : {len(FileToSend)}")
            if len(FileToSend)==0:
                AllFileSendMax=True
            boucleemission = LimiteurDebit(options.debit)
            boucleemission.depart_chrono()
            logging.info(f"{mtime2str(time.time())} - Emission des donnees")
            TransmitDelay=max(300, time.time()-float(Dscrutation.et.get(xfl.ATTR_TIME)))
            FileLessRedundancy=0
            LastFileSendMax=False
            while (boucleemission.temps_total() < TransmitDelay*4) and (not LastFileSendMax):
                if len(FileToSend)!=0:
                    item=FileToSend.pop(0)
                    f=item['file']
                    i=item['iteration']
                    logging.debug(f"Iteration: {i}")
                    separator = '/'
                    fullpathfichier = repertoire + separator + f
                    if fullpathfichier.isfile():
                        stable=(fullpathfichier.getmtime()==float(DRef.dict[f].get(xfl.ATTR_MTIME)) and \
                            fullpathfichier.getsize()==int(DRef.dict[f].get(xfl.ATTR_SIZE)))
                        if not stable:
                            DRef.dict[f].set(ATTR_CRC,'0')
                            DRef.dict[f].set(ATTR_NBSEND,'0')
                        if (stable or fullpathfichier.getsize()<1024 or f=="BFTPsynchro.xml"):
                            crc_value = DRef.dict[f].get(ATTR_CRC)
                            if crc_value is None or crc_value == '0':
                                current_CRC = str(CalcCRC(fullpathfichier))
                                DRef.dict[f].set(ATTR_CRC, current_CRC)
                                crc_value = current_CRC
                            if (envoyer(fullpathfichier, f, limiteur_debit, crc=int(crc_value)) != -1):
                                DRef.dict[f].set(ATTR_LASTSEND, str(time.time()))
                                DRef.dict[f].set(ATTR_NBSEND, str(int(DRef.dict[f].get(ATTR_NBSEND) or 0) + 1))
                                if int(DRef.dict[f].get(ATTR_NBSEND) or 0) > MinFileRedundancy:
                                    LastFileSendMax=True
                                    if (FileLessRedundancy == 0): AllFileSendMax=True
                                else:
                                    FileLessRedundancy+=1
                else:
                    LastFileSendMax=True
                    if options.boucle:
                        attente=options.pause-boucleemission.temps_total()
                        if attente > 0:
                            logging.info(f"{mtime2str(time.time())} - Attente avant nouvelle scrutation")
                            time.sleep(attente)
            logging.info(f"{mtime2str(time.time())} - Sauvegarde du fichier de reprise")
            DRef.et.set(xfl.ATTR_TIME, str(time.time()))
            if XFLFile == "BFTPsynchro.xml":
                if os.path.isfile(XFLFile):
                    try:
                        os.rename(XFLFile,XFLFileBak)
                    except:
                        os.remove(XFLFileBak)
                        os.rename(XFLFile,XFLFileBak)
            DRef.write_file(XFLFile)
            
            if options.boucle is not None:
                if iteration_count >= options.boucle:
                    logging.info(f"Nombre maximum d'itérations atteint ({options.boucle}). Arrêt de la synchronisation.")
                    break
                else:
                    logging.info(f"Fin de l'itération {iteration_count}. Attente de {options.pause} secondes avant la prochaine itération.")
                    time.sleep(options.pause)

        if XFLFile_id is not None and XFLFile_id != False:
            try:
                debug(f"Suppression du fichier de reprise temporaire : {XFLFile}")
                os.close(XFLFile_id)
                os.remove(XFLFile)
            except OSError as e:
                logging.warning(f"Erreur lors de la fermeture/suppression du fichier temporaire : {e}")

        return iteration_count > 0  # Retourne True si au moins une itération a été effectuée

#==============================================================================
# PROGRAMME PRINCIPAL
#=====================
if __name__ == '__main__':
    try:
        os.stat_float_times(False)
    except AttributeError:
        # Cette fonction n'existe plus dans les versions récentes de Python
        # Les temps sont maintenant toujours retournés en nombre flottant
        pass

    (options, args) = analyse_options()
    cible = path(args[0])
    HOST = options.adresse
    PORT = options.port_UDP
    MODE_DEBUG = options.debug
    # pour mesurer les stats de reception:
    stats = Stats()

    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(levelname)-8s %(message)s',
                datefmt='%d/%m/%Y %H:%M:%S',
                filename='bftp.log',
                filemode='a')
    logging.info("Demarrage de BlindFTP")

    # Emission de messages heartbeat
    HB_emis=HeartBeat()
    HB_recus=HeartBeat()
    if not(options.recevoir):
        HB_emis.Th_envoyer_BoucleheartbeatT()

    if options.envoi_fichier:
        envoyer(cible, cible.name)
    elif (options.synchro_arbo or options.synchro_arbo_stricte):
        # Délais pour considérer un fichier "hors ligne" comme définitivement effacé
        OffLineDelay=OFFLINEDELAY
        # Fichier référence de l'arborescence synchronisée
        # TODO : Nom du fichier transmis en paramètre
        print("Lecture/contruction du fichier de reprise")
        XFLFile_id=False
        working=TraitEncours.TraitEnCours()
        working.StartIte()
        if options.reprise:
            XFLFile="BFTPsynchro.xml"
            XFLFileBak="BFTPsynchro.bak"
        else:
            XFLFile_id,XFLFile=tempfile.mkstemp(prefix='BFTP_',suffix='.xml')
        DRef = xfl.DirTree()
        if (XFLFile_id):
            debug("Fichier de reprise de la session : %s" %XFLFile)
            DRef.read_disk(cible, working.AffCar)
        else:
            debug("Lecture du fichier de reprise : %s" %XFLFile)
            try:
                DRef.read_file(XFLFile)
            except:
                DRef.read_disk(cible, working.AffCar)
        
        # Appel de la fonction synchro_arbo modifiée
        synchronisation_effectuee = synchro_arbo(cible)

        if synchronisation_effectuee:
            logging.info("La synchronisation a été effectuée avec succès.")
        else:
            logging.info("Aucune synchronisation n'a été effectuée.")

        # Nettoyage après la synchronisation
        if (XFLFile_id):
            debug(f"Suppression du fichier de reprise temporaire : {XFLFile}")
            os.close(XFLFile_id)
            os.remove(XFLFile)

    elif options.recevoir:
        CHEMIN_DEST = path(args[0])
        # on commence par augmenter la priorité du processus de réception:
        augmenter_priorite()
        # thread de timeout des heartbeat
        HB_recus.Th_checktimeout_heartbeatT()
        # puis on se met en réception:
        recevoir(CHEMIN_DEST)
    logging.info("Arret de BlindFTP")
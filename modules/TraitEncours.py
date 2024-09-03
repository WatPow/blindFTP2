#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
----------------------------------------------------------------------------
TraitEncours: Classe afficher un motif de traitement en cours (sablier en TXT).
----------------------------------------------------------------------------

version 0.04 du 08/07/2023

Auteur:
- Laurent VILLEMIN (LV) - Laurent.villemin(a)laposte.net
"""

import time
import sys

class TraitEnCours:
    """
        Module permettant un affichage d'un motif cyclique
        ou version texte du sablier graphique
        Affichages disponibles
            un seul caractère d'une chaine affiché en boucle
            une chaine en défilement Droite Gauche
            une chaine en défilement Gauche Droite
            une chaine en clignotement
            ...
    """
# Variables internes
# __chaine : chaine contenant le motif affiché
# __mod : longueur de la chaine, utilisé pour la rotation D/G
# __temps : date du dernier affichage (optimise l'affichage au strict nécessaire)

    def __init__(self):
        """
        Initialisation du motif par défaut
        """
        self.__chaine='/-\\|'
        self.__mod=len(self.__chaine)
        self.__temps=time.time()

    def NewChaine(self, newchaine, LgMax=79, truncate=False):
        """
        Affectation d'un nouveau motif
        Controle du paramètre LgMax
        """

        lg=len(newchaine)
        if truncate==True and lg > LgMax:
            # Chaine trop longue à couper en 2 + insertion de "..." au milieu
            l1 = (LgMax - 3) // 2
            l2 = LgMax - l1 - 3
            self.__chaine = newchaine[0:l1] + "..." + newchaine[lg-l2:lg]
        else:
            self.__chaine=newchaine
        self.__mod=len(self.__chaine)

    def StartIte(self,val=None):
        """
        Démarrage du compteur d'iteration
        """
        if val==None:
            self.__ite=0
        else:
            self.__ite=val

    def __IncrementIte(self):
        """
        Increment du compteur
        """
        self.__ite+=1
        return(self.__ite)

    def __ChDecalDG(self):
        """
        Décalage d'une chaine de droite à gauche
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__chaine[(pos-1)%self.__mod]
            pos+=1
        return(newchaine)

    def __ChDecalGD(self):
        """
        Décalage d'une chaine de gauche à droite
        """
        pos=0
        newchaine=''
        while pos <= self.__mod:
            newchaine+=self.__chaine[(pos+1)%self.__mod]
            pos+=1
        return(newchaine)

    def AffCar(self, *args):
        """
        Affichage caractere par caractère
        """
        CurrentTime=time.time()
        if CurrentTime-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            print("{}\r".format(self.__chaine[self.__ite%self.__mod]), end='')
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneDG(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de droite à gauche
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__chaine=self.__ChDecalGD()
            print("{}\r".format(self.__chaine), end='')
            sys.stdout.flush()
            self.__temps=CurrentTime


    def AffLigneGD(self, *args):
        """
        Affichage d'une ligne selon un mode "chenillard" de gauche à droite
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.2:
            self.__ite=self.__IncrementIte()
            self.__chaine=self.__ChDecalDG()
            print("{}\r".format(self.__chaine), end='')
            sys.stdout.flush()
            self.__temps=CurrentTime

    def AffLigneBlink(self, *args):
        """
        Affichage d'une ligne en mode clignotant
        """
        CurrentTime=time.time()
        if time.time()-self.__temps > 0.4:
            self.__ite=self.__IncrementIte()
            if (self.__ite%2):
                print("{}\r".format(self.__chaine), end='')
            else:
                print(" "*self.__mod + "\r", end='')
            sys.stdout.flush()
            self.__temps=CurrentTime
if __name__ == '__main__':
    print("Module d'affichage d'un motif indiquant un 'Traitement en cours'")
    temp=0
    a=TraitEnCours()
    a.StartIte()
    print("Working (caractere)...")
    while temp < 30:
        temp+=1
        a.AffCar()
        time.sleep(0.1)
    a.StartIte()
    a.NewChaine('>12345  ')
    print("Working (Ligne de Gauche a Droite)...")
    while temp < 60:
        temp+=1
        a.AffLigneGD()
        time.sleep(0.2)
    a.StartIte()
    a.NewChaine('12345<  ')
    print("Working (Ligne de Droite a Gauche)...")
    while temp < 90:
        temp+=1
        a.AffLigneDG()
        time.sleep(0.2)
    a.NewChaine('Blinking')
    print("Working (clignotement)...")
    while temp < 120:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)
    a.NewChaine('Blinking a message too long for my small terminal which can only display 60 rows. So I must truncate it in the middle', LgMax=59, truncate=True)
    print("Working (clignotement avec tronquature)")
    while temp < 150:
        temp+=1
        a.AffLigneBlink()
        time.sleep(0.2)

    ToQuit=input("Appuyer sur Entree pour quitter")



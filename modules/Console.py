#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
----------------------------------------------------------------------------
Console: pour simplifier l'affichage de chaînes sur la console.
----------------------------------------------------------------------------

v0.03 du 08/07/2023

Copyright Philippe Lagadec 2005-2023
Auteur:
- Philippe Lagadec (PL) - philippe.lagadec(a)laposte.net

Ce logiciel est régi par la licence CeCILL soumise au droit français et
respectant les principes de diffusion des logiciels libres. Vous pouvez
utiliser, modifier et/ou redistribuer ce programme sous les conditions
de la licence CeCILL telle que diffusée par le CEA, le CNRS et l'INRIA
sur le site "http://www.cecill.info".

En contrepartie de l'accessibilité au code source et des droits de copie,
de modification et de redistribution accordés par cette licence, il n'est
offert aux utilisateurs qu'une garantie limitée.  Pour les mêmes raisons,
seule une responsabilité restreinte pèse sur l'auteur du programme,  le
titulaire des droits patrimoniaux et les concédants successifs.

A cet égard  l'attention de l'utilisateur est attirée sur les risques
associés au chargement,  à l'utilisation,  à la modification et/ou au
développement et à la reproduction du logiciel par l'utilisateur étant
donné sa spécificité de logiciel libre, qui peut le rendre complexe à
manipuler et qui le réserve donc à des développeurs et des professionnels
avertis possédant  des  connaissances  informatiques approfondies.  Les
utilisateurs sont donc invités à charger  et  tester  l'adéquation  du
logiciel à leurs besoins dans des conditions permettant d'assurer la
sécurité de leurs systèmes et ou de leurs données et, plus généralement,
à l'utiliser et l'exploiter dans les mêmes conditions de sécurité.

Le fait que vous puissiez accéder à cet en-tête signifie que vous avez
pris connaissance de la licence CeCILL, et que vous en avez accepté les
termes.
"""

#=== IMPORTS ==================================================================

import sys

#=== CONSTANTES ===============================================================

# Nombre de caractères temporaires affichés par Print_temp sur la ligne actuelle:
global _car_temp
_car_temp = 0


#------------------------------------------------------------------------------
# print_console
#-------------------
def print_console(chaine, errors='replace', newline=True):
    """
    Pour afficher une chaîne sur la console.

    errors: cf. aide du module codecs
    newline: indique s'il faut aller à la ligne
    """
    if newline:
        print(chaine)
    else:
        print(chaine, end='')

#------------------------------------------------------------------------------
# Print
#-------------------
def Print(chaine):
    """Affiche une chaîne sur la console, et passe à la ligne suivante,
    comme print. Si Print_temp a été utilisé précédemment, les éventuels
    caractères qui dépassent sont effacés pour obtenir un affichage
    correct.
    """
    global _car_temp
    if _car_temp > len(chaine):
        print(" "*_car_temp + "\r", end='')
    _car_temp = 0
    print_console(chaine)

#------------------------------------------------------------------------------
# Print_temp
#-------------------
def Print_temp(chaine, taille_max=79, NL=False):
    """Affiche une chaîne temporaire sur la console, sans passer à la ligne
    suivante, et en tronquant au milieu pour ne pas dépasser taille_max.
    Si Print_temp a été utilisé précédemment, les éventuels caractères qui
    dépassent sont effacés pour obtenir un affichage correct.
    """
    global _car_temp
    lc = len(chaine)
    if lc > taille_max:
        # si la chaine est trop longue, on la coupe en 2 et on ajoute
        # "..." au milieu
        l1 = (taille_max - 3) // 2
        l2 = taille_max - l1 - 3
        chaine = chaine[0:l1] + "..." + chaine[lc-l2:lc]
        lc = len(chaine)
        if lc != taille_max:
            raise ValueError("erreur dans Print_temp(): lc=%d" % lc)
    if _car_temp > lc:
        print(" "*_car_temp + "\r", end='')
    _car_temp = lc
    print_console(chaine + "\r", newline=NL)



#------------------------------------------------------------------------------
# MAIN
#-------------------
if __name__ == "__main__":
    Print("test de chaine longue: " + "a"*200)
    Print_temp("chaine longue temporaire...")
    Print_temp("chaine moins longue")
    print("")
    Print_temp("chaine longue temporaire...")
    Print("suite")
    Print_temp("chaine trop longue: "+"a"*100)
    print("")
    Print_temp("chaine accentuée très longue...")
    Print_temp("chaine rétrécie.")
    print("")



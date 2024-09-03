#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
----------------------------------------------------------------------------
TabBits: Classe pour manipuler un tableau de bits de grande taille.
----------------------------------------------------------------------------

version 0.04 du 08/07/2023


Copyright Philippe Lagadec 2005-2023
Auteur:
- Philippe Lagadec (PL) - philippe.lagadec(a)laposte.net
"""

import array

#------------------------------------------------------------------------------
# classe TabBits
#--------------------------

class TabBits:
	"""Classe pour manipuler un tableau de bits de grande taille."""
	
	def __init__ (self, taille, buffer=None, readFile=None):
		"""constructeur de TabBits.
		
		taille: nombre de bits du tableau.
		buffer: chaine utilisée pour remplir le tableau (optionnel).
		readFile: fichier utilisé pour remplir le tableau (optionnel).
		"""
		self._taille = taille
		self.nb_true = 0    # nombre de bits à 1, 0 par défaut
		if buffer == None and readFile == None:
			# on calcule le nombre d'octets nécessaires pour le buffer
			taille_buffer = (taille+7)//8
			# on crée un objet array de Bytes
			self._buffer = array.array('B')
			# on ajoute N éléments nuls
			self._buffer.extend([0]*taille_buffer)
		else:
			# pas encore écrit...
			raise NotImplementedError

	def get (self, indexBit):
		"""Pour lire un bit dans le tableau. Retourne un booléen."""
		# index de l'octet correspondant dans le buffer et décalage du bit dans l'octet
		indexOctet, decalage =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		masque = 1 << decalage
		bit = octet & masque
		# on retourne un booléen
		return bool(bit)

	def set (self, indexBit, valeur):
		"""Pour écrire un bit dans le tableau."""
		# on s'assure que valeur est un booléen
		valeur = bool(valeur)
		# index de l'octet correspondant dans le buffer et décalage du bit dans l'octet
		indexOctet, decalage =  divmod (indexBit, 8)
		octet = self._buffer[indexOctet]
		masque = 1 << decalage
		ancienne_valeur = bool(octet & masque)
		if valeur == True and ancienne_valeur == False:
			# on doit positionner le bit à 1
			octet = octet | masque
			self._buffer[indexOctet] = octet
			self.nb_true += 1
		elif valeur == False and ancienne_valeur == True:
			# on doit positionner le bit à 0
			masque = 0xFF ^ masque
			octet = octet & masque
			self._buffer[indexOctet] = octet
			self.nb_true -= 1

	def __str__ (self):
		"""pour convertir le TabBits en chaîne contenant des 0 et des 1."""
		return ''.join('1' if self.get(i) else '0' for i in range(self._taille))
		
if __name__ == "__main__":
	# quelques tests si le module est lancé directement
	N=100
	tb = TabBits(N)
	print(str(tb))
	tb.set(2, True)
	tb.set(7, True)
	tb.set(N-1, True)
	print(str(tb))
	print("tb[0] = %d" % tb.get(0))
	print("tb[2] = %d" % tb.get(2))
	print("tb[%d] = %d" % (N-1, tb.get(N-1)))
	print("taille bits = %d" % tb._taille)
	print("taille buffer = %d" % len(tb._buffer))

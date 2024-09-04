# BlindFTP2

BlindFTP est une application de transfert de fichiers en ligne de commande, initialement développée en 2008. Ce projet a été mis à jour pour être compatible avec Python 3, simplifié, et la partie Windows a été supprimée. De plus, une nouvelle fonctionnalité a été ajoutée au paramètre `-b` pour spécifier un nombre d'itérations pour la redondance.

## Fonctionnalités

- Envoi de fichiers
- Synchronisation d'arborescence
- Réception de fichiers
- Limitation du débit
- Mode debug
- Envoi en boucle avec possibilité de spécifier un nombre d'itérations
- Pause entre deux boucles
- Reprise à chaud des fichiers

## Paramètres

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Afficher l'aide |
| `-e`, `--envoi` | Envoyer le fichier |
| `-s`, `--synchro` | Synchroniser l'arborescence |
| `-r`, `--reception` | Recevoir des fichiers dans le répertoire indiqué |
| `-a ADRESSE` | Adresse destination: Adresse IP ou nom de machine |
| `-p PORT_UDP` | Port UDP |
| `-l DEBIT` | Limite du débit (Kbps) |
| `-d`, `--debug` | Mode Debug |
| `-b`, `--boucle` | Envoi des fichiers en boucle (optionnel: nombre d'itérations [int]) |
| `-P`, `--pause` | Pause entre 2 boucles (en secondes) |
| `-c`, `--continue` | Fichier de reprise à chaud |

## Installation

Pour installer BlindFTP, vous devez avoir Python 3 installé sur votre machine.
```bash
git clone https://github.com/WatPow/blindftp2.git
cd blindftp2
```

## Utilisation

### Envoi de fichiers

1. Initialisation :
   - La commande commence par appeler le script `bftp.py` avec l'interpréteur Python.
   - L'option `-e` ou `--envoi` indique que l'opération est un envoi de fichier.

2. Spécification du fichier source :
   - L'option `-S` ou `--source` est utilisée pour spécifier le chemin du fichier source à envoyer.
   - Exemple : `/home/user/documents/document.txt`

3. Adresse de destination :
   - L'option `-a` ou `--adresse` est utilisée pour spécifier l'adresse IP de la machine de destination.
   - Exemple : `192.168.2.20`

4. Processus d'envoi :
   - Le script `bftp.py` lit le fichier source spécifié.
   - Il divise le fichier en paquets de données.
   - Il envoie chaque paquet de données à l'adresse IP de destination via le protocole UDP.
   - Si l'option de redondance `-b` est spécifiée, le fichier est envoyé plusieurs fois pour assurer la redondance.
   - Si l'option de pause `--pause` est spécifiée, une pause est effectuée entre chaque itération d'envoi.

Exemple concret :

```bash
/usr/bin/python3 bftp.py -b 3 -S dossie_source -a 192.168.2.20 -P 5 -d 1024
```

### Réception de fichiers

1. Initialisation :
   - La commande commence par appeler le script `bftp.py` avec l'interpréteur Python.
   - L'option `-r` ou `--recevoir` indique que l'opération est une réception de fichier.

2. Spécification du répertoire de réception :
   - Vous spécifiez le répertoire où les fichiers reçus seront stockés.
   - Exemple : `/home/user/reception`

3. Adresse locale :
   - L'option `-a` ou `--adresse` est utilisée pour spécifier l'adresse IP locale de la machine qui reçoit les fichiers.
   - Exemple : `192.168.2.20`

4. Processus de réception :
   - Le script `bftp.py` configure la machine pour écouter les paquets de données entrants sur le port UDP spécifié (par défaut 5005).
   - Lorsqu'un paquet de données est reçu, il est assemblé avec les autres paquets pour reconstituer le fichier original.
   - Le fichier reconstitué est stocké dans le répertoire de réception spécifié.
   - Si l'option de redondance `-b` est spécifiée, le script attend plusieurs itérations pour s'assurer que tous les paquets ont été reçus.

Exemple concret :

```bash
sudo /usr/bin/python3 bftp.py -r /home/user/reception/ -a 192.168.2.20
```


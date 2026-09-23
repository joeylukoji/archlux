# Cas de référence

Plans et certificats **gelés**, comparés octet à octet.

Un certificat produit en `1.2.0` doit rester reproductible en `1.2.x` : tout changement
de comportement de l'oracle ou du certificat casse un cas de référence, et cette rupture
doit être **visible en revue**, pas découverte par un utilisateur.

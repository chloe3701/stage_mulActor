# Stage_multi-acteur

Il est possible de modifier les options d'optimisation en modifiant les variables du début du fichier main.py

emission_CO2_heure:
    - True: L'émission de CO2 par kgH2 a un seuil horaire
    - False: L'émission de CO2 par kgH2 a un seuil sur l'horizon entier d'optim: Possible de compenser d'un temps à l'autre

optim_prix:
    - "McCormick" : Utilise les enveloppes de McCormick pour obtenir un relaxation linéaire de Prix * Quantitée
    - None : Prix fixé dans data.py (/!\ il reste une contrainte dans modélisation qui empêche P2 de distribuer à C1)

Liste des packages à installer:
    - pyomo
    - matplotlib
    - plotly
    - pylatex (avoir aussi le compilateur latex)
    - kaleido
    - pymoo
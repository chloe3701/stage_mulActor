# Fichier de configuration d'optimisation. Synthétise les arguments variables du code

# Horizon d'optimisation (entre 1 et 8736)
# 2190: 3 mois
Time_horizon = 1

# Contraintes d'émissions de CO2 à la production
# Si emission_CO2_heure = True : A chaque heure, les producteurs doivent produire tq 1kgH2 génère < 3.5kgCO2
# Si emission_CO2_heure = False : La contrainte horaire est relachée et porte sur l'horizon d'optimisation complet
emission_CO2_heure = True

# Configuration des prix
# Si optim_prix = False : On utilise des prix fixé pour l'optim
# Si optim_prix = True : On linéarise prix * quantité avec les enveloppes de McCormick (approximation)
optim_prix = False

# Prix fixes si optim_prix = False
Prix_vente_H2 = {
    "P1_electrolyse(avec PV)": {"C1_industriel": 6, "C2_mobilite": 10},
    "P2_electrolyse": {"C1_industriel": 8, "C2_mobilite": 11.4},
    "P3_SMR": {"C1_industriel": 4.75, "C2_mobilite": 7.6},
}

# Degradation acceptable dans la résolution du max_min pour améliorer les émissions de CO2
# Entre 0 et 1
degradation_acceptable = 0

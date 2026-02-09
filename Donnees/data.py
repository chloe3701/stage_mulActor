import Utils.utils as utils
import config

# fichier de données csv
fichier_données = "Donnees/Stage_dataseries.csv"

# Debut des données 106
debut_data = 0
# Horizon de temps en heure max = 8736
Time_horizon = config.Time_horizon
# Energie
Energie = ["Elec_reseau", "PV", "Gaz"]
Electricite = ["Elec_reseau", "PV"]

# Producteurs
Prod = ["P1_electrolyse(avec PV)", "P2_electrolyse", "P3_SMR"]
P_electrolyseur = ["P1_electrolyse(avec PV)", "P2_electrolyse"]
P_SMR = ["P3_SMR"]

# Consommateurs
Cons = ["C1_industriel", "C2_mobilite"]

# Acteurs
Acteurs = Prod + Cons

# Time
Time = [i for i in range(Time_horizon)]


# Production_elec : Stock disponible d'électricité - en MWh
# Impact_elec : Impact carbone de l'électricité - en kgCo2/MWh
# Prix_energie : Prix de l'énergie - en €/MWh
# Demande_H2 : Demande d'H2 du client j
Production_elec, Impact_elec, Prix_energie, Demande_H2 = utils.read_data(
    fichier_données, Time_horizon
)


# ----------------------------#
#    Données producteurs      #
# ----------------------------#
# Rendement électrolyseur - en kgH2/MWh
Rendement_electrolyseur = {p: 20 for p in Prod}
# Rendement vaporeformage - en kgH2/MWh
Rendement_vaporeformage = {p: 20 for p in Prod}
# Taille vaporeformeur - en MW
Taille_vaporeformeur = {p: 1_000_000 for p in Prod}
# Taille max de l'électrolyseur - en MW
Taille_max_electrolyseur = {p: 10 for p in P_electrolyseur} | {p: 0 for p in P_SMR}
# Taille max du stockage - en kgH2
Taille_max_stockage = {p: 1_000 for p in P_electrolyseur} | {p: 0 for p in P_SMR}
# Taille max du captage - en kgCO2
Taille_max_captage = {p: 0 for p in P_electrolyseur} | {p: 1_000 for p in P_SMR}

# Calcul des CAPEX

# CAPEX en EUR/unit
# CAPEX electrolyseur - en EUR/MW
CAPEX_electrolyseur = {p: 600_000 for p in Prod}
# CAPEX stockage - en EUR/kgH2
CAPEX_stockage = {p: 1_000 for p in Prod}
# CAPEX captage - en EUR/kgCO2
CAPEX_captage = {p: 4_800 for p in Prod}

# Durée de vie
# electrolyseur - en années
Vie_electrolyseur = {p: 10 for p in Prod}
# stockage - en années
Vie_stockage = {p: 10 for p in Prod}
# captage - en années
Vie_captage = {p: 10 for p in Prod}

# CAPEX en EUR/unit/h
# electrolyseur - en EUR/MW/h
CAPEX_t_electrolyseur = {
    p: CAPEX_electrolyseur[p] / (8760 * Vie_electrolyseur[p]) for p in Prod
}
# stockage - en EUR/kgH2/h
CAPEX_t_stockage = {p: CAPEX_stockage[p] / (8760 * Vie_stockage[p]) for p in Prod}
# captage - en EUR/kgCO2/h
CAPEX_t_captage = {p: CAPEX_captage[p] / (8760 * Vie_captage[p]) for p in Prod}


# Impact vaporeformage - en kgCO2/kgH2
Impact_vaporeformage = {p: 10 for p in Prod}
# Impact Co2 maximal autorisé - en kgCO2 / kgH2
Impact_max = {p: 3.5 for p in Prod}

# ----------------------------#
#    Données consommateurs    #
# ----------------------------#
# Prix de vente - en €/kgH2
Prix_vente_H2 = config.Prix_vente_H2

# Demande totale
Demande_totale = sum(sum(values) for values in Demande_H2.values())
# Prix acceptés par le consommateur : prix cible et prix max
Pire_prix = {"C1_industriel": 10, "C2_mobilite": 20}
Meilleur_prix = {"C1_industriel": 0, "C2_mobilite": 0}

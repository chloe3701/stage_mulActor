import pyomo.environ as pyo
from Donnees.data import (
    Prod,
    Cons,
    Energie,
    Time,
    Prix_vente_H2,
    Acteurs,
    P_SMR,
    P_electrolyseur,
    Production_elec,
    Electricite,
    Demande_H2,
    Pire_prix,
)
import Definition.Acteurs.prod_electrolyse as p_electrolyse
import Definition.Acteurs.prod_SMR as p_SMR
import Definition.Acteurs.consommateur as consommateur

# Modélisation du scénario :
#   - 2 Producteur via électrolyse:
#       P1 : Source d'énergie PV + réseau
#       P2 : Source d'énergie réseau
#   => Stockage et électrolyseur à dimensionner
#   - 1 Producteur via vaporéformage
#   => Captage d'émission CO2 à dimensionner
#   - 2 Consommateurs d'H2


def init_model(
    emission_CO2_heure: bool = True, display: bool = False, optim_prix: bool = False
) -> pyo.ConcreteModel:
    """Initialise un modèle Pyomo pour la modélisation d'une chaîne de distribution simplifiée d'hydrogène.

    Args:
        emission_CO2_heure (bool, optional):
            Si True, les contraintes d'emisions CO2 sont horaires.
            Sinon, la contrainte quota d'emissions carbone porte sur l'horizon entier d'optimisation.
            Defaults to True.
        display (bool, optional):
            Si True, active les print. Defaults to False.
        optim_prix (bool, optional):
            Si True, fait rentrer le prix de vente de l'H2 en variable d'optimisation en utilisant l'approximation de variables bilinéaire
            des enveloppes de McCormick. Defaults to False.

    Returns:
        pyo.ConcreteModel:
            Le modèle Pyomo avec les paramètres,
            variables, fonctions objectifs, et contraintes définies.
    """

    # Fonction display
    def _print(texte: str) -> None:
        if display:
            print(texte)

    model = pyo.ConcreteModel()

    # --------------------------------------------------#
    #                Paramètres de prix                #
    # --------------------------------------------------#
    def init_prix(model, p, c):
        return Prix_vente_H2[p][c]

    model.Prix_vente_H2 = pyo.Param(Prod, Cons, initialize=init_prix, mutable=True)
    # --------------------------------------------------#
    #               Variables de décision              #
    # --------------------------------------------------#

    # Variables de flux

    # Quantitée d'énergie provenant de la source e consommée par le producteur i à temps t. En MWh
    # Q_energie[i,e,t]
    model.Q_energie = pyo.Var(Prod, Energie, Time, within=pyo.NonNegativeReals)

    # Quantitée d'énergie totale consommée par le producteur i à temps t. En MWh
    # Q_energie_total[i,t]
    model.Q_energie_total = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantitée d'H2 produite par le producteur i à temps t. En kgH2
    # Q_H2_prod[i,t]
    model.Q_H2_prod = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantitée d'H2 dans le stock du producteur i à temps t. En kgH2
    # Q_H2_stock[i,t]
    model.Q_H2_stock = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantitée d'H2 dans le stock initial du producteur i. En kgH2
    # Q_H2_init_stock[i]
    model.Q_H2_init_stock = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Quantité d’H2 rentrant dans le stockage du producteur i à temps t. En kgH2
    # Q_H2_stock_in[i,t]
    model.Q_H2_stock_in = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantité d’H2 sortant du stockage du producteur i à temps t. En kgH2
    # Q_H2_stock_out[i,t]
    model.Q_H2_stock_out = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantité d’H2 vendue sur le marché par le producteur i à temps t (avant répartition entre les consommateurs). En kgH2
    # Q_H2_a_vendre[i,t]
    model.Q_H2_a_vendre = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Quantité d’H2 vendue par le producteur i au consommateur j à temps t. En kgH2
    # Q_H2_vendu[i,j,t]
    model.Q_H2_vendu = pyo.Var(Prod, Cons, Time, within=pyo.NonNegativeReals)

    # Variables de dimensionnement

    # Taille de l'électrolyseur du producteur i. En MW
    # Taille_electrolyseur[i]
    model.Taille_electrolyseur = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Taille du stockage du producteur i. En kgH2
    # Taille_stockage[i]
    model.Taille_stockage = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Taille du captage de CO2 du producteur i. En kgCO2
    # Taille_captage[i]
    model.Taille_captage = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Variables économiques

    # Prix total de l'énergie consommée par le producteur i. En EUR
    # P_energie_total[i]
    model.P_energie_total = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Coût d’investissement du producteur i pour son électrolyseur par heure. En EUR/h
    # P_CAPEX_Electrolyseur[i]
    model.P_CAPEX_Electrolyseur = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Coût d’investissement du producteur i pour son stockage par heure. En EUR/h
    # P_CAPEX_Stockage[i]
    model.P_CAPEX_Stockage = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Coût d’investissement du producteur i pour son système de captage d'émission CO2 par heure. En EUR/h
    # P_CAPEX_Captage[i]
    model.P_CAPEX_Captage = pyo.Var(Prod, within=pyo.NonNegativeReals)

    # Prix payé par le consommateur j au producteur i à temps t. En EUR
    # P_H2_vendu[i,j,t]
    model.P_H2_vendu = pyo.Var(Prod, Cons, Time, within=pyo.NonNegativeReals)

    # Prix de l'hydrogène entre le producteur i et le consommateur j. En EUR/kgH2
    # P_H2_contrat[i,j]
    # /!\ Seulement si on utilise la relaxation linéaire de McCormick pour optimiser le prix
    if optim_prix:
        model.P_H2_contrat = pyo.Var(Prod, Cons, within=pyo.NonNegativeReals)

    # Variables environnementales

    # Impact CO2 du producteur i à temps t. En kgCO2
    # Impact_prod[i,t]
    model.Impact_prod = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Emissions de CO2 générés par le vaporeformage du producteur i à temps t. En kgCO2
    # Emission_vaporeformage[i,t]
    model.Emission_vaporeformage = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    # Emissions de CO2 captées par le producteur via vaporéformage i à temps t. En kgCO2
    # Captage[i,t]
    model.Captage = pyo.Var(Prod, Time, within=pyo.NonNegativeReals)

    Nb_var = sum(1 for _ in model.component_data_objects(pyo.Var))
    _print(f"Nombre de variables : {Nb_var}")

    # --------------------------------------------------#
    #               Objectifs individuels              #
    # --------------------------------------------------#

    # Variables représentant la valeur de la fonction objective si optimisation individuelle
    model.fn_obj = pyo.Var(Acteurs, within=pyo.Reals)

    p_electrolyse.objectif(model, P_electrolyseur)
    p_SMR.objectif(model, P_SMR)
    consommateur.objectif(model, Cons)

    # --------------------------------------------------#
    #               Contraintes                         #
    # --------------------------------------------------#
    # Sources d'énergie
    def C_prod_elec_max_energie_rule(m, e, t):
        return sum(m.Q_energie[i, e, t] for i in Prod) <= Production_elec[e][t]

    model.C_prod_elec_max_energie = pyo.Constraint(
        Electricite, Time, rule=C_prod_elec_max_energie_rule
    )

    # P1: Producteur via électrolyse avec PV + Elec réseau
    def C_P1_energie_rule(m, t):
        return m.Q_energie["P1_electrolyse(avec PV)", "Gaz", t] == 0

    model.C_P1_energie = pyo.Constraint(Time, rule=C_P1_energie_rule)

    # P2: Producteur via électrolyse avec Elec réseau
    def C_P2_energie_rule(m, t):
        return (
            m.Q_energie["P2_electrolyse", "Gaz", t]
            + m.Q_energie["P2_electrolyse", "PV", t]
            == 0
        )

    model.C_P2_energie = pyo.Constraint(Time, rule=C_P2_energie_rule)

    # P3: Producteur via SMR
    def C_P3_energie_rule(m, t):
        return (
            m.Q_energie["P3_SMR", "Elec_reseau", t] + m.Q_energie["P3_SMR", "PV", t]
            == 0
        )

    model.C_P3_energie = pyo.Constraint(Time, rule=C_P3_energie_rule)

    p_electrolyse.contraintes(model, P_electrolyseur, emission_CO2_heure, optim_prix)
    p_SMR.contraintes(model, P_SMR, emission_CO2_heure, optim_prix)
    consommateur.contraintes(model, Cons, optim_prix)

    # relaxation linéarisation P_H2_vendu[i,j,t] = Q_H2_vendu[i,j,t] * P_H2_contrat[i,j]
    # avec:
    #       0 <= Q_H2_vendu[i,j] <= Demande_H2[j][t]
    #       0 <= P_H2_contrat[i,j] <= Pire_prix[j]
    # Adapté de McCormick
    if optim_prix:

        def C_cormick_1_rule(m, i, j, t):
            return m.P_H2_vendu[i, j, t] <= m.Q_H2_vendu[i, j, t] * Pire_prix[j]

        model.C_cormick_1 = pyo.Constraint(Prod, Cons, Time, rule=C_cormick_1_rule)

        def C_cormick_2_rule(m, i, j, t):
            return m.P_H2_vendu[i, j, t] <= Demande_H2[j][t] * m.P_H2_contrat[i, j]

        model.C_cormick_2 = pyo.Constraint(Prod, Cons, Time, rule=C_cormick_2_rule)

        def C_cormick_3_rule(m, i, j, t):
            return (
                m.P_H2_vendu[i, j, t]
                >= Pire_prix[j] * m.Q_H2_vendu[i, j, t]
                + Demande_H2[j][t] * m.P_H2_contrat[i, j]
                - Pire_prix[j] * Demande_H2[j][t]
            )

        model.C_cormick_3 = pyo.Constraint(Prod, Cons, Time, rule=C_cormick_3_rule)

        def C_cormick_4_rule(m, i, j, t):
            return m.P_H2_vendu[i, j, t] >= 0

        model.C_cormick_4 = pyo.Constraint(Prod, Cons, Time, rule=C_cormick_4_rule)

    Nb_contr = sum(1 for _ in model.component_data_objects(pyo.Constraint))
    _print(f"Nombre de contraintes : {Nb_contr}")
    return model

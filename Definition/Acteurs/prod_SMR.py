import pyomo.environ as pyo
from Donnees.data import (
    Cons,
    Energie,
    Time,
    Time_horizon,
    Rendement_vaporeformage,
    Taille_vaporeformeur,
    Impact_max,
    Taille_max_captage,
    Prix_energie,
    CAPEX_t_captage,
    Impact_vaporeformage,
)


def objectif(model: pyo.ConcreteModel, Names: list[str]) -> pyo.ConcreteModel:
    """
    Définit la contrainte correspondant à la valeur de l'objectif des producteurs utilisant le SMR et un système CCS.

    Cette valeur correspond au cout de production moins les revenus liés à la vente.

    Elle est stockée dans la variable fn_obj[i].
    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo dans lequel les variables et contraintes sont définies.
        Names (list[str]):
            Liste des noms des producteurs via smr.

    Returns:
        pyo.ConcreteModel:
            Le modèle Pyomo avec la contrainte C_obj_prod_smr qui défini la valeur des fn_obj[i].
    """

    # /!\ si modification, ne pas oublier de la changer dans point_nadir.py
    def C_obj_prod_smr_rule(m, i):
        cout_energie = m.P_energie_total[i]
        cout_CAPEX = m.P_CAPEX_Captage[i] * Time_horizon
        recettes = sum(model.P_H2_vendu[i, j, t] for j in Cons for t in Time)
        return m.fn_obj[i] == cout_energie + cout_CAPEX - recettes

    model.C_obj_prod_smr = pyo.Constraint(Names, rule=C_obj_prod_smr_rule)
    return model


def contraintes(
    model: pyo.ConcreteModel,
    Names: list[str],
    emission_CO2_heure: bool = True,
    optim_prix: bool = False,
) -> pyo.ConcreteModel:
    """
    Ajoute les contraintes liées aux producteurs via smr dans le modèle Pyomo.

    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo dans lequel les variables et contraintes sont définies.
        Names (list[str]): Liste des noms des producteurs smr.
        emission_CO2_heure (bool, optional):
            Si True, les contraintes d'emisions CO2 sont horaires.
            Sinon, la contrainte quota d'emissions carbone porte sur l'horizon entier d'optimisation.
            Defaults to True.
        optim_prix (bool, optional):
            Si True, le prix de vente de l'H2 est inclu en variable d'optimisation.
            Certaines contraintes ne doivent dans ce cas pas être générées. Defaults to False.


    Returns:
        pyo.ConcreteModel:
            Le modèle avec les contraintes des producteurs smr.
    """
    # Contraintes flux physiques

    # Quantité d'énergie achetée par le producteur
    def C_prod_smr_0_rule(m, i, t):
        return m.Q_energie_total[i, t] == sum(m.Q_energie[i, e, t] for e in Energie)

    model.C_prod_smr_0 = pyo.Constraint(Names, Time, rule=C_prod_smr_0_rule)

    # Quantité d'H2 produite avec le gaz acheté
    def C_prod_smr_1_rule(m, i, t):
        return m.Q_H2_prod[i, t] == m.Q_energie_total[i, t] * Rendement_vaporeformage[i]

    model.C_prod_smr_1 = pyo.Constraint(Names, Time, rule=C_prod_smr_1_rule)

    # Quantité d'H2 vendu
    def C_prod_smr_1bis_rule(m, i, t):
        return m.Q_H2_a_vendre[i, t] == m.Q_H2_prod[i, t]

    model.C_prod_smr_1bis = pyo.Constraint(Names, Time, rule=C_prod_smr_1bis_rule)

    # Contrainte de dimensionnement electrolyseur
    def C_prod_smr_2_rule(m, i, t):
        return m.Q_energie_total[i, t] <= Taille_vaporeformeur[i]

    model.C_prod_smr_2 = pyo.Constraint(Names, Time, rule=C_prod_smr_2_rule)

    # Quantité d'H2 vendu
    def C_prod_smr_3_rule(m, i, t):
        return m.Q_H2_prod[i, t] == sum(m.Q_H2_vendu[i, j, t] for j in Cons)

    model.C_prod_smr_3 = pyo.Constraint(Names, Time, rule=C_prod_smr_3_rule)

    # Contrainte de dimensionnement système de capture CO2
    def C_prod_smr_4_rule(m, i, t):
        return m.Captage[i, t] <= m.Taille_captage[i]

    model.C_prod_smr_4 = pyo.Constraint(Names, Time, rule=C_prod_smr_4_rule)

    # Taille max captage
    def C_prod_smr_5_rule(m, i):
        return m.Taille_captage[i] <= Taille_max_captage[i]

    model.C_prod_smr_5 = pyo.Constraint(Names, rule=C_prod_smr_5_rule)

    # Contraintes économiques

    # Cout de production d'H2 : Energie
    def C_prod_smr_6_rule(m, i):
        return m.P_energie_total[i] == sum(
            m.Q_energie_total[i, t] * Prix_energie["Gaz"][t] for t in Time
        )

    model.C_prod_smr_6 = pyo.Constraint(Names, rule=C_prod_smr_6_rule)

    # Cout de production : CAPEX par heure
    def C_prod_smr_7_rule(m, i):
        return m.P_CAPEX_Captage[i] == m.Taille_captage[i] * CAPEX_t_captage[i]

    model.C_prod_smr_7 = pyo.Constraint(Names, rule=C_prod_smr_7_rule)

    # Si on n'optimise pas avec McCormick
    # Prix vendu aux consommateurs (contrainte redondante avec la modélisation des consommateurs)
    if not optim_prix:

        def C_prod_smr_8_rule(m, i, j, t):
            return (
                m.P_H2_vendu[i, j, t] == m.Q_H2_vendu[i, j, t] * m.Prix_vente_H2[i, j]
            )

        model.C_prod_smr_8 = pyo.Constraint(Names, Cons, Time, rule=C_prod_smr_8_rule)

    # Contraintes environnement

    # Emissions de CO2 liés au vaporéformage
    def C_prod_smr_9_rule(m, i, t):
        return (
            m.Emission_vaporeformage[i, t]
            == m.Q_H2_prod[i, t] * Impact_vaporeformage[i]
        )

    model.C_prod_smr_9 = pyo.Constraint(Names, Time, rule=C_prod_smr_9_rule)

    # Impact carbone producteur
    def C_prod_smr_10_rule(m, i, t):
        return m.Impact_prod[i, t] == m.Emission_vaporeformage[i, t] - m.Captage[i, t]

    model.C_prod_smr_10 = pyo.Constraint(Names, Time, rule=C_prod_smr_10_rule)

    # Contraintes d'emissions maximum
    # Si contrainte horaire
    if emission_CO2_heure:

        def C_prod_smr_11_rule(m, i, t):
            return m.Impact_prod[i, t] <= Impact_max[i] * m.Q_H2_prod[i, t]

        model.C_prod_smr_11 = pyo.Constraint(Names, Time, rule=C_prod_smr_11_rule)
    # Si contrainte en moyenne
    else:

        def C_prod_smr_11_rule(m, i):
            return sum(m.Impact_prod[i, t] for t in Time) <= Impact_max[i] * sum(
                m.Q_H2_prod[i, t] for t in Time
            )

        model.C_prod_smr_11 = pyo.Constraint(Names, rule=C_prod_smr_11_rule)

    return model

import pyomo.environ as pyo
from Donnees.data import Time, Prod, Demande_H2


def objectif(model: pyo.ConcreteModel, Names: list[str]) -> pyo.ConcreteModel:
    """
    Définit la contrainte correspondant à la valeur de l'objectif des consommateur.

    Cette valeur correspond au prix moyen payé par kilogramme d'hydrogène (EUR/kgH2).
    Elle est stockée dans la variable fn_obj[j].

    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo dans lequel les variables et contraintes sont définies.
        Names (list[str]):
            Liste des noms des consommateurs.

    Returns:
        pyo.ConcreteModel:
        Le modèle Pyomo avec la contrainte C_val_cons qui défini la valeur des fn_obj[j].
    """

    # /!\ si modification, ne pas oublier de la changer dans point_nadir.py
    # Valeur de la fonction objective des consommateur:
    # prix au kilo de l'H2
    def C_val_cons_rule(m, j):
        prix_total = sum(model.P_H2_vendu[i, j, t] for t in Time for i in Prod)
        demande_tot_cons = sum(Demande_H2[j][t] for t in Time)
        if demande_tot_cons == 0:
            return m.fn_obj[j] == 0
        else:
            return m.fn_obj[j] == prix_total / demande_tot_cons

    model.C_val_cons = pyo.Constraint(Names, rule=C_val_cons_rule)

    return model


def contraintes(
    model: pyo.ConcreteModel, Names: list[str], optim_prix: bool = False
) -> pyo.ConcreteModel:
    """
    Ajoute les contraintes liées aux consommateurs dans le modèle Pyomo.

    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo dans lequel les variables et contraintes sont définies.
        Names (list[str]): Liste des noms des consommateurs.
        optim_prix (bool, optional):
            Si True, le prix de vente de l'H2 est inclu en variable d'optimisation.
            Certaines contraintes ne doivent dans ce cas pas être générées. Defaults to False.

    Returns:
        pyo.ConcreteModel:
            Le modèle avec les contraintes des consommateurs.
    """

    # La demande est satisfaite
    def C_cons_1_rule(m, j, t):
        return sum(m.Q_H2_vendu[i, j, t] for i in Prod) == Demande_H2[j][t]

    model.C_cons_1 = pyo.Constraint(Names, Time, rule=C_cons_1_rule)

    # Si on n'optimise pas avec McCormick
    # Prix payé aux producteur (contrainte redondante avec la modélisation des producteurs)
    if not optim_prix:

        def C_cons_2_rule(m, i, j, t):
            return (
                m.P_H2_vendu[i, j, t] == m.Q_H2_vendu[i, j, t] * m.Prix_vente_H2[i, j]
            )

        model.C_cons_2 = pyo.Constraint(Prod, Names, Time, rule=C_cons_2_rule)
    return model

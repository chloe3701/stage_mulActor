import Resolution.goal_programming as gp
import pyomo.environ as pyo
import config as config
from Donnees.data import Prod, Time, Demande_totale, Cons, Acteurs
import Utils.plotting as plot
from pyomo.opt import TerminationCondition


# Résolution d'un problème multi-objectif en maximisant l'insatisfaction minimum


def max_min_satisfaction(
    model: pyo.ConcreteModel,
    lower_bound: dict[str, float],
    upper_bound: dict[str, float],
    utopia: dict[str, float],
    nadir: dict[str, float],
    display: bool = True,
    optim_prix: bool = False,
) -> tuple[dict[str, float], dict[str, float], float]:
    """
    Optimise le modèle selon une approche de satisfaction équitable (max-min),
    puis minimise l'empreinte CO2 sous contrainte de dégradation acceptée.

    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo.
        lower_bound (dict[str, float]):
            Valeurs pour lesquelles tout acteur est satisfait au maximum.
        upper_bound (dict[str, float]):
            Valeurs pour lesquelles tout acteur n'est plus satisfait.
        utopia (dict[str, float]):
            Valeurs optimales (utopiques) par acteur.
        nadir (dict[str, float]):
            Valeurs nadir par acteur.
        display (bool, optional):
            Si True, affiche les résultats dans la console. Defaults to False.
        optim_prix (bool, optional):
            True si les prix sont des variables d'optimisation. Defaults to False.

    Returns:
        tuple[dict[str, float], dict[str, float], float]:
            - Objectifs obtenus (f_new),
            - Satisfaction finale par acteur,
            - Impact CO2 moyen par kg d'H2,
            - Liste des acteurs considérés dans l'optimisation.
    """

    def _print(texte: str) -> None:
        if display:
            print(texte)

    def calcul_CO2() -> float:
        """
        Calcule l'empreinte carbone moyenne (en CO2) par kg d'hydrogène consommé,
        en sommant les impacts de production sur tout l'horizon temporel
        et en divisant par la demande totale.

        Returns:
            float:
                Impact carbone moyen par kg d' H2 (arrondi à 4 décimales).
        """
        total_impact_co2 = sum(
            pyo.value(model.Impact_prod[i, t]) for i in Prod for t in Time
        )
        return round(total_impact_co2 / Demande_totale, 4)

    # Calcul manuel de la satisfaction après optimisation
    def calcul_satisfaction(Names: list[str]) -> dict[str, float]:
        """
        Calcule les taux de satisfaction pour chaque acteur
        après optimisation du modèle.

        Args:
            Names (list[str]):
                Liste des noms d'acteurs à évaluer.

        Returns:
            dict[str, float]:
                Dictionnaire des taux de satisfaction (entre 0 et 1) par acteur.
        """
        satisfaction = {}
        for a in Names:
            if upper_bound[a] > lower_bound[a]:
                satisfaction[a] = min(
                    max(
                        pyo.value(
                            (model.fn_obj[a] - upper_bound[a])
                            / (lower_bound[a] - upper_bound[a])
                        ),
                        0,
                    ),
                    1,
                )
            elif utopia[a] == nadir[a]:
                satisfaction[a] = 1
            else:
                satisfaction[a] = pyo.value(
                    (model.fn_obj[a] - nadir[a]) / (utopia[a] - nadir[a])
                )
        _print(satisfaction)
        return satisfaction

    if not optim_prix:
        Names = Prod.copy()
        # Si tout les prix sont les mêmes, on optimise pas le consommateur
        for c in Cons:
            valeurs = [
                pyo.value(model.Prix_vente_H2[i, c])
                for i in Prod
                if (i, c) in model.Prix_vente_H2
            ]
            if len(set(valeurs)) > 1:
                Names.append(c)
    else:
        Names = Acteurs

    gp.satisfaction_function(
        model, lower_bound, upper_bound, utopia, nadir, Names=Names
    )

    # Variable de linéarisation
    model.z = pyo.Var(within=pyo.NonNegativeReals)

    # z > d- -> z maximize
    def linear_rule(m, a):
        return m.z <= m.satisfaction[a]

    model.linear_z = pyo.Constraint(Names, rule=linear_rule)

    model.objectif = pyo.Objective(expr=model.z, sense=pyo.maximize)

    _print("\n---------------------------------------------")
    _print("---Maximisation de la satisfaction minimum---")
    _print("---------------------------------------------")
    solver = pyo.SolverFactory("cplex")
    results = solver.solve(model)
    if hasattr(model, "linear_z"):
        del model.linear_z

    if results.solver.termination_condition == TerminationCondition.infeasible:
        print("La version Max_Min est infaisable.")
        exit()
    _print(f"Valeur objective max min: {model.objectif()}\n")

    # Calcul des anciennes fonctions objectives après optimisation
    f_new = {}
    satisfaction = calcul_satisfaction(Names)
    satisf_evolution = []

    # La boucle suivante permet de garantir l'optimalité de Pareto
    Acteurs_a_optim = Names.copy()
    while Acteurs_a_optim != []:
        # ajout contraintes satisfaction
        # + nouvelle résolution
        satisfaction_a_optim = {a: satisfaction[a] for a in Acteurs_a_optim}
        min_acteur = min(satisfaction_a_optim, key=satisfaction_a_optim.get)
        satisf_min = satisfaction_a_optim[min_acteur]
        _print(
            f"L'acteur le moins satisfait est : {min_acteur} avec une satisfaction de {satisf_min}\n"
        )

        def C_seuil_satisf_rule(m, a):
            if a in Acteurs_a_optim:
                return m.satisfaction[a] >= satisf_min
            else:
                return m.satisfaction[a] >= satisfaction[a]

        model.C_seuil_satisf = pyo.Constraint(Names, rule=C_seuil_satisf_rule)

        Acteurs_a_optim.remove(min_acteur)

        # z > d- -> z maximize
        def linear_rule(m, a):
            return m.z <= m.satisfaction[a]

        model.linear_z = pyo.Constraint(Acteurs_a_optim, rule=linear_rule)

        results = solver.solve(model, warmstart=True)
        satisfaction = calcul_satisfaction(Names)
        satisf_evolution.append([satisfaction[a] for a in Names])

        if hasattr(model, "C_seuil_satisf"):
            del model.C_seuil_satisf
        if hasattr(model, "linear_z"):
            del model.linear_z

    # Après optimisation économique, on optimise la partie environnementale
    # On fixe un taux de dégradation acceptable sur la satisfaction
    degradation_acceptable = config.degradation_acceptable

    def C_seuil_satisf_rule(m, a):
        return m.satisfaction[a] >= satisfaction[a] - degradation_acceptable

    model.C_seuil_satisf = pyo.Constraint(Names, rule=C_seuil_satisf_rule)

    model.linear_z = pyo.Constraint(Names, rule=linear_rule)

    del model.objectif
    model.objectif = pyo.Objective(
        expr=sum(model.Impact_prod[i, t] for i in Prod for t in Time),
        sense=pyo.minimize,
    )
    results = solver.solve(model, warmstart=True)
    satisfaction = calcul_satisfaction(Names)
    satisf_evolution.append([satisfaction[a] for a in Names])

    iterations = [f"Optimisation n°{i}" for i in range(len(satisf_evolution) - 1)] + [
        f"Optimisation CO2\n(dégradation: {config.degradation_acceptable})"
    ]

    plot.plot_data(
        file_name="Resultats\\evolution_maxmin.png",
        data=satisf_evolution,
        labels_fn=iterations,
        labels_acteurs=Names,
        titre="Évolution de la satisfaction des acteurs",
        titre_legende="Itérations",
        y_axis_titre="Satisfaction",
    )

    for a in Names:
        f_new[a] = pyo.value(model.fn_obj[a])
        _print(
            f"\nActeur:{a}\n- Initialement :\n   Objectif={lower_bound[a]}\n   Pire={upper_bound[a]}\n   Utopie={utopia[a]}\n   Nadir={nadir[a]}"
        )
        _print(
            f"- Résultats :\n   Valeur de l'objectif={pyo.value(model.fn_obj[a])}\n   Taux de satisfaction={satisfaction[a]}"
        )

    _print("---------------------------------------------")

    plot.sankey_flow_diag(model, filename="Resultats\\max_min_sankey.png")
    return f_new, satisfaction, calcul_CO2(), Names

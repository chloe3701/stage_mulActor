import pyomo.environ as pyo
from Donnees.data import Prod, Acteurs, Time, Demande_totale
import Utils.plotting as plot
from pyomo.opt import TerminationCondition


# Définition de la fonction de satisfaction:
#
# Inputs:
# lower_bound est la valeur à laquelle chaque acteur aspire
# upper_bound est la valeur maximale que chaque acteur est prêt à accepter
# utopia est la valeur minimale que chaque acteur peut atteindre indépendemment
# worst est la valeur maximale que chaque acteur peut atteindre indépendemment
#
# Outputs:
# si lower_bound < upper_bound
# si fn ≤ lower_bound: satisfaction = 1
# si fn ≥ upper_bound: satisfaction = 0
# sinon satisfaction = (fn - upper_bound) / (lower_bound - upper_bound)
#
# si lower_bound == upper_bound
# satisfaction = (fn - nadir) / (lower_bound - nadir)
def satisfaction_function(
    model: pyo.ConcreteModel,
    lower_bound: dict[str, float],
    upper_bound: dict[str, float],
    utopia: dict[str, float],
    nadir: dict[str, float],
    Names: list[str] = Acteurs,
) -> None:
    """
    Ajoute au modèle Pyomo les contraintes modélisant la satisfaction de chaque acteur.
    La fonction de satisfaction est bornée entre 0 et 1.

    Args:
        model (pyo.ConcreteModel):
            Le modèle Pyomo dans lequel ajouter les contraintes.
        lower_bound (dict[str, float]):
            Valeurs pour lesquelles tout acteur est satisfait au maximum.
        upper_bound (dict[str, float]):
            Valeurs pour lesquelles tout acteur n'est plus satisfait.
        utopia (dict[str, float]):
            Valeurs optimales (utopiques) par acteur.
        nadir (dict[str, float]):
            Valeurs nadir par acteur.
        Names (list[str], optional):
            Liste des noms des acteurs. Defaults to Acteurs.
    """

    def big_M(
        utopia: dict[str, float], upper_bound: dict[str, float]
    ) -> dict[str, float]:
        """
        Calcul du plus petit big M permettant d'activer correctement les contraintes.

        Le calcul est effectué pour chaque acteur en prenant la différence entre
        la borne supérieure et la valeur de l'utopie, avec une petite marge
        supplémentaire (+5) pour éviter des erreurs dues à la précision numérique.

        Une bonne estimation de M améliore la performance du solveur en évitant
        des valeurs trop grandes (relaxations trop lâches) ou trop petites (invalidation des contraintes).

        Args:
            utopia (dict[str, float]):
                Dictionnaire associant à chaque acteur sa valeur d'utopie.
            upper_bound (dict[str, float]):
                Dictionnaire des bornes supérieures associées à chaque acteur

        Returns:
            dict[str,float]:
                Dictionnaire des constantes de type big M pour chaque acteur
        """
        M = {}
        for a in Names:
            # Ajout d'une petite marge pour palier aux erreurs de précision décimale
            M[a] = upper_bound[a] - utopia[a] + 5
        return M

    M = big_M(utopia, upper_bound)

    model.satisfaction = pyo.Var(Names, within=pyo.Reals)
    # Variable binaires pour partitionner la fonction
    # bin=1 => fn ≥ upper_bound
    model.bin = pyo.Var(Names, within=pyo.Binary)

    # (1-bin) ≥ satisfaction ≥ 0
    def C_satisf_1_a_rule(m, a):
        if upper_bound[a] == lower_bound[a]:
            return m.satisfaction[a] <= 1
        else:
            return (1 - m.bin[a]) >= m.satisfaction[a]

    model.C_satisf_1_a = pyo.Constraint(Names, rule=C_satisf_1_a_rule)

    def C_satisf_1_b_rule(m, a):
        return m.satisfaction[a] >= 0

    model.C_satisf_1_b = pyo.Constraint(Names, rule=C_satisf_1_b_rule)

    # Bx ≥ upper_bound - M(1−bin)
    def C_satisf_2_rule(m, a):
        if upper_bound[a] == lower_bound[a]:
            return m.bin[a] == 0
        else:
            return m.fn_obj[a] >= upper_bound[a] - M[a] * (1 - m.bin[a])

    model.C_satisf_2 = pyo.Constraint(Names, rule=C_satisf_2_rule)

    # satisfaction <= (fn - upper_bound) / (lower_bound - upper_bound) + M * bin
    def C_satisf_3_rule(m, a):
        if upper_bound[a] > lower_bound[a]:
            return (
                m.satisfaction[a]
                <= ((m.fn_obj[a] - upper_bound[a]) / (lower_bound[a] - upper_bound[a]))
                + M[a] * m.bin[a]
            )
        elif upper_bound[a] < lower_bound[a]:
            raise ValueError(f"Invalid bounds for actor {a}: upper_bound < lower_bound")
        else:
            if utopia[a] == nadir[a]:
                return m.satisfaction[a] == 1
            else:
                return m.satisfaction[a] == (m.fn_obj[a] - nadir[a]) / (
                    utopia[a] - nadir[a]
                )

    model.C_satisf_3 = pyo.Constraint(Names, rule=C_satisf_3_rule)


def goal_programming(
    model: pyo.ConcreteModel,
    lower_bound: dict[str, float],
    upper_bound: dict[str, float],
    utopia: dict[str, float],
    nadir: dict[str, float],
    display: bool = False,
) -> tuple[dict[str, float], dict[str, float], float]:
    """
    Applique la méthode de Goal Programming pour maximiser la satisfaction des acteurs,
    selon leurs objectifs respectifs et leurs bornes de performance.

    Args:
        model (pyo.ConcreteModel):
            Modèle Pyomo à optimiser.
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

    Returns:
        tuple[dict[str, float], dict[str, float], float]:
            - Nouvelles valeurs des fonctions objectifs des acteurs.
            - Satisfaction atteinte pour chaque acteur.
            - Impact CO₂ moyen par kg d'H2 produit.
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
                Impact carbone moyen par kg de H₂ (arrondi à 4 décimales).
        """
        total_impact_co2 = sum(
            pyo.value(model.Impact_prod[i, t]) for i in Prod for t in Time
        )
        return round(total_impact_co2 / Demande_totale, 4)

    satisfaction_function(model, lower_bound, upper_bound, utopia, nadir)

    # Définition de la nouvelle fonction objective
    # maximiser la satisfaction totale
    model.objectif = pyo.Objective(
        expr=sum(model.satisfaction[a] for a in Acteurs), sense=pyo.maximize
    )

    _print("\n--------------------------------------------")
    _print("---Maximisation de la satisfaction totale---")
    _print("--------------------------------------------")
    solver = pyo.SolverFactory("cplex")
    results = solver.solve(model, tee=False)

    if results.solver.termination_condition == TerminationCondition.infeasible:
        print("La version Goal Programming est infaisable.")
        exit()
    _print(f"Valeur objective goal programming: {model.objectif()}")

    # Calcul des anciennes fonctions objectives après optimisation
    f_new = {}
    for a in Acteurs:
        f_new[a] = pyo.value(model.fn_obj[a])
        _print(
            f"\nActeur:{a}\n- Initialement :\n   Objectif={lower_bound[a]}\n   Pire={upper_bound[a]}\n   Utopie={utopia[a]}\n   Nadir={nadir[a]}"
        )
        _print(
            f"- Résultats :\n   Valeur de l'objectif={pyo.value(model.fn_obj[a])}\n   Taux de satisfaction={pyo.value(model.satisfaction[a])}"
        )
    _print("--------------------------------------------")

    plot.sankey_flow_diag(model, filename="Resultats\\GP_sankey.png")
    return f_new, {a: model.satisfaction[a].value for a in Acteurs}, calcul_CO2()

import pyomo.environ as pyo
from Donnees.data import Demande_totale, Prod, Time, Cons, Demande_H2, Acteurs


def optim_individuelle(
    model: pyo.ConcreteModel, display: bool = False
) -> tuple[
    dict[str, float], dict[str, float], dict[str, float], dict[str, dict[str, float]]
]:
    """
    Réalise une optimisation individuelle pour chaque acteur afin de déterminer :
    - Le point utopique (meilleur objectif atteignable pour chaque acteur),
    - Le point nadir (pire valeur observée pour chaque objectif lorsque d'autres sont priorisés),
    - Le pire point (objectif maximal pour chaque acteur),
    - Les résultats croisés obtenus lorsque chaque acteur est priorisé.

    Args:
        model (pyo.ConcreteModel):
            Le modèle pyomo
        display (bool, optional):
            Active l'affichage des étapes de résolution. Defaults to False.

    Returns:
        tuple[ dict[str, float], dict[str, float], dict[str, float], dict[str, dict[str, float]] ]:
            - point_utopia (dict[str, float]):
                Meilleure valeur atteignable (objectif minimal) pour chaque acteur.
            - point_nadir (dict[str, float]):
                Pire valeur observée de chaque objectif dans les optimisations priorisant les autres acteurs.
            - point_worst (dict[str, float]):
                Valeur maximale atteignable pour chaque objectif (utile pour encadrer les bornes).
            - priority_results (dict[str, dict[str, float]]):
                Dictionnaire des résultats obtenus pour chaque acteur b lorsque l'acteur a est priorisé
                (i.e., priority_results[a][b] correspond à l'objectif de b quand a est priorisé).
    """

    # Fonction display
    def _print(texte: str) -> None:
        if display:
            print(texte)

    def calcul_CO2() -> None:
        """
        Calcule l'empreinte carbone moyenne (en CO2) par kg d'hydrogène consommé,
        en sommant les impacts de production sur tout l'horizon temporel
        et en divisant par la demande totale.

        Affiche l'impact carbone moyen par kg de H2 (arrondi à 4 décimales).
        """
        total_impact_co2 = sum(
            pyo.value(model.Impact_prod[i, t]) for i in Prod for t in Time
        )
        _print(total_impact_co2)
        _print(
            f"Somme totale de l'impact CO2 des producteurs : {round(total_impact_co2 / Demande_totale, 4)} kgCo2/kgH2\n"
        )

    _print("Objectifs sans priorité :")
    expr = sum(model.fn_obj[a] for a in Prod) + sum(
        model.fn_obj[a] * sum(Demande_H2[a][t] for t in Time) for a in Cons
    )
    model.objective = pyo.Objective(expr=expr, sense=pyo.minimize)
    solver = pyo.SolverFactory("cplex")
    solver.solve(model, tee=False)

    results = {}
    # Point idéal/utopia
    point_utopia = {}
    # Point Nadir
    point_nadir = {}
    # Pire point (en maximisant)
    point_worst = {}
    # taille_max = {"electrolyseur" : {}, "stockage" :{}, "captage" : {}}
    for a in Acteurs:
        results[a] = pyo.value(model.fn_obj[a])
        _print(f"Objectif {a}: {results[a]}")
        point_utopia[a] = point_worst[a] = point_nadir[a] = results[a]
    calcul_CO2()
    del model.objective

    # Calcul du point idéal
    priority_results = {}
    for a in Acteurs:
        _print(f"Objectifs en priorisant {a} :")
        model.objective = pyo.Objective(expr=model.fn_obj[a], sense=pyo.minimize)
        solver.solve(model, tee=False)

        point_utopia[a] = pyo.value(model.fn_obj[a])

        results = {}
        for b in Acteurs:
            results[b] = pyo.value(model.fn_obj[b])
            point_nadir[b] = max(point_nadir[b], results[b])
            _print(f"Objectif {b}: {results[b]}")
        priority_results[a] = results
        calcul_CO2()
        del model.objective

    # Calcul du pire point
    # NB: Peut être enlever pour résultat + rapides
    for a in Acteurs:
        model.objective = pyo.Objective(expr=model.fn_obj[a], sense=pyo.maximize)
        solver.solve(model, tee=False)
        point_worst[a] = pyo.value(model.fn_obj[a])
        del model.objective

        # point_worst[a] = 0

    return point_utopia, point_nadir, point_worst, priority_results

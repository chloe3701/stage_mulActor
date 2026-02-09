import Definition.modelisation as modelisation
import config as config
import Resolution.point_nadir as p_nad
import Donnees.data as data
import Resolution.optim_individuelle as optim_indiv
import Resolution.goal_programming as gp
import Resolution.max_min_satisfaction as max_min
import Utils.rapport_latex as rapport
import time


def main():
    # Options d'optimisation récupérée du fichier config.py
    optim_prix = config.optim_prix
    emission_CO2_heure = config.emission_CO2_heure

    # initialisation du model
    model_gp = modelisation.init_model(
        display=False, emission_CO2_heure=emission_CO2_heure, optim_prix=optim_prix
    )

    # Récupération des informations obtenues grace aux optimisations individuelles
    start_time = time.time()
    point_utopia, point_nadir, point_worst, priority_results = (
        optim_indiv.optim_individuelle(model_gp, display=False)
    )
    end_time = time.time()
    exec_time_indiv = end_time - start_time

    # Calcul du point nadir
    point_nadir = p_nad.point_nadir(point_nadir)

    # Définition des objectifs de chaque acteurs
    # lower_bound est la valeur à laquelle chaque acteur aspire
    lower_bound = {}
    # upper_bound est la valeur maximale que chaque acteur est prêt à accepter
    upper_bound = {}
    for a in modelisation.Prod:
        lower_bound[a] = point_utopia[a]
        # Le producteur n'accepte pas de vendre à perte => Peut être le point nadir selon modification
        upper_bound[a] = 0
    for a in modelisation.Cons:
        # Le consommateur a des attentes sur le prix d'achat
        lower_bound[a] = data.Meilleur_prix[a]
        upper_bound[a] = data.Pire_prix[a]

    # Résolution Goal Programming
    start_time = time.time()
    f_gp, satisf_gp, CO2_gp = gp.goal_programming(
        model_gp,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        utopia=point_utopia,
        nadir=point_nadir,
        display=False,
    )
    end_time = time.time()
    exec_time_gp = end_time - start_time

    # Résolution max min
    model_mm = modelisation.init_model(
        display=False, emission_CO2_heure=emission_CO2_heure, optim_prix=optim_prix
    )
    start_time = time.time()
    f_mm, satisf_mm, CO2_mm, Names = max_min.max_min_satisfaction(
        model_mm,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        utopia=point_utopia,
        nadir=point_nadir,
        display=False,
        optim_prix=optim_prix,
    )
    end_time = time.time()

    # Si jamais il y avait des acteurs enlevé de l'optimisation
    # (ex : les consommateurs achetent au même prix partout)
    if not optim_prix:
        for c in data.Cons:
            if c not in Names:
                f_mm[c] = f_gp[c]
                satisf_mm[c] = satisf_gp[c]

    exec_time_mm = end_time - start_time

    # Pour génération du rapport Latex
    results = {
        "Options d'optimisation": {
            "Prix_variable": optim_prix,
            "Contrainte_CO2": emission_CO2_heure,
        },
        "Optimisations Individuelles": {
            "Table de priorité": priority_results,
            "Point Idéal": point_utopia,
            "Pire Point": point_worst,
            "Point Nadir": point_nadir,
            "Temps": exec_time_indiv,
        },
        "Goal Programming": {
            **{
                a: {"Fonction objective": f_gp[a], "Satisfaction": satisf_gp[a]}
                for a in data.Acteurs
            },
            "Impact CO2": CO2_gp,
            "Sankey": "GP_sankey.png",
            "Model": model_gp,
            "Temps": exec_time_gp,
        },
        "Max min satisfaction": {
            **{
                a: {"Fonction objective": f_mm[a], "Satisfaction": satisf_mm[a]}
                for a in data.Acteurs
            },
            "Impact CO2": CO2_mm,
            "Evolution maxmin": "evolution_maxmin.png",
            "Sankey": "max_min_sankey.png",
            "Model": model_mm,
            "Temps": exec_time_mm,
        },
    }
    rapport.rapport_latex(
        filename="Resultats/Fichier_resultat",
        title="Rapport d'optimisation",
        results=results,
    )


if __name__ == "__main__":
    main()
    print("Done")

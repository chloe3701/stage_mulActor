from pylatex import Document, Section, Subsection, NewPage, Command, Figure, Tabular
from pylatex.utils import NoEscape
from typing import Any
import os
import Donnees.data as data
import pyomo.environ as pyo
import Utils.plotting as plot


# Génération d'un rapport d'optimisation Latex
def rapport_latex(filename: str, title: str, results: dict[str, Any]) -> None:
    """
    Generate a detailed LaTeX report from optimization results and save it as a PDF.

    Args:
        filename (str):
            Output filename for the generated PDF report.
        title (str):
            Title of the report
        results (dict[str, Any]):
            Dictionary containing optimization results, models,
            figures (paths to images), and related data structured by method names and keys.
            See in main.
    """
    doc = Document()
    doc.preamble.append(Command("usepackage", "xcolor"))
    doc.preamble.append(Command("usepackage", "colortbl"))
    doc.preamble.append(Command("title", title))
    doc.preamble.append(Command("usepackage", "geometry"))
    doc.preamble.append(Command("geometry", "top=1in, bottom=1in, left=1in, right=1in"))
    doc.append(NoEscape(r"\maketitle"))

    with doc.create(Section("Informations")):
        model = results["Goal Programming"]["Model"]
        doc.append(
            f"Horizon d'optimisation: {data.Time_horizon / 24:.2f} jours ({data.Time_horizon}h).\n"
        )
        doc.append(f"Acteurs du réseau: {', '.join(map(str, data.Acteurs))}.\n")
        doc.append(
            f"Nombre de variables: {sum(1 for _ in model.component_data_objects(pyo.Var))}.\n"
        )
        doc.append(
            f"Nombre de contraintes: {sum(1 for _ in model.component_data_objects(pyo.Constraint))}.\n"
        )
        if results["Options d'optimisation"]["Prix_variable"]:
            doc.append("\n\nOptimisation des prix de vente en utilisant McCormick.")
        if results["Options d'optimisation"]["Contrainte_CO2"]:
            doc.append("Les producteurs doivent respecter une contrainte CO2 horaire.")
        else:
            doc.append("Les producteurs doivent respecter une contrainte CO2 globale.")
        del results["Options d'optimisation"]
        doc.append("\nPrix fixés entre Producteurs et consommateurs:\n\n")
        col_format = "|" + "c|" * (len(data.Prod) + 1)
        with doc.create(Tabular(col_format)) as table:
            table.add_hline()
            table.add_row([""] + [p for p in data.Prod])
            table.add_hline()
            for c in data.Cons:
                row = [c] + [pyo.value(model.Prix_vente_H2[p, c]) for p in data.Prod]
                table.add_row(row)
                table.add_hline()
    doc.append(NewPage())

    for method, res in results.items():
        if method == "Optimisations Individuelles":
            with doc.create(Section(method)):
                doc.append(f"Temps d'éxécution: {res['Temps']:.2f}sec")
                with doc.create(Subsection("Table de priorité")):
                    col_format = "|" + "c|" * (len(data.Acteurs) + 1)
                    doc.append(
                        "Dans le tableau de priorité, chaque ligne montre les résultats obtenus en priorisant l'acteur mentionné dans la première colomne.\n\n"
                    )
                    with doc.create(Tabular(col_format)) as table:
                        table.add_hline()
                        row = [""] + [a for a in data.Acteurs]
                        table.add_row(row)
                        table.add_hline()
                        for a in data.Acteurs:
                            row = [a] + [
                                f"{res['Table de priorité'][a][b]:.0f}"
                                for b in data.Acteurs
                            ]
                            table.add_row(row)
                            table.add_hline()
                with doc.create(Subsection("Point significatifs")):
                    points = ["Point Idéal", "Point Nadir", "Pire Point"]
                    col_format = "|" + "c|" * (len(points) + 1)
                    with doc.create(Tabular(col_format)) as table:
                        table.add_hline()
                        row = ["Acteur"] + [p for p in points]
                        table.add_row(row)
                        table.add_hline()
                        for a in data.Acteurs:
                            row = [a] + [f"{res[p][a]:.0f}" for p in points]
                            table.add_row(row)
                            table.add_hline()
                doc.append(NewPage())

        else:
            with doc.create(Section(method)):
                model = res["Model"]
                doc.append(
                    f"Valeur de la fonction objective: {pyo.value(model.objectif()):.2f}\n"
                )
                doc.append(f"Temps d'éxécution: {res['Temps']:.2f}sec")
                # Résultats généraux
                with doc.create(Subsection("Résultats généraux")):
                    with doc.create(Tabular("|c|c|c|")) as table:
                        table.add_hline()
                        table.add_row(("Acteur", "Fonction objective", "Satisfaction"))
                        table.add_hline()
                        for a in data.Acteurs:
                            table.add_row(
                                (
                                    a,
                                    f"{res[a]['Fonction objective']:.0f}",
                                    f"{res[a]['Satisfaction']:.2f}",
                                )
                            )
                            table.add_hline()
                # Informations Producteurs
                with doc.create(Subsection("Résultats Producteurs")):
                    doc.append(f"Impact CO2 moyen : {res['Impact CO2']} kgC02/kgH2\n\n")
                    col_format = "|" + "c|" * (len(data.Prod) + 1)
                    with doc.create(Tabular(col_format)) as table:
                        table.add_hline()
                        row = (
                            [""]
                            + [p for p in data.P_electrolyseur]
                            + [p for p in data.P_SMR]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Quantitée d'H2 produite
                        row = [
                            NoEscape(r"\rowcolor{lightgray} Qté. d'H2 prod - en kgH2")
                        ]
                        q = []
                        for p in data.Prod:
                            val = [
                                round(
                                    (
                                        sum(
                                            pyo.value(model.Q_H2_a_vendre[p, t])
                                            for t in data.Time
                                            if model.Q_H2_a_vendre[p, t].value
                                            is not None
                                        )
                                    ),
                                    2,
                                )
                            ]
                            q += val
                            row += val
                        table.add_row(row)
                        table.add_hline()
                        # Achat d'énergie
                        row = ["Total d'achat d'énergie - en MWh"]
                        for p in data.Prod:
                            row += [
                                f"{sum(pyo.value(model.Q_energie_total[p, t]) for t in data.Time):.2f}"
                            ]
                        table.add_row(row)
                        table.add_hline()
                        # Achat d'énergie
                        row = [
                            NoEscape(
                                r"\rowcolor{lightgray} Cout total d'achat d'énergie - en EUR"
                            )
                        ]
                        for p in data.Prod:
                            row += [f"{pyo.value(model.P_energie_total[p]):.2f}"]
                        table.add_row(row)
                        table.add_hline()
                        # Emissions CO2 total
                        row = ["Total emission CO2 - en kgCO2"]
                        em = []
                        for p in data.Prod:
                            val = [
                                round(
                                    (
                                        sum(
                                            pyo.value(model.Impact_prod[p, t])
                                            for t in data.Time
                                            if model.Impact_prod[p, t] is not None
                                        )
                                    ),
                                    2,
                                )
                            ]
                            em += val
                            row += val
                        table.add_row(row)
                        table.add_hline()
                        # Emissions CO2 /kgH2
                        row = [
                            NoEscape(
                                r"\rowcolor{lightgray} Emission CO2 - en kgCO2/kgH2"
                            )
                        ]
                        for p in range(len(data.Prod)):
                            if q[p] != 0:
                                row += [round(em[p] / q[p], 2)]
                            else:
                                row += [0]
                        table.add_row(row)
                        table.add_hline()
                        # Dimensionnement électrolyseur
                        row = (
                            ["Dim. Electrolyseur - en MW"]
                            + [
                                round((pyo.value(model.Taille_electrolyseur[p])), 2)
                                for p in data.P_electrolyseur
                            ]
                            + ["" for _ in data.P_SMR]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Utilisation électrolyseur A MODIF!!!
                        u = []
                        for p in data.P_electrolyseur:
                            u += [
                                round(
                                    (
                                        (
                                            sum(
                                                pyo.value(model.Q_energie_total[p, t])
                                                for t in data.Time
                                                if model.Q_energie_total[p, t]
                                                is not None
                                            )
                                        )
                                        / (
                                            pyo.value(model.Taille_electrolyseur[p])
                                            * data.Time_horizon
                                        )
                                    ),
                                    2,
                                )
                                if pyo.value(model.Taille_electrolyseur[p]) != 0
                                else 0
                            ]
                        row = (
                            ["Taux d'utilisa° Electrolyseur"]
                            + u
                            + ["" for _ in data.P_SMR]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Dimensionnement stockage
                        row = (
                            [NoEscape(r"\rowcolor{lightgray} Dim. Stockage - en kgH2")]
                            + [
                                round(pyo.value(model.Taille_stockage[p]), 2)
                                for p in data.P_electrolyseur
                            ]
                            + ["" for _ in data.P_SMR]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Utilisation stockage
                        u = []
                        for p in data.P_electrolyseur:
                            u += [
                                round(
                                    (
                                        (
                                            sum(
                                                pyo.value(model.Q_H2_stock_in[p, t])
                                                for t in data.Time
                                                if model.Q_H2_stock_in[p, t] is not None
                                            )
                                        )
                                        / pyo.value(model.Taille_stockage[p])
                                    ),
                                    2,
                                )
                                if pyo.value(model.Taille_stockage[p]) != 0
                                else 0
                            ]
                        row = (
                            [
                                NoEscape(
                                    r"\rowcolor{lightgray} Utilisa° Stockage - en \#cycles"
                                )
                            ]
                            + u
                            + ["" for _ in data.P_SMR]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Dimensionnement captage
                        row = (
                            ["Dim. Captage - en kgCO2"]
                            + ["" for _ in data.P_electrolyseur]
                            + [
                                round(pyo.value(model.Taille_captage[p]), 2)
                                for p in data.P_SMR
                            ]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # Utilisation captage
                        row = (
                            ["CO2 Capté - en kgCO2"]
                            + ["" for _ in data.P_electrolyseur]
                            + [
                                f"{sum(pyo.value(model.Captage[p, t]) for t in data.Time):.2f}"
                                for p in data.P_SMR
                            ]
                        )
                        table.add_row(row)
                        table.add_hline()
                        # CAPEX
                        cap = []
                        for p in data.P_electrolyseur:
                            cap += [
                                round(
                                    pyo.value(
                                        model.P_CAPEX_Electrolyseur[p]
                                        + model.P_CAPEX_Stockage[p]
                                    )
                                    * data.Time_horizon,
                                    0,
                                )
                            ]
                        for p in data.P_SMR:
                            cap += [
                                round(
                                    pyo.value(model.P_CAPEX_Captage[p])
                                    * data.Time_horizon,
                                    0,
                                )
                            ]
                        row = [NoEscape(r"\rowcolor{lightgray} CAPEX - en EUR")] + cap
                        table.add_row(row)
                        table.add_hline()
                        # Prix moyen achat énergie
                        enr = []
                        for p in data.Prod:
                            q_tot = sum(
                                pyo.value(model.Q_energie_total[p, t])
                                for t in data.Time
                            )
                            if q_tot != 0:
                                enr += [
                                    round(
                                        (pyo.value(model.P_energie_total[p]) / q_tot), 0
                                    )
                                ]
                            else:
                                enr += [0]
                        row = ["Prix moyen achat énergie - en EUR/MWh"] + enr
                        table.add_row(row)
                        table.add_hline()
                        # LCOH
                        row = [NoEscape(r"\rowcolor{lightgray}LCOH - en EUR/kgH2")]
                        lcoh = []
                        for p in range(len(data.Prod)):
                            q_tot = sum(
                                pyo.value(model.Q_energie_total[data.Prod[p], t])
                                for t in data.Time
                            )
                            if q_tot != 0:
                                if p < len(data.P_electrolyseur):
                                    lcoh += [
                                        f"{(enr[p] + cap[p] / q_tot) * (1 / data.Rendement_electrolyseur[data.Prod[p]]):.2f}"
                                    ]
                                else:
                                    lcoh += [
                                        f"{(enr[p] + cap[p] / q_tot) * (1 / data.Rendement_vaporeformage[data.Prod[p]]):.2f}"
                                    ]
                            else:
                                lcoh += [0]
                        table.add_row(row + lcoh)
                        table.add_hline()
                        # Part de l'énergie dans le LCOH
                        row = ["Part de l'énergie dans le LCOH - en %"]
                        for p in range(len(data.Prod)):
                            if lcoh[p] != 0:
                                if p < len(data.P_electrolyseur):
                                    row += [
                                        f"{(((enr[p]) * (1 / data.Rendement_electrolyseur[data.Prod[p]])) / float(lcoh[p])) * 100:.0f}"
                                    ]
                                else:
                                    row += [
                                        f"{(((enr[p]) * (1 / data.Rendement_vaporeformage[data.Prod[p]])) / float(lcoh[p])) * 100:.0f}"
                                    ]
                            else:
                                row += [0]
                        table.add_row(row)
                        table.add_hline()

                with doc.create(Subsection("Sankey graph")):
                    with doc.create(Figure(position="h!")) as fig:
                        fig.add_image(res["Sankey"], width=NoEscape(r"0.5\textwidth"))
                doc.append(NewPage())
    with doc.create(Section("Evolution de l'algorithme max min séquentiel")):
        with doc.create(Figure(position="h!")) as fig:
            fig.add_image(
                results["Max min satisfaction"]["Evolution maxmin"],
                width=NoEscape(r"0.8\textwidth"),
            )
            fig.add_caption(
                "Comparaison de l'évolution de la satisfaction avec l'algorithme max min"
            )
    with doc.create(Section("Comparaison des méthodes")):
        # data = [ [ _ for _ in labels_acteurs ] for _ in labels_fn ]
        labels_fn = ["Goal Programming", "Max min satisfaction"]
        data_satisf = [
            [results[method][a]["Satisfaction"] for a in data.Acteurs]
            for method in labels_fn
        ]
        plot.plot_data(
            "Resultats\\temp.png", data_satisf, labels_fn, data.Acteurs, "", "", ""
        )
        with doc.create(Figure(position="h!")) as fig:
            fig.add_image("temp.png", width=NoEscape(r"0.8\textwidth"))
            fig.add_caption("Comparaison of the satisfaction of the different methods")

    doc.generate_pdf(filename, clean_tex=True, compiler="pdflatex")
    if os.path.exists("Resultats\\temp.png"):
        os.remove("Resultats\\temp.png")

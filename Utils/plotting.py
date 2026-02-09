import plotly.graph_objects as go
import pyomo.environ as pyo
import os
import plotly.colors as pc
import matplotlib.pyplot as plt
import Donnees.data as data


def generate_colors(n, colorscale="Viridis"):
    # fonction générée par ia : Generate n distinct colors from a given Plotly colorscale
    return pc.sample_colorscale(colorscale, [i / max(n - 1, 1) for i in range(n)])


def sankey_flow_diag(model: pyo.ConcreteModel, filename: str) -> None:
    """
    Generate and save a Sankey diagram visualizing hydrogen and energy flows.

    Args:
        model (pyo.ConcreteModel):
            The pyomo model
        filename (str):
            Path to the output image file where the Sankey diagram
            will be saved. The directory will be created if it does not exist.
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    n_prod = len(data.Prod)
    n_cons = len(data.Cons)
    n_energy = len(data.Energie)

    prod_colors = generate_colors(n_prod, "Viridis")
    cons_colors = generate_colors(n_cons, "Plasma")
    energy_color = "#1f77b4"

    labels = data.Acteurs + data.Energie
    node_colors = prod_colors + cons_colors + [energy_color] * n_energy

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=labels,
                    color=node_colors,
                ),
                link=dict(
                    source=[
                        e + n_prod + n_cons for _ in data.Prod for e in range(n_energy)
                    ]
                    + [i for _ in data.Cons for i in range(n_prod)],
                    target=[i for i in range(n_prod) for _ in range(n_energy)]
                    + [j + n_prod for j in range(n_cons) for _ in data.Prod],
                    value=[
                        *[
                            sum(
                                pyo.value(model.Q_energie[i, e, t])
                                * data.Rendement_electrolyseur[i]
                                for t in data.Time
                            )
                            for i in data.P_electrolyseur
                            for e in data.Energie
                        ],
                        *[
                            sum(
                                pyo.value(model.Q_energie[i, e, t])
                                * data.Rendement_vaporeformage[i]
                                for t in data.Time
                            )
                            for i in data.P_SMR
                            for e in data.Energie
                        ],
                        *[
                            sum(pyo.value(model.Q_H2_vendu[i, j, t]) for t in data.Time)
                            for j in data.Cons
                            for i in data.Prod
                        ],
                    ],
                ),
            )
        ]
    )

    fig.update_layout(title_text="Flow de distribution d'H2", font_size=10)
    fig.write_image(filename)


# Fonction pour générer un plots d'histogrammes
# data = [ [ _ for _ in labels_acteurs ] for _ in labels_fn ]
def plot_data(
    file_name: str,
    data: list[list[float]],
    labels_fn: list[str],
    labels_acteurs: list[str],
    titre: str,
    titre_legende: str,
    y_axis_titre: str,
) -> None:
    """
    Generic function to generate several histograms aligned with one another

    Args:
        file_name (str):
            Path where the generated plot image will be saved.
        data (list[list[float]]):
            2D list of numerical values where each inner list
            corresponds to the fn value of actor.
            - inner list: the value of the bar
            - outer list: define one histogram
        labels_fn (list[str]):
            - Labels corresponding to each function: values of bars accross histograms
        labels_acteurs (list[str]):
            Labels for each actor (subplots).
        titre (str):
            Main title for the entire figure.
        titre_legende (str):
            Title for the legend describing the function labels.
        y_axis_titre (str):
            Label for the shared y-axis.
    """

    def generate_colors(x):
        # fonction générée par ia
        cmap = plt.colormaps["tab10"]  # Utilise un colormap avec couleurs distinctes
        color_map = [cmap(i / 10) for i in range(10)]
        return color_map[:x]

    n_indices = len(data[0])
    n_functions = len(data)

    colors = generate_colors(n_functions)

    # Création des sous-plots alignés horizontalement
    fig, axes = plt.subplots(1, n_indices, figsize=(3 * n_indices, 4), sharey=True)

    # Si un seul index, convertir axes en liste pour éviter les erreurs
    if n_indices == 1:
        axes = [axes]

    # Tracé des histogrammes
    for i in range(n_indices):
        values = [f[i] for f in data]

        # Création de l'histogramme
        bars = axes[i].bar(labels_fn, values, color=colors)

        axes[i].set_title(labels_acteurs[i])
        axes[i].set_xticks([])
        axes[i].grid(axis="y", linestyle="--", alpha=0.7)
    axes[0].set_ylabel(y_axis_titre)
    axes[-1].legend(
        bars,
        labels_fn,
        title=titre_legende + "\n",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
    )
    fig.suptitle(titre)
    plt.savefig(file_name, bbox_inches="tight", dpi=300)

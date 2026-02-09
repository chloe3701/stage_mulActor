from Donnees.data import (
    Prod,
    Acteurs,
    Cons,
    Prix_vente_H2,
    P_electrolyseur,
    Rendement_vaporeformage,
    Impact_vaporeformage,
    CAPEX_t_captage,
    P_SMR,
    Time_horizon,
    Time,
    Demande_H2,
    CAPEX_t_electrolyseur,
    Prix_energie,
    Production_elec,
    Rendement_electrolyseur,
)
import config as config
import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.termination.default import DefaultMultiObjectiveTermination
from pymoo.optimize import minimize


def point_nadir(f_nadir: dict[str, float]) -> dict[str, float]:
    """
    Calculate the nadir point for a multi-objective optimization problem.

    The nadir point represents the worst objective function values among
    the Pareto-optimal solutions.

    For problems with two or fewer objectives, the input nadir point is returned directly
    as it is computed using sequential mono-objective optimisations.

    For more than two objectives, the function sets up and solves a multi-objective
    optimization problem using NSGA-II to estimate the nadir points.
    NB: This part is experimental and not working properly. Therefore we return the
    nadir point inputed.

    Args:
        f_nadir (dict[str, float]):
            The estimation of the nadir point computed previously using sequential
            mono-objective optimisation.

    Returns:
        dict[str, float]:
            In theory: a better approximate of the nadir point using NSGA-II.
            In practice: returns the estimation in the input.
    """
    # Cas où 2 objectifs
    if len(Acteurs) <= 2:
        return f_nadir

    return f_nadir

    # Ne fonctionne pas correctement

    if not config.optim_prix:
        Names = Prod.copy()
        # Si tout les prix sont les mêmes, on optimise pas le consommateur
        for c in Cons:
            valeurs = [sous_dico[c] for sous_dico in Prix_vente_H2.values()]
            if len(set(valeurs)) > 1:
                Names.append(c)
        if len(Names) <= 2:
            return f_nadir
    nb_Prod = len(Prod)
    nb_P_elec = len(P_electrolyseur)
    nb_P_SMR = len(P_SMR)
    nb_Cons = len(Cons)

    # Cas où 3 ou + objectifs
    class MyProblem(ElementwiseProblem):
        def __init__(self):
            self.nb_var = [[0 for _ in Cons] for _ in range(nb_Prod - 1)]

            for p in range(nb_Prod - 1):
                for c in range(nb_Cons):
                    self.nb_var[p][c] = Time_horizon

            self.total_vars = (nb_Prod - 1) * nb_Cons * Time_horizon

            super().__init__(
                n_var=self.total_vars,
                # n_obj = len(Acteurs),
                n_obj=5,
                # n_ieq_constr = 2 * nb_Cons * Time_horizon,
                n_ieq_constr=nb_Cons * Time_horizon,
                xl=np.zeros(self.total_vars),
                xu=np.array(
                    [
                        Demande_H2[c][t]
                        for _ in range(nb_Prod - 1)
                        for c in Cons
                        for t in Time
                    ]
                ),
            )

        def decode(self, x):
            """
                Reshape and round the decision variable array for easier manipulation.

            Args:
                x (numpy array):
                    A flat 1D array representing decision variables
                    for production allocation over producers, consumers,
                    and time steps.

            Returns:
                numpy array:
                    A 3D array reshaped to dimensions
                    (number_of_producers - 1, number_of_consumers, time_horizon),
                    with values rounded to two decimal places.
            """
            x_reshaped = x.reshape((nb_Prod - 1, nb_Cons, Time_horizon))
            x_reshaped = np.round(x_reshaped, 2)
            return x_reshaped

        def _evaluate(self, x, out, *args, **kwargs):
            flux = self.decode(x)
            flux_P3 = []

            # Objectifs
            # In pymoo, minimization
            F = []
            for p in range(nb_Prod):
                # P_electrolyseur
                if p < nb_P_elec:
                    f = -np.sum(
                        np.sum(
                            (
                                flux[p, c, :]
                                * Prix_vente_H2[P_electrolyseur[p]][Cons[c]]
                                for c in range(nb_Cons)
                            )
                        )
                    )
                    flux_max = np.max(np.sum(flux[p, :, :], axis=0))
                    capex = CAPEX_t_electrolyseur[P_electrolyseur[p]] * Time_horizon
                    f += flux_max * capex
                    if Prod[p] == "P1_electrolyse(avec PV)":
                        p_elec = (
                            np.sum(
                                [
                                    np.sum(flux[p, c, t] for c in range(nb_Cons))
                                    * min(
                                        Prix_energie["Elec_reseau"][t],
                                        Prix_energie["PV"][t]
                                        if Production_elec["PV"][t] > 0
                                        else 10_000,
                                    )
                                    for t in Time
                                ]
                            )
                            / Rendement_electrolyseur[P_electrolyseur[p]]
                        )
                    else:
                        p_elec = (
                            np.sum(
                                [
                                    np.sum(flux[p, c, t] for c in range(nb_Cons))
                                    * Prix_energie["Elec_reseau"][t]
                                    for t in Time
                                ]
                            )
                            / Rendement_electrolyseur[P_electrolyseur[p]]
                        )
                    f += p_elec
                    F.append(f)
                # P_smr => Contrainte C02 horaire
                else:
                    p_ = p - nb_P_elec
                    # On fixe manuellement un acteur qui doit remplir la demande manquante
                    # Pour augmenter la proba d'obtenir une solution
                    if p_ + 1 == nb_P_SMR:
                        for c in range(nb_Cons):
                            flux_P3.append([])
                            for t in Time:
                                flux_P3[c].append(
                                    max(
                                        Demande_H2[Cons[c]][t]
                                        - np.sum(
                                            flux[p_var, c, t]
                                            for p_var in range(nb_Prod)
                                            if p_var != p
                                        ),
                                        0,
                                    )
                                )
                    else:
                        print("Erreur pas impplémenté pour P_SMR >=2")
                        exit()
                    # Profit de vente d'H2
                    f = -sum(
                        np.sum(flux_P3[c] * Prix_vente_H2[P_SMR[p_]][Cons[c]])
                        for c in range(nb_Cons)
                    )
                    # Fixe le CAPEX du captage
                    if config.emission_CO2_heure:
                        flux_max = np.max(np.sum(flux_P3[:][:], axis=0))
                        captage = max(
                            flux_max * Impact_vaporeformage[P_SMR[p_]] - 3.5, 0
                        )
                        capex = CAPEX_t_captage[P_SMR[p_]] * Time_horizon
                        f += capex * captage
                    else:
                        print("Error: Contrainte globale pas encore implémentée")
                        exit()
                    # Cout de production
                    p_gaz = sum(
                        np.sum(
                            [
                                (flux_P3[c][t] * Prix_energie["Gaz"][t])
                                / Rendement_vaporeformage[P_SMR[p_]]
                                for t in Time
                            ]
                        )
                        for c in range(nb_Cons)
                    )
                    f += p_gaz
                    F.append(f)
            # Consommateurs
            for c in range(nb_Cons):
                if np.sum(Demande_H2[Cons[c]]) > 0:
                    dem = np.sum(Demande_H2[Cons[c]])
                    f = np.sum(
                        np.sum(
                            flux[p, c, :] * Prix_vente_H2[Prod[p]][Cons[c]]
                            for p in range(nb_Prod - 1)
                        )
                    )
                    f += sum(flux_P3[c] * Prix_vente_H2[P_SMR[p_]][Cons[c]])
                    f = f / dem
                else:
                    f = 0
                F.append(f)
            # Contrainte : sum_p flux[p][c][t] == Demande_H2[c][t]
            # vu que P3 complète: sa valeur doit être >=0
            G = []
            for c in range(nb_Cons):
                for t in Time:
                    G.append(-flux_P3[c][t])
            out["F"] = np.array(F)
            out["G"] = np.array(G)

    # Definition de mon problème, version simplifiée du model pyomo
    problem = MyProblem()
    algorithm = NSGA2(
        pop_size=100,
        sampling=FloatRandomSampling(),
        crossover=SBX(eta=15, prob=0.8),
        mutation=PM(eta=20, prob=0.2),
        eliminate_duplicates=True,
    )
    termination = DefaultMultiObjectiveTermination(
        xtol=1e-1, cvtol=1e-1, ftol=1e-1, period=20, n_max_gen=150, n_max_evals=100000
    )

    res = minimize(
        problem, algorithm, termination, seed=3, save_history=True, verbose=True
    )

    F = res.F
    # points_nadir = []
    for i, a in enumerate(Acteurs):
        nad = np.max(F[:, i])
        ideal = np.min(F[:, i])
        print(f"nad {a} : {nad}")
        print(f"ideal {a} : {ideal}")

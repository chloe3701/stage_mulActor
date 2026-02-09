import csv
import Donnees.data as data


# Read data of csv file
def read_data(
    csv_file: str, Time_horizon: int
) -> tuple[
    dict[str, list[float]],
    dict[str, list[float]],
    dict[str, list[float]],
    dict[str, list[float]],
]:
    """
    Reads and extracts structured data from a CSV file for a given time horizon.

    Args:
        csv_file (str):
            Path to the CSV file to read.
        Time_horizon (int):
         Number of time periods (rows) to read from the file.

    Raises:
        ValueError: If an expected key (producer, consumer, or energy type) is missing in the CSV headers.

    Returns:
        tuple[ dict[str, list[float]], dict[str, list[float]], dict[str, list[float]], dict[str, list[float]], ]:
            - Electricity production by source
            - CO2 impact by electricity source
            - Energy prices by energy type
            - Hydrogen demand by consumer
    """
    Production_elec = {}
    Impact_elec = {}
    Prix_energie = {}
    Demande_H2 = {}

    with open(csv_file, "r") as file:
        reader = csv.reader(file, delimiter=";")

        # Récupération des index
        index = {}
        headers = next(reader)
        for i, header in enumerate(headers):
            index[header] = i

        for e in data.Electricite:
            if e not in index:
                raise ValueError(f"'{e}' n'existe pas dans le fichier CSV.")
            Production_elec[e] = []
            if e + "_impact" not in index:
                raise ValueError(f"'{e}'_impact n'existe pas dans le fichier CSV.")
            Impact_elec[e] = []
        for e in data.Energie:
            if e + "_prix" not in index:
                raise ValueError(f"'{e}'_prix n'existe pas dans le fichier CSV.")
            Prix_energie[e] = []
        for c in data.Cons:
            if c not in index:
                raise ValueError(f"'{c}'_prix n'existe pas dans le fichier CSV.")
            Demande_H2[c] = []

        # Passer les lignes d'information
        for _ in range(3):
            next(reader, None)

        # Aller au début des données souhaitées
        for _ in range(data.debut_data):
            next(reader, None)

        # Complétion des données
        for t, row in enumerate(reader):
            if t >= Time_horizon:
                break
            for e in data.Electricite:
                Production_elec[e].append(float(row[index[e]]))
                Impact_elec[e].append(float(row[index[e + "_impact"]]))
            for e in data.Energie:
                Prix_energie[e].append(float(row[index[e + "_prix"]]))
            for c in data.Cons:
                Demande_H2[c].append(round(float(row[index[c]]), 2))
    return Production_elec, Impact_elec, Prix_energie, Demande_H2

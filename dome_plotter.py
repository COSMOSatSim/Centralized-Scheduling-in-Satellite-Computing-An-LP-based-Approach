import json
import sys
import os
from matplotlib import pyplot as plt

PATH = "Generated_datasets/simulation_dataset.json"
PLOT_PATH = "Dome_Plots/"

# Ensure output directory exists
if not os.path.exists(PLOT_PATH):
    os.makedirs(PLOT_PATH, exist_ok=True)
elif not os.path.isdir(PLOT_PATH):
    raise RuntimeError(f"Path '{PLOT_PATH}' exists and is not a directory")

def clean_name(name: str) -> str:
    return name.replace("STARLINK", "").replace("[DTC]", "").strip()

def open_generated_dataset(config_path: str) -> dict:
    with open(config_path, "r") as file:
        simulation_dataset = json.load(file)
    return simulation_dataset


def plot_dome(snapshot: dict):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    xs = [satellite["position"][0] for satellite in snapshot]
    ys = [satellite["position"][1] for satellite in snapshot]
    zs = [satellite["position"][2] for satellite in snapshot]

    ax.scatter(xs, ys, zs)

    for satellite in snapshot:
        x, y, z = satellite["position"]
        ax.text(x, y, z, satellite["satellite"])

    plt.savefig(f"{PLOT_PATH}dome_plot.png")
    plt.close()


def zoom_3d(ax: plt.Axes, factor: float):
    """
    Zoom su un plot 3D riducendo il range degli assi.

    - factor > 1 → zoom in
    - factor < 1 → zoom out
    """
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_mid = sum(x_limits) / 2
    y_mid = sum(y_limits) / 2
    z_mid = sum(z_limits) / 2

    x_range = (x_limits[1] - x_limits[0]) / factor
    y_range = (y_limits[1] - y_limits[0]) / factor
    z_range = (z_limits[1] - z_limits[0]) / factor

    ax.set_xlim3d(x_mid - x_range / 2, x_mid + x_range / 2)
    ax.set_ylim3d(y_mid - y_range / 2, y_mid + y_range / 2)
    ax.set_zlim3d(z_mid - z_range / 2, z_mid + z_range / 2)


def set_3d_view(ax, elev: int = 30, azim: int = 45):
    """
    Imposta la prospettiva di un grafico 3D.

    Parametri:
    - ax: l'oggetto Axes3D
    - elev: angolo di elevazione (gradi), 0 = piano xy
    - azim: angolo azimutale (gradi), rotazione attorno all'asse z
    - distance: opzionale, distanza della “camera” dal centro (float)
    """
    ax.view_init(elev=elev, azim=azim)


def _set_axes_equal(ax: plt.Axes):
    """Set 3D plot axes to equal scale.

    This makes spheres/positions look correct instead of distorted.
    """
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    y_range = abs(y_limits[1] - y_limits[0])
    z_range = abs(z_limits[1] - z_limits[0])

    max_range = max(x_range, y_range, z_range)

    x_mid = sum(x_limits) / 2.0
    y_mid = sum(y_limits) / 2.0
    z_mid = sum(z_limits) / 2.0

    ax.set_xlim3d(x_mid - max_range / 2, x_mid + max_range / 2)
    ax.set_ylim3d(y_mid - max_range / 2, y_mid + max_range / 2)
    ax.set_zlim3d(z_mid - max_range / 2, z_mid + max_range / 2)


def plot_dome_network(snapshot: dict, save_path: str = None, annotate: bool = True):
    """Plot satellites as points and draw lines to their neighbors.

    - `snapshot` is the list of satellite dicts (each must have `satellite` and `position`).
    - neighbor names are read from `satellite['neighbors_metrics'][i]['name']`.

    The function avoids drawing duplicate edges by tracking drawn pairs.
    """

    sat_info = {sat.get("satellite"): tuple(sat.get("position")) for sat in snapshot}

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")


    # Draw edges (avoid duplicates)
    drawn = set()  # Coppia già disegnata
    for sat in snapshot:
        name = sat.get("satellite")
        pos = sat.get("position")
        
        ax.text(pos[0], pos[1], pos[2], clean_name(name), fontsize=6, alpha=0.8)  # Name label
        ax.scatter(pos[0], pos[1], pos[2], s=20, c="tab:blue", alpha=0.8)

        p1 = (pos[0], pos[1], pos[2])
        neighbors = sat.get("neighbors_metrics")

        for neigh in neighbors:
            nname = neigh.get("name")
            p2 = sat_info.get(nname)

            link = tuple(sorted((name, nname)))
            if link in drawn:
                continue
            drawn.add(link)
            ax.plot(
                [p1[0], p2[0]],
                [p1[1], p2[1]],
                [p1[2], p2[2]],
                color="gray",
                linewidth=0.4,
                linestyle='--',
                alpha=0.5,
            )


    _set_axes_equal(ax)
    set_3d_view(ax, elev=30, azim=30)
    zoom_3d(ax, factor=1.3)
    #plt.show()
    plt.savefig(save_path, dpi=200)
    plt.close()


snapshot = open_generated_dataset(PATH)[0]["satellites"]
plot_dome_network(snapshot, save_path=f"{PLOT_PATH}dome_network.png", annotate=True)

from mplsoccer import Pitch
import matplotlib.pyplot as plt

def plot_player_position_usage(position_minutes, player_name="Player Name"):
    """
    position_minutes: list of dicts like:
        [{'position': 'RCB', 'minutes': 3000},
         {'position': 'LCB', 'minutes': 2000},
         {'position': 'CCB', 'minutes': 800},
         {'position': 'RB', 'minutes': 400}]
    """
    # Position map (rough coordinates on a pitch)
    pos_coords = {
        "GK": (6, 40),
        "LB": (20, 10), "LCB": (30, 25), "CCB": (30, 40), "RCB": (30, 55), "RB": (20, 70),
        "LWB": (35, 10), "RWB": (35, 70),
        "LM": (50, 10), "CM": (50, 40), "RM": (50, 70),
        "LAM": (60, 20), "AM": (60, 40), "RAM": (60, 60),
        "LW": (80, 10), "SS": (80, 30), "CF": (80, 40), "RW": (80, 70)
    }

    total_minutes = sum([p["minutes"] for p in position_minutes])
    primary_position = max(position_minutes, key=lambda x: x["minutes"])["position"]

    pitch = Pitch(pitch_type='statsbomb', line_zorder=2, pitch_color='white')
    fig, ax = pitch.draw(figsize=(10, 6))
    pitch.annotate(player_name, (60, 5), ax=ax, ha='center', fontsize=14, fontweight='bold')

    for p in position_minutes:
        pos = p["position"]
        minutes = p["minutes"]
        pct = minutes / total_minutes * 100
        if pos not in pos_coords:
            continue

        x, y = pos_coords[pos]
        # Highlight primary position
        if pos == primary_position:
            ax.add_patch(plt.Circle((x, y), 3.5, color='black', zorder=3))
        pitch.scatter(x, y, ax=ax, color='blue', s=150, zorder=4)
        pitch.annotate(f"{pct:.0f}%", (x, y + 3), ax=ax, ha='center', fontsize=10)

    ax.set_title(f"Positional Usage – {player_name}", fontsize=16)
    plt.tight_layout()
    plt.show()

sample_data = [
    {'position': 'RCB', 'minutes': 3000},
    {'position': 'LCB', 'minutes': 2000},
    {'position': 'CCB', 'minutes': 800},
    {'position': 'RB', 'minutes': 400}
]

plot_player_position_usage(sample_data, player_name="Cristhian Mosquera")

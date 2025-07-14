import json
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
    
TOP_N_ARTISTS= None
NODE_SIZE = 300
FONT_SIZE = 8
FIGURE_SIZE = (20, 20)

with open("/home/jasmine/PROJECTS/riffnet/artist_relationships.json", "r") as f:
    edges = json.load(f)

try:
    features_df = pd.read_csv("/home/jasmine/PROJECTS/riffnet/ALL_FEATURES_1010.csv")
    top_artists = set(features_df.nlargest(TOP_N_ARTISTS, "popularity")["name"]) if TOP_N_ARTISTS else None
except FileNotFoundError:
    top_artists = None

G = nx.DiGraph()  # Use DiGraph for similarity (asymmetric), will handle tour/festival as undirected\n",
for edge in edges:
    source = edge["origin"]
    target = edge["target"]
    edge_type = edge["type"]
    weight = edge["weight"]
    if top_artists and (source not in top_artists or target not in top_artists):
        continue
    # For tour and festival edges, add both directions to simulate undirected edges\n",
    if edge_type in ["tour", "festival"]:
        G.add_edge(source, target, type=edge_type, weight=weight, **{k: v for k, v in edge.items() if k not in ["origin", "target", "type", "weight"]})
        G.add_edge(target, source, type=edge_type, weight=weight, **{k: v for k, v in edge.items() if k not in ["origin", "target", "type", "weight"]})
    else:  # Similarity edges are directed\n",
        G.add_edge(source, target, type=edge_type, weight=weight)

print(f"Graph created with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

edge_colors = {"similarity": "blue",
               "tour": "red",
               "festival": "green"}

edge_widths = [G[u][v]["weight"] * 2 for u, v in G.edges()]  # Scale weight for visibility\n",
edge_colors_list = [edge_colors[G[u][v]["type"]] for u, v in G.edges()]

pos = nx.spring_layout(G, k=0.5, iterations=50)
plt.figure(figsize=FIGURE_SIZE)
nx.draw_networkx_nodes(G, pos, node_size=NODE_SIZE, node_color="lightblue"),
nx.draw_networkx_edges(G, pos, edge_color=edge_colors_list, width=edge_widths, alpha=0.7)
nx.draw_networkx_labels(G, pos, font_size=FONT_SIZE)
plt.title("Artist Relationships Network\n(Blue: Similarity, Red: Tour, Green: Festival)")
plt.axis("off")

from matplotlib.lines import Line2D
legend_elements = [Line2D([0], [0], color="blue", lw=2, label="Similarity"),
                   Line2D([0], [0], color="red", lw=2, label="Tour"),
                   Line2D([0], [0], color="green", lw=2, label="Festival")]
plt.legend(handles=legend_elements, loc="upper right")
plt.show()
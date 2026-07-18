# packages/graph/visualizer.py

from pathlib import Path

class GraphVisualizer:

    @staticmethod
    def save_png(graph, filename: str = "graph.png"):

        png = graph.get_graph().draw_mermaid_png()

        Path(filename).write_bytes(png)

        print(f"✅ Graph saved as {filename}")
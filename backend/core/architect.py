import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DIAGRAM_PATH = "data/indexes/architecture.png"


class ArchitectureDiagramGenerator:
    """
    Generates a layered architecture diagram from parsed files.
    Groups files into layers: API → Core → Models → Utils
    """

    LAYER_KEYWORDS = {
        "api":     ["api", "route", "router", "endpoint", "view", "controller"],
        "core":    ["core", "service", "engine", "pipeline", "processor"],
        "models":  ["model", "schema", "entity", "dto", "type"],
        "data":    ["db", "database", "store", "repository", "cache", "vector"],
        "utils":   ["util", "helper", "config", "setting", "constant", "common"],
    }

    LAYER_COLORS = {
        "api":    "#667eea",
        "core":   "#764ba2",
        "models": "#f093fb",
        "data":   "#4facfe",
        "utils":  "#43e97b",
        "other":  "#a8a8a8",
    }

    LAYER_ORDER = ["api", "core", "models", "data", "utils", "other"]

    def generate(self, parsed_files: list, output_path: str = DIAGRAM_PATH) -> dict:
        """Build and save architecture diagram. Returns layer assignment map."""
        layers = self._assign_layers(parsed_files)
        self._draw(layers, parsed_files, output_path)
        return layers

    def _assign_layers(self, parsed_files: list) -> dict:
        """Assign each file to an architecture layer."""
        layers = {layer: [] for layer in self.LAYER_ORDER}
        for pf in parsed_files:
            path_lower = pf.file_path.lower()
            assigned   = False
            for layer, keywords in self.LAYER_KEYWORDS.items():
                if any(kw in path_lower for kw in keywords):
                    layers[layer].append(pf.file_path)
                    assigned = True
                    break
            if not assigned:
                layers["other"].append(pf.file_path)
        # Remove empty layers
        return {k: v for k, v in layers.items() if v}

    def _draw(self, layers: dict, parsed_files: list, output_path: str):
        file_info = {pf.file_path: pf for pf in parsed_files}

        fig, ax = plt.subplots(figsize=(16, 10))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, len(layers) * 2.5 + 1)
        ax.axis("off")
        ax.set_facecolor("#f8f9fa")
        fig.patch.set_facecolor("#f8f9fa")

        ax.text(5, len(layers) * 2.5 + 0.5, "System Architecture",
                ha="center", va="center", fontsize=16,
                fontweight="bold", color="#2d2d2d")

        y = len(layers) * 2.5 - 0.5

        for layer_name in self.LAYER_ORDER:
            if layer_name not in layers:
                continue

            files  = layers[layer_name]
            color  = self.LAYER_COLORS.get(layer_name, "#aaa")
            height = 1.8

            # Layer background
            rect = mpatches.FancyBboxPatch(
                (0.2, y - height + 0.1), 9.6, height,
                boxstyle="round,pad=0.1",
                facecolor=color + "22",
                edgecolor=color,
                linewidth=2,
            )
            ax.add_patch(rect)

            # Layer label
            ax.text(0.5, y - height / 2 + 0.1, layer_name.upper(),
                    va="center", fontsize=9, fontweight="bold",
                    color=color, rotation=90)

            # File boxes inside the layer
            n = len(files)
            x_start = 1.0
            x_step  = min(8.5 / max(n, 1), 2.5)

            for i, fp in enumerate(files):
                x   = x_start + i * x_step
                pf  = file_info.get(fp)
                fn_count  = len(pf.functions) if pf else 0
                cls_count = len(pf.classes) if pf else 0
                fname     = os.path.basename(fp)

                # File box
                box = mpatches.FancyBboxPatch(
                    (x, y - height + 0.3), min(x_step - 0.15, 2.3), height - 0.5,
                    boxstyle="round,pad=0.08",
                    facecolor="white",
                    edgecolor=color,
                    linewidth=1.5,
                )
                ax.add_patch(box)

                # Filename
                ax.text(x + 0.15, y - 0.35, fname,
                        fontsize=7.5, fontweight="bold",
                        color="#2d2d2d", va="top",
                        wrap=True)

                # Stats
                ax.text(x + 0.15, y - 0.65,
                        f"fn:{fn_count}  cls:{cls_count}",
                        fontsize=6.5, color="#666", va="top")

            y -= height + 0.4

        # Legend
        legend_x = 0.3
        for layer_name, color in self.LAYER_COLORS.items():
            if layer_name in layers:
                patch = mpatches.Patch(color=color, label=layer_name.capitalize())
                ax.add_patch(mpatches.FancyBboxPatch(
                    (legend_x, 0.1), 0.3, 0.25,
                    facecolor=color, edgecolor="none",
                ))
                ax.text(legend_x + 0.35, 0.22, layer_name.capitalize(),
                        fontsize=7, va="center", color="#444")
                legend_x += 1.4

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"🏗️  Architecture diagram saved → {output_path}")
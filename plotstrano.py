import pandas as pd
import matplotlib.pyplot as plt
import os

# Percorso al file
file_path = "csv.csv"  # Modifica se necessario

# Cartella per salvare eventuali grafici
output_dir = "grafici_output"
os.makedirs(output_dir, exist_ok=True)

# Caricamento CSV con tabulazione
df = pd.read_csv(file_path, sep="\t")
df.columns = [col.strip() for col in df.columns]

# Plot
plt.figure(figsize=(10, 8))
x = df.index

for col in df.columns:
    # Converti "mu" in "μ" e "lambda" in "λ" nella legenda
    label = col.replace("mu", "μ").replace("lambda", "λ")
    plt.plot(x, df[col], linestyle='-', label=label, alpha=0.9)

plt.xlabel('Completed Task',fontsize=20)
plt.ylabel('Response Time (Rᵣ,ᵢ,ⱼ)',fontsize=20)

# Asse X: da 1 a 200 con step di 100
plt.xticks([i for i in range(1, 1201, 200)],fontsize=20)
plt.yticks(fontsize=20)

plt.ylim(bottom=0)
plt.grid(axis='y', linestyle='--', alpha=0.6)
plt.legend(fontsize=20)
plt.tight_layout()

# Salvataggio (opzionale)
plt.savefig(os.path.join(output_dir, 'line_plot_csv.png'), dpi=300)

# Mostra a video
plt.show()
plt.close()

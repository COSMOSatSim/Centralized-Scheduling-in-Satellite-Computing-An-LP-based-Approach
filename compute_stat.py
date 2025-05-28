#!/usr/bin/env python3
import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox

def process_file(input_path):
    """
    Processa un singolo CSV grezzo, genera un file *_stats.csv con le statistiche richieste.
    """
    df = pd.read_csv(input_path)
    # Rinomina e pulizia colonna Num Hops
    df.rename(columns=lambda x: x.strip(), inplace=True)
    if 'Num Hops' in df.columns:
        df['Num Hops'] = pd.to_numeric(df['Num Hops'], errors='coerce')
    else:
        df['Num Hops'] = pd.NA

    # 1) elimina righe con Exec_after_set nullo
    filtered = df[df['Exec_after_set'].notna()].copy()

    # 2) Totali
    total = len(filtered)

    # 3) Fallimenti
    failed = filtered['TMAX_exceeded'].sum()
    pct_failed = (failed / total * 100) if total > 0 else 0.0

    # 4) Success
    success_df = filtered[filtered['TMAX_exceeded'] == False]
    success_total = len(success_df)

    # 5) Priorità
    high = filtered[filtered['Task Priority'] == 'high']
    low  = filtered[filtered['Task Priority'] == 'low']

    failed_high = high['TMAX_exceeded'].sum()
    failed_low  = low['TMAX_exceeded'].sum()
    pct_high    = ( failed_high / total * 100) if failed_high > 0 else 0.0
    pct_low     = ( failed_low / total  * 100) if failed_low  > 0 else 0.0

    success_high = len(high[high['TMAX_exceeded'] == False])
    success_low = len(low[low['TMAX_exceeded'] == False])
    pct_success_high = (success_high / total * 100) if len(high) > 0 else 0.0
    pct_success_low = (success_low / total * 100) if len(low) > 0 else 0.0

    # 6) Exec After Sunset
    exec_after_total = filtered['Exec_after_set'].sum()
    pct_exec_after = (exec_after_total / total * 100) if total > 0 else 0.0
    exec_after_success = len(filtered[
        (filtered['Exec_after_set'] == True) &
        (filtered['TMAX_exceeded'] == True) &
        (filtered['Num Hops'] < 6)
    ])

    # 7) SUCCESS e FAIL Hop
    success_hop = len(filtered[
        (filtered['TMAX_exceeded'] == False) &
        (filtered['Num Hops'] < 6)
    ])
    fail_hop = len(filtered[
        (filtered['TMAX_exceeded'] == True) &
        (filtered['Num Hops'] >= 6)
    ])

    # 8) Statistiche R = Time in system
    tcol = 'Time in system'
    if tcol in filtered.columns:
        print(tcol)
        times = pd.to_numeric(filtered[tcol], errors='coerce').dropna()
        r_avg = times.mean()
        r_max = times.max()
        r_min = times.min()
        r_std = times.std()
        r_var = times.var()
        r_90  = times.quantile(0.90)
        r_95  = times.quantile(0.95)
        mse   = r_var / success_total if success_total > 0 else None
        mse2  = mse / 2 if mse is not None else None
    else:
        r_avg = r_max = r_min = r_std = r_var = r_90 = r_95 = mse = mse2 = None

    # 9) Riepilogo metriche
    metrics = [
        ('Total Requests', total),
        ('Failed Requests', failed),
        ('Success Requests', success_total),
        ('Percent Failed (Total)', f"{pct_failed:.2f}"),
        ('Failed High (n)', failed_high),
        ('Failed Low (n)', failed_low),
        ('Percent Failed (High)', f"{pct_high:.2f}"),
        ('Percent Failed (Low)', f"{pct_low:.2f}"),
        ('Percent Success (Total)', f"{(success_total / total * 100 if total > 0 else 0.0):.2f}"),
        ('High Success', success_high),
        ('Low Success', success_low),
        ('Percent Success (High)', f"{pct_success_high:.2f}"),
        ('Percent Success (Low)', f"{pct_success_low:.2f}"),
        ('Executed After Sunset Total', exec_after_total),
        ('Percent Exec After Sunset Total', f"{pct_exec_after:.2f}"),
        ('Executed After Sunset Success', exec_after_success),
        ('Success (hop<6)', success_hop),
        ('Fail (hop>=6)', fail_hop),
        ('R Avg', round(r_avg, 3) if r_avg is not None else None),
        ('R Max', round(r_max, 3) if r_max is not None else None),
        ('R Min', round(r_min, 3) if r_min is not None else None),
        ('R Std', round(r_std, 3) if r_std is not None else None),
        ('R Var', round(r_var, 3) if r_var is not None else None),
        ('R MSE', round(mse, 3) if mse is not None else None),
        ('R 90%', round(r_90, 3) if r_90 is not None else None),
        ('R 95%', round(r_95, 3) if r_95 is not None else None),
        ('R MSE/2', round(mse2, 3) if mse2 is not None else None)
    ]
    summary = pd.DataFrame(metrics, columns=['Metric', 'Value'])

    base, _ = os.path.splitext(input_path)
    out = f"{base}_stats.csv"
    summary.to_csv(out, index=False)
    print(f"✔️  Riepilogo creato: {out}")
    return out

def extract_cpu_and_at(filename):
    cpu = filename.split('_')[-1]
    at = filename.split('_')[-3]
    name = filename.split('_')[-5]
    return cpu, at, name

def unify_stats(stats_paths):
    """
    Ritorna DataFrame wide di unione di più *_stats.csv,
    con colonna 'File' e una colonna per ogni metrica.
    """
    records = []
    for path in stats_paths:
        df = pd.read_csv(path)
        data = df.set_index('Metric')['Value'].to_dict()
        # Estrai nome breve eliminando prefisso e suffisso
        raw = os.path.splitext(os.path.basename(path))[0]
        # rimuovi suffisso _stats
        raw_no_stats = raw.rsplit('_stats', 1)[0]
        # rimuovi prefisso simulation_results_
        prefix = 'results_20_0_80_exponential_'
        if raw_no_stats.startswith(prefix):
            shortened = raw_no_stats[len(prefix):]
        else:
            shortened = raw_no_stats
        cpu, at, name = extract_cpu_and_at(shortened)
        data['File'] = shortened
        data['Name'] = name
        data['CPU'] = cpu
        data['AT'] = at
        records.append(data)
    combined = pd.DataFrame(records)
    cols = [ 'CPU', 'AT', 'Name'] + [c for c in combined.columns if c not in ['CPU', 'AT', 'Name']]
    return combined[cols]


def main():
    root = tk.Tk()
    root.withdraw()

    folder = filedialog.askdirectory(title="Seleziona la cartella dei CSV")
    if not folder:
        return
    all_files = os.listdir(folder)
    raw_paths = [os.path.join(folder, f) for f in all_files
                 if f.startswith('results') and f.endswith('.csv') and not f.endswith('_stats.csv')]
    if not raw_paths:
        messagebox.showinfo("Info", "Nessun file corrispondente trovato.")
        return

    stats_files = []
    for path in raw_paths:
        try:
            stats_files.append(process_file(path))
        except Exception as e:
            messagebox.showwarning("Warning", f"Errore elaborando {path}: {e}")

    if messagebox.askyesno("Unire file", "Vuoi creare i file unificati per failed e success? "):
        combined = unify_stats(stats_files)
        fail_cols = [
              'CPU', 'AT', 'Name', 'Total Requests', 'Success Requests', 'Failed Requests', 'Percent Failed (Total)', 'Failed High (n)', 'Failed Low (n)',
             'Percent Failed (High)', 'Percent Failed (Low)',
            'Executed After Sunset Total', 'Percent Exec After Sunset Total',
            'Executed After Sunset Success', 'Fail (hop>=6)'
        ]
        succ_cols = [
             'CPU', 'AT', 'Name', 'Total Requests', 'Success Requests', 'High Success', 'Low Success',
            'Percent Success (Total)', 'Percent Success (High)', 'Percent Success (Low)',
            'Success (hop<6)', 'Executed After Sunset Success',
            'R Avg', 'R Max', 'R Min', 'R Std', 'R Var', 'R MSE', 'R 90%', 'R 95%', 'R MSE/2'
        ]
        fail_path = filedialog.asksaveasfilename(
            title="Salva file unificato FAILED come", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if fail_path:
            combined.loc[:, [c for c in fail_cols if c in combined.columns]].to_csv(fail_path, index=False)
        succ_path = filedialog.asksaveasfilename(
            title="Salva file unificato SUCCESS come", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if succ_path:
            combined.loc[:, [c for c in succ_cols if c in combined.columns]].to_csv(succ_path, index=False)

if __name__ == "__main__":
    main()
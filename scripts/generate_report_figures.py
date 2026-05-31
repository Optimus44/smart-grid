import pandas as pd
import matplotlib.pyplot as plt
import os

bench_dir = 'bench'
output_dir = 'report/images'
os.makedirs(output_dir, exist_ok=True)

files = {
    '1-day': os.path.join(bench_dir, 'q3_results_energy_readings.csv'),
    '3-hour': os.path.join(bench_dir, 'q3_results_energy_readings_3h.csv'),
    '1-week': os.path.join(bench_dir, 'q3_results_energy_readings_week.csv'),
}

# Read and compute mean execution time per query per config
summary = {}
for name, path in files.items():
    df = pd.read_csv(path)
    means = df.groupby('query_id')['execution_ms'].mean()
    summary[name] = means

# Build DataFrame
queries = sorted(set().union(*[s.index.tolist() for s in summary.values()]))
data = {q: [summary[c].get(q, float('nan')) for c in files.keys()] for q in queries}
summary_df = pd.DataFrame(data, index=list(files.keys()))
summary_df = summary_df.T
summary_df.to_csv(os.path.join(output_dir, 'q3_summary_table.csv'))

# Plot bar charts per query
for q in summary_df.index:
    vals = summary_df.loc[q]
    plt.figure(figsize=(6,4))
    vals.plot(kind='bar')
    plt.title(f'Query {q} average execution time (ms)')
    plt.ylabel('Execution time (ms)')
    plt.xlabel('Configuration')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f'{q}_perf.png'))
    plt.close()

# Also overall plot grouped
summary_df.plot(kind='bar', figsize=(10,6))
plt.title('Average execution time by query and hypertable configuration')
plt.ylabel('Execution time (ms)')
plt.xlabel('Query')
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'all_queries_perf.png'))

print('Generated figures in', output_dir)

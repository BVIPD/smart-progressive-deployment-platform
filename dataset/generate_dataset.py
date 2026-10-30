import numpy as np
import pandas as pd

np.random.seed(42)

n = 2000

cpu = np.random.uniform(5, 100, n)
memory = np.random.uniform(10, 100, n)
latency = np.random.uniform(20, 1500, n)
error_rate = np.random.uniform(0, 15, n)
traffic = np.random.uniform(100, 10000, n)

risk = (
    (cpu > 85).astype(int) +
    (memory > 90).astype(int) +
    (latency > 800).astype(int) +
    (error_rate > 5).astype(int)
)

success = (risk < 2).astype(int)

noise = np.random.random(n) < 0.08
success = np.where(noise, 1 - success, success)

df = pd.DataFrame({
    "cpu_usage": cpu,
    "memory_usage": memory,
    "latency": latency,
    "error_rate": error_rate,
    "traffic": traffic,
    "deployment_success": success
})

df.to_csv("dataset/deployment_metrics.csv", index=False)

print("Dataset generated successfully!")
print(df.head())
print("\nDataset shape:", df.shape)
print("\nDeployment results:")
print(df["deployment_success"].value_counts())

import pandas as pd
import os
import random

file_path = "trades.csv"

# Create file if not exists
if not os.path.exists(file_path):
    df = pd.DataFrame(columns=["Trade", "Profit"])
    df.to_csv(file_path, index=False)

# Load existing data
df = pd.read_csv(file_path)

# Generate new trade
new_trade_number = len(df) + 1
new_profit = random.randint(-100, 300)

# Add new trade
new_row = pd.DataFrame([[new_trade_number, new_profit]], columns=["Trade", "Profit"])
df = pd.concat([df, new_row], ignore_index=True)

# Save back
df.to_csv(file_path, index=False)

print(f"New Trade Added: {new_trade_number}, Profit: {new_profit}")
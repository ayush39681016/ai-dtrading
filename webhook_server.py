from flask import Flask, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

file_path = "trades.csv"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    profit = data.get("profit", 0)

    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=["Trade", "Profit"])
    else:
        df = pd.read_csv(file_path)

    new_trade_number = len(df) + 1

    new_row = pd.DataFrame([[new_trade_number, profit]], columns=["Trade", "Profit"])
    df = pd.concat([df, new_row], ignore_index=True)

    df.to_csv(file_path, index=False)

    return jsonify({"status": "success", "trade": new_trade_number})

if __name__ == '__main__':
    app.run(port=5000)
import pandas as pd

def analyze_results(log_file='logs/tournament_results.csv'):
    """
    Reads the tournament log file with Pandas and prints a summary
    of the results.
    """
    try:
        df = pd.read_csv(log_file)
    except FileNotFoundError:
        print(f"Error: Log file not found at '{log_file}'.")
        print("Please run the tournament first using 'python tournament/runner.py'")
        return

    print("--- Tournament Analysis ---")

    # 1. Calculate Win Rate
    print("\n1. Overall Win Rates:")
    win_counts = df['winner_type'].value_counts()
    total_games = len(df)
    win_rates = (win_counts / total_games) * 100
    
    for wizard_type, rate in win_rates.items():
        print(f"   - {wizard_type}: {rate:.2f}% ({win_counts[wizard_type]} wins)")

    # 2. Analyze Resource Efficiency for Winners
    print("\n2. Average Resources for Winners at Match End:")
    avg_resources = df.groupby('winner_type')[['winner_hp', 'winner_mp']].mean()
    print(avg_resources.to_string(float_format="%.2f"))
    
    # 3. Average Match Duration
    print("\n3. Average Match Duration:")
    avg_duration_by_winner = df.groupby('winner_type')['match_duration_ticks'].mean()
    print(avg_duration_by_winner.to_string(float_format="%.2f ticks"))
    
    print("\n--- End of Analysis ---")


if __name__ == '__main__':
    analyze_results()

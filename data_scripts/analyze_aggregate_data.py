import pandas as pd
import statsmodels.stats.weightstats as smw
import matplotlib.pyplot as plt
import argparse
import os
from IPython.display import display

# The names of columns that are not metrics and must hence always be included in the dataframes
NON_METRIC_COLUMNS = ["model", "input", "deployment-mechanism"]

# The absolute path of the "data_scripts" directory where this script is in
SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))

# The absolute path of the parent directory, which is the root of the benchmark suite
BENCHMARK_DIR = os.path.abspath(os.path.join(SCRIPTS_DIR, ".."))

# The absolute path of the "results" directory where the results of the experiments are stored
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")

# The name of the CSV file where the aggregate results from all the experiments within
# an experiment set are stored 
AGGREGATE_CSV_FILENAME = "aggregate_results.csv"
PERF_AGGREGATE_CSV_FILENAME = f"perf_{AGGREGATE_CSV_FILENAME}"
TIME_AGGREGATE_CSV_FILENAME = f"time_{AGGREGATE_CSV_FILENAME}"

def chart_compare_across_models_or_inputs(aggregate_df, metrics, across_models, constant_value):
    deployment_mechanisms = aggregate_df["deployment-mechanism"].unique()
    display(aggregate_df)
    print(deployment_mechanisms)


    if across_models:            
        # If comparing across models, then models represent the variable, while the input represents a constant
        variable = "model"
        constant = "input"
    else:
        # Otherwise, it is the other way around
        variable = "input"
        constant = "model"

    for metric in metrics:
        # Ensure this metric is in this dataframe (since some metrics are only for the perf dataframes,
        # and others for the time dataframes)
        if f"{metric}-mean" in aggregate_df.columns:
            plt.figure(metric)
            metric_name_without_hyphen = metric.replace("-", " ")

            for deployment_mechanism in deployment_mechanisms:

                # Get only the rows for this deployment mechanism
                deployment_mechanism_metric_df = aggregate_df[aggregate_df["deployment-mechanism"] == deployment_mechanism]
                
                # Plot the mean and confidence interval for each deployment mechanism
                variable_values = deployment_mechanism_metric_df[variable].unique().tolist()
                means = deployment_mechanism_metric_df[f"{metric}-mean"].tolist()
                errors = [deployment_mechanism_metric_df[f"{metric}-error-lower"].tolist(), deployment_mechanism_metric_df[f"{metric}-error-upper"].tolist()]
                plt.errorbar(variable_values, means, yerr=errors, label=deployment_mechanism, capsize=5)

            # Set title and labels
            plt.title(f"{metric_name_without_hyphen} by {variable} on {constant} {constant_value}\nfor different deployment mechanisms")
            plt.ylabel(metric_name_without_hyphen)
            plt.xlabel(variable)
            plt.legend()
            plt.show()

def compare_across_models_or_inputs(perf_aggregate_df, time_aggregate_df, across_models, variable_values, constant_value, metrics):
    if across_models:
        # If comparing across models, then models represent the variable, while the input represents a constant
        variable = "model"
        constant = "input"
    else:
        # Otherwise, it is the other way around
        variable = "input"
        constant = "model"

    # Filter the dataframes to only include rows with the specified variable values and constant value
    perf_aggregate_df = perf_aggregate_df[perf_aggregate_df[variable].isin(variable_values)]
    perf_aggregate_df = perf_aggregate_df[perf_aggregate_df[constant] == constant_value]

    print(constant)
    print(constant_value)

    time_aggregate_df = time_aggregate_df[time_aggregate_df[variable].isin(variable_values)]
    print("only keep variable in variable values")
    display(time_aggregate_df)
    time_aggregate_df = time_aggregate_df[time_aggregate_df[constant] == constant_value]
    print("constant must equal constant value")
    display(time_aggregate_df)

    # For each metric and deployment mechanism, lineplot the mean and confidence intervals
    #chart_compare_across_models_or_inputs(perf_aggregate_df, metrics, across_models, constant_value)
    chart_compare_across_models_or_inputs(time_aggregate_df, metrics, across_models, constant_value)

def compare_across_models(perf_aggregate_df, time_aggregate_df, models_to_compare, input, metrics):
    compare_across_models_or_inputs(perf_aggregate_df, time_aggregate_df, True, models_to_compare, input, metrics)

def compare_across_inputs(perf_aggregate_df, time_aggregate_df, inputs_to_compare, model, metrics):
    compare_across_models_or_inputs(perf_aggregate_df, time_aggregate_df, False, inputs_to_compare, model, metrics)

def remove_irrelevant_df_columns(df, metric_cols):
    # Remove the columns that are not required
    cols_to_keep = [col for col in NON_METRIC_COLUMNS + metric_cols if col in df.columns]
    return df[cols_to_keep]

def main():
    parser = argparse.ArgumentParser(description="Analyze aggregated performance data for a set of experiments")
    parser.add_argument("--experiment-set", type=str, required=True, help="The experiment set to analyze.")
    parser.add_argument("--compare-across-models", action="store_true", help="Compare across models.")
    parser.add_argument("--models-to-compare", type=str, nargs="+", help="The models to compare.")
    parser.add_argument("--input", type=str, help="The single input to use in comparing models.")
    parser.add_argument("--compare-across-inputs", action="store_true", help="Compare across inputs.")
    parser.add_argument("--inputs-to-compare", type=str, nargs="+", help="The inputs to compare.")
    parser.add_argument("--model", type=str, help="The model to use in comparing inputs.")
    parser.add_argument("--metrics", type=str, nargs="+", default=["wall-time-seconds"], help="The metrics to analyze.")

    args = parser.parse_args()

    # Load the aggregate results
    perf_aggregate_csv_path = os.path.join(RESULTS_DIR, args.experiment_set, PERF_AGGREGATE_CSV_FILENAME)
    perf_aggregate_df = pd.read_csv(perf_aggregate_csv_path)
    time_aggregate_csv_path = os.path.join(RESULTS_DIR, args.experiment_set, TIME_AGGREGATE_CSV_FILENAME)
    time_aggregate_df = pd.read_csv(time_aggregate_csv_path)

    # Get the names of the columns corresponding to the provided metrics
    metric_cols_suffixes = ["-mean", "-error-lower", "-error-upper"]
    metric_cols = [f"{metric}{suffix}" for metric in args.metrics for suffix in metric_cols_suffixes]

    # Remove irrelevant columns from the dataframes
    perf_aggregate_df = remove_irrelevant_df_columns(perf_aggregate_df, metric_cols)
    time_aggregate_df = remove_irrelevant_df_columns(time_aggregate_df, metric_cols)

    if args.compare_across_models:
        if args.models_to_compare is None:
            print("You must provide a list of models to compare.")
        if args.input is None:
            print("You must provide a single input to use in comparing models.")
        compare_across_models(None, time_aggregate_df, args.models_to_compare, args.input, args.metrics)
    if args.compare_across_inputs:
        if args.inputs_to_compare is None:
            print("You must provide a list of inputs to compare.")
        if args.model is None:
            print("You must provide a single model to use in comparing inputs.")
        compare_across_inputs(None, time_aggregate_df, args.inputs_to_compare, args.model, args.metrics)

if __name__ == "__main__":
    main()
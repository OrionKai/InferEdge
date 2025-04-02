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
# PERF_AGGREGATE_CSV_FILENAME = f"perf_{AGGREGATE_CSV_FILENAME}"
# TIME_AGGREGATE_CSV_FILENAME = f"time_{AGGREGATE_CSV_FILENAME}"

def chart_compare_across_models_or_inputs(aggregate_df, metrics, across_models, variable_values, constant_value, 
    view_output, save_output, plots_path):
    deployment_mechanisms = aggregate_df["deployment-mechanism"].unique()
    variable_values_str = "_".join(variable_values)

    if across_models:            
        # If comparing across models, then models represent the variable, while the input represents a constant
        variable = "model"
        constant = "input"
        plot_filename_prefix = f"aggregate_models_{variable_values_str}_for_input_{constant_value}"
    else:
        # Otherwise, it is the other way around
        variable = "input"
        constant = "model"
        plot_filename_prefix = f"aggregate_models_{variable_values_str}_for_model_{constant_value}"

    for metric in metrics:
        # Ensure this metric is in this dataframe (since some metrics are only for the perf dataframes,
        # and others for the time dataframes)
        if f"{metric}-mean" in aggregate_df.columns:
            plt.figure(metric)
            metric_name_without_hyphen = metric.replace("-", " ")
            metric_with_underscores = metric.replace("-", "_")

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

            # Rotate the x-axis labels for better readability
            plt.xticks(rotation=45)
            plt.tight_layout()

            if save_output:
                plot_filename = f"{plot_filename_prefix}_{metric_with_underscores}_lineplot.png"
                plot_filepath = os.path.join(plots_path, plot_filename)
                plt.savefig(plot_filepath)

            if view_output:
                plt.show()

def compare_across_models_or_inputs(aggregate_df, across_models, variable_values, constant_value, 
    metrics, view_output, save_output, plots_path):
    if across_models:
        # If comparing across models, then models represent the variable, while the input represents a constant
        variable = "model"
        constant = "input"
    else:
        # Otherwise, it is the other way around
        variable = "input"
        constant = "model"

    # Filter the dataframes to only include rows with the specified variable values and constant value
    aggregate_df = aggregate_df[aggregate_df[variable].isin(variable_values)]
    aggregate_df = aggregate_df[aggregate_df[constant] == constant_value]

    # For each metric and deployment mechanism, lineplot the mean and confidence intervals
    chart_compare_across_models_or_inputs(aggregate_df, metrics, across_models, variable_values, constant_value, view_output, 
        save_output, plots_path)

def compare_across_models(aggregate_df, models_to_compare, input, metrics, view_output, save_output, plots_path):
    compare_across_models_or_inputs(aggregate_df, True, models_to_compare, input, metrics, view_output, save_output, plots_path)

def compare_across_inputs(aggregate_df, inputs_to_compare, model, metrics, view_output, save_output, plots_path):
    compare_across_models_or_inputs(aggregate_df, False, inputs_to_compare, model, metrics, view_output, save_output, plots_path)

def remove_irrelevant_df_columns(df, metric_cols):
    # Remove the columns that are not required
    print(metric_cols)
    cols_to_keep = [col for col in NON_METRIC_COLUMNS + metric_cols if col in df.columns]
    print(cols_to_keep)
    return df[cols_to_keep]

def main():
    parser = argparse.ArgumentParser(description="Analyze aggregated performance data for a set of experiments")
    parser.add_argument("--experiment-set", type=str, help="The experiment set to analyze.")
    parser.add_argument("--compare-across-models", action="store_true", help="Compare across models.")
    parser.add_argument("--models-to-compare", type=str, help="The models to compare.")
    parser.add_argument("--input", type=str, help="The single input to use in comparing models.")
    parser.add_argument("--compare-across-inputs", action="store_true", help="Compare across inputs.")
    parser.add_argument("--inputs-to-compare", type=str, help="The inputs to compare.")
    parser.add_argument("--model", type=str, help="The model to use in comparing inputs.")
    parser.add_argument("--metrics", type=str, help="The metrics to analyze.")
    parser.add_argument("--view-output", action="store_true", help="View the output of the analysis.")
    parser.add_argument("--save-output", action="store_true", 
        help="Save the output of the analysis to files.")

    args = parser.parse_args()

    metrics = [metric.strip() for metric in args.metrics.split(",")]

    # Load the aggregate results
    experiments_set_path = os.path.join(RESULTS_DIR, args.experiment_set)
    analyzed_results_path = os.path.join(experiments_set_path, "analyzed_results")
    aggregate_csv_path = os.path.join(analyzed_results_path, AGGREGATE_CSV_FILENAME)
    aggregate_df = pd.read_csv(aggregate_csv_path)

    # Get the names of the columns corresponding to the provided metrics
    metric_cols_suffixes = ["-mean", "-error-lower", "-error-upper"]
    metric_cols = [f"{metric}{suffix}" for metric in metrics for suffix in metric_cols_suffixes]

    # Remove irrelevant columns from the dataframe
    aggregate_df = remove_irrelevant_df_columns(aggregate_df, metric_cols)

    # Get the path to the plots directory
    plots_path = os.path.join(analyzed_results_path, "plots")

    if args.compare_across_models:
        if args.models_to_compare is None:
            print("You must provide a list of models to compare.")
        if args.input is None:
            print("You must provide a single input to use in comparing models.")
        models_to_compare = [model.strip() for model in args.models_to_compare.split(",")]
        compare_across_models(aggregate_df, models_to_compare, args.input, metrics, args.view_output, args.save_output,
            plots_path)
    if args.compare_across_inputs:
        if args.inputs_to_compare is None:
            print("You must provide a list of inputs to compare.")
        if args.model is None:
            print("You must provide a single model to use in comparing inputs.")
        inputs_to_compare = [input.strip() for input in args.inputs_to_compare.split(",")]
        compare_across_inputs(aggregate_df, inputs_to_compare, args.model, metrics, args.view_output, args.save_output,
            plots_path)

if __name__ == "__main__":
    main()
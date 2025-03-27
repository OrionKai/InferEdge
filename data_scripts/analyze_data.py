"""This script analyzes the experimental data, determining if there is a statistically significant difference
   in the performance of different deployment mechanisms and quantifying the extent of that difference.
"""
import pandas as pd
import statsmodels.stats.weightstats as smw
from itertools import combinations
import matplotlib.pyplot as plt
import argparse

# String representing the default value for the --metrics argument
DEFAULT_METRICS = "instructions,cpu-cycles,cache-references,cache-misses,page-faults,bus-cycles," \
    "branch-instructions,branch-misses,major-faults,minor-faults,avg_memory_over_time,max_memory_over_time," \
    "cpu_total_utilization,cpu_user_utilization,cpu_system_utilization,wall-time-seconds"

# The names of columns that are not metrics and must hence always be included in the dataframes
NON_METRIC_COLUMNS = ["index", "experiment_type", "trial_number", "start_time"]

# The absolute path of the "data_scripts" directory where this script is in
SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))

# The absolute path of the parent directory, which is the root of the benchmark suite
BENCHMARK_DIR = os.path.abspath(os.path.join(SCRIPTS_DIR, ".."))

# The absolute path of the "results" directory where the results of the experiments are stored
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")

def welch_t_test_with_confidence_interval(arr_x, arr_y, alpha=0.05):
    # Calculate the mean of the data and compare them
    descr_stats_x = smw.DescrStatsW(arr_x)
    descr_stats_y = smw.DescrStatsW(arr_y)
    compare_means = smw.CompareMeans(descr_stats_x, descr_stats_y)

    # Calculate the confidence interval of the difference of the means;
    # use Welch's t-test which does not assume equal variances
    # between the samples represented by arr_x and arr_y
    ci_lower, ci_upper = compare_means.tconfint_diff(usevar="unequal", alpha=alpha)
    
    # Get the difference of the means
    x_mean = descr_stats_x.mean
    y_mean = descr_stats_y.mean
    mean_diff = abs(y_mean - x_mean)

    # Get the half-width of the confidence interval
    ci_half_width = (ci_upper - ci_lower) / 2

    # Determine statistical significance by checking if the confidence interval
    # contains zero (no difference between the means)
    statistically_significant = not (ci_lower <= 0 <= ci_upper)

    # Get individual confidence intervals for the means
    x_ci = descr_stats_x.tconfint_mean(alpha=alpha)
    y_ci = descr_stats_y.tconfint_mean(alpha=alpha)

    return x_mean, y_mean, mean_diff, ci_lower, ci_upper, ci_half_width, statistically_significant, x_ci, y_ci

def analyze_data_significant_difference(df, significance_level, include_insignificant_output=False):
    # Specify the columns that store metrics
    metric_cols = [col for col in df.columns if col not in ["index", "experiment_type", "trial_number", "start_time"]]

    # For each deployment mechanism, group the results for each metric
    grouped_df = df.groupby("experiment_type")[metric_cols]

    # For each pair of experiment types and each metric, test for statistically
    # significant differences and calculate the effect size confidence intervals
    types = df["experiment_type"].unique()
    results = []

    # This dataframe will save, for each deployment mechanism, its statistics for each metric, for further analysis
    # in other functions e.g. visualizations
    aggregate_df = pd.DataFrame(columns=["deployment_mechanism", "metric", "mean", "ci_lower", "ci_upper"])

    for deployment_mechanism_x, deployment_mechanism_y in combinations(types, 2):
        for metric in metric_cols:
            arr_x = grouped_df.get_group(deployment_mechanism_x)[metric]
            arr_y = grouped_df.get_group(deployment_mechanism_y)[metric]

            x_mean, y_mean, mean_diff, ci_lower, ci_upper, ci_half_width, statistically_significant, x_ci, y_ci = \
                welch_t_test_with_confidence_interval(arr_x, arr_y, alpha=significance_level)

            results.append({
                "deployment_mechanism_x": deployment_mechanism_x,
                "deployment_mechanism_y": deployment_mechanism_y,
                "metric": metric,
                "x_mean": x_mean,
                "y_mean": y_mean,
                "mean_diff": mean_diff,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "ci_half_width": ci_half_width,
                "statistically_significant": statistically_significant,
                "x_ci": x_ci,
                "y_ci": y_ci
            })
        
            # In the future, this can be made more efficient as these values are being calculated
            # multiple times currently (e.g. when comparing deployment mechanism x with deployment mechanism y,
            # then comparing deployment mechanism y with deployment mechanism z, y's values are recalculated)
            new_row = pd.DataFrame([{
                "deployment_mechanism": deployment_mechanism_x,
                "metric": metric,
                "mean": x_mean,
                "error_lower": x_mean - x_ci[0],
                "error_upper": x_ci[1] - x_mean
            }])
            aggregate_df = pd.concat([aggregate_df, new_row], ignore_index=True)
            new_row = pd.DataFrame([{
                "deployment_mechanism": deployment_mechanism_y,
                "metric": metric,
                "mean": y_mean,
                "error_lower": y_mean - y_ci[0],
                "error_upper": y_ci[1] - y_mean
            }])
            aggregate_df = pd.concat([aggregate_df, new_row], ignore_index=True)

    # Remove duplicate rows from the aggregate dataframe
    aggregate_df = aggregate_df.drop_duplicates()

    # TODO: let the user pick which experiment types to compare and which metrics to show
    # TODO: group results by combination so can clearly differentiate
    # Print out the results of the statistical tests and effect size calculations
    for result in results:
        if result["statistically_significant"] == True:
            # Reporting of results and calculations for ratio based on those used by the Sightglass benchmark,
            # available at https://github.com/bytecodealliance/sightglass/blob/main/crates/analysis/src/effect_size.rs
            # (accessed: 27 Jan. 2025)
            print(f"Statistically significant difference between {result['deployment_mechanism_x']} and {result['deployment_mechanism_y']} for {result['metric']}")
        else:
            print(f"No statistically significant difference between {result['deployment_mechanism_x']} and {result['deployment_mechanism_y']} for {result['metric']}")
            if not include_insignificant_output:
                continue

        print(f"Mean difference: {result['mean_diff']:.2f} ± {result['ci_half_width']:.2f} with confidence level {(1 - significance_level) * 100.0}%")
        print(f"{result['deployment_mechanism_x']} average: {result['x_mean']:.2f} (95% CI: {result['x_ci'][0]:.2f} to {result['x_ci'][1]:.2f})")
        print(f"{result['deployment_mechanism_y']} average: {result['y_mean']:.2f} (95% CI: {result['y_ci'][0]:.2f} to {result['y_ci'][1]:.2f})")
        
        if result["x_mean"] < result["y_mean"]:
            ratio = result["y_mean"] / result["x_mean"]
            ratio_ci = result["ci_half_width"] / result["x_mean"]
            ratio_min = ratio - ratio_ci
            ratio_max = ratio + ratio_ci
            print(f"{result['deployment_mechanism_y']} is {ratio_min:.2f} to {ratio_max:.2f} times larger than {result['deployment_mechanism_x']} for {result['metric']}\n")
        else:
            ratio = result["x_mean"] / result["y_mean"]
            ratio_ci = result["ci_half_width"] / result["y_mean"]
            ratio_min = ratio - ratio_ci
            ratio_max = ratio + ratio_ci
            print(f"{result['deployment_mechanism_x']} is {ratio_min:.2f} to {ratio_max:.2f} times larger than {result['deployment_mechanism_y']} for {result['metric']}\n")

    return aggregate_df

def parse_csv_rows(results_filename, deployment_mechanisms, metrics, include_docker_overhead=True, is_perf_file=True):
    df = pd.read_csv(results_filename)

    # Drop columns corresponding to metrics that were not specified
    df = df.drop(df.columns.difference(NON_METRIC_COLUMNS + metrics), axis=1)

    if include_docker_overhead:
        # Rename "docker_container_and_daemon" as an deployment mechanism to just "docker"
        # TODO: replace experiment_type with deployment_mechanism
        df["experiment_type"] = df["experiment_type"].apply(lambda deployment_mechanism: 
            "docker" if deployment_mechanism.startswith("docker_container_and_daemon") else deployment_mechanism)

        # Remove the rows whose deployment mechanism is "docker_container"
        df = df[~df["experiment_type"].str.startswith("docker_container")]
    else:
        # Rename "docker_container" as an deployment mechanism to just "docker"
        df["experiment_type"] = df["experiment_type"].apply(lambda deployment_mechanism: 
            "docker" if deployment_mechanism == "docker_container" else deployment_mechanism)

        # Remove the rows whose deployment mechanism is "docker_container_and_daemon"
        df = df[~df["experiment_type"].str.startswith("docker_container_and_daemon")]        

    if is_perf_file:
        # Add new columns for instructions-per-cycle and cycles-per-instruction
        df["instructions-per-cycle"] = df["instructions"] / df["cpu-cycles"]
        df["cycles-per-instruction"] = df["cpu-cycles"] / df["instructions"]

    # Drop rows corresponding to deployment mechanisms that were not specified
    df = df.drop(df[~df["experiment_type"].isin(deployment_mechanisms)].index)

    return df

def plot_metrics_bar_chart(aggregate_df):
    # For each metric, plot the mean and confidence interval for each deployment mechanism
    metrics = aggregate_df["metric"].unique()

    for metric in metrics:
        metric_name_without_hyphen = metric.replace("-", " ")
        plt.figure(metric)
        metric_df = aggregate_df[aggregate_df["metric"] == metric]

        # Plot the mean and confidence interval for each deployment mechanism
        deployment_mechanisms = metric_df["deployment_mechanism"].unique().tolist()
        means = metric_df["mean"].tolist()
        errors = [metric_df["error_lower"].tolist(), metric_df["error_upper"].tolist()]
        plt.bar(deployment_mechanisms, means, yerr=errors, capsize=5)

        plt.title(f"{metric_name_without_hyphen} by deployment mechanism")
        plt.ylabel(metric_name_without_hyphen)
        plt.xlabel("deployment mechanism")
    plt.show()

  
import os

# The absolute path of the "scripts" directory where this script is in
scripts_dir = os.path.abspath(os.path.dirname(__file__))

# The absolute path of the parent "Benchmark" directory
benchmark_dir = os.path.abspath(os.path.join(scripts_dir, ".."))

def main():
    parser = argparse.ArgumentParser(description="Analyze performance data.")
    parser.add_argument("--experiment-set", type=str, required=True, help="The experiment set to analyze.")
    parser.add_argument("--model", type=str, required=True, help="The model used in the experiment to analyze.")
    parser.add_argument("--input", type=str, required=True, help="The input used in the experiment to analyze.")
    parser.add_argument("--significance_level", type=float, default=0.05, help="The significance level to use (e.g., 0.05).")
    parser.add_argument("--exclude_docker_overhead", action="store_true", default=False, help="Exclude Docker overhead in the analysis.")
    parser.add_argument("--include_insignificant_output", action="store_true", default=False, help="Include statistical comparisons when they are not statistically significant.")
    parser.add_argument("--mechanisms", type=str, default="docker,wasm_interpreted,wasm_aot,native",
                    help="Comma-separated list of mechanisms to include (choose from docker, wasm_interpreted, wasm_aot, native)")
    parser.add_argument("--metrics", type=str, default=DEFAULT_METRICS,
                    help="Comma-separated list of metrics to include")
    args = parser.parse_args()

    deployment_mechanisms = [m.strip().lower() for m in args.mechanisms.split(",")]
    metrics = [m.strip().lower() for m in args.metrics.split(",")]

    perf_filename = f"{args.experiment_set}_{args.model}_{args.input}_perf.csv"
    time_filename = f"{args.experiment_set}_{args.model}_{args.input}_time.csv"
    
    perf_path = os.path.join(RESULTS_DIR, args.experimental_set, perf_filename)
    time_path = os.path.join(RESULTS_DIR, args.experimental_set, time_filename)

    print("Analyzing performance data...")
    perf_df = parse_csv_rows(perf_path, deployment_mechanisms, metrics, not args.exclude_docker_overhead)
    perf_aggregate_df = analyze_data_significant_difference(perf_df, args.significance_level, args.include_insignificant_output)
    time_df = parse_csv_rows(time_path, deployment_mechanisms, metrics, not args.exclude_docker_overhead, is_perf_file=False)
    time_aggregate_df = analyze_data_significant_difference(time_df, args.significance_level, args.include_insignificant_output)
    
    plot_metrics_bar_chart(perf_aggregate_df)
    plot_metrics_bar_chart(time_aggregate_df)

    
    
    # TODO: Write the statistics to a file, whilst also recording the model and input 

if __name__ == "__main__":
    main()
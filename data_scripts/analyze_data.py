"""This script analyzes the experimental data, determining if there is a statistically significant difference
   in the performance of different deployment mechanisms and quantifying the extent of that difference.
"""
import pandas as pd
import numpy as np
import statsmodels.stats.weightstats as smw
import math
from itertools import combinations
import argparse

# TODO: output CSV file

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

def analyze_perf_data(df, significance_level, include_insignificant_output=False):
    # Specify the columns that store metrics
    metric_cols = [col for col in df.columns if col not in ["index", "experiment_type", "trial_number", "start_time"]]

    # For each experiment type, group the results for each metric
    grouped_df = df.groupby("experiment_type")[metric_cols]

    # For each pair of experiment types and each metric, test for statistically
    # significant differences and calculate the effect size confidence intervals
    types = df["experiment_type"].unique()
    results = []
    for experiment_type_x, experiment_type_y in combinations(types, 2):
        for metric in metric_cols:
            arr_x = grouped_df.get_group(experiment_type_x)[metric]
            arr_y = grouped_df.get_group(experiment_type_y)[metric]

            x_mean, y_mean, mean_diff, ci_lower, ci_upper, ci_half_width, statistically_significant, x_ci, y_ci = \
                welch_t_test_with_confidence_interval(arr_x, arr_y, alpha=significance_level)

            results.append({
                "experiment_type_x": experiment_type_x,
                "experiment_type_y": experiment_type_y,
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
    
    # TODO: let the user pick which experiment types to compare and which metrics to show
    # TODO: group results by combination so can clearly differentiate
    # Print out the results of the statistical tests and effect size calculations
    for result in results:
        if result["statistically_significant"] == True:
            # Reporting of results and calculations for ratio based on those used by the Sightglass benchmark,
            # available at https://github.com/bytecodealliance/sightglass/blob/main/crates/analysis/src/effect_size.rs
            # (accessed: 27 Jan. 2025)
            print(f"Statistically significant difference between {result['experiment_type_x']} and {result['experiment_type_y']} for {result['metric']}")
        else:
            print(f"No statistically significant difference between {result['experiment_type_x']} and {result['experiment_type_y']} for {result['metric']}")
            if not include_insignificant_output:
                continue

        print(f"Mean difference: {result['mean_diff']:.2f} ± {result['ci_half_width']:.2f} with confidence level {(1 - significance_level) * 100.0}%")
        print(f"{result['experiment_type_x']} average: {result['x_mean']:.2f} (95% CI: {result['x_ci'][0]:.2f} to {result['x_ci'][1]:.2f})")
        print(f"{result['experiment_type_y']} average: {result['y_mean']:.2f} (95% CI: {result['y_ci'][0]:.2f} to {result['y_ci'][1]:.2f})")
        
        if result["x_mean"] < result["y_mean"]:
            ratio = result["y_mean"] / result["x_mean"]
            ratio_ci = result["ci_half_width"] / result["x_mean"]
            ratio_min = ratio - ratio_ci
            ratio_max = ratio + ratio_ci
            print(f"{result['experiment_type_y']} is {ratio_min:.2f} to {ratio_max:.2f} times larger than {result['experiment_type_x']} for {result['metric']}\n")
        else:
            ratio = result["x_mean"] / result["y_mean"]
            ratio_ci = result["ci_half_width"] / result["y_mean"]
            ratio_min = ratio - ratio_ci
            ratio_max = ratio + ratio_ci
            print(f"{result['experiment_type_x']} is {ratio_min:.2f} to {ratio_max:.2f} times larger than {result['experiment_type_y']} for {result['metric']}\n")

def parse_csv_rows(results_filename, include_docker_overhead=True, is_perf_file=True):
    df = pd.read_csv(results_filename)

    if include_docker_overhead:
        # Rename "docker_container_and_daemon" as an experiment type to just "docker"
        df["experiment_type"] = df["experiment_type"].apply(lambda experiment_type: 
            "docker" if experiment_type.startswith("docker_container_and_daemon") else experiment_type)

        # Remove the rows whose experiment type is "docker_container"
        df = df[~df["experiment_type"].str.startswith("docker_container")]
    else:
        # Rename "docker_container" as an experiment type to just "docker"
        df["experiment_type"] = df["experiment_type"].apply(lambda experiment_type: 
            "docker" if experiment_type == "docker_container" else experiment_type)

        # Remove the rows whose experiment type is "docker_container_and_daemon"
        df = df[~df["experiment_type"].str.startswith("docker_container_and_daemon")]        

    if is_perf_file:
        # Add new columns for instructions-per-cycle and cycles-per-instruction
        df["instructions-per-cycle"] = df["instructions"] / df["cpu-cycles"]
        df["cycles-per-instruction"] = df["cpu-cycles"] / df["instructions"]

    return df

def main():
    parser = argparse.ArgumentParser(description="Analyze performance data.")
    parser.add_argument("--perf_results", type=str, required=True, help="The filename for performance results.")
    parser.add_argument("--time_results", type=str, required=True, help="The filename for time results.")
    parser.add_argument("--significance_level", type=float, default=0.05, help="The significance level to use (e.g., 0.05).")
    parser.add_argument("--exclude_docker_overhead", action="store_true", default=False, help="Exclude Docker overhead in the analysis.")
    parser.add_argument("--include_insignificant_output", action="store_true", default=False, help="Include statistical comparisons when they are not statistically significant.")
    args = parser.parse_args()

    perf_df = parse_csv_rows(args.perf_results, not args.exclude_docker_overhead)
    analyze_perf_data(perf_df, args.significance_level, args.include_insignificant_output)
    time_df = parse_csv_rows(args.time_results, not args.exclude_docker_overhead, is_perf_file=False)
    analyze_perf_data(time_df, args.significance_level, args.include_insignificant_output)

if __name__ == "__main__":
    main()
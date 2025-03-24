"""This script runs all the experiments and collects the relevant data, storing it in the 
   specified files.
"""
import requests
import json
import subprocess
import csv
import random
import os
import argparse
import time
from datetime import datetime
from sys import platform

# The absolute path of the "scripts" directory where this script is in
scripts_dir = os.path.abspath(os.path.dirname(__file__))

# The absolute path of the parent "Benchmark" directory
benchmark_dir = os.path.abspath(os.path.join(scripts_dir, ".."))
benchmark_dir = scripts_dir

# Path to the WebAssembly binary
WASM_BINARY_PATH = os.path.expanduser("~/.wasmedge/bin/wasmedge")

# Path to the WebAssembly files
INTERPRETED_WASM_FILE_PATH = f"{benchmark_dir}/wasm/interpreted.wasm"
AOT_WASM_FILE_PATH_TEMPLATE = f"{benchmark_dir}/wasm/aot.{{extension}}"

# Path to cAdvisor perf events config file
CADVISOR_PERF_CONFIG_PATH = f"{benchmark_dir}/cadvisor/perf_config.json"

# The list of perf events to measure
def read_perf_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
        return config.get("core").get("events")

PERF_EVENTS = read_perf_config(CADVISOR_PERF_CONFIG_PATH)

# Path to the cAdvisor binary
CADVISOR_BINARY_PATH = f"{benchmark_dir}/cadvisor/cadvisor"

NATIVE_BINARY_NAME = "torch_image_classification"

# Path to the native-compiled code
NATIVE_BINARY_PATH = f"{benchmark_dir}/native/{NATIVE_BINARY_NAME}"

# Container and image names
CONTAINER_NAME="benchmarked-container"
IMG_NAME_TEMPLATE="image-classification:{arch}"         

# The command to start the container
CONTAINER_START_CMD_TEMPLATE=f"sudo docker run --privileged --name {CONTAINER_NAME} {{img_name}}"

CONTAINER_STOP_CMD="sudo docker stop {container_name}"
CONTAINER_REMOVE_CMD="sudo docker rm {container_name}"
CONTAINER_INSPECT_ID_CMD="sudo docker inspect -f '{{{{.Id}}}}' {container_name}"

# Commands to start and stop cAdvisor
CADVISOR_START_CMD = f"sudo {CADVISOR_BINARY_PATH} -perf_events_config={CADVISOR_PERF_CONFIG_PATH}"
CADVISOR_STOP_CMD = f"sudo pkill -f {CADVISOR_BINARY_PATH}"

# Command to clear OS-level caches
CLEAR_CACHE_CMD = "sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'"

LD_LIBRARY_PATH = os.environ.get("LD_LIBRARY_PATH")
PATH = os.environ.get("PATH")

# The command used to start perf
PERF_CMD_PREFIX=f"sudo LD_LIBRARY_PATH={LD_LIBRARY_PATH} PATH={PATH} perf stat -e"

# The command used to measure wall time
TIME_CMD_PREFIX="/usr/bin/time -v"

# The words identifying the part of /usr/bin/time -v's or Prometheus's output containing the 
# max RSS value, alongside the shorter name for max RSS as it will be written in the 
# results file
MAX_RSS_TIME_IDENTIFIER_IN_TIME = "Maximum resident set size"
MAX_RSS_TIME_IDENTIFIER_IN_PROMETHEUS = "container_memory_max_usage_bytes"
MAX_RSS_TIME_SHORTHAND = "max-rss-bytes"
MAX_RSS_TIME_IDENTIFIER_AND_SHORTHAND = (MAX_RSS_TIME_IDENTIFIER_IN_TIME, MAX_RSS_TIME_SHORTHAND)

# The list of metrics from running /usr/bin/time to measure, alongside the 
# shorter name of the metric as it will be written in the results file
TIME_METRICS = [("Elapsed (wall clock) time", "wall-time-seconds"), 
    MAX_RSS_TIME_IDENTIFIER_AND_SHORTHAND]

# The endpoint that Prometheus is listening on
PROMETHEUS_URL="http://localhost:9090"

# The name of the files to store results in
PERF_RESULTS_FILENAME = "perf_results.csv"
TIME_RESULTS_FILENAME = "time_results.csv"
MAX_RSS_RESULTS_FILENAME = "max_rss_results.csv"

# Basic field names to include in every CSV file storing experiment results
CSV_BASIC_FIELD_NAMES = ["experiment_type", "trial_number", "start_time"] 

# Field names for memory metrics
MEMORY_FIELD_NAMES = ["avg_memory_over_time", "max_memory_over_time"]

# Field names for CPU metrics
CPU_FIELD_NAMES = ["cpu_total_utilization", "cpu_user_utilization", "cpu_system_utilization"]

# Number of CPU cores 
NUM_CORES = os.cpu_count()

# Name of custom cgroup we will execute the Wasm process in, so cAdvisor and Prometheus can track
# its metrics
CUSTOM_CGROUP_NAME = "custom"

## Prometheus queries
PROMETHEUS_MAX_RSS_QUERY = f"(container_memory_max_usage_bytes{{name='{CONTAINER_NAME}'}})"
PROMETHEUS_CONTAINER_MEMORY_USAGE_BYTES_FIELD_NAME = "container_memory_usage_bytes"
PROMETHEUS_QUERIES_LABELS = [None] + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES
# For the Docker experiments, we need to specify the container name
PROMETHEUS_PERF_AND_MEMORY_QUERIES_WITH_NAME = [
    "sum by (event) (container_perf_events_total{{name='{name_or_id}'}})",
    "avg_over_time(container_memory_usage_bytes{{name='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "max_over_time(container_memory_usage_bytes{{name='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "100 * rate(container_cpu_usage_seconds_total{{name='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_user_seconds_total{{name='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_system_seconds_total{{name='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}"
]
# For the Wasm experiments, we need to specify the cgroup ID instead of the name
PROMETHEUS_PERF_AND_MEMORY_QUERIES = [
    "sum by (event) (container_perf_events_total{{id='{name_or_id}'}})",
    "avg_over_time(container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "max_over_time(container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "100 * rate(container_cpu_usage_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_user_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_system_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}"
]
# Gets the combined metrics for the container and the Docker daemon
PROMETHEUS_DOCKER_COMBINED_PERF_AND_MEMORY_QUERIES = ["""sum by (event) (increase(container_perf_events_total{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] 
    @ {end_container_timestamp:.2f})) 
    + 
    sum by (event) (increase(container_perf_events_total{{id='{name_or_id}'}}[{container_duration_ms}ms] 
    @ {end_container_timestamp:.2f}))""",
    "avg_over_time(combined_memory_usage_bytes[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "max_over_time(combined_memory_usage_bytes[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    """100 * ( sum(rate(container_cpu_usage_seconds_total{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}))
    + 
    sum(rate(container_cpu_usage_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})) )""" 
    + f" / {NUM_CORES}",
    """100 * ( sum(rate(container_cpu_user_seconds_total{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}))
    +
    sum(rate(container_cpu_user_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})) )""" 
    + f" / {NUM_CORES}",
    """100 * ( sum(rate(container_cpu_system_seconds_total{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}))
    +
    sum(rate(container_cpu_system_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})) )""" 
    + f" / {NUM_CORES}",
]
PROMETHEUS_DOCKER_DAEMON_MEMORY_QUERY = "container_memory_usage_bytes{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}"
PROMETHEUS_DOCKER_CONTAINER_MEMORY_QUERY = "container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}"

# The commands used to start a custom cgroup and execute a command in it
CREATE_CGROUP_CMD=f"sudo cgcreate -g memory:{CUSTOM_CGROUP_NAME}"
EXEC_IN_CGROUP_CMD_PREFIX=f"sudo LD_LIBRARY_PATH={LD_LIBRARY_PATH} PATH={PATH} cgexec -g memory:{CUSTOM_CGROUP_NAME}"
DELETE_CGROUP_CMD=f"sudo cgdelete -g memory:{CUSTOM_CGROUP_NAME}"

# Variable tracking whether cAdvisor is currently running or not
cadvisor_running = False

def is_cgroup_v2():
    return os.path.isfile("/sys/fs/cgroup/cgroup.controllers")

def is_mac():
    return platform == "darwin"

# Because collect_time_data only measures max RSS of the Docker command
# used to tell the daemon to create the container, we need this experiment here to 
# get accurate max RSS metrics for Docker
def collect_time_data(n, time_metrics, results_filename, docker_run_experiment_function,
    non_container_run_experiment_function, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd,
    mechanisms=["docker","wasm_interpreted","wasm_aot","native"]):
    time_metrics_short_names = [time_metric[1] for time_metric in time_metrics]

    # Randomly intersperse experiments of each type
    experiments = []
    if "docker" in mechanisms:
        experiments += ["docker"] * n
    if "wasm_interpreted" in mechanisms:
        experiments += ["wasm_interpreted"] * n
    if "wasm_aot" in mechanisms:
        experiments += ["wasm_aot"] * n
    if "native" in mechanisms:
        experiments += ["native"] * n
    random.shuffle(experiments)

    # Keep track of trial number for each deployment mechanism
    docker_trial = 1
    wasm_interpreted_trial = 1
    wasm_aot_trial = 1
    native_trial = 1


    metrics = []

    MAX_RETRIES = 5

    for experiment in experiments:
        print(f"Starting {experiment} experiment")
        start_time = datetime.utcnow()

        if experiment == "docker":
            trial = docker_trial
            print(f"Trial {trial}")
            docker_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = docker_run_experiment_function(container_start_cmd + " " + container_exec_cmd, time_metrics)
                    remove_container(CONTAINER_NAME)
                    trial_metrics_rows = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, time_metrics_short_names)
                    metrics.extend(trial_metrics_rows)
                    break
                except Exception as e:
                    print(f"Error during docker trial {trial}, attempt {attempt + 1}: {e}")
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_interpreted":
            trial = wasm_interpreted_trial
            print(f"Trial {trial}")
            wasm_interpreted_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = non_container_run_experiment_function(wasm_interpreted_cmd, time_metrics)
                    trial_metrics_rows = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, time_metrics_short_names)
                    metrics.extend(trial_metrics_rows)
                    break
                except Exception as e:
                    print(f"Error during wasm_interpreted trial {trial}, attempt {attempt + 1}: {e}")
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_aot":
            trial = wasm_aot_trial
            print(f"Trial {trial}")
            wasm_aot_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = non_container_run_experiment_function(wasm_aot_cmd, time_metrics)
                    trial_metrics_rows = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, time_metrics_short_names)
                    metrics.extend(trial_metrics_rows)
                    break
                except Exception as e:
                    print(f"Error during wasm_aot trial {trial}, attempt {attempt + 1}: {e}")
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "native":
            trial = native_trial
            print(f"Trial {trial}")
            native_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = non_container_run_experiment_function(native_cmd, time_metrics)
                    trial_metrics_rows = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, time_metrics_short_names)
                    metrics.extend(trial_metrics_rows)
                    break
                except Exception as e:
                    print(f"Error during native trial {trial}, attempt {attempt + 1}: {e}")
                    if attempt == MAX_RETRIES - 1:
                        raise
    
    # Write the results into a CSV
    field_names = CSV_BASIC_FIELD_NAMES + time_metrics_short_names
    write_metrics_to_csv(results_filename, field_names, metrics)

# TODO: remove time_metrics as arg if only
def collect_only_max_rss_data(n, time_metrics, results_filename, container_exec_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms):
    collect_time_data(n, time_metrics, results_filename, run_container_max_rss_experiment, 
        run_time_experiment, container_exec_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)

def collect_only_time_data(n, time_metrics, results_filename, container_exec_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms):
    collect_time_data(n, time_metrics, results_filename, run_time_experiment,
        run_time_experiment, container_exec_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)

def prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics_sets, metrics_keys):
    # trial_metrics_sets is a list of tuples in format ("special_identifier", trial_metrics_set)
    # where trial_metrics_set is a list consisting of the trial metrics themselves
    # Used so can store different types of metrics for the same experiment type, eg. for
    # container perf experiment we want to store one set of metrics for the container
    # and another for the Docker overhead
    trial_metrics_rows = []

    for trial_metrics_set in trial_metrics_sets:
        identifier = trial_metrics_set[0]
        trial_metrics = trial_metrics_set[1]
    
        trial_metrics_row = {
            "experiment_type": experiment + identifier,
            "trial_number": trial,
            "start_time": start_time.isoformat(),
        }

        for metric_key in metrics_keys:
            trial_metrics_row[metric_key] = trial_metrics[metric_key]
        
        trial_metrics_rows.append(trial_metrics_row)

    return trial_metrics_rows

def write_metrics_to_csv(results_filename, field_names, metrics):
    with open(results_filename, "w", newline="") as csv_file:
        print(f"Writing results to {results_filename}")
        writer = csv.DictWriter(csv_file, fieldnames = field_names)
        writer.writeheader()
        writer.writerows(metrics)

# time_metrics is unused, only need it so can pass as function
def run_container_max_rss_experiment(cmd, time_metrics):
    start_cadvisor_if_not_running()
    cmd = TIME_CMD_PREFIX.split() + cmd.split()
    time_output = run_shell_cmd_and_get_stderr(cmd)
    time_metrics = [MAX_RSS_TIME_IDENTIFIER_AND_SHORTHAND]
    parsed_time_output = parse_time_output(time_output, time_metrics)

    prometheus_output = query_prometheus(PROMETHEUS_MAX_RSS_QUERY)
    parsed_prometheus_output = parse_prometheus_output(prometheus_output)

    trial_metrics = {}
    trial_metrics[MAX_RSS_TIME_SHORTHAND] = parsed_time_output[MAX_RSS_TIME_SHORTHAND] + \
        parsed_prometheus_output[MAX_RSS_TIME_IDENTIFIER_IN_PROMETHEUS]

    return [("", trial_metrics)] 

def run_time_experiment(cmd, time_metrics):
    stop_cadvisor_if_running()
    cmd = TIME_CMD_PREFIX.split() + cmd.split()
    time_output = run_shell_cmd_and_get_stderr(cmd)

    return [("", parse_time_output(time_output, time_metrics))]

def parse_time_output(output, time_metrics):
    metrics = {}
    for line in output.split("\n"):
        for metric in time_metrics:
            metric_full_name = metric[0]
            metric_short_name = metric[1]

            if metric_full_name in line:
                words = line.strip().split()
                raw_value = words[-1]
                
                if metric_short_name == "wall-time-seconds":
                    time_parts = raw_value.split(":")
                    float_time_parts = [float(time_part) for time_part in time_parts]
                    if len(time_parts) == 2: # m:ss format
                        mins, seconds = float_time_parts
                        value = mins * 60 + seconds
                    elif len(time_parts) == 3: # h:mm:ss format
                        hours, mins, seconds = float_time_parts
                        value = hours * 3600 + mins * 60

                elif metric_short_name == "max-rss-bytes":
                    value = int(raw_value) * 1024

                metrics[metric_short_name] = value

    return metrics

def collect_perf_data(n, perf_events, results_filename, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd,
    mechanisms=["docker", "wasm_interpreted", "wasm_aot", "native"]):
    # Randomly intersperse experiments of each type
    experiments = []
    if "docker" in mechanisms:
        experiments += ["docker"] * n
    if "wasm_interpreted" in mechanisms:
        experiments += ["wasm_interpreted"] * n
    if "wasm_aot" in mechanisms:
        experiments += ["wasm_aot"] * n
    if "native" in mechanisms:
        experiments += ["native"] * n
    random.shuffle(experiments)

    # Keep track of trial number for each deployment mechanism
    docker_trial = 1
    wasm_interpreted_trial = 1
    wasm_aot_trial = 1
    native_trial = 1

    metrics = []

    MAX_RETRIES = 20

    for experiment in experiments:
        print(f"Starting {experiment} experiment")
        start_time = datetime.utcnow()
        
        # TODO: use constants for experiment types
        if experiment == "docker":
            trial = docker_trial
            print(f"Trial {trial}")
            docker_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_container_perf_and_memory_experiment(perf_events, container_exec_cmd, container_start_cmd)
                    remove_container(CONTAINER_NAME)
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during docker trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_interpreted":
            trial = wasm_interpreted_trial
            print(f"Trial {trial}")
            wasm_interpreted_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, wasm_interpreted_cmd)
                    # TODO: currently delete series/remove container cmds repeated after each trial here instead of in
                    # the experiment functions, because in time_data there is a function that is used for both container and non-container
                    cleanup_custom_cgroup()
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during wasm_interpreted trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_aot":
            trial = wasm_aot_trial
            print(f"Trial {trial}")
            wasm_aot_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, wasm_aot_cmd)
                    cleanup_custom_cgroup()
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during wasm_aot trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "native":
            trial = native_trial
            print(f"Trial {trial}")
            native_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, native_cmd)
                    cleanup_custom_cgroup()
                    delete_prometheus_series_given_id(f"/{CUSTOM_CGROUP_NAME}")
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during native trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    if attempt == MAX_RETRIES - 1:
                        raise

    
    # Write the results into a CSV
    field_names = CSV_BASIC_FIELD_NAMES + perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES
    write_metrics_to_csv(results_filename, field_names, metrics)

    stop_cadvisor()

#TODO: do start, stop prometheus too

def start_cadvisor():
    run_shell_cmd_in_background(CADVISOR_START_CMD.split())
    time.sleep(3)

def start_cadvisor_if_not_running():
    global cadvisor_running
    if not cadvisor_running:
        start_cadvisor()
        cadvisor_running = True

# Need to stop it whenever we are about to run an experiment using perf stat,
# since otherwise perf stat cannot access the performance counters cAdvisor
# is using
def stop_cadvisor():
    run_shell_cmd(CADVISOR_STOP_CMD.split())

def stop_cadvisor_if_running():
    global cadvisor_running
    if cadvisor_running:
        stop_cadvisor()
        cadvisor_running = False

def run_non_container_perf_and_memory_experiment(perf_events, cmd): 
    start_cadvisor_if_not_running()

    # Create the cgroup that the  process will be assigned to
    run_shell_cmd(CREATE_CGROUP_CMD.split())

    start_time = datetime.utcnow()
    start_timestamp = start_time.timestamp()

    # TODO: parameterize the commands
    run_in_cgroup_cmd = EXEC_IN_CGROUP_CMD_PREFIX.split() + cmd.split()
    run_shell_cmd(run_in_cgroup_cmd)

    end_time = datetime.utcnow()
    end_timestamp = end_time.timestamp()

    execution_duration_ms = round((end_timestamp - start_timestamp) * 1000)

    # TODO: replace with container_name argument
    metrics = {}

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES, PROMETHEUS_QUERIES_LABELS):
        # TODO: standardize whether or not we're using / at the start of name or id more properyl
        formatted_query = query.format(name_or_id=f"/{CUSTOM_CGROUP_NAME}", 
            container_duration_ms=execution_duration_ms, end_container_timestamp=end_timestamp)
        metrics.update(get_parsed_prometheus_query_results(formatted_query, label))

    return [("", metrics)]

def run_container_perf_and_memory_experiment(perf_events, container_exec_cmd, container_start_cmd):
    start_cadvisor_if_not_running()

    start_container_time = datetime.utcnow()
    start_container_timestamp = start_container_time.timestamp()

    # TODO: parameterize the commands
    container_cmd = container_start_cmd.split() + container_exec_cmd.split()
    run_shell_cmd(container_cmd)

    end_container_time = datetime.utcnow()
    end_container_timestamp = end_container_time.timestamp()

    container_duration_ms = round((end_container_timestamp - start_container_timestamp) * 1000)
    
    # TODO: replace with container_name argument
    container_cgroup_id = get_cgroup_id_for_container(CONTAINER_NAME)
    container_metrics = {}

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES_WITH_NAME, PROMETHEUS_QUERIES_LABELS):
        formatted_query = query.format(name_or_id=CONTAINER_NAME, container_duration_ms=container_duration_ms, 
            end_container_timestamp=end_container_timestamp)
        container_metrics.update(get_parsed_prometheus_query_results(formatted_query, label))

    container_and_daemon_metrics = {}

    for query, label in zip(PROMETHEUS_DOCKER_COMBINED_PERF_AND_MEMORY_QUERIES, PROMETHEUS_QUERIES_LABELS):
        formatted_query = query.format(name_or_id=container_cgroup_id, container_duration_ms=container_duration_ms, 
            end_container_timestamp=end_container_timestamp)
        container_and_daemon_metrics.update(get_parsed_prometheus_query_results(formatted_query, label))

    return [("_container", container_metrics), ("_container_and_daemon", container_and_daemon_metrics)]

def elementwise_sum(arr_x, arr_y):
    if len(arr_x) != len(arr_y):
        raise ValueError("Arrays must be of the same length to sum them elementwise")
    return [x_val + y_val for x_val, y_val in zip(arr_x, arr_y)]

def stop_container(container_name):
    cmd = CONTAINER_STOP_CMD.format(container_name=container_name).split()
    run_shell_cmd(cmd)

def remove_container(container_name):
    cmd = CONTAINER_REMOVE_CMD.format(container_name=container_name).split()
    delete_prometheus_series_given_name(container_name)
    run_shell_cmd(cmd)

def get_cgroup_id_for_container(container_name):
    cmd = CONTAINER_INSPECT_ID_CMD.format(container_name=container_name).split()
    # We first strip whitespace from the command, then strip the single quotes from the output
    # Otherwise the last single quote will not be caught
    container_id = run_shell_cmd_and_get_stdout(cmd).strip().strip("'")

    if is_cgroup_v2():
        return f"/system.slice/docker-{container_id}.scope"
    # TODO: test this on an actual system with cgroup v1
    else:
        return f"memory/docker/{container_id}"

def run_shell_cmd_and_get_stdout(cmd):
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE).stdout

def run_shell_cmd_and_get_stderr(cmd):
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.DEVNULL, 
        stderr=subprocess.PIPE).stderr

def run_shell_cmd(cmd):
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(cmd)}")
        print(f"Return code: {e.returncode}")
        print(f"Output: {e.output}")
        print(f"Error: {e.stderr}")
        raise

def run_shell_cmd_in_background(cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)

def query_prometheus(query):
    params = {"query": query}
    return query_prometheus_with_params(params)

def query_prometheus_with_params(params):
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", 
        params)
    data = response.json()
    if data["status"] != "success":
        raise Exception("Error: Prometheus query failed")
    return data["data"]["result"]


def delete_prometheus_series_given_name(name):
    """Deletes Prometheus data for series with a given name. This function is
    required because sometimes, metrics collected from the execution of
    eg. a container from a previous trial can persist."""
    match = f"{{name='{name}'}}"
    delete_prometheus_series(match)

def cleanup_custom_cgroup():
    run_shell_cmd(DELETE_CGROUP_CMD.split())
    delete_prometheus_series_given_id(CUSTOM_CGROUP_NAME)

def delete_prometheus_series_given_id(id):
    """Deletes Prometheus data for series with a given name. This function is
    required because metrics collected from the execution of
    eg. a process within the same cgroup from a previous trial can persist."""
    match = f"{{id='{id}'}}"
    delete_prometheus_series(match)

def delete_prometheus_series(match):
    params = {"match[]": match}
    response = requests.post(f"{PROMETHEUS_URL}/api/v1/admin/tsdb/delete_series", params=params)
    if response.status_code != 204:
        raise Exception("Error: Prometheus series deletion failed")

def get_parsed_prometheus_query_results(query, label=None):
    data = query_prometheus(query)
    return parse_prometheus_output(data, label)

def parse_prometheus_output(output, label=None):
    # TODO: detect if instruction not counted and inform user
    metrics = {}
    for entry in output:
        metric = entry["metric"]
        if "event" in metric:
            key = metric["event"]
        elif "__name__" in metric:
            key = metric["__name__"]
        else:
            key = label if label is not None else "unknown_metric"

        # If the metric contains multiple values, make sure we use all of them
        if "values" in entry:
            value = [round(float(value), 2) for _, value in entry["values"]]
        else:
            value = round(float(entry["value"][1]), 2)
        metrics[key] = value
    return metrics

def main():
    # Parse the command line arguments to determine which model and input to use
    parser = argparse.ArgumentParser(description="Benchmark the performance of different edge ML deployment mechanisms")
    parser.add_argument("--model", type=str, required=True, help="The ML model to use")
    parser.add_argument("--input", type=str, required=True, help="The input file to run ML inference on")
    parser.add_argument("--trials", type=int, required=True, help="The number of trials to run for each experiment type")
    parser.add_argument("--mechanisms", type=str, default="docker,wasm_interpreted,wasm_aot,native",
                        help="Comma-separated list of mechanisms to include (choose from docker, wasm_interpreted, wasm_aot, native)")
    parser.add_argument("--arch", type=str, required=True, help="The architecture to ")

    args = parser.parse_args()
    model = args.model
    input_file = args.input
    trials = args.trials
    mechanisms = set(m.strip().lower() for m in args.mechanisms.split(","))
    arch = args.arch

    # Path to the model and input
    model_path = f"models/{model}"
    input_path = f"inputs/{input_file}"

    img_name = IMG_NAME_TEMPLATE.format(arch=arch)

    # The command to execute the workload inside the container
    container_start_cmd = CONTAINER_START_CMD_TEMPLATE.format(img_name=img_name)
    container_exec_cmd = f"./{NATIVE_BINARY_NAME} {model_path} {input_path}"
    
    # For Macs, the AoT Wasm file must have the .so extension
    if is_mac():
        aot_wasm_file_path = AOT_WASM_FILE_PATH_TEMPLATE.format(extension="so")
    else:
        aot_wasm_file_path = AOT_WASM_FILE_PATH_TEMPLATE.format(extension="wasm")


    # The commands to execute for the WebAssembly deployment mechanisms
    wasm_interpreted_cmd =f"{WASM_BINARY_PATH} --dir .:. {INTERPRETED_WASM_FILE_PATH} {model_path} {input_path}"
    wasm_aot_cmd = f"{WASM_BINARY_PATH} --dir .:. {aot_wasm_file_path} {model_path} {input_path}"

    # The command to execute for the native deployment mechanism
    native_cmd = f"{NATIVE_BINARY_PATH} {model_path} {input_path}"

    program_start_time = datetime.utcnow().isoformat()

    results_filename_prefix = program_start_time + f"{model}" + f"{input_file}"

    try:
        # TODO: clean up custom cgroup in case previous execution did not terminate properly

        # TODO: sort out args after adding new ones
        collect_perf_data(trials, PERF_EVENTS, results_filename_prefix + PERF_RESULTS_FILENAME, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)
        collect_only_time_data(trials, [TIME_METRICS[0]], results_filename_prefix + TIME_RESULTS_FILENAME, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)
        #collect_only_max_rss_data(trials, [TIME_METRICS[1]], MAX_RSS_RESULTS_FILENAME + program_start_time, container_exec_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd)
    finally:
        stop_cadvisor()

if __name__ == "__main__":
    main()
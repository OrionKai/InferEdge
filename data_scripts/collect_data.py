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
from datetime import datetime, timezone
from sys import platform

# The absolute path of the "scripts" directory where this script is in TODO: fix
SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))

# The absolute path of the parent "Benchmark" directory
BENCHMARK_DIR = os.path.join(SCRIPTS_DIR, "..")
# Right now BENCHMARK_DIR = SCRIPTS_DIR because putting this script in the SCRIPTS_DIR
# caused path problems, so this script is currently on the root level of the Benchmark directory
BENCHMARK_DIR = SCRIPTS_DIR

# The absolute path of the directory storing results
RESULTS_DIR = os.path.join(BENCHMARK_DIR, "results")

# Path to the WebAssembly binary
WASM_BINARY_PATH = os.path.expanduser("~/.wasmedge/bin/wasmedge")

# Path to the WebAssembly files
INTERPRETED_WASM_FILE_PATH = f"{BENCHMARK_DIR}/wasm/interpreted.wasm"
AOT_WASM_FILE_PATH_TEMPLATE = f"{BENCHMARK_DIR}/wasm/aot.{{extension}}"

# Path to cAdvisor perf events config file
CADVISOR_PERF_CONFIG_PATH = f"{BENCHMARK_DIR}/cadvisor/perf_config.json"

# The list of perf events to measure
def read_perf_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
        return config.get("core").get("events")

PERF_EVENTS = read_perf_config(CADVISOR_PERF_CONFIG_PATH)

# Path to the cAdvisor, Prometheus binaries
CADVISOR_BINARY_PATH = f"{BENCHMARK_DIR}/cadvisor/cadvisor"
PROMETHEUS_BINARY_PATH = f"{BENCHMARK_DIR}/prometheus/prometheus"

# Path to the native-compiled code
NATIVE_BINARY_NAME = "torch_image_classification"
NATIVE_BINARY_PATH = f"{BENCHMARK_DIR}/native/{NATIVE_BINARY_NAME}"

MODELS_PATH = f"{BENCHMARK_DIR}/models"
INPUTS_PATH = f"{BENCHMARK_DIR}/inputs"

# Container and image names
CONTAINER_NAME="benchmarked-container"
IMG_NAME_TEMPLATE="image-classification:{arch}"         

# Commands to start, stop, remove, inspect container
# CONTAINER_START_CMD_TEMPLATE=f"sudo docker run --privileged --name {CONTAINER_NAME} {{img_name}}"
CONTAINER_START_CMD_TEMPLATE = f"sudo docker run --privileged --name {CONTAINER_NAME} -v {MODELS_PATH}:/models -v {INPUTS_PATH}:/inputs {{img_name}}"

CONTAINER_STOP_CMD = "sudo docker stop {container_name}"
CONTAINER_REMOVE_CMD = "sudo docker rm {container_name}"
CONTAINER_INSPECT_ID_CMD = "sudo docker inspect -f '{{{{.Id}}}}' {container_name}"

# Commands to start and stop Prometheus, cAdvisor
PROMETHEUS_START_CMD = f"sudo {PROMETHEUS_BINARY_PATH} --config.file={BENCHMARK_DIR}/prometheus/prometheus.yml --web.enable-admin-api" 
PROMETHEUS_STOP_CMD = f"sudo pkill -f {PROMETHEUS_BINARY_PATH}"
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

# The list of metrics from running time to measure, alongside the 
# new name of the metric as it will be written in the results file
TIME_METRICS = [("Elapsed (wall clock) time", "wall-time-seconds")]

# The endpoint that Prometheus is listening on
PROMETHEUS_URL="http://localhost:9090"

# The suffixes of the filenames to store results in
PERF_RESULTS_FILENAME_SUFFIX = "_perf_results.csv"
TIME_RESULTS_FILENAME_SUFFIX = "_time_results.csv"

# Basic field names to include in every CSV file storing experiment results
CSV_BASIC_FIELD_NAMES = ["deployment-mechanism", "trial-number", "start-time"] 

# Field names for memory metrics
MEMORY_FIELD_NAMES = ["avg-memory-over-time-sampled", "max-memory-over-time-sampled", "max-memory-over-time"]

# Field names for CPU metrics
CPU_FIELD_NAMES = ["cpu-total-utilization", "cpu-user-utilization", "cpu-system-utilization"]

# Number of CPU cores 
NUM_CORES = os.cpu_count()

# Name of custom cgroup we will execute non-container processes in, so cAdvisor and Prometheus can track
# their metrics
CUSTOM_CGROUP_NAME = "custom"

# How long we measure the Docker daemon's metrics for, as a baseline, before the 
# container experiment is started
DAEMON_MEASUREMENT_TIME = 10

# How long we wait after cAdvisor & Prometheus are started before starting an experiment
CADVISOR_PROMETHEUS_WAIT_TIME = 20

## Prometheus queries
PROMETHEUS_CONTAINER_MEMORY_USAGE_BYTES_FIELD_NAME = "container_memory_usage_bytes"
PROMETHEUS_QUERIES_LABELS = [None] + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES

# The daemon's ID as expected by Prometheus
DAEMON_ID = "/system.slice/docker.service"

PROMETHEUS_PERF_AND_MEMORY_QUERIES = [
    "sum by (event) (container_perf_events_total{{id='{name_or_id}'}})",
    "avg_over_time(container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "max_over_time(container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})",
    "container_memory_max_usage_bytes{{id='{name_or_id}'}}",
    "100 * rate(container_cpu_usage_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_user_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}",
    "100 * rate(container_cpu_system_seconds_total{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f})" + f" / {NUM_CORES}"
]

# When trying to measure a baseline for the Docker daemon's overhead, we need to get a time-independent measure for perf events, so 
# use rate, since we cannot guarantee that the measurement time for the baseline will be the same as the container
# execution time
PROMETHEUS_PERF_QUERIES_RATE = """sum by (event) (rate(container_perf_events_total{{id='{name_or_id}'}}[{container_duration_ms}ms] 
    @ {end_container_timestamp:.2f}))"""

# Similarly when measuring the total increase in the Docker daemon's overhead, we use increase since the daemon will have been running
# from before the experiment started, so it would contain values that do not directly correspond to the experiment's
PROMETHEUS_PERF_QUERIES_INCREASE = """sum by (event) (increase(container_perf_events_total{{id='{name_or_id}'}}[{container_duration_ms}ms]
    @ {end_container_timestamp:.2f}))"""

# Queries for the Docker daemon's overhead when measuring its baseline state
PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_BASELINE = [PROMETHEUS_PERF_QUERIES_RATE.replace("{name_or_id}", DAEMON_ID)]
for query in PROMETHEUS_PERF_AND_MEMORY_QUERIES[1:]:
    PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_BASELINE.append(query.replace("{name_or_id}", DAEMON_ID))

# Queries for the Docker daemon's overhead when measuring it during the container experiment
PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_DURING_CONTAINER = [PROMETHEUS_PERF_QUERIES_INCREASE.replace("{name_or_id}", DAEMON_ID)]
for query in PROMETHEUS_PERF_AND_MEMORY_QUERIES[1:]:
    PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_DURING_CONTAINER.append(query.replace("{name_or_id}", DAEMON_ID))

PROMETHEUS_DOCKER_DAEMON_MEMORY_QUERY = "container_memory_usage_bytes{{id='/system.slice/docker.service'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}"
PROMETHEUS_DOCKER_CONTAINER_MEMORY_QUERY = "container_memory_usage_bytes{{id='{name_or_id}'}}[{container_duration_ms}ms] @ {end_container_timestamp:.2f}"

# The commands used to start a custom cgroup and execute a command in it
CREATE_CGROUP_CMD=f"sudo cgcreate -g memory:{CUSTOM_CGROUP_NAME}"
EXEC_IN_CGROUP_CMD_PREFIX=f"sudo LD_LIBRARY_PATH={LD_LIBRARY_PATH} PATH={PATH} cgexec -g memory:{CUSTOM_CGROUP_NAME}"
DELETE_CGROUP_CMD=f"sudo cgdelete -g memory:{CUSTOM_CGROUP_NAME}"

# Variable tracking whether cAdvisor and Prometheus are currently running or not
cadvisor_and_prometheus_running = False

def is_cgroup_v2():
    return os.path.isfile("/sys/fs/cgroup/cgroup.controllers")

def is_mac():
    return platform == "darwin"

def collect_time_data(n, time_metrics, results_filename, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd,
    deployment_mechanisms=["docker","wasm_interpreted","wasm_aot","native"]):
    time_metrics_short_names = [time_metric[1] for time_metric in time_metrics]

    # Randomly intersperse experiments of each type
    experiments = []
    if "docker" in deployment_mechanisms:
        experiments += ["docker"] * n
    if "wasm_interpreted" in deployment_mechanisms:
        experiments += ["wasm_interpreted"] * n
    if "wasm_aot" in deployment_mechanisms:
        experiments += ["wasm_aot"] * n
    if "native" in deployment_mechanisms:
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
        start_time = datetime.now(timezone.utc)
        trial_metrics = {}

        if experiment == "docker":
            trial = docker_trial
            print(f"Trial {trial}")
            docker_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_time_experiment(container_start_cmd + " " + container_exec_cmd, time_metrics)
                    remove_container(CONTAINER_NAME)
                    trial_metrics_rows = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, time_metrics_short_names)
                    metrics.extend(trial_metrics_rows)
                    break
                except Exception as e:
                    print(f"Error during docker trial {trial}, attempt {attempt + 1}: {e}")
                    remove_container(CONTAINER_NAME)
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_interpreted":
            trial = wasm_interpreted_trial
            print(f"Trial {trial}")
            wasm_interpreted_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_time_experiment(wasm_interpreted_cmd, time_metrics)
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
                    trial_metrics = run_time_experiment(wasm_aot_cmd, time_metrics)
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
                    trial_metrics = run_time_experiment(native_cmd, time_metrics)
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
            "deployment-mechanism": experiment + identifier,
            "trial-number": trial,
            "start-time": start_time.isoformat(),
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

def run_time_experiment(cmd, time_metrics):
    stop_cadvisor_and_prometheus_if_running()
    cmd = TIME_CMD_PREFIX.split() + cmd.split()
    time_output = run_shell_cmd_and_get_stderr(cmd)

    return [("", parse_time_output(time_output, time_metrics))]

def parse_time_output(output, time_metrics):
    metrics = {}
    for line in output.split("\n"):
        for metric in time_metrics:
            metric_actual_name = metric[0]
            metric_new_name = metric[1]

            if metric_actual_name in line:
                words = line.strip().split()
                raw_value = words[-1]
                
                if metric_new_name == "wall-time-seconds":
                    time_parts = raw_value.split(":")
                    float_time_parts = [float(time_part) for time_part in time_parts]
                    if len(time_parts) == 2: # m:ss format
                        mins, seconds = float_time_parts
                        value = mins * 60 + seconds
                    elif len(time_parts) == 3: # h:mm:ss format
                        hours, mins, seconds = float_time_parts
                        value = hours * 3600 + mins * 60 + seconds

                metrics[metric_new_name] = value

    return metrics

def collect_perf_data(n, perf_events, results_filename, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd,
    deployment_mechanisms=["docker", "wasm_interpreted", "wasm_aot", "native"]):
    # Randomly intersperse experiments of each type
    experiments = []
    if "docker" in deployment_mechanisms:
        experiments += ["docker"] * n
    if "wasm_interpreted" in deployment_mechanisms:
        experiments += ["wasm_interpreted"] * n
    if "wasm_aot" in deployment_mechanisms:
        experiments += ["wasm_aot"] * n
    if "native" in deployment_mechanisms:
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
        start_time = datetime.now(timezone.utc)
        trial_metrics = {}
        
        if experiment == "docker":
            trial = docker_trial
            print(f"Trial {trial}")
            docker_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_container_perf_and_memory_experiment(perf_events, container_exec_cmd, container_start_cmd)
                    remove_container_and_its_prometheus_data(CONTAINER_NAME)
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during docker trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    remove_container(CONTAINER_NAME)
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_interpreted":
            trial = wasm_interpreted_trial
            print(f"Trial {trial}")
            wasm_interpreted_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, wasm_interpreted_cmd)
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during wasm_interpreted trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    cleanup_custom_cgroup()
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "wasm_aot":
            trial = wasm_aot_trial
            print(f"Trial {trial}")
            wasm_aot_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, wasm_aot_cmd)
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during wasm_aot trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    cleanup_custom_cgroup()
                    if attempt == MAX_RETRIES - 1:
                        raise
        elif experiment == "native":
            trial = native_trial
            print(f"Trial {trial}")
            native_trial += 1
            for attempt in range(MAX_RETRIES):
                try:
                    trial_metrics = run_non_container_perf_and_memory_experiment(perf_events, native_cmd)
                    #delete_prometheus_series_given_id(f"/{CUSTOM_CGROUP_NAME}") TODO: check if this was necessary
                    trial_metrics_row = prepare_trial_data_as_csv_rows(experiment, trial, start_time, trial_metrics, 
                        perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES)
                    metrics.extend(trial_metrics_row)
                    break
                except Exception as e:
                    print(f"Error during native trial {trial}, attempt {attempt + 1}: {e}")
                    print(trial_metrics)
                    cleanup_custom_cgroup()
                    if attempt == MAX_RETRIES - 1:
                        raise
    
    # Write the results into a CSV
    field_names = CSV_BASIC_FIELD_NAMES + perf_events + MEMORY_FIELD_NAMES + CPU_FIELD_NAMES
    write_metrics_to_csv(results_filename, field_names, metrics)

    stop_cadvisor_and_prometheus()

def start_cadvisor_and_prometheus():
    start_cadvisor()
    start_prometheus()
    global cadvisor_and_prometheus_running
    cadvisor_and_prometheus_running = True

def start_prometheus():
    run_shell_cmd_in_background(PROMETHEUS_START_CMD.split())

def start_cadvisor():
    run_shell_cmd_in_background(CADVISOR_START_CMD.split())

def start_cadvisor_and_prometheus_if_not_running():
    global cadvisor_and_prometheus_running
    if not cadvisor_and_prometheus_running:
        start_cadvisor_and_prometheus()

    # Give cAdvisor and Prometheus time to start up
    time.sleep(CADVISOR_PROMETHEUS_WAIT_TIME)

def stop_cadvisor_and_prometheus():
    stop_cadvisor()
    stop_prometheus()   
    global cadvisor_and_prometheus_running
    cadvisor_and_prometheus_running = False

def stop_prometheus():
    run_shell_cmd(PROMETHEUS_STOP_CMD.split())

def stop_cadvisor():
    run_shell_cmd(CADVISOR_STOP_CMD.split())

def stop_cadvisor_and_prometheus_if_running():
    global cadvisor_and_prometheus_running
    if cadvisor_and_prometheus_running:
        stop_cadvisor_and_prometheus()
        

def run_non_container_perf_and_memory_experiment(perf_events, cmd): 
    start_cadvisor_and_prometheus_if_not_running()

    # Create the cgroup that the process will be assigned to
    run_shell_cmd(CREATE_CGROUP_CMD.split())

    start_time = datetime.now(timezone.utc)
    start_timestamp = start_time.timestamp()

    run_in_cgroup_cmd = EXEC_IN_CGROUP_CMD_PREFIX.split() + cmd.split()
    run_shell_cmd(run_in_cgroup_cmd)

    end_time = datetime.now(timezone.utc)
    end_timestamp = end_time.timestamp()

    execution_duration_ms = round((end_timestamp - start_timestamp) * 1000)

    metrics = {}

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES, PROMETHEUS_QUERIES_LABELS):
        # TODO: standardize whether or not we're using / at the start of name or id more properyl
        formatted_query = query.format(name_or_id=f"/{CUSTOM_CGROUP_NAME}", 
            container_duration_ms=execution_duration_ms, end_container_timestamp=end_timestamp)
        metrics.update(get_parsed_prometheus_query_results(formatted_query, label))

    cleanup_custom_cgroup()

    return [("", metrics)]

def run_container_perf_and_memory_experiment(perf_events, container_exec_cmd, container_start_cmd):
    start_cadvisor_and_prometheus_if_not_running()

    # Clear the daemon's cgroup first, so maximum memory usage is not affected by memory
    # usage that occured before the experiment
    cleanup_daemon_cgroup()

    # Get the daemon's baseline metrics
    daemon_metrics_baseline = {}
    time.sleep(DAEMON_MEASUREMENT_TIME)

    curr_time = datetime.now(timezone.utc)
    curr_timestamp = curr_time.timestamp()

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_BASELINE, PROMETHEUS_QUERIES_LABELS):
        formatted_query = query.format(container_duration_ms=DAEMON_MEASUREMENT_TIME * 1000, 
            end_container_timestamp=curr_timestamp)
        daemon_metrics_baseline.update(get_parsed_prometheus_query_results(formatted_query, label))

    # Run the container and time the execution
    start_container_time = datetime.now(timezone.utc)
    start_container_timestamp = start_container_time.timestamp()

    container_cmd = container_start_cmd.split() + container_exec_cmd.split()
    run_shell_cmd(container_cmd)

    end_container_time = datetime.now(timezone.utc)
    end_container_timestamp = end_container_time.timestamp()

    container_duration_ms = round((end_container_timestamp - start_container_timestamp) * 1000)
    
    # Get the container's metrics during the execution time
    container_cgroup_id = get_cgroup_id_for_container(CONTAINER_NAME)
    container_metrics = {}

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES, PROMETHEUS_QUERIES_LABELS):
        formatted_query = query.format(name_or_id=container_cgroup_id, container_duration_ms=container_duration_ms, 
            end_container_timestamp=end_container_timestamp)
        container_metrics.update(get_parsed_prometheus_query_results(formatted_query, label))

    # Get the daemon's metrics during that same time
    daemon_metrics_during_container = {}

    for query, label in zip(PROMETHEUS_PERF_AND_MEMORY_QUERIES_DAEMON_DURING_CONTAINER, PROMETHEUS_QUERIES_LABELS):
        formatted_query = query.format(container_duration_ms=container_duration_ms, 
            end_container_timestamp=end_container_timestamp)
        daemon_metrics_during_container.update(get_parsed_prometheus_query_results(formatted_query, label))

    # Sum the metrics for the container and the daemon during the container's execution
    container_and_daemon_metrics = {key: container_metrics[key] + daemon_metrics_during_container[key] 
        for key in container_metrics}

    # Multiply the perf events part of the daemon's baseline metrics by the container's execution time in
    # seconds, since the former was obtained using rate
    for perf_event in PERF_EVENTS:
        daemon_metrics_baseline[perf_event] = round(daemon_metrics_baseline[perf_event] * (container_duration_ms / 1000))

    # Subtract the daemon's baseline metrics from the daemon's metrics during the container's execution
    daemon_extra_overhead_metrics = {key: max(0, daemon_metrics_during_container[key] - daemon_metrics_baseline[key])
        for key in daemon_metrics_during_container}

    # Sum the metrics for the container and only the extra overhead for the daemon during the container's execution
    container_and_daemon_extra_overhead_metrics = {key: container_metrics[key] + daemon_extra_overhead_metrics[key]
        for key in container_metrics}

    return [("_container", container_metrics), ("_container_and_daemon", container_and_daemon_metrics),
        ("_container_and_daemon_extra_overhead", container_and_daemon_extra_overhead_metrics)]

def stop_container(container_name):
    cmd = CONTAINER_STOP_CMD.format(container_name=container_name).split()
    run_shell_cmd(cmd)

def remove_container(container_name):
    cmd = CONTAINER_REMOVE_CMD.format(container_name=container_name).split()

    try:
        run_shell_cmd(cmd)
    except subprocess.CalledProcessError as e:
        # The following error happens if the container was not successfully
        # started in the first place; this does not necessarily indicate a 
        # major failure so we can ignore it
        if "No such container" not in e.stderr:
            raise

def remove_container_and_its_prometheus_data(container_name):
    remove_container(container_name)
    delete_prometheus_series_given_name(container_name)

def get_cgroup_id_for_container(container_name):
    cmd = CONTAINER_INSPECT_ID_CMD.format(container_name=container_name).split()
    # We first strip whitespace from the command, then strip the single quotes from the output
    # Otherwise the last single quote will not be caught
    container_id = run_shell_cmd_and_get_stdout(cmd).strip().strip("'")

    if is_cgroup_v2():
        return f"/system.slice/docker-{container_id}.scope"
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
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    if cgroup_exists(CUSTOM_CGROUP_NAME):
        run_shell_cmd(DELETE_CGROUP_CMD.split())
    delete_prometheus_series_given_id(CUSTOM_CGROUP_NAME)

def cgroup_exists(cgroup_name):
    # For cgroup v1, check in /sys/fs/cgroup/memory/cgroup_name
    path_v1 = f"/sys/fs/cgroup/memory/{cgroup_name}"
    # For cgroup v2, typically the unified hierarchy is mounted at /sys/fs/cgroup
    path_v2 = f"/sys/fs/cgroup/{cgroup_name}"
    
    return os.path.exists(path_v1) or os.path.exists(path_v2)

def cleanup_daemon_cgroup():
    delete_prometheus_series_given_id(DAEMON_ID)

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
        if label is not None:
            key = label
        elif "event" in metric:
            key = metric["event"]
        elif "__name__" in metric:
            key = metric["__name__"]
        else:
            key = "unknown_metric"

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
    parser.add_argument("--arch", type=str, required=True, help="The architecture of the target device this is being run on")
    parser.add_argument("--set_name", type=str, required=True, help="The name of the set of experiments being run")

    args = parser.parse_args()
    model = args.model
    input_file = args.input
    trials = args.trials
    mechanisms = set(m.strip().lower() for m in args.mechanisms.split(","))
    arch = args.arch
    set_name = args.set_name

    # Path to the model and input
    model_path = f"models/{model}"
    input_path = f"inputs/{input_file}"

    img_name = IMG_NAME_TEMPLATE.format(arch=arch)

    # The command to execute the workload inside the container
    container_start_cmd = CONTAINER_START_CMD_TEMPLATE.format(img_name=img_name)
    container_exec_cmd = f"./{NATIVE_BINARY_NAME} /{model_path} /{input_path}"
    
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

    results_filename_prefix = f"{model}_{input_file}"
    results_filename_prefix = results_filename_prefix.replace(".", "_")

    results_filename_prefix_with_path = os.path.join(RESULTS_DIR, set_name, results_filename_prefix)

    try:
        print("CURRENT TIME", datetime.now(timezone.utc))
        print("CURRENT TIME", datetime.now(timezone.utc).timestamp())
        # TODO: clean up custom cgroup in case previous execution did not terminate properly
        collect_perf_data(trials, PERF_EVENTS, results_filename_prefix_with_path + PERF_RESULTS_FILENAME_SUFFIX, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)
        collect_time_data(trials, TIME_METRICS, results_filename_prefix_with_path + TIME_RESULTS_FILENAME_SUFFIX, container_exec_cmd, container_start_cmd, wasm_interpreted_cmd, wasm_aot_cmd, native_cmd, mechanisms)
    finally:
        stop_cadvisor_and_prometheus()

if __name__ == "__main__":
    main()
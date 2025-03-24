#!/bin/bash
# This script analyzes performance and time results files from a specified results directory,
# runs the Python analysis for each pair (displaying its full output), and appends a summary CSV row
# for each pair with specific metrics. Note: most of this was generated using AI for prototyping purposes,
# so it is likely to require significant revision.
#
# Usage: $0 [results_dir] [include_insig_output]
# where include_insig_output should be "true" (to include the flag) or "false" (or omitted) to not include it.

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 [results_dir] [include_insig_output]"
    exit 1
fi

results_dir="$1"
include_insig_output="${2:-false}"  # defaults to false if not provided

# Significance level used for all runs
significance_level=0.05

# Create (or overwrite) CSV output file with header
OUTPUT_CSV="analysis_summary.csv"
echo ",Model,Mechanism,Max memory,Avg memory,Wall time" > "$OUTPUT_CSV"

# Loop over each performance results file in the results directory
for perf_file in "$results_dir"/*perf_results.csv; do
  # Extract the common prefix (everything before 'perf_results.csv')
  base="${perf_file%perf_results.csv}"
  # Construct the corresponding time results filename
  time_file="${base}time_results.csv"
  
  # Check whether the corresponding time results file exists
  if [ -f "$time_file" ]; then
    echo "Running analysis for:"
    echo "  Perf: $perf_file"
    echo "  Time: $time_file"
    
    # Run the Python analysis script for this pair and capture its full output.
    if [ "$include_insig_output" = "true" ]; then
      analysis_output=$(python3 analyze_data.py --perf_results "$perf_file" --time_results "$time_file" --significance_level "$significance_level" --include_insignificant_output)
    else
      analysis_output=$(python3 analyze_data.py --perf_results "$perf_file" --time_results "$time_file" --significance_level "$significance_level")
    fi
    
    # Display the full output from the Python analysis.
    echo "$analysis_output"
    
    # Extract wall-time averages (assumed to be the last occurrence of "docker average:" / "wasm_aot average:")
    docker_wall=$(echo "$analysis_output" | grep -i "docker average:" | tail -n 1 | awk '{print $3}')
    wasm_wall=$(echo "$analysis_output" | grep -i "wasm_aot average:" | tail -n 1 | awk '{print $3}')
    
    [ -z "$docker_wall" ] && docker_wall="NA"
    [ -z "$wasm_wall" ] && wasm_wall="NA"
    
    # Extract memory-related stats using awk.
    # Look for the block marked by "avg_memory_over_time" then capture the first subsequent "docker average:" and "wasm_aot average:" values.
    docker_avg_mem=$(echo "$analysis_output" | awk '/avg_memory_over_time/ {flag=1} flag && /docker average:/ {print $3; exit}')
    wasm_avg_mem=$(echo "$analysis_output" | awk '/avg_memory_over_time/ {flag=1} flag && /wasm_aot average:/ {print $3; exit}')
    
    # Similarly for max memory.
    docker_max_mem=$(echo "$analysis_output" | awk '/max_memory_over_time/ {flag=1} flag && /docker average:/ {print $3; exit}')
    wasm_max_mem=$(echo "$analysis_output" | awk '/max_memory_over_time/ {flag=1} flag && /wasm_aot average:/ {print $3; exit}')
    
    # Use "NA" as placeholder if memory values are not found.
    [ -z "$docker_avg_mem" ] && docker_avg_mem="NA"
    [ -z "$wasm_avg_mem" ] && wasm_avg_mem="NA"
    [ -z "$docker_max_mem" ] && docker_max_mem="NA"
    [ -z "$wasm_max_mem" ] && wasm_max_mem="NA"
    
    # Extract the model code from the performance results filename.
    # This assumes the filename contains a pattern like "resnet" followed by digits.
    model_code=$(basename "$perf_file" | grep -Eo "resnet[0-9]+")
    [ -z "$model_code" ] && model_code="UNKNOWN"
    
    # Append two rows to the CSV summary file:
    # First row for Docker; second row for AoT.
    echo ",${model_code},Docker,${docker_max_mem},${docker_avg_mem},${docker_wall}" >> "$OUTPUT_CSV"
    echo ",,AoT,${wasm_max_mem},${wasm_avg_mem},${wasm_wall}" >> "$OUTPUT_CSV"
    
    echo "Analysis for model ${model_code} appended to ${OUTPUT_CSV}."
    
    # Pause and wait for user input before processing the next pair.
    echo "Analysis complete. Press Enter to continue to the next pair..."
    read -r
  else
    echo "Warning: Time results file not found for $perf_file"
  fi
done

echo "CSV summary saved in ${OUTPUT_CSV}."
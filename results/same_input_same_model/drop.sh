#!/bin/bash
# Process each CSV file ending with perf_results.csv
for file in *perf_results.csv; do
    echo "Processing $file..."
    awk -F, 'BEGIN {OFS=","}
        NR==1 {
            # Rename headers:
            # Change "avg-memory-over-time-sampled" to "avg-memory-over-time-in-bytes"
            $14 = "avg-memory-over-time-in-bytes";
            # Change "max-memory-over-time" to "max-memory-over-time-in-bytes"
            $16 = "max-memory-over-time-in-bytes";
            # Rename utilization columns by appending "-percentage"
            $17 = "cpu-total-utilization-percentage";
            $18 = "cpu-user-utilization-percentage";
            $19 = "cpu-system-utilization-percentage";
            # Print desired columns: 1-14, skip 15, then 16-19
            print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$16,$17,$18,$19;
            next;
        }
        {
            # For data rows, print the same columns in order.
            print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$16,$17,$18,$19;
        }' "$file" > tmp && mv tmp "$file"
done

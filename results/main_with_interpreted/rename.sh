#!/bin/bash
for file in efficientnet*.csv; do
    newfile=$(echo "$file" | sed -E 's/^(.*_pt)_(.*)_(perf|time)_results\.csv$/\1-\2-\3_results.csv/')
    if [ "$file" != "$newfile" ]; then
        echo "Renaming '$file' to '$newfile'"
        mv "$file" "$newfile"
    fi
done

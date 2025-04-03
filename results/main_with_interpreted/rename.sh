#!/bin/bash
for file in *.csv; do
    newfile=$(echo "$file" | sed -E '
        s/^(.*_pt)_(.*)_(perf|time)_results\.csv$/\1-\2-\3_results.csv/;
        s/MultipleObjectsScenery/__MOS__/g;
        s/MultipleObjects/2_MultipleObjects/g;
        s/SingleObject/1_SingleObject/g;
        s/__MOS__/3_MultipleObjectsScenery/g;
        s/_(jpg|pt)/.\1/g
    ')
    if [ "$file" != "$newfile" ]; then
        echo "Renaming '$file' to '$newfile'"
        mv "$file" "$newfile"
    fi
done

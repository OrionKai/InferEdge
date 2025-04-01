#!/bin/bash
# This script is meant to be run on the Raspberry Pi to perform the data collection experiments for a number
# of different models and inputs.

export USERNAME=$(whoami)
export SUITE_PATH="/home/$USERNAME/Desktop/CS4099Suite"
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/$USERNAME/.wasmedge/lib64:$SUITE_PATH/libtorch/lib
export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin

function main() {
    # Check for the required arguments
    if [ "$#" -ne 3 ]; then
        echo "Usage: $0 <trials> <experiments set name> <mechanisms>"
        exit 1
    fi

    if [ "$(uname -m)" = "aarch64" ]; then
        arch="arm64"
    else
        arch="amd64"
    fi

    trials=$1
    set_name=$2
    mechanisms=$3

    cd $SUITE_PATH
    mkdir -p results/$set_name
    source myenv/bin/activate

    run_data_collection $trials
}

function run_data_collection() {
    # Iterate over each model file in the models folder and each input file in the inputs folder
    for model in models/*; do
        for input in inputs/*; do
            if [ -f "$model" ] && [ -f "$input" ]; then
                echo "Running collect_data.py with $(basename "$model") and $(basename "$input")"

                options=""
                if [ "$is_mac" = 1 ]; then
                    options="$options --is_mac"
                fi
                if [ "$allow_missing_metrics" = 1 ]; then
                    options="$options --allow_missing_metrics"
                fi

                if [ "$allow_missing_metrics" = 1 ]; then
                    python collect_data.py --model "$(basename "$model")" --input "$(basename "$input")" \
                        --trials $trials --set_name $set_name --mechanisms "$mechanisms" \
                        --arch $arch --allow_missing_metrics
                else
                    python collect_data.py --model "$(basename "$model")" --input "$(basename "$input")" \
                        --trials $trials --set_name $set_name --mechanisms "$mechanisms" \
                        --arch $arch
                fi
            fi
        done
    done
}

# Check for optional arguments: -a for allowing missing perf events and -m for Mac
while getopts "am" opt; do
    case $opt in
        a)
            allow_missing_metrics=1
            ;;
        m)
            is_mac=1
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Remove the processed options
shift $((OPTIND - 1))

main $1 $2 $3
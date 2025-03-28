#!/bin/bash
# This script is meant to be run on the Raspberry Pi to perform the data collection experiments for a number
# of different models and inputs.

export USERNAME=$(whoami)
export SUITE_PATH="/home/$USERNAME/Desktop/CS4099Suite"
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/$USERNAME/.wasmedge/lib64:$SUITE_PATH/libtorch/lib
export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin

function main() {
    if [ "$#" -ne 3 ]; then
        echo "Usage: $0 <trials> <experiments set name> <mechanisms>"
        exit 1
    fi

    if [ "$(uname -m)" == "aarch64" ]; then
        arch="arm64"
    else
        arch="amd64"
    fi

    trials=$1
    set_name=$2
    mechanisms=$3

    cd $SUITE_PATH
    mkdir results/$set_name
    source myenv/bin/activate

    run_data_collection $trials
}

function run_data_collection() {
    # Iterate over each model file in the models folder and each input file in the inputs folder
    for model in models/*; do
        for input in inputs/*; do
            if [[ -f "$model" && -f "$input" ]]; then
                echo "Running collect_data.py with $(basename "$model") and $(basename "$input")"
                python collect_data.py --model "$(basename "$model")" --input "$(basename "$input")" \
                    --trials $trials --set_name $set_name --mechanisms "$mechanisms" \
                    --arch $arch
            fi
        done
    done
}

main $1 $2 $3
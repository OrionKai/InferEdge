# This script is meant to be run on the Raspberry Pi to perform the data collection experiments for a number
# of different models and inputs.

export USERNAME=$(whoami)
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/$USERNAME/.wasmedge/lib64:/home/$USERNAME/libtorch/lib
export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin

function main() {
    if [ "$#" -ne 2 ]; then
        echo "Usage: $0 <suite name> <trials> <experiments set name>"
        exit 1
    fi

    suite_name=$1
    trials=$2
    set_name=$3

    cd $suite_path
    mkdir results/$set_name

    source python/myenv/bin/activate

    run_data_collection $trials
}

function run_data_collection() {
    # Iterate over each model file in the models folder and each input file in the inputs folder
    for model in models/*; do
        for input in inputs/*; do
            if [[ -f "$model" && -f "$input" ]]; then
                echo "Running collect_data.py with $(basename "$model") and $(basename "$input")"
                python collect_data.py --model "$(basename "$model")" --input "$(basename "$input")" --trials $trials --output-folder "results/$set_name"
            fi
        done
    done
}

main
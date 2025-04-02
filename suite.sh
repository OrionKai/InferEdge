#!/bin/bash
# Global variables
export PYTORCH_VERSION="1.7.1"
export PYTHON_VERSION="cp39"
export PYTORCH_ABI="libtorch-cxx11-abi"
export PROMETHEUS_VERSION="3.2.1"
export SUITE_NAME="CS4099Suite"

function main() {
    prompt_user_for_action
}

function prompt_user_for_target_details_if_not_set() {
    if [ -z "$target_address" ] || [ -z "$target_username" ] || [ -z "$target_password" ]; then
        prompt_user_for_target_details
    fi
}

function prompt_user_for_target_details() {
    read -p "Enter the target machine's address: " target_address
    read -p "Enter the target machine's username: " target_username
    read -s -p "Enter the target machine's password: " target_password
    echo
}

function prompt_user_for_architecture_if_not_set() {
    if [ -z "$arch" ]; then
        prompt_user_for_architecture
    fi
}

function prompt_user_for_architecture() {
    while true; do
        echo "Which of the following architectures does the target machine use?"
            echo "1. x86_64"
            echo "2. aarch64"
        local arch_input
        read -p "Enter the number identifying the architecture: " arch_input
        case $arch_input in
            1) arch="amd64"; break ;;
            2) arch="arm64"; break ;;
            *) echo "Invalid option." ;;
        esac
    done

    echo "Architecture set to $arch."
    prompt_user_for_mac_if_not_set
}

function prompt_user_for_mac_if_not_set() {
    if [ -z "$is_mac" ]; then
        prompt_user_for_mac
    fi
}

function prompt_user_for_mac() {
    while true; do
        echo "Is the target machine a Mac?"
            echo "1. Yes"
            echo "2. No"
        local is_mac_input
        read -p "Enter the number identifying the correct option: " is_mac_input
        case $is_mac_input in
            1) is_mac=1; break ;;
            2) is_mac=0; break ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function prompt_user_for_action() {
    while true; do
        echo "What would you like to do?"
            echo "1. Run the entire suite"
            echo "2. Perform specific actions"
            echo "3. Set/change target machine details"
            echo "4. Exit"
        local action
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) run_suite ;;
            2) prompt_user_for_specific_actions ;;
            3) prompt_user_for_target_details ;;
            4) exit 0 ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function run_suite() {
    prompt_user_for_target_details_if_not_set
    acquire_files
    transfer_files
    setup_target_machine
    run_data_collection
    retrieve_data_collection_results
    run_data_analysis
}

function prompt_user_for_specific_actions() {
    while true; do
        echo "What would you like to do?"
            echo "1. Acquire files to transfer to target machine"
            echo "2. Transfer files to target machine"
            echo "3. Setup target machine"
            echo "4. Run data collection on target machine"
            echo "5. Retrieve data collection results from target machine"
            echo "6. Run data analysis on host machine"
            echo "7. Back to main menu"
        local action
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) acquire_files ;;
            2) transfer_files ;;
            3) setup_target_machine ;;
            4) run_data_collection ;;
            5) retrieve_data_collection_results ;;
            6) run_data_analysis ;;
            7) prompt_user_for_action ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function acquire_files() {
    prompt_user_for_architecture_if_not_set
    if [ "$arch" = "arm64" ]; then
        setup_qemu
    fi
    # install_rust
    # install_python_and_dependencies # TODO: check if torchvision really required
    # generate_model_files

    # case $arch in
    #     "arm64") acquire_files_arm64_specific ;;
    #     "amd64") acquire_files_amd64_specific ;;
    # esac

    # build_cadvisor
    # download_prometheus 
    build_docker_and_native 
    # compile_wasm 
}

function setup_qemu() {
    echo "Setting up QEMU for aarch64..."
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
}

function install_rust() {
    if ! command -v rustc &> /dev/null; then
        echo "Rust is not installed. Would you like to install Rust through the script?"
            echo "1. Yes"
            echo "2. No"
        read -p "Enter the number identifying your choice: " choice
        if [ "$choice" = "1" ]; then
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
            source $HOME/.cargo/env
        else
            echo "Please install Rust manually and re-run this script."
            exit 1
        fi
    fi
}

function install_python_and_dependencies() {
    if ! command -v python3 &> /dev/null; then
        echo "Python3 is not installed. Would you like to install Python3 through the script?"
            echo "1. Yes"
            echo "2. No"
        read -p "Enter the number identifying your choice: " choice
        if [ "$choice" = "1" ]; then
            if [ "$uname -m" != "Darwin" ]; then
                sudo apt install python3 python3-pip python3-venv
            else 
                # For Macs
                brew install python3
            fi
        else
            echo "Please install Python3 manually and re-run this script."
            exit 1
        fi        
    fi

    python3 -m venv myenv
    source myenv/bin/activate

    # Check
    pip install -r python/host/requirements.txt
}

function generate_model_files() {
    echo "Generating model files..."

    mkdir -p models

    generate_mobilenet_model
    generate_efficientnet_models
    generate_resnet_models
}

function generate_efficientnet_models() {
    echo "Which EfficientNet models would you like to generate?"
        echo "1. EfficientNetB0"
        echo "2. EfficientNetB1"
        echo "3. EfficientNetB2"
        echo "4. EfficientNetB3"
        echo "5. EfficientNetB4"
        echo "6. EfficientNetB5"
        echo "7. EfficientNetB6"
        echo "8. EfficientNetB7"
    local efficientnet_input
    read -p "Enter the numbers identifying the EfficientNet models you would like to generate (comma-separated): " efficientnet_input
    
    IFS="," read -r -a efficientnet_models_idx <<< "$efficientnet_input"
    local efficientnet_models=()

    for efficientnet_model_idx in "${efficientnet_models_idx[@]}"; do
        case $efficientnet_model_idx in
            1) efficientnet_models+=("--b0") ;;
            2) efficientnet_models+=("--b1") ;;
            3) efficientnet_models+=("--b2") ;;
            4) efficientnet_models+=("--b3") ;;
            5) efficientnet_models+=("--b4") ;;
            6) efficientnet_models+=("--b5") ;;
            7) efficientnet_models+=("--b6") ;;
            8) efficientnet_models+=("--b7") ;;
        esac
    done

    cd models
    python3 ../host_scripts/model_generation/gen_efficientnet_models.py "${efficientnet_models[@]}"
    cd -
}

function generate_resnet_models() {
    echo "Which ResNet models would you like to generate?"
        echo "1. ResNet18"
        echo "2. ResNet34"
        echo "3. ResNet50"
        echo "4. ResNet101"
        echo "5. ResNet152"
    local resnet_input
    read -p "Enter the numbers identifying the ResNet models you would like to generate (comma-separated): " resnet_input

    IFS="," read -r -a resnet_models_idx <<< "$resnet_input"
    local resnet_models=()

    for resnet_model_idx in "${resnet_models_idx[@]}"; do
        case $resnet_model_idx in
            1) resnet_models+=("--resnet18") ;;
            2) resnet_models+=("--resnet34") ;;
            3) resnet_models+=("--resnet50") ;;
            4) resnet_models+=("--resnet101") ;;
            5) resnet_models+=("--resnet152") ;;
        esac
    done

    cd models
    python3 ../host_scripts/model_generation/gen_resnet_models.py "${resnet_models[@]}"
    cd -
}

function generate_mobilenet_model() {
    echo "Which MobileNet models would you like to generate?"
        echo "1. MobileNetV3-Small"
        echo "2. MobileNetV3-Large"
    local mobilenet_input
    read -p "Enter the numbers identifying the MobileNet models you would like to generate (comma-separated): " mobilenet_input
    
    IFS="," read -r -a mobilenet_models_idx <<< "$mobilenet_input"
    local mobilenet_models=()

    for mobilenet_model_idx in "${mobilenet_models_idx[@]}"; do
        case $mobilenet_model_idx in
            1) mobilenet_models+=("--mobilenetv3_small") ;;
            2) mobilenet_models+=("--mobilenetv3_large") ;;
        esac
    done

    cd models
    python3 ../host_scripts/model_generation/gen_mobilenet_models.py "${mobilenet_models[@]}"
    cd -
}

function acquire_files_arm64_specific() {
    download_libtorch_arm64 
    build_wasmedge "wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps" 
}

function acquire_files_amd64_specific() {
    download_libtorch_amd64
    build_wasmedge "wasmedge/wasmedge:manylinux_2_28_x86_64-plugins-deps"
}

function build_wasmedge() {
    echo "Building WasmEdge..."
    local image="$1"          # e.g. wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps

    local platform="linux/$arch"

    # Get the WasmEdge source code
    git clone https://github.com/WasmEdge/WasmEdge.git
    cd WasmEdge
    git checkout 61db304fc4041dfae7cc736858a999a221260933
    cd -

    # Give the script to run inside the container the necessary permissions
    chmod +x build_scripts/wasmedge/inside_docker_"$arch".sh

    local platform="linux/$arch"

    local build_dir="wasmedge"
    mkdir -p "$build_dir"

    # The build will randomly fail sometimes so we retry until it succeeds
    docker pull --platform "$platform" "$image"
    until sudo docker run --platform "$platform" --rm \
        --entrypoint /bin/bash \
        -v "$(pwd)/$build_dir":/root/wasmedge-install \
        -v "$(pwd)/WasmEdge":/root/wasmedge \
        -v "$(pwd)/libtorch":/root/libtorch \
        -v "$(pwd)/build_scripts/wasmedge/inside_docker_${arch}.sh":/root/inside_docker.sh \
        "$image" -c "git config --global --add safe.directory /root/wasmedge && /root/inside_docker.sh"
    do
        echo "WasmEdge build failed. Retrying..."
    done

    # The build by default stores the libwasmedgePluginWasiNN.so in the wrong directory
    # for some reason, so we move it here
    mkdir -p "$build_dir"/plugin

    # This file was technically created by another user when the Docker container was run
    # so we need to use sudo to move it
    sudo mv "$build_dir"/lib64/wasmedge/libwasmedgePluginWasiNN.so "$build_dir"/plugin

    # Clean up; again, we need to use sudo because some of the files inside this directory
    # were technically created by another user when the Docker container was run
    sudo rm -rf WasmEdge
}

function download_libtorch_arm64() {
    echo "Downloading libtorch..."
    local build_dir="libtorch"

    # Download and extract libtorch
    curl -s -L -o torch.whl https://download.pytorch.org/whl/cpu/torch-${PYTORCH_VERSION}-${PYTHON_VERSION}-${PYTHON_VERSION}-linux_aarch64.whl
    unzip torch.whl -d torch_unzipped
    rm -f torch.whl
    mkdir "$build_dir"
    mv torch_unzipped/torch/lib torch_unzipped/torch/bin torch_unzipped/torch/include \
        torch_unzipped/torch/share "$build_dir"
    rm -rf torch_unzipped
}

function download_libtorch_amd64() {
    echo "Downloading libtorch..."

    # Download and extract libtorch
    export TORCH_LINK="https://download.pytorch.org/libtorch/cpu/${PYTORCH_ABI}-shared-with-deps-${PYTORCH_VERSION}%2Bcpu.zip" && \
    curl -s -L -o torch.zip $TORCH_LINK && \
    unzip -q torch.zip && \
    rm -f torch.zip 
}

function build_cadvisor() {
    echo "Downloading cAdvisor..."

    local image_name="cadvisor-build:$arch"
    local build_dir="cadvisor"
    mkdir -p "$build_dir"

    # Build the container that will build cAdvisor
    docker buildx build --platform linux/"$arch" -t "$image_name" -f Dockerfiles/cadvisor_build/Dockerfile --output type=docker .

    # Create a temporary container so we can extract the 
    # build results
    local container_id=$(docker create "$image_name")
    docker cp "$container_id":/output/. "$build_dir"

    # Clean up the container
    docker rm "$container_id"
}

function download_prometheus() {
    echo "Downloading Prometheus..."
    local url="https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-${arch}.tar.gz"
    local output_file="prometheus.tar.gz"
    local extract_dir="prometheus-${PROMETHEUS_VERSION}.linux-${arch}"
    local temp_dir="prometheus_temp"
    
    curl -L -o "$output_file" "$url"
    mkdir -p "$temp_dir"
    tar -xzf "$output_file" -C "$temp_dir"
    mv "$temp_dir"/"$extract_dir"/prometheus prometheus

    rm -rf "$temp_dir"
    rm "$output_file"
}

function build_docker_and_native() {
    echo "Building the Docker image and native binary..."
    local image_name="image-classification:$arch"

    # Build the Docker container 
    docker buildx build --platform linux/"$arch" -t "$image_name" -f Dockerfiles/image_classification/Dockerfile --output type=docker .

    # Save the Docker container into a tar file
    docker save -o docker/image-classification-${arch}.tar "$image_name"

    # Extract the binary compiled for the container so it can also be run for the 
    # native deployment mechanism
    mkdir -p native
    local container_id=$(docker create "$image_name")
    docker cp "$container_id":/torch_image_classification native

    # Clean up the container
    docker rm "$container_id"
}

function compile_wasm() {
    echo "Compiling the WebAssembly binary..."
    cd rust/wasm
    rustup target add wasm32-wasip1
    cargo build --target=wasm32-wasip1 --release
    cd - 

    # Move the compiled Wasm binary to the wasm directory
    mkdir -p wasm
    mv rust/wasm/target/wasm32-wasip1/release/interpreted.wasm wasm
}   

function transfer_files() {
    prompt_user_for_target_details_if_not_set

    # Transfer the suite files to the target machine, including 
    # models, inputs, native & wasm binaries, libtorch, Docker tar file, the
    # data collection Python file, and the Cadvisor and Prometheus binaries
    echo "Transferring suite files to target device..."
    transfer_suite_files

    # Transfer the results of the WasmEdge build, which will be located
    # in a separate location to the rest of the suite
    echo "Transferring WasmEdge files to target device..."
    transfer_wasmedge_files
}   

function transfer_suite_files() {
    # Create a directory to store the suite files in the target machine
    sshpass -p "$target_password" ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/Desktop/$SUITE_NAME"

    # Transfer the suite files to the target machine
    sshpass -p "$target_password" scp -r models inputs native wasm libtorch cadvisor prometheus python docker target_scripts data_scripts/collect_data.py \
        "$target_username"@"$target_address":/home/"$target_username"/Desktop/"$SUITE_NAME"

    # Create a directory in the suite directory to store results 
    sshpass -p "$target_password" ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/Desktop/$SUITE_NAME/results"
}   

function transfer_wasmedge_files() {
    # Create a directory to store the WasmEdge files in the target machine
    sshpass -p "$target_password" ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/.wasmedge"

    # Transfer the WasmEdge files to the target machine
    sshpass -p "$target_password" scp -r wasmedge "$target_username"@"$target_address":/home/"$target_username"/.wasmedge
}

function setup_target_machine() {
    prompt_user_for_target_details_if_not_set

    # Ask the user if they want to run the script directly, in case the target
    # machine has an Internet connection, or if they want to simply transfer it in
    # case the target machine cannot access the Internet while connected to the host
    echo "How would you like to setup the target machine? Note that running the script
        requires that the target machine has an Internet connection."
        echo "1. Run the setup script directly on the target machine from this machine"
        echo "2. Run the setup script manually on the target machine"
    local setup_option
    read -p "Enter the number identifying the setup option: " setup_option
    case $setup_option in
        1) run_setup_script ;;
        2) transfer_setup_script ;;
        *) echo "Invalid option." ;;
    esac
}

function run_setup_script() {
    prompt_user_for_mac_if_not_set
    
    if [ "$is_mac" = 1 ]; then
        sshpass -p "$target_password" ssh -t "$target_username@$target_address" "chmod +x /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh && sudo /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh -m"
    else
        sshpass -p "$target_password" ssh -t "$target_username@$target_address" "chmod +x /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh && sudo /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh"
    fi
}

function transfer_setup_script() {
    echo "Please run the script on the target as follows: /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh"
    echo "If the target is on a Mac, please run the script on the target as follows instead: /home/$target_username/Desktop/$SUITE_NAME/target_scripts/setup.sh -m"

    echo "You may need to disconnect the target machine's Ethernet connection to allow it to connect to the Internet"
}

function run_data_collection() {
    prompt_user_for_target_details_if_not_set
    prompt_user_for_mac_if_not_set

    echo "Running data collection on target device..."

    local set_name
    read -p "Enter a name to identify this set of experiments: " set_name

    local trials
    read -p "Enter the number of trials to run for each experiment: " trials

    prompt_user_for_mechanisms

    echo "Would you like to allow experiment trials to have missing data on some metrics (e.g. instructions retired)?"
    echo "If you have doubts that the target machine can access perf metrics, you should answer 'yes'."
    echo "Additionally, if you are running the experiments on a virtual machine, you are advised to answer 'yes' as other metrics may be unavailable."
        echo "1. Yes"
        echo "2. No"
    local allow_missing_metrics_input
    read -p "Enter the number identifying your choice: " allow_missing_metrics_input
    case $allow_missing_metrics_input in
        1) allow_missing_metrics=1 ;;
        2) allow_missing_metrics=0 ;;
        *) echo "Invalid option." ;;
    esac

    options=""
    if [ "$is_mac" = 1 ]; then
        options="$options -m"
    fi
    if [ "$allow_missing_metrics" = 1 ]; then
        options="$options -a"
    fi

    sshpass -p "$target_password" ssh -t "$target_username@$target_address" "/home/$target_username/Desktop/$SUITE_NAME/target_scripts/collect_data.sh $options $trials $set_name $mechanisms"
}

function prompt_user_for_mechanisms() {
    echo "Which deployment mechanisms would you like to include? Note that when analyzing data, you can only include deployment mechanisms that were included in the data collection."
        echo "1. Native"
        echo "2. Docker"
        echo "3. WebAssembly interpreted"
        echo "4. WebAssembly ahead of time (AoT)-compiled"
    local mechanisms_input
    read -p "Enter the numbers identifying the deployment mechanisms you would like to include (comma-separated): " mechanisms_input

    # Convert the mechanisms input into a comma-separated string eg. "native,docker"
    IFS=',' read -ra mechanisms_array <<< "$mechanisms_input"
    mechanisms=()

    for mechanism in "${mechanisms_array[@]}"; do
        case $mechanism in
            1) mechanisms+=("native") ;;
            2) mechanisms+=("docker") ;;
            3) mechanisms+=("wasm_interpreted") ;;
            4) mechanisms+=("wasm_aot") ;;
        esac
    done

    mechanisms=$(IFS=,; echo "${mechanisms[*]}")
}

function retrieve_data_collection_results() {
    prompt_user_for_target_details_if_not_set

    echo "Retrieving results from target device..."

    local set_name
    read -p "Enter the name of the set of experiments to retrieve results from: " set_name

    sshpass -p "$target_password" scp -r "$target_username@$target_address:/home/$target_username/Desktop/$SUITE_NAME/results/$set_name" results
}

function run_data_analysis() {
    install_python_and_dependencies

    echo "Analyzing results of experiments..."

    local set_name
    read -p "Enter the name of the set of experiments to analyze: " set_name

    run_per_experiment_data_analysis $set_name

    echo "Would you like to perform aggregate analysis on the entire set of experiments, using the results of the previous analyses?"
        echo "1. Yes"
        echo "2. No"
    local aggregate_analysis_input
    read -p "Enter the number identifying your choice: " aggregate_analysis_input
    case $aggregate_analysis_input in
        1) run_aggregate_data_analysis $set_name ;;
        2) echo "Exiting..." ;;
        *) echo "Invalid option." ;;
    esac
}

function run_per_experiment_data_analysis() { 
    set_name=$1

    local significance_level
    read -p "Enter the significance level to be used for the analysis (if nothing is entered, the default of 0.05 will be used): " significance_level
    if [ -z "$significance_level" ]; then
        significance_level=0.05
    fi

    options=""
    local view_output
    echo "Would you like to view the output for each experiment? If you answer 'no', you can still choose to save the outputs to files."
        echo "1. Yes"
        echo "2. No"
    local view_output_input
    read -p "Enter the number identifying your choice: " view_output_input
    case $view_output_input in
        1) options="$options --view-output" ;;
        2) ;;
        *) echo "Invalid option." ;;
    esac 

    local save_output
    echo "Would you like to save the output for each experiment to a file?"
        echo "1. Yes"
        echo "2. No"
    local save_output_input
    read -p "Enter the number identifying your choice: " save_output_input
    case $save_output_input in
        1) options="$options --save-output" ;;
        2) ;;
        *) echo "Invalid option." ;;
    esac

    prompt_user_for_mechanisms
    prompt_user_for_metrics $set_name

    echo "Which view of the Docker deployment mechanism's overhead would you like to use?"
        echo "1. Include only the Docker container's overhead"
        echo "2. Include the Docker container's overhead and the Docker daemon's full overhead"
        echo "3. Include the Docker container's overhead and the Docker daemon's estimated additional overhead due to the container"
    local docker_overhead_input
    read -p "Enter the number identifying your choice: " docker_overhead_input
    case $docker_overhead_input in
        1) docker_overhead=0 ;;
        2) docker_overhead=1 ;;
        3) docker_overhead=2 ;;
        *) echo "Invalid option." ;;
    esac

    if [ "$view_output_input" = 1 ]; then
        local include_insig_output
        echo "Would you like to print statistically insignificant output during the analysis?"
            echo "1. Yes"
            echo "2. No"
        local include_insig_output_input
        read -p "Enter the number identifying your choice: " include_insig_output_input
        case $include_insig_output_input in
            1) options="$options --include_insignificant_output" ;;
            2) ;;
            *) echo "Invalid option." ;;
        esac
    fi
    
    # For each combination of model and input, there's a perf results file and a time results file
    # so only need to iterate over one of them
    for results_file in $(ls results/$set_name/*time_results.csv); do
        model=$(basename "$results_file" | cut -d '-' -f 1)
        input=$(basename "$results_file" | cut -d '-' -f 2)
        echo "Analyzing data for $model and $input..."
        echo data_scripts/analyze_data.py \
            --experiment-set "$set_name" \
            --model "$model" \
            --input "$input" \
            --significance-level "$significance_level" \
            --docker-overhead-view "$docker_overhead" \
            --mechanisms "$mechanisms" \
            --metrics "$metrics" \
            $options 
        python3 data_scripts/analyze_data.py \
            --experiment-set "$set_name" \
            --model "$model" \
            --input "$input" \
            --significance-level "$significance_level" \
            --docker-overhead-view "$docker_overhead" \
            --mechanisms "$mechanisms" \
            --metrics "$metrics" \
            $options 
        echo "Analysis complete. Press Enter to continue to the next experiment..."
        read -r
    done
}

function prompt_user_for_metrics() {
    set_name=$1

    echo "Based on the data collected, the following metrics are available for analysis:"
        # Read one time file and one perf file to get the available metrics
        time_file=$(ls results/$set_name/*time_results.csv | head -n 1)
        perf_file=$(ls results/$set_name/*perf_results.csv | head -n 1)

        # The first 3 columns are the same for all result files; they only include non-metric columns
        # such as deployment mechanism, trial number and start time
        time_metrics=$(head -n 1 "$time_file" | tr -d '\r' | cut -d ',' -f 4-)
        perf_metrics=$(head -n 1 "$perf_file" | tr -d '\r' | cut -d ',' -f 4-)

        echo "time metrics: $time_metrics"

        echo "$time_metrics,$perf_metrics"
    read -p "Enter the metrics you would like to analyze (comma-separated). If nothing is entered, all metrics will be used: " metrics
    if [ -z "$metrics" ]; then
        metrics="$time_metrics,$perf_metrics"
    fi
}

function list_models_and_inputs() {
    set_name=$1

    echo "Based on the data collected, the following models and inputs are available for analysis:"
        # Read the aggregate results file's unique values for the first and second columns, which
        # correspond to the model and input respectively
        models=$(cut -d ',' -f 1 results/$set_name/analyzed_results/aggregate_results.csv | tail -n +2 | sort -u| paste -sd, -)        
        inputs=$(cut -d ',' -f 2 results/$set_name/analyzed_results/aggregate_results.csv | tail -n +2 | sort -u| paste -sd, -)

        echo "models: $models"
        echo "inputs: $inputs"
}

function run_aggregate_data_analysis() {
    set_name=$1

    prompt_user_for_metrics $set_name

    local options=""
    local view_output
    echo "Would you like to view all of the plots that will be produced? If you answer 'no', you can still choose to save the outputs to files."
        echo "1. Yes"
        echo "2. No"
    local view_output_input
    read -p "Enter the number identifying your choice: " view_output_input
    case $view_output_input in
        1) options="$options --view-output" ;;
        2) ;;
        *) echo "Invalid option." ;;
    esac 

    local save_output
    echo "Would you like to save all of the plots to files?"
        echo "1. Yes"
        echo "2. No"
    local save_output_input
    read -p "Enter the number identifying your choice: " save_output_input
    case $save_output_input in
        1) options="$options --save-output" ;;
        2) ;;
        *) echo "Invalid option." ;;
    esac

    list_models_and_inputs $set_name

    echo "Would you like to compare across models?"
        echo "1. Yes"
        echo "2. No"
    local compare_across_models_input
    read -p "Enter the number identifying your choice: " compare_across_models_input
    case $compare_across_models_input in
        1) compare_across_models=1 ;;
        2) compare_across_models=0 ;;
        *) echo "Invalid option." ;;
    esac

    if [ "$compare_across_models" = 1 ]; then
        read -p "Enter the models to compare (comma-separated): " models_to_compare
        read -p "Enter the input to use in comparing models: " input
        options="$options --compare-across-models --models-to-compare $models_to_compare --input $input"
    fi

    echo "Would you like to compare across inputs?"
        echo "1. Yes"
        echo "2. No"
    local compare_across_inputs_input
    read -p "Enter the number identifying your choice: " compare_across_inputs_input
    case $compare_across_inputs_input in
        1) compare_across_inputs=1 ;;
        2) compare_across_inputs=0 ;;
        *) echo "Invalid option." ;;
    esac

    if [ "$compare_across_inputs" = 1 ]; then
        read -p "Enter the inputs to compare (comma-separated): " inputs_to_compare
        read -p "Enter the model to use in comparing inputs: " model
        options="$options --compare-across-inputs --inputs-to-compare $inputs_to_compare --model $model"
    fi

    echo data_scripts/analyze_aggregate_data.py \
        --experiment-set "$set_name" \
        --metrics "$metrics" \
        $options

    python3 data_scripts/analyze_aggregate_data.py \
        --experiment-set "$set_name" \
        --metrics "$metrics" \
        $options
}

main
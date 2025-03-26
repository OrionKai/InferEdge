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
    prompt_user_for_architecture_if_not_set
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

    # If target architecture is aarch64, set up QEMU
    if [ "$arch" = "arm64" ]; then
        echo "Setting up QEMU for aarch64..."
        docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    fi
}

function prompt_user_for_action() {
    while true; do
        echo "What would you like to do?"
            echo "1. Run the entire suite"
            echo "2. Perform specific actions"
            echo "3. Set/change target machine details"
        local action
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) run_suite ;;
            2) prompt_user_for_specific_actions ;;
            3) prompt_user_for_target_details ;;
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
    #install_rust
    #install_python_and_dependencies
    #generate_model_files

    case $arch in
        "arm64") acquire_files_arm64_specific ;;
        "amd64") acquire_files_amd64_specific ;;
    esac

    #build_cadvisor
    #download_prometheus 
    #build_docker_and_native 
    #compile_wasm 
}

function install_rust() {
    if ! command -v rustc &> /dev/null; then
        echo "Rust is not installed. Would you like to install Rust through the script?"
            echo "1. Yes"
            echo "2. No"
        read -p "Enter the number identifying your choice: " choice
        if [ "$choice" == "1" ]; then
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
        if [ "$choice" == "1" ]; then
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
    pip install -r python/host/requirements.txt
}

function generate_model_files() {
    echo "Generating model files..."
    for script in models/gen_*.py; do
        python3 "$script"
    done

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
    python3 gen_efficientnet_models.py "${efficientnet_models[@]}"
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
    python3 gen_resnet_models.py "${resnet_models[@]}"
    cd -
}

function generate_mobilenet_model() {
    echo "Would you like to generate the MobileNet model?"
        echo "1. Yes"
        echo "2. No"
    local mobilenet_input
    read -p "Enter the number identifying your choice: " mobilenet_input

    if [ "$mobilenet_input" = "1" ]; then
        cd models
        python3 gen_mobilenet_model.py
        cd -
    fi
}

function acquire_files_arm64_specific() {
    # Just do build wasmedge and build cadvisor
    download_libtorch_arm64 # ok
    build_wasmedge "wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps" # not ok
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

    local platform="linux/$arch"

    docker pull --platform "$platform" "$image"
    local container_id=$(sudo docker run --platform "$platform" --rm \
        -v "$(pwd)/WasmEdge":/root/wasmedge \
        -v "$(pwd)/libtorch":/root/libtorch \
        -v "$(pwd)/build_scripts/wasmedge/inside_docker_${arch}.sh":/root/inside_docker.sh \
        "$image" /bin/bash /root/inside_docker.sh)

    # Copy and execute the inside_docker.sh script inside the container 
    # TODO: script not being run inside container
    # docker cp build_scripts/wasmedge/inside_docker_"$arch".sh "$container_id":/root/inside_docker.sh
    # docker exec "$container_id" /bin/bash /root/inside_docker.sh

    local build_dir="wasmedge"

    # Copy the build results into the wasmedge directory
    mkdir -p "$build_dir"
    docker cp "$container_id":/root/wasmedge-install/. "$build_dir"
    mkdir -p "$build_dir"/plugin
    mv "$build_dir"/lib64/wasmedge/libwasmedgePluginWasiNN.so "$build_dir"/plugin

    # Clean up the container
    docker stop "$container_id"
    docker rm "$container_id"

    rm -rf WasmEdge
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
    echo "Transferring files to target device..."
    prompt_user_for_target_details_if_not_set

    # Transfer the suite files to the target machine, including 
    # models, inputs, native & wasm binaries, libtorch, Docker tar file, the
    # data collection Python file, and the Cadvisor and Prometheus binaries
    # TODO: keep getting permission denied
    transfer_suite_files

    # Transfer the results of the WasmEdge build, which will be located
    # in a separate location to the rest of the suite
    transfer_wasmedge_files
}   

function transfer_suite_files() {
    # Create a directory to store the suite files in the target machine
    sshpass -p "$target_password" ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/$SUITE_NAME"

    # Transfer the suite files to the target machine
    sshpass -p "$target_password" scp -r models inputs native wasm libtorch cadvisor prometheus python docker data_scripts/collect_data.py \
        "$target_username"@"$target_address":/home/"$target_username"/"$SUITE_NAME"

    # Create a directory in the suite directory to store results 
    sshpass -p "$target_password" ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/$SUITE_NAME/results"
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
    echo "How would you like to setup the target machine?"
        echo "1. Run the setup script directly on the target machine"
        echo "2. Transfer the setup script to the target machine, so you can run it there manually"
    local setup_option
    read -p "Enter the number identifying the setup option: " setup_option
    case $setup_option in
        1) run_setup_script ;;
        2) transfer_setup_script ;;
        *) echo "Invalid option." ;;
    esac

    sshpass -p "$target_password" ssh "$target_username@$target_address" 'bash -s' < target_scripts/setup.sh
}

function run_setup_script() {
    sshpass -p "$target_password" ssh "$target_username@$target_address" 'bash -s' < target_scripts/setup.sh
}

function transfer_setup_script() {
    sshpass -p "$target_password" scp target_scripts/setup.sh "$target_username@$target_address":/home/"$target_username"/"$SUITE_NAME"
}

function run_data_collection() {
    prompt_user_for_target_details_if_not_set

    echo "Running data collection on target device..."

    local set_name
    read -p "Enter a name to identify this set of experiments: " set_name

    sshpass -p "$target_password" ssh "$target_username@$target_address" 'bash -s' < target_scripts/collect_data.sh
}

function retrieve_data_collection_results() {
    prompt_user_for_target_details_if_not_set

    echo "Retrieving results from target device..."

    local set_name
    read -p "Enter the name of the set of experiments to retrieve results from: " set_name

    sshpass -p "$target_password" scp -r "$target_username@$target_address:/home/$target_username/$SUITE_NAME/results/$set_name" results
}

function run_data_analysis() {
    echo "Analyzing results of experiments..."

    local set_name
    read -p "Enter the name of the set of experiments to analyze: " set_name
    host_scripts/analyze_data.sh results/$set_name false
}

main
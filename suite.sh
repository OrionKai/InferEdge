#!/bin/bash
# Global variables
export PYTORCH_VERSION="1.7.1"
export PYTHON_VERSION="cp39"
export PYTORCH_ABI="libtorch-cxx11-abi"
export PROMETHEUS_VERSION="3.2.1"
export SUITE_NAME="CS4099Suite"

function main() {
    if [ "$#" -ne 3 ]; then
        echo "Usage: $0 <target address> <target username> <target password>"
        exit 1
    fi

    target_address=$1
    target_username=$2
    target_password=$3

    prompt_user_for_architecture

    # If target architecture is aarch64, set up QEMU
    if [ "$arch" = "arm64" ]; then
        echo "Setting up QEMU for aarch64..."
        docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    fi

    prompt_user_for_action
}

function prompt_user_for_architecture() {
    while true; do
        echo "Which of the following architectures does the target machine use?"
            echo "1. x86_64"
            echo "2. aarch64"
        local arch_input
        read -p "Enter the number identifying the architecture: " arch_input
        case $arch_input in
            1) arch="amd64" ;;
            2) arch="arm64" ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function prompt_user_for_action() {
    while true; do
        echo "What would you like to do?"
            echo "1. Run the entire suite"
            echo "2. Perform specific actions"
        local action
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) run_suite ;;
            2) prompt_user_for_specific_actions ;;
            *) echo "Invalid option." ;;
        esac
    done
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
        local action
        read -p "Enter the number identifying the action you would like to perform: " action
        case $action in
            1) acquire_files ;;
            2) transfer_files ;;
            3) setup_target_machine ;;
            4) run_data_collection ;;
            5) retrieve_data_collection_results ;;
            6) run_data_analysis ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function acquire_files() {
    case $arch in
        "arm64") acquire_files_arm64 ;;
        "amd64") acquire_files_amd64 ;;
    esac
}

function acquire_files_arm64() {
    build_wasmedge "wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps" 
    download_libtorch_arm64
    build_cadvisor 
    download_prometheus
    build_docker_and_native 
    compile_wasm
}

function acquire_files_amd64() {
    build_wasmedge "wasmedge/wasmedge:manylinux_2_28_x86_64-plugins-deps"
    download_libtorch_amd64
    build_cadvisor 
    download_prometheus 
    build_docker_and_native 
    compile_wasm
}

function build_wasmedge() {
    local image="$1"          # e.g. wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps

    local platform="linux/$arch"

    # Get the WasmEdge source code
    git clone https://github.com/WasmEdge/WasmEdge.git
    cd WasmEdge
    git checkout 61db304fc4041dfae7cc736858a999a221260933
    cd -

    local platform="linux/$arch"

    docker pull --platform "$platform" "$image"
    local container_id=$(sudo docker run -d --platform "$platform" \
        -v ./WasmEdge:/root/wasmedge \
        -v ./libtorch:/root/libtorch \
        "$image")

    # Copy and execute the inside_docker.sh script inside the container 
    docker cp build_scripts/wasmedge/inside_docker_"$arch" "$container_id":/root/inside_docker.sh
    docker exec -it "$container_id" /bin/bash /root/inside_docker.sh

    local build_dir="wasmedge"

    # Copy the build results into the wasmedge directory
    mkdir -p "$build_dir"
    docker cp "$container_id":/root/wasmedge-install/. "$build_dir"
    mkdir -p "$build_dir"/plugin
    mv "$build_dir"/lib64/wasmedge/libwasmedgePluginWasiNN.so "$build_dir"/plugin

    # Clean up the container
    docker stop "$container_id"
    docker rm "$container_id"
}

function download_libtorch_arm64() {
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
    # Download and extract libtorch
    export TORCH_LINK="https://download.pytorch.org/libtorch/cpu/${PYTORCH_ABI}-shared-with-deps-${PYTORCH_VERSION}%2Bcpu.zip" && \
    curl -s -L -o torch.zip $TORCH_LINK && \
    unzip -q torch.zip && \
    rm -f torch.zip 
}

function build_cadvisor() {
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
    local image_name="image-classification:$arch"

    # Build the Docker container 
    docker buildx build --platform linux/"$arch" -t "$image_name" --output type=docker .

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
    cd rust/wasm
    cargo build --target=wasm32-wasi --release
    cd - 
}   

function transfer_files() {
    # Transfer the suite files to the target machine, including 
    # models, inputs, native & wasm binaries, libtorch, Docker tar file, the
    # data collection Python file, and the Cadvisor and Prometheus binaries
    transfer_suite_files

    # Transfer the results of the WasmEdge build, which will be located
    # in a separate location to the rest of the suite
    transfer_wasmedge_files
}   

function transfer_suite_files() {
    # Create a directory to store the suite files in the target machine
    ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/$SUITE_NAME"

    # Transfer the suite files to the target machine
    scp -r models inputs native wasm libtorch cadvisor prometheus python docker data_scripts/collect_data.py \
        "$target_username"@"$target_address":/home/"$target_username"/"$SUITE_NAME"

    # Create a directory in the suite directory to store results 
    ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/$SUITE_NAME/results"
}   

function transfer_wasmedge_files() {
    # Create a directory to store the WasmEdge files in the target machine
    ssh "$target_username"@"$target_address" "mkdir -p /home/$target_username/.wasmedge"

    # Transfer the WasmEdge files to the target machine
    scp -r wasmedge "$target_username"@"$target_address":/home/"$target_username"/.wasmedge
}

function setup_target_machine() {
    ssh "$target_username@$target_address" 'bash -s' < target_scripts/setup.sh
}

function run_data_collection() {
    local set_name
    read -p "Enter a name to identify this set of experiments: " set_name

    ssh "$target_username@$target_address" 'bash -s' < target_scripts/collect_data.sh
}

function retrieve_data_collection_results() {
    local set_name
    read -p "Enter the name of the set of experiments to retrieve results from: " set_name

    scp -r "$target_username@$target_address:/home/$target_username/$SUITE_NAME/results/$set_name" results
}

function run_data_analysis() {
    local set_name
    read -p "Enter the name of the set of experiments to analyze: " set_name
    host_scripts/analyze_data.sh results/$set_name false
}

main()

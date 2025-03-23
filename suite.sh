#!/bin/bash
# Global variables
export PYTORCH_VERSION="1.7.1"
export PYTHON_VERSION="cp39"

main() {
    if [ "$#" -ne 3 ]; then
        echo "Usage: $0 <target address> <target username> <target password>"
        exit 1
    fi

    target_address=$1
    target_username=$2
    target_password=$3

    prompt_user_for_architecture
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
            1) target_architecture="x86_64" ;;
            2) target_architecture="aarch64" ;;
            *) echo "Invalid option." ;;
        esac
    done
}

function prompt_user_for_action() {
    while true; do
        echo "What would you like to do?"
            echo "1. Run the entire suite"
            echo "2. Perform specific actions"
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
    case $target_architecture in
        "aarch64") acquire_files_aarch64 ;;
        "x86_64") acquire_files_x86_64 ;;
    esac
}

function acquire_files_aarch64() {
    build_wasmedge "linux/arm64" "wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps" "inside_docker_arm64.sh"
    download_libtorch_aarch64
    build_cadvisor_aarch64
    build_prometheus_aarch64
    build_docker_aarch64
    compile_native_aarch64
    compile_wasm
}

function acquire_files_x86_64() {
    build_wasmedge "linux/amd64" "wasmedge/wasmedge:manylinux_2_28_x86_64-plugins-deps" "inside_docker_arm64.sh"
}

function build_wasmedge() {
    local platform="$1"       # e.g. linux/arm64 or linux/amd64
    local image="$2"          # e.g. wasmedge/wasmedge:manylinux_2_28_aarch64-plugins-deps
    local inside_docker_script="$3" # e.g. inside_docker_arm64.sh

    # Get the WasmEdge source code
    git clone https://github.com/WasmEdge/WasmEdge.git
    cd WasmEdge
    git checkout 61db304fc4041dfae7cc736858a999a221260933
    cd ..

    # For arm64, set up QEMU
    if [ "$platform" == "linux/arm64" ]; then
        docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    fi

    docker pull --platform "$platform" "$image"
    CONTAINER_ID=$(sudo docker run -d --platform "$platform" \
        -v ./WasmEdge:/root/wasmedge \
        "$image")

    # Copy and execute the inside_docker.sh script inside the container 
    docker cp build_scripts/wasmedge/"$inside_docker_script" "$CONTAINER_ID":/root/inside_docker.sh
    docker exec -it "$CONTAINER_ID" /bin/bash /root/inside_docker.sh

    # Copy the build results into the wasmedge directory
    mkdir -p wasmedge
    docker cp "$CONTAINER_ID":/root/wasmedge-install/. wasmedge
    mkdir -p wasmedge/plugin
    mv wasmedge/lib64/wasmedge/libwasmedgePluginWasiNN.so wasmedge/plugin
}

function download_libtorch_aarch64() {
    # Download and extract libtorch, then set necessary paths
    curl -s -L -o torch.whl https://download.pytorch.org/whl/cpu/torch-${PYTORCH_VERSION}-${PYTHON_VERSION}-${PYTHON_VERSION}-linux_aarch64.whl
    unzip torch.whl -d torch_unzipped
    rm -f torch.whl
    mkdir libtorch
    mv torch_unzipped/torch/lib torch_unzipped/torch/bin torch_unzipped/torch/include torch_unzipped/torch/share libtorch
    rm -rf torch_unzipped
}

function download_libtorch_x86_64() {

}

function build_cadvisor_aarch64() {

}

function build_cadvisor_x86_64() {

}

function build_prometheus_aarch64() {

}

function build_prometheus_x86_64() {

}

function build_docker_aarch64() {

}

function build_docker_x86_64() {

}

function compile_native_aarch64() {

}

function compile_native_x86_64() {

}

function compile_wasm() {

}

function transfer_files() {
    # Transfer the results of the build to the target machine
    # scp -r wasmedge pi@192.168.0.100:/home/pi/.wasmedge
}

main()

# This script is meant to be run on the Raspberry Pi to perform one-time setup of the environment in preparation 
# for the experiments.
DESKTOP_DIRECTORY="~/Desktop"
BENCHMARK_DIRECTORY="$DESKTOP_DIRECTORY/Benchmark"
BENCHMARK_SCRIPTS_DIRECTORY="$BENCHMARK_DIRECTORY/scripts"
DOCKER_TAR_FILE="docker-mechanism.tar"
PYTORCH_VERSION="1.7.1"
PYTHON_VERSION="cp39"
USERNAME=$(whoami)

sudo apt-get update

# Move the wasmedge file to the appropriate location
# After downloading the WasmEdge-install folder TODO: add to suite-files
mv wasmedge/* /home/$USERNAME/.wasmedge
chmod u+x /home/$USERNAME/.wasmedge/bin/wasmedge
# Create symbolic links in case they were not uploaded 
ln -s /home/$USERNAME/.wasmedge/lib64/libwasmedge.so.0.1.0 /home/$USERNAME/.wasmedge/lib64/libwasmedge.so
ln -s /home/$USERNAME/.wasmedge/lib64/libwasmedge.so.0.1.0 /home/$USERNAME/.wasmedge/plugin/libwasmedge.so.0

# Ensure memory controller enabled for cgroup v2
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CGROUP_ENABLE_PARAM="cgroup_enable=memory"
CURRENT_CMDLINE_CONTENTS="$(cat "$CMDLINE_FILE")"

if !grep -q "$CGROUP_ENABLE_PARAM" <<< "$CURRENT_CMDLINE_CONTENTS"
then 
    echo "$CMDLINE_FILE does not contain parameters to enable memory controller" 
    echo "Backing up original $CMDLINE_FILE to $CMDLINE_FILE.bak"
    sudo cp "$CMDLINE_FILE" "$CMDLINE_FILE.bak"

    echo "Adding required parameters to $CMDLINE_FILE"
    NEW_CMDLINE_CONTENTS="${CURRENT_CMDLINE_CONTENTS} ${CGROUP_ENABLE_PARAM}"

    echo "Successfully updated $CMDLINE_FILE, reboot the system for the changes to take effect"
    sudo sh -c "echo '$NEW_CMDLINE_CONTENTS' > $CMDLINE_FILE"
fi

# Setup Prometheus
sudo docker pull prom/prometheus:latest
mkdir -p ~/prometheus/config

# Setup cAdvisor TODO: add to suite-files
sudo apt-get install libpfm4 linux-perf
# mkdir -p $DESKTOP_DIRECTORY/cadvisor_files
# mv cadvisor $DESKTOP_DIRECTORY/cadvisor_files
# mv 
# cd Desktop
# mkdir cadvisor_files
# mv cadvisor cadvisor_files
# mv perf_config.json cadvisor_files

# Load the container
docker load -i "$DOCKER_TAR_FILE"

# Setup Python (no script to transfer scripts, requirements.txt yet)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip cgroup-tools
python3 -m venv "$BENCHMARK_SCRIPTS_DIRECTORY/myenv" 
source "$BENCHMARK_SCRIPTS_DIRECTORY/myenv/bin/activate" && pip install -r requirements.txt

# Download and extract libtorch, then set necessary paths (currently only for ARM64)
curl -s -L -o torch.whl https://download.pytorch.org/whl/cpu/torch-${PYTORCH_VERSION}-${PYTHON_VERSION}-${PYTHON_VERSION}-linux_aarch64.whl
unzip torch.whl -d torch_unzipped
rm -f torch.whl
mkdir libtorch
mv torch_unzipped/torch/lib torch_unzipped/torch/bin torch_unzipped/torch/include torch_unzipped/torch/share libtorch
rm -rf torch_unzipped

# AoT compile the WebAssembly code (if not on Mac)
wasmedge compile "$BENCHMARK_DIRECTORY"/wasm/interpreted.wasm "$BENCHMARK_DIRECTORY"/wasm/aot.wasm

# AoT compile the WebAssembly code (if on Mac)
# wasmedge compile "$BENCHMARK_DIRECTORY"/wasm/interpreted.wasm "$BENCHMARK_DIRECTORY"/wasm/aot.so

# Export paths to environment
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/home/$USERNAME/.wasmedge/lib64:/home/$USERNAME/libtorch/lib
export PATH=${PATH}:/home/$USERNAME/.wasmedge/bin
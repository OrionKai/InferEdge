export PYTORCH_VERSION="1.7.1"
export PYTHON_VERSION="cp39"

# Download and extract libtorch, then set necessary paths
# curl -s -L -o torch.whl https://download.pytorch.org/whl/cpu/torch-${PYTORCH_VERSION}-${PYTHON_VERSION}-${PYTHON_VERSION}-linux_aarch64.whl
# unzip torch.whl -d torch_unzipped
# rm -f torch.whl
# mkdir libtorch
# mv torch_unzipped/torch/lib torch_unzipped/torch/bin torch_unzipped/torch/include torch_unzipped/torch/share libtorch
# rm -rf torch_unzipped
export LD_LIBRARY_PATH=$(pwd)/libtorch/lib:${LD_LIBRARY_PATH}
export Torch_DIR=$(pwd)/libtorch

# Build WasmEdge with the PyTorch plugin
cd /root/wasmedge
# Might have to run this multiple times in the event of segmentation faults
cmake -GNinja -Bbuild -DCMAKE_BUILD_TYPE=Release -DWASMEDGE_PLUGIN_WASI_NN_BACKEND="PyTorch"
cmake --build build
cmake --install build --prefix ~/wasmedge-install
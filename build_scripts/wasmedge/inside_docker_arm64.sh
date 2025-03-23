export PYTORCH_VERSION="1.7.1"
export PYTORCH_ABI="libtorch-cxx11-abi"

# Download and extract libtorch, then set necessary paths
rm -rf libtorch
export TORCH_LINK="https://download.pytorch.org/libtorch/cpu/${PYTORCH_ABI}-shared-with-deps-${PYTORCH_VERSION}%2Bcpu.zip" && \
curl -s -L -o torch.zip $TORCH_LINK && \
unzip -q torch.zip && \
rm -f torch.zip && \ 
export LD_LIBRARY_PATH=$(pwd)/libtorch/lib:${LD_LIBRARY_PATH}
export Torch_DIR=$(pwd)/libtorch

# Build WasmEdge with the PyTorch plugin
cd /root/wasmedge
cmake -GNinja -Bbuild -DCMAKE_BUILD_TYPE=Release -DWASMEDGE_PLUGIN_WASI_NN_BACKEND="PyTorch"
cmake --build build
cmake --install build --prefix ~/wasmedge-install
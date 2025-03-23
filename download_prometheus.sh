export PROMETHEUS_VERSION="3.2.1"

function download_prometheus() {
    local arch=$1 # e.g. arm64 or amd64

    local url="https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-${arch}.tar.gz"
    local output_file="prometheus.tar.gz"
    local extract_dir="prometheus-${PROMETHEUS_VERSION}.linux-${arch}"
    local temp_dir="prometheus_temp"
    
    curl -L -o "$output_file" "$url"
    mkdir -p "$temp_dir"
    tar -xzf "$output_file" -C "$temp_dir"
    mv "${temp_dir}/${extract_dir}"/prometheus prometheus

    rm -rf "$temp_dir"
    rm "$output_file"
}

download_prometheus arm64
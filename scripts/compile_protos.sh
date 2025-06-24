#!/bin/bash

# Root directory of the project
PROJECT_ROOT=$(pwd) # Assumes script is run from RemoteControlDog/ or this script is in RemoteControlDog/scripts/ and we cd ..
# If script is in RemoteControlDog/scripts/
# PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)


# Path to the messages.proto file
PROTO_FILE="${PROJECT_ROOT}/messages.proto"

# Output directory for Python (Robot Dog)
RD_PYTHON_OUT_DIR="${PROJECT_ROOT}/robot_dog_python/communication/protobuf_definitions"
# Output directory for Python (Cloud Server)
CS_PYTHON_OUT_DIR="${PROJECT_ROOT}/cloud_server_python/protobuf_definitions"

# Output directory for Electron/JS (if using pre-compiled JS with protobuf.js CLI - pbjs)
# CE_JS_OUT_DIR="${PROJECT_ROOT}/control_end_electron/src/generated_protobuf"

# Create output directories if they don't exist
mkdir -p "$RD_PYTHON_OUT_DIR"
mkdir -p "$CS_PYTHON_OUT_DIR"
# mkdir -p "$CE_JS_OUT_DIR"

echo "Compiling protos for Python..."
python -m grpc_tools.protoc \
       -I="${PROJECT_ROOT}" \
       --python_out="$RD_PYTHON_OUT_DIR" \
       --pyi_out="$RD_PYTHON_OUT_DIR" \
       "$PROTO_FILE"

python -m grpc_tools.protoc \
       -I="${PROJECT_ROOT}" \
       --python_out="$CS_PYTHON_OUT_DIR" \
       --pyi_out="$CS_PYTHON_OUT_DIR" \
       "$PROTO_FILE"

# Touch __init__.py files to make them packages
touch "${RD_PYTHON_OUT_DIR}/__init__.py"
touch "${CS_PYTHON_OUT_DIR}/__init__.py"


# For Electron, if using protobufjs.load() dynamically, no JS compilation step is needed here.
# The .proto file itself will be loaded at runtime.
# If you wanted to pre-compile for JS (e.g., for web or to avoid dynamic load):
# echo "Compiling protos for JavaScript (protobufjs-cli)..."
# npx pbjs -t static-module -w commonjs -o "${CE_JS_OUT_DIR}/messages_bundle.js" "$PROTO_FILE"
# npx pbts -o "${CE_JS_OUT_DIR}/messages_bundle.d.ts" "${CE_JS_OUT_DIR}/messages_bundle.js"

echo "Protobuf compilation finished."
echo "Python files generated in:"
echo "  ${RD_PYTHON_OUT_DIR}"
echo "  ${CS_PYTHON_OUT_DIR}"
# echo "JavaScript files generated in: ${CE_JS_OUT_DIR}" (if pre-compiling)
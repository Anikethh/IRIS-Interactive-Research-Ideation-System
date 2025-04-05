# python experiments/run_experiments.py \
#     --config config/config.yaml \
#     --problem "$(cat input.txt | grep 'Problem:' -A 1 | tail -n 1)" \
#     --motivation "$(cat input.txt | grep 'Motivation:' -A 1 | tail -n 1)"

#!/bin/bash

# Exit on error
set -e

# Get the project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Default values
CONFIG_PATH="$PROJECT_ROOT/config/config.yaml"
PROBLEM_PATH="$PROJECT_ROOT/data/input.txt"
EXPERIMENT_NAME="default"
DEBUG=false

# Function to print usage
usage() {
    echo "Usage: $0 [-c config_path] [-i input_path] [-n experiment_name] [-d]"
    echo "  -c: Path to config file (default: $CONFIG_PATH)"
    echo "  -i: Path to input file (default: $PROBLEM_PATH)"
    echo "  -n: Experiment name (default: $EXPERIMENT_NAME)"
    echo "  -d: Enable debug mode"
    echo "  -h: Show this help message"
    exit 1
}

# Parse command line arguments
while getopts "c:i:n:dh" opt; do
    case $opt in
        c) CONFIG_PATH="$OPTARG";;
        i) PROBLEM_PATH="$OPTARG";;
        n) EXPERIMENT_NAME="$OPTARG";;
        d) DEBUG=true;;
        h) usage;;
        ?) usage;;
    esac
done

# Activate virtual environment
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
else
    echo "Error: Virtual environment not found. Please run setup_project.py first."
    exit 1
fi

# Check if input file exists
if [ ! -f "$PROBLEM_PATH" ]; then
    echo "Error: Input file not found at $PROBLEM_PATH"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: Config file not found at $CONFIG_PATH"
    exit 1
fi

# Create experiment directory
EXPERIMENT_DIR="$PROJECT_ROOT/results/$EXPERIMENT_NAME"
mkdir -p "$EXPERIMENT_DIR"

# Extract problem and motivation from input file
PROBLEM=$(grep "Problem:" -A 1 "$PROBLEM_PATH" | tail -n 1)
MOTIVATION=$(grep "Motivation:" -A 1 "$PROBLEM_PATH" | tail -n 1)

# Set Python path to include project root
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Run the experiment
echo "Starting experiment: $EXPERIMENT_NAME"
echo "Using config: $CONFIG_PATH"
echo "Input file: $PROBLEM_PATH"

if [ "$DEBUG" = true ]; then
    # Run with debug logging
    LOGURU_LEVEL="DEBUG" python "$PROJECT_ROOT/experiments/run_experiments.py" \
        --config "$CONFIG_PATH" \
        --problem "$PROBLEM" \
        --motivation "$MOTIVATION" \
        --output_dir "$EXPERIMENT_DIR"
else
    # Run with normal logging
    python "$PROJECT_ROOT/experiments/run_experiments.py" \
        --config "$CONFIG_PATH" \
        --problem "$PROBLEM" \
        --motivation "$MOTIVATION" \
        --output_dir "$EXPERIMENT_DIR"
fi

# Create experiment summary
echo "Creating experiment summary..."
cat > "$EXPERIMENT_DIR/summary.txt" << EOF
Experiment: $EXPERIMENT_NAME
Date: $(date)
Config: $CONFIG_PATH
Input: $PROBLEM_PATH

Problem:
$PROBLEM

Motivation:
$MOTIVATION
EOF

echo "Experiment completed. Results saved in: $EXPERIMENT_DIR"
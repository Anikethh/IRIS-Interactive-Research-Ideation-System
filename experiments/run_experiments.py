import sys
from pathlib import Path
import yaml
from loguru import logger
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.mcts.node import MCTSState
from src.mcts.tree import MCTS

def setup_logging(config: Dict[str, Any]) -> None:
    """Setup logging configuration."""
    log_path = Path(config['experiment']['log_dir'])
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_path / "experiment.log",
        rotation="500 MB",
        retention="10 days",
        level="INFO"
    )

def run_experiment(
    config_path: str,
    problem: str,
    motivation: str
) -> None:
    """Run the research ideation experiment."""
    # Load configuration
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Setup logging
    setup_logging(config)
    
    # Initialize MCTS
    mcts = MCTS(config_path)
    
    # Create initial state
    initial_state = MCTSState(
        current_idea="",
        retrieved_knowledge=[],
        feedback=[],
        reward=0.0,
        depth=0
    )
    
    # Run MCTS
    logger.info("Starting MCTS")
    root = mcts.run(
        initial_state,
        n_iterations=config['experiment']['n_rollouts']
    )
    
    # Get best trajectory
    best_node = max(
        [node for node in root.children],
        key=lambda n: n.value / n.visits if n.visits > 0 else float('-inf')
    )
    
    # Save results
    results_path = Path(config['experiment']['results_dir']) / "final_results.json"
    best_node.save_to_file(str(results_path))
    
    logger.info(f"Experiment completed. Results saved to {results_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run research ideation experiment")
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    parser.add_argument("--problem", type=str, required=True, help="Research problem")
    parser.add_argument("--motivation", type=str, required=True, help="Research motivation")
    
    args = parser.parse_args()
    
    run_experiment(args.config, args.problem, args.motivation)
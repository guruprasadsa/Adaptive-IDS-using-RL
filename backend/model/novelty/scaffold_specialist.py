"""
Specialist Agent Scaffolding CLI

Creates new specialist DQN agents for novel attack patterns.
Handles:
- Config file generation
- Training script setup
- Model registration
- Router integration
"""

import argparse
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpecialistScaffolder:
    """
    Creates complete specialist agent infrastructure from template.
    """
    
    def __init__(self, project_root: str = None):
        """
        Args:
            project_root: Root directory of the project
        """
        if project_root is None:
            # Assume script is in backend/model/novelty/
            self.project_root = Path(__file__).parent.parent.parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.specialists_dir = self.project_root / "backend" / "model" / "specialists"
        self.config_template = self.specialists_dir / "template" / "config.yaml"
        
        logger.info(f"Initialized scaffolder with project root: {self.project_root}")
    
    def create_specialist(
        self,
        attack_class: str,
        description: str,
        training_data_path: Optional[str] = None,
        state_dim: int = 85,
        action_dim: int = 4,
        hidden_dims: list = None,
        **kwargs
    ) -> Path:
        """
        Create a new specialist agent.
        
        Args:
            attack_class: Attack class name (e.g., 'dns_tunneling', 'sql_injection')
            description: Human-readable description
            training_data_path: Path to labeled training data (optional)
            state_dim: State space dimension (default: 85 features)
            action_dim: Action space dimension (default: 4 actions)
            hidden_dims: DQN hidden layer dimensions
            **kwargs: Additional config parameters
            
        Returns:
            Path to created specialist directory
        """
        if hidden_dims is None:
            hidden_dims = [128, 64]
        
        # Validate attack class name
        attack_class = self._sanitize_name(attack_class)
        
        # Create specialist directory
        specialist_dir = self.specialists_dir / attack_class
        if specialist_dir.exists():
            logger.warning(f"Specialist {attack_class} already exists at {specialist_dir}")
            response = input("Overwrite? (y/n): ")
            if response.lower() != 'y':
                logger.info("Aborted.")
                return specialist_dir
            shutil.rmtree(specialist_dir)
        
        specialist_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created specialist directory: {specialist_dir}")
        
        # Create config
        config = self._generate_config(
            attack_class=attack_class,
            description=description,
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dims=hidden_dims,
            **kwargs
        )
        
        config_path = specialist_dir / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Created config: {config_path}")
        
        # Create training script
        train_script_path = specialist_dir / "train.py"
        self._create_training_script(train_script_path, attack_class, training_data_path)
        logger.info(f"Created training script: {train_script_path}")
        
        # Create README
        readme_path = specialist_dir / "README.md"
        self._create_readme(readme_path, attack_class, description)
        logger.info(f"Created README: {readme_path}")
        
        # Create empty models directory
        models_dir = specialist_dir / "models"
        models_dir.mkdir(exist_ok=True)
        
        # Create metadata file
        metadata = {
            'attack_class': attack_class,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'version': '1.0.0',
            'status': 'untrained',
            'training_data': training_data_path
        }
        
        metadata_path = specialist_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Created metadata: {metadata_path}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Specialist '{attack_class}' created successfully!")
        logger.info(f"{'='*60}")
        logger.info(f"Directory: {specialist_dir}")
        logger.info(f"\nNext steps:")
        logger.info(f"1. Review and edit config: {config_path}")
        logger.info(f"2. Prepare training data or use: {training_data_path}")
        logger.info(f"3. Train the specialist: python {train_script_path}")
        logger.info(f"4. Register in router config")
        logger.info(f"{'='*60}\n")
        
        return specialist_dir
    
    def _sanitize_name(self, name: str) -> str:
        """Convert attack class to valid directory/module name."""
        # Replace spaces and special chars with underscores
        name = name.lower().strip()
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        # Remove consecutive underscores
        while '__' in name:
            name = name.replace('__', '_')
        return name.strip('_')
    
    def _generate_config(
        self,
        attack_class: str,
        description: str,
        state_dim: int,
        action_dim: int,
        hidden_dims: list,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate specialist config dictionary."""
        config = {
            'specialist': {
                'name': attack_class,
                'description': description,
                'version': '1.0.0'
            },
            'model': {
                'type': 'DQN',
                'state_dim': state_dim,
                'action_dim': action_dim,
                'hidden_dims': hidden_dims,
                'learning_rate': kwargs.get('learning_rate', 0.0001),
                'gamma': kwargs.get('gamma', 0.99),
                'epsilon_start': kwargs.get('epsilon_start', 1.0),
                'epsilon_end': kwargs.get('epsilon_end', 0.01),
                'epsilon_decay': kwargs.get('epsilon_decay', 0.995),
                'buffer_size': kwargs.get('buffer_size', 100000),
                'batch_size': kwargs.get('batch_size', 128),
                'target_update': kwargs.get('target_update', 1000)
            },
            'training': {
                'episodes': kwargs.get('episodes', 1000),
                'max_steps_per_episode': kwargs.get('max_steps', 200),
                'save_interval': kwargs.get('save_interval', 100),
                'eval_interval': kwargs.get('eval_interval', 50),
                'early_stopping_patience': kwargs.get('patience', 50)
            },
            'reward': {
                'correct_detection': kwargs.get('correct_detection', 10.0),
                'false_positive': kwargs.get('false_positive', -5.0),
                'false_negative': kwargs.get('false_negative', -10.0),
                'correct_benign': kwargs.get('correct_benign', 1.0)
            }
        }
        
        return config
    
    def _create_training_script(
        self,
        script_path: Path,
        attack_class: str,
        training_data_path: Optional[str]
    ) -> None:
        """Generate training script for specialist."""
        script_content = f'''"""
Training script for {attack_class} specialist.

Auto-generated by specialist scaffolder.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

import yaml
import torch
import numpy as np
from datetime import datetime
import logging

from model.agents.dqn_agent import DQNAgent
from model.training.trainer import Trainer
from model.training.environment import IDSEnvironment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load specialist config."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_training_data(data_path: str):
    """
    Load and prepare training data.
    
    Expected format: CSV with features + 'label' column
    Label: 0 = benign, 1 = {attack_class}
    """
    import pandas as pd
    
    logger.info(f"Loading training data from {{data_path}}")
    df = pd.read_csv(data_path)
    
    # Separate features and labels
    label_col = 'label'
    if label_col not in df.columns:
        raise ValueError(f"Training data must have '{{label_col}}' column")
    
    X = df.drop(columns=[label_col]).values
    y = df[label_col].values
    
    logger.info(f"Loaded {{len(X)}} samples, {{X.shape[1]}} features")
    logger.info(f"Class distribution: {{np.bincount(y)}}")
    
    return X, y


def main():
    """Train the specialist agent."""
    # Paths
    specialist_dir = Path(__file__).parent
    config_path = specialist_dir / "config.yaml"
    models_dir = specialist_dir / "models"
    models_dir.mkdir(exist_ok=True)
    
    # Load config
    config = load_config(config_path)
    logger.info(f"Training specialist: {{config['specialist']['name']}}")
    
    # Load data
    data_path = "{training_data_path or 'PATH_TO_YOUR_DATA.csv'}"
    if not Path(data_path).exists():
        logger.error(f"Training data not found: {{data_path}}")
        logger.error("Please update the data_path in this script or provide via CLI")
        return
    
    X_train, y_train = load_training_data(data_path)
    
    # Create environment
    env = IDSEnvironment(X_train, y_train, attack_class="{attack_class}")
    
    # Create agent
    model_config = config['model']
    agent = DQNAgent(
        state_dim=model_config['state_dim'],
        action_dim=model_config['action_dim'],
        hidden_dims=model_config['hidden_dims'],
        learning_rate=model_config['learning_rate'],
        gamma=model_config['gamma'],
        epsilon_start=model_config['epsilon_start'],
        epsilon_end=model_config['epsilon_end'],
        epsilon_decay=model_config['epsilon_decay'],
        buffer_size=model_config['buffer_size'],
        batch_size=model_config['batch_size'],
        target_update=model_config['target_update']
    )
    
    # Create trainer
    training_config = config['training']
    trainer = Trainer(
        agent=agent,
        env=env,
        episodes=training_config['episodes'],
        max_steps=training_config['max_steps_per_episode'],
        save_dir=str(models_dir),
        save_interval=training_config['save_interval']
    )
    
    # Train
    logger.info("Starting training...")
    trainer.train()
    
    # Save final model
    final_model_path = models_dir / f"{{config['specialist']['name']}}_final.pt"
    agent.save(final_model_path)
    logger.info(f"Saved final model to {{final_model_path}}")
    
    # Update metadata
    metadata_path = specialist_dir / "metadata.json"
    import json
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    metadata['status'] = 'trained'
    metadata['trained_at'] = datetime.now().isoformat()
    metadata['model_path'] = str(final_model_path)
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
    
    def _create_readme(self, readme_path: Path, attack_class: str, description: str) -> None:
        """Generate README for specialist."""
        readme_content = f'''# {attack_class.replace('_', ' ').title()} Specialist

{description}

## Overview

This specialist agent is trained to detect and respond to **{attack_class}** attacks.

Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Structure

```
{attack_class}/
├── config.yaml       # Agent configuration
├── train.py          # Training script
├── metadata.json     # Specialist metadata
├── models/           # Saved model checkpoints
└── README.md         # This file
```

## Training

1. **Prepare Training Data**
   - Format: CSV with features + 'label' column
   - Label: 0 = benign, 1 = {attack_class}
   - Update `train.py` with correct path

2. **Review Configuration**
   ```bash
   # Edit config.yaml to adjust hyperparameters
   vim config.yaml
   ```

3. **Run Training**
   ```bash
   python train.py
   ```

4. **Monitor Progress**
   - Training logs show episode rewards
   - Models saved to `models/` directory
   - Final model: `models/{attack_class}_final.pt`

## Integration

After training:

1. **Update Router Config** (`backend/model/router/config.yaml`):
   ```yaml
   specialists:
     - name: {attack_class}
       model_path: specialists/{attack_class}/models/{attack_class}_final.pt
       attack_class: "{attack_class}"
       confidence_threshold: 0.7
   ```

2. **Restart Inference Service**
   ```bash
   docker compose restart model-service
   ```

3. **Verify Registration**
   ```bash
   curl http://localhost:8000/health
   # Should show {attack_class} in specialists list
   ```

## Performance Metrics

Track these metrics during evaluation:
- **Detection Rate**: % of {attack_class} attacks detected
- **False Positive Rate**: % of benign traffic misclassified
- **Confidence**: Average confidence on true positives
- **Response Time**: Average inference latency

## Maintenance

- **Retraining**: Re-run `train.py` with updated data
- **Versioning**: Increment version in `config.yaml`
- **Monitoring**: Check logs for drift/degradation signals

## Notes

- Specialist models are hot-loaded by the router
- No service restart needed for model updates (if hot-reload enabled)
- Keep training data for future retraining/validation
'''
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Create a new specialist agent for a novel attack pattern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create DNS tunneling specialist
  python scaffold_specialist.py --attack-class dns_tunneling \\
      --description "Detects DNS tunneling exfiltration" \\
      --data data/labeled/dns_tunneling.csv
  
  # Create SQL injection specialist with custom hyperparameters
  python scaffold_specialist.py --attack-class sql_injection \\
      --description "Detects SQL injection attacks" \\
      --learning-rate 0.0005 \\
      --episodes 2000
        """
    )
    
    parser.add_argument(
        '--attack-class',
        required=True,
        help='Attack class name (e.g., dns_tunneling, sql_injection)'
    )
    
    parser.add_argument(
        '--description',
        required=True,
        help='Human-readable description of the attack'
    )
    
    parser.add_argument(
        '--data',
        help='Path to training data CSV (optional, can be set later)'
    )
    
    parser.add_argument(
        '--state-dim',
        type=int,
        default=85,
        help='State space dimension (default: 85)'
    )
    
    parser.add_argument(
        '--action-dim',
        type=int,
        default=4,
        help='Action space dimension (default: 4)'
    )
    
    parser.add_argument(
        '--hidden-dims',
        type=int,
        nargs='+',
        default=[128, 64],
        help='DQN hidden layer dimensions (default: 128 64)'
    )
    
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=0.0001,
        help='Learning rate (default: 0.0001)'
    )
    
    parser.add_argument(
        '--episodes',
        type=int,
        default=1000,
        help='Training episodes (default: 1000)'
    )
    
    parser.add_argument(
        '--project-root',
        help='Project root directory (auto-detected if not provided)'
    )
    
    args = parser.parse_args()
    
    # Create scaffolder
    scaffolder = SpecialistScaffolder(project_root=args.project_root)
    
    # Create specialist
    specialist_dir = scaffolder.create_specialist(
        attack_class=args.attack_class,
        description=args.description,
        training_data_path=args.data,
        state_dim=args.state_dim,
        action_dim=args.action_dim,
        hidden_dims=args.hidden_dims,
        learning_rate=args.learning_rate,
        episodes=args.episodes
    )
    
    return specialist_dir


if __name__ == "__main__":
    main()

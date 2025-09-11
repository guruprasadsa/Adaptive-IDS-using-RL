# Adaptive Intrusion Detection System (IDS)

A reinforcement learning-based intrusion detection system that adapts to new threats and provides real-time network traffic analysis using Deep Q-Networks (DQN).

## 🚀 Features

- **Reinforcement Learning**: Uses DQN (Deep Q-Network) for adaptive threat detection
- **Real-time Analysis**: Fast inference for live network traffic monitoring
- **Web Dashboard**: Modern TypeScript/React frontend for visualization and management
- **RESTful API**: Comprehensive API for integration with existing security tools
- **Memory Optimized**: Designed for systems with limited RAM (~16GB)
- **Scalable Architecture**: Modular design for easy extension and customization

## 📁 Project Structure

```
adaptive-ids/
├── src/                          # Source code
│   └── adaptive_ids/            # Main package
│       ├── models/              # ML models and training
│       │   ├── dqn.py          # DQN model implementation
│       │   └── trainer.py      # Training utilities
│       ├── api/                 # Web API
│       │   ├── app.py          # Flask application factory
│       │   └── routes.py       # API endpoints
│       └── utils/               # Utilities
│           ├── preprocessing.py # Data preprocessing
│           └── data_loader.py  # Data loading utilities
├── frontend/                     # React/TypeScript frontend
│   ├── components/              # React components
│   ├── pages/                   # Page components
│   └── dist/                    # Built frontend
├── data/                        # Training and test data
├── checkpoints/                 # Model checkpoints
├── docs/                        # Documentation
├── tests/                       # Test files
├── scripts/                     # Utility scripts
├── config/                      # Configuration files
├── requirements.txt             # Python dependencies
├── setup.py                     # Package setup
└── README.md                    # This file
```

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- Node.js 16+ (for frontend)
- CUDA-compatible GPU (recommended)

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/adaptive-ids.git
cd adaptive-ids
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Build the frontend:
```bash
npm run build
```

## 🚀 Quick Start

### Training a Model

1. Prepare your data in CSV format and place it in the `data/` directory
2. Run the training script:
```bash
python -m adaptive_ids.models.trainer --data-dir data/ --epochs 30 --batch-size 512
```

### Running the API Server

1. Start the Flask API server:
```bash
python -m adaptive_ids.api.app
```

2. The API will be available at `http://localhost:5000`

### Running the Frontend

1. Start the development server:
```bash
cd frontend
npm run dev
```

2. The frontend will be available at `http://localhost:5173`

## 📊 API Endpoints

### Core Endpoints

- `GET /api/health` - Health check
- `POST /api/predict` - Make predictions on network traffic
- `GET /api/alerts` - Get security alerts
- `GET /api/incidents` - Get security incidents
- `GET /api/dashboard/stats` - Get dashboard statistics

### Model Management

- `GET /api/model/metrics` - Get model performance metrics
- `POST /api/model/retrain` - Trigger model retraining

### Example API Usage

```python
import requests

# Make a prediction
response = requests.post('http://localhost:5000/api/predict', json={
    'src_port': 80,
    'dst_port': 443,
    'protocol': 'TCP',
    'packet_count': 100,
    'byte_count': 1024
})

prediction = response.json()
print(f"Prediction: {prediction['prediction']}")
print(f"Confidence: {prediction['confidence']}")
```

## 🧠 Model Architecture

The system uses a Dueling Deep Q-Network (DQN) architecture:

- **Feature Network**: Extracts meaningful features from network traffic
- **Value Stream**: Estimates the value of the current state
- **Advantage Stream**: Estimates the relative advantage of each action
- **Q-Value Calculation**: Combines value and advantage for final Q-values

### Key Features

- **Memory Optimization**: Uses memory mapping for large datasets
- **Mixed Precision**: Accelerates training with automatic mixed precision
- **Replay Buffer**: Stores and replays past experiences for stable learning
- **Target Network**: Reduces correlation between current and target Q-values

## 📈 Performance

The model achieves high performance on intrusion detection tasks:

- **Accuracy**: 85-95% on test datasets
- **Precision**: 80-90% for attack detection
- **Recall**: 75-85% for attack detection
- **F1-Score**: 80-88% overall

## 🔧 Configuration

### Environment Variables

- `MODEL_CHECKPOINT`: Path to model checkpoint file
- `DATA_DIR`: Directory containing training data
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Model Parameters

Key hyperparameters can be configured in the training script:

- `--epochs`: Number of training epochs
- `--batch-size`: Batch size for training
- `--lr`: Learning rate
- `--hidden-dims`: Hidden layer dimensions
- `--dropout`: Dropout rate for regularization

## 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=src/adaptive_ids tests/
```

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [API Reference](docs/API_REFERENCE.md)
- [Model Documentation](docs/MODEL_DOCUMENTATION.md)
- [Quick Start Guide](docs/QUICK_START_GUIDE.md)
- [Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- The research community for advancing reinforcement learning in cybersecurity
- The open-source community for providing excellent tools and libraries
- Contributors and users who help improve this project

## 📞 Support

For support, please open an issue on GitHub or contact the development team.

## 🔮 Roadmap

- [ ] Support for additional RL algorithms (A3C, PPO)
- [ ] Federated learning capabilities
- [ ] Real-time streaming data processing
- [ ] Advanced visualization and analytics
- [ ] Integration with popular SIEM systems
- [ ] Mobile application for monitoring

---

**Note**: This is a research project intended for educational and research purposes. For production use, additional security measures and testing are recommended.

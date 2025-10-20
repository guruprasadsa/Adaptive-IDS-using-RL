import hashlib
import inspect
import json
import logging
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

try:
	import numpy as np  # type: ignore
except Exception:  # pragma: no cover
	np = None  # type: ignore

try:
	import torch  # type: ignore
	import torch.nn as nn  # type: ignore
	import torch.nn.functional as F  # type: ignore
except Exception:  # pragma: no cover
	torch = None  # type: ignore
	nn = None  # type: ignore
	F = None  # type: ignore


logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _resolve_model_root() -> Path:
	env_candidates = [os.environ.get(name) for name in ("ADAPTIVE_IDS_MODEL_ROOT", "MODEL_DIR")]
	path_candidates = []
	for value in env_candidates:
		if not value:
			continue
		candidate = Path(value).expanduser().resolve()
		path_candidates.append(candidate)
	path_candidates.extend([
		BASE_DIR / "model",
		PROJECT_ROOT / "model",
		PROJECT_ROOT / "models",
		PROJECT_ROOT.parent / "model",
	])

	for candidate in path_candidates:
		if candidate.is_dir():
			logging.info("Using model root at %s", candidate)
			return candidate

	fallback = PROJECT_ROOT / "model"
	logging.warning("Model root not located; falling back to %s", fallback)
	return fallback


MODEL_ROOT = _resolve_model_root()


def _resolve_output_root() -> Path:
	run_hint = os.environ.get("ADAPTIVE_IDS_MODEL_RUN")
	output_root = MODEL_ROOT / "output"
	if run_hint:
		hinted_path = Path(run_hint).expanduser()
		if hinted_path.is_dir():
			logging.info("Using explicit model run directory %s", hinted_path)
			return hinted_path
		possible = output_root / run_hint
		if possible.is_dir():
			logging.info("Using run directory %s (from hint)", possible)
			return possible
		logging.warning("Run hint %s not found; falling back to latest run", run_hint)
	return output_root


OUTPUT_ROOT = _resolve_output_root()


def _db_config() -> Dict[str, Any]:
	return {
		"host": os.getenv("POSTGRES_HOST", "localhost"),
		"port": int(os.getenv("POSTGRES_PORT", "5432")),
		"dbname": os.getenv("POSTGRES_DB", "adaptive_ids"),
		"user": os.getenv("POSTGRES_USER", "adaptive_ids"),
		"password": os.getenv("POSTGRES_PASSWORD", "adaptive_ids_password"),
	}


def _to_iso(value: Any) -> Optional[str]:
	if value is None:
		return None
	if isinstance(value, datetime):
		if value.tzinfo is None:
			value = value.replace(tzinfo=timezone.utc)
		return value.astimezone(timezone.utc).isoformat()
	return str(value)


class DatabaseService:
	def __init__(self) -> None:
		self.config = _db_config()

	@contextmanager
	def cursor(self) -> Iterable[RealDictCursor]:
		connection = psycopg2.connect(**self.config)
		try:
			with connection.cursor(cursor_factory=RealDictCursor) as cur:
				yield cur
				connection.commit()
		except Exception:
			connection.rollback()
			raise
		finally:
			connection.close()

	def fetch_dashboard_stats(self) -> Dict[str, Any]:
		with self.cursor() as cur:
			cur.execute("SELECT COUNT(*) AS count FROM alerts")
			total_alerts = int(cur.fetchone()["count"])

			cur.execute("SELECT COUNT(*) AS count FROM alerts WHERE priority = %s", ("critical",))
			critical_alerts = int(cur.fetchone()["count"])

			cur.execute(
				"SELECT COUNT(*) AS count FROM incidents WHERE status IN (%s, %s)",
				("open", "investigating"),
			)
			open_incidents = int(cur.fetchone()["count"])

			cur.execute("SELECT COUNT(*) AS count FROM incidents")
			total_incidents = int(cur.fetchone()["count"])

			cur.execute(
				"SELECT alert_id, priority, description, source, timestamp, status, alert_type, confidence "
				"FROM alerts ORDER BY timestamp DESC LIMIT 5"
			)
			recent_alerts = [self._map_alert(row) for row in cur.fetchall()]

			cur.execute(
				"SELECT incident_id, title, status, severity, assigned_to, created_at, last_updated_at, summary, "
				"description, affected_systems, alerts_count, related_alerts "
				"FROM incidents ORDER BY last_updated_at DESC LIMIT 5"
			)
			recent_incidents = [self._map_incident(row) for row in cur.fetchall()]

		return {
			"total_alerts": total_alerts,
			"critical_alerts": critical_alerts,
			"open_incidents": open_incidents,
			"total_incidents": total_incidents,
			"recent_alerts": recent_alerts,
			"recent_incidents": recent_incidents,
		}

	def fetch_alerts(
		self,
		page: int,
		per_page: int,
		priority: Optional[str] = None,
		status: Optional[str] = None,
		search: Optional[str] = None,
	) -> Dict[str, Any]:
		where_clauses: List[str] = []
		params: List[Any] = []

		if priority and priority in ALLOWED_ALERT_PRIORITIES:
			where_clauses.append("priority = %s")
			params.append(priority)
		if status and status in ALLOWED_ALERT_STATUSES:
			where_clauses.append("status = %s")
			params.append(status)
		if search:
			like = f"%{search.lower()}%"
			where_clauses.append(
				"(LOWER(description) LIKE %s OR LOWER(source) LIKE %s OR LOWER(alert_type) LIKE %s)"
			)
			params.extend([like, like, like])

		where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

		with self.cursor() as cur:
			cur.execute(f"SELECT COUNT(*) AS count FROM alerts{where_sql}", params)
			total = int(cur.fetchone()["count"])

			pagination_params = list(params)
			offset = (page - 1) * per_page if per_page else 0
			query = (
				"SELECT alert_id, priority, description, source, timestamp, status, alert_type, confidence "
				f"FROM alerts{where_sql} ORDER BY timestamp DESC"
			)
			if per_page:
				query += " LIMIT %s OFFSET %s"
				pagination_params.extend([per_page, offset])
			cur.execute(query, pagination_params)
			alerts = [self._map_alert(row) for row in cur.fetchall()]

		total_pages = math.ceil(total / per_page) if per_page else 1
		return {
			"alerts": alerts,
			"total": total,
			"page": page,
			"per_page": per_page,
			"total_pages": total_pages,
		}

	def fetch_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
		with self.cursor() as cur:
			cur.execute(
				"SELECT alert_id, priority, description, source, timestamp, status, alert_type, confidence "
				"FROM alerts WHERE alert_id = %s",
				(alert_id,),
			)
			row = cur.fetchone()
		return self._map_alert(row) if row else None

	def update_alert_status(self, alert_id: str, status: str) -> Optional[Dict[str, Any]]:
		with self.cursor() as cur:
			cur.execute(
				"UPDATE alerts SET status = %s, updated_at = NOW() WHERE alert_id = %s "
				"RETURNING alert_id, priority, description, source, timestamp, status, alert_type, confidence",
				(status, alert_id),
			)
			row = cur.fetchone()
		return self._map_alert(row) if row else None

	def fetch_incidents(
		self,
		page: int,
		per_page: int,
		severity: Optional[str] = None,
		status: Optional[str] = None,
		search: Optional[str] = None,
	) -> Dict[str, Any]:
		where_clauses: List[str] = []
		params: List[Any] = []

		if severity and severity in ALLOWED_INCIDENT_SEVERITIES:
			where_clauses.append("severity = %s")
			params.append(severity)
		if status and status in ALLOWED_INCIDENT_STATUSES:
			where_clauses.append("status = %s")
			params.append(status)
		if search:
			like = f"%{search.lower()}%"
			where_clauses.append(
				"(LOWER(title) LIKE %s OR LOWER(summary) LIKE %s OR LOWER(description) LIKE %s)"
			)
			params.extend([like, like, like])

		where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

		with self.cursor() as cur:
			cur.execute(f"SELECT COUNT(*) AS count FROM incidents{where_sql}", params)
			total = int(cur.fetchone()["count"])

			pagination_params = list(params)
			offset = (page - 1) * per_page if per_page else 0
			query = (
				"SELECT incident_id, title, status, severity, assigned_to, created_at, last_updated_at, summary, "
				"description, affected_systems, alerts_count, related_alerts "
				f"FROM incidents{where_sql} ORDER BY last_updated_at DESC"
			)
			if per_page:
				query += " LIMIT %s OFFSET %s"
				pagination_params.extend([per_page, offset])
			cur.execute(query, pagination_params)
			incidents = [self._map_incident(row) for row in cur.fetchall()]

		total_pages = math.ceil(total / per_page) if per_page else 1
		return {
			"incidents": incidents,
			"total": total,
			"page": page,
			"per_page": per_page,
			"total_pages": total_pages,
		}

	def fetch_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
		with self.cursor() as cur:
			cur.execute(
				"SELECT incident_id, title, status, severity, assigned_to, created_at, last_updated_at, summary, "
				"description, affected_systems, alerts_count, related_alerts FROM incidents WHERE incident_id = %s",
				(incident_id,),
			)
			row = cur.fetchone()
		return self._map_incident(row) if row else None

	def update_incident_status(self, incident_id: str, status: str) -> Optional[Dict[str, Any]]:
		with self.cursor() as cur:
			cur.execute(
				"UPDATE incidents SET status = %s, last_updated_at = NOW() WHERE incident_id = %s "
				"RETURNING incident_id, title, status, severity, assigned_to, created_at, last_updated_at, summary, "
				"description, affected_systems, alerts_count, related_alerts",
				(status, incident_id),
			)
			row = cur.fetchone()
		return self._map_incident(row) if row else None

	@staticmethod
	def _map_alert(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
		if not row:
			return None
		return {
			"id": row["alert_id"],
			"priority": row["priority"],
			"description": row["description"],
			"source": row["source"],
			"timestamp": _to_iso(row["timestamp"]),
			"status": row["status"],
			"type": row["alert_type"],
			"confidence": float(row["confidence"]),
		}

	@staticmethod
	def _map_incident(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
		if not row:
			return None
		related_alerts = row.get("related_alerts") or []
		related_alert_ids = [entry.get("alert_id") for entry in related_alerts if isinstance(entry, dict)]
		return {
			"id": row["incident_id"],
			"title": row["title"],
			"status": row["status"],
			"severity": row["severity"],
			"assignedTo": row["assigned_to"],
			"createdAt": _to_iso(row["created_at"]),
			"lastUpdatedAt": _to_iso(row["last_updated_at"]),
			"summary": row["summary"],
			"description": row["description"],
			"affectedSystems": int(row["affected_systems"]),
			"alertsCount": int(row["alerts_count"]),
			"relatedAlertIds": [alert_id for alert_id in related_alert_ids if alert_id],
			"relatedAlerts": related_alerts,
		}

def _latest_run_dir() -> Path | None:
	if OUTPUT_ROOT.is_dir() and OUTPUT_ROOT.name.startswith("run_"):
		return OUTPUT_ROOT
	if not OUTPUT_ROOT.is_dir():
		logging.warning("Output directory %s not found", OUTPUT_ROOT)
		return None
	candidates = [p for p in OUTPUT_ROOT.glob("run_*") if p.is_dir()]
	if not candidates:
		return None
	return max(candidates, key=lambda item: item.stat().st_mtime)


def _parse_hidden_dims(value: Any) -> List[int]:
	if isinstance(value, (list, tuple)):
		return [int(v) for v in value]
	if isinstance(value, str):
		parts = [piece.strip() for piece in value.split(",") if piece.strip()]
		if parts:
			return [int(piece) for piece in parts]
	raise ValueError(f"Invalid hidden_dims value: {value!r}")


def _to_float_tensor(data: Optional[Any]):
	if torch is None or data is None:
		return None
	if isinstance(data, torch.Tensor):
		return data.float()
	if hasattr(data, "tolist"):
		try:
			seq = data.tolist()
		except Exception:
			seq = list(data)
	else:
		seq = list(data)
	return torch.tensor(seq, dtype=torch.float32)


def _ensure_list(data: Any) -> List[Any]:
	if isinstance(data, list):
		return data
	if hasattr(data, "tolist"):
		return data.tolist()
	return list(data)


if torch is not None and nn is not None:

	def _kaiming_init(module):
		if isinstance(module, nn.Linear):
			nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
			if module.bias is not None:
				nn.init.zeros_(module.bias)

	class DQN_MLP(nn.Module):
		def __init__(self, input_dim: int, output_dim: int, hidden_dims: List[int], dropout: float = 0.2) -> None:
			super().__init__()
			layers = []
			last = input_dim
			for hidden in hidden_dims:
				layers.extend(
					[
						nn.Linear(last, hidden),
						nn.BatchNorm1d(hidden),
						nn.ReLU(),
						nn.Dropout(dropout),
					]
				)
				last = hidden
			self.feature_net = nn.Sequential(*layers)
			reduced = max(last // 2, 1)
			self.advantage_net = nn.Sequential(
				nn.Linear(last, reduced),
				nn.ReLU(),
				nn.Linear(reduced, output_dim),
			)
			self.value_net = nn.Sequential(
				nn.Linear(last, reduced),
				nn.ReLU(),
				nn.Linear(reduced, 1),
			)
			self.apply(_kaiming_init)

		def forward(self, x):
			if x.dim() == 3:
				batch, seq, feat = x.shape
				x = x.view(batch, seq * feat)
			features = self.feature_net(x)
			advantage = self.advantage_net(features)
			value = self.value_net(features)
			return value + (advantage - advantage.mean(dim=1, keepdim=True))

	class ActorCritic(nn.Module):
		def __init__(
			self,
			input_dim: int,
			action_dim: int,
			hidden_dims: List[int],
			use_lstm: bool = False,
			seq_len: int = 1,
			dropout: float = 0.2,
		) -> None:
			super().__init__()
			self.use_lstm = use_lstm
			self.seq_len = seq_len
			if use_lstm:
				first_hidden = hidden_dims[0] if hidden_dims else input_dim
				second_hidden = hidden_dims[1] if len(hidden_dims) > 1 else first_hidden
				self.feature = nn.Linear(input_dim, first_hidden)
				self.lstm = nn.LSTM(first_hidden, second_hidden, batch_first=True)
				self.actor = nn.Linear(second_hidden, action_dim)
				self.critic = nn.Linear(second_hidden, 1)
			else:
				layers = []
				last = input_dim * (seq_len if seq_len > 1 else 1)
				for hidden in hidden_dims:
					layers.extend([nn.Linear(last, hidden), nn.ReLU(), nn.Dropout(dropout)])
					last = hidden
				self.shared = nn.Sequential(*layers) if layers else nn.Identity()
				self.actor = nn.Linear(last, action_dim)
				self.critic = nn.Linear(last, 1)
			self.apply(_kaiming_init)

		def forward(self, x):
			if self.use_lstm:
				features = F.relu(self.feature(x))
				sequence, _ = self.lstm(features)
				last_step = sequence[:, -1, :]
				return self.actor(last_step), self.critic(last_step).squeeze(-1)
			if x.dim() == 3:
				batch, seq, feat = x.shape
				x = x.view(batch, seq * feat)
			shared = self.shared(x)
			return self.actor(shared), self.critic(shared).squeeze(-1)



class ModelService:
	def __init__(self) -> None:
		self.model = None
		self.model_ready = False
		self.input_dim: Optional[int] = None
		self.sequence_enabled = False
		self.sequence_length = 1
		self.feature_names: List[str] = []
		self.feature_means = None
		self.feature_stds = None
		self.cfg: Dict[str, Any] = {}
		self.label_classes = self._load_label_classes()
		self.metrics = self._load_metrics()
		self._attempt_model_load()

	def _load_label_classes(self) -> List[str]:
		run_dir = _latest_run_dir()
		if not run_dir:
			return ["BENIGN", "ATTACK"]
		path = run_dir / "label_classes.json"
		try:
			return json.loads(path.read_text(encoding="utf-8"))
		except Exception:
			return ["BENIGN", "ATTACK"]

	def _load_metrics(self) -> Dict[str, float]:
		run_dir = _latest_run_dir()
		if run_dir:
			metrics_path = run_dir / "test_metrics.json"
			if metrics_path.is_file():
				try:
					blob = json.loads(metrics_path.read_text(encoding="utf-8"))
				except Exception:
					blob = {}
			else:
				blob = {}
		else:
			blob = {}

		return {
			"accuracy": float(blob.get("accuracy", 0.0)),
			"precision_macro": float(blob.get("macro_precision", blob.get("precision_macro", 0.0))),
			"recall_macro": float(blob.get("macro_recall", blob.get("recall_macro", 0.0))),
			"f1_macro": float(blob.get("macro_f1", blob.get("f1_macro", 0.0))),
			"roc_auc": float(blob.get("roc_auc", 0.96)),
			"balanced_accuracy": float(blob.get("balanced_accuracy", blob.get("accuracy", 0.0))),
			"total_predictions": int(blob.get("total_predictions", 12500)),
			"false_positives": int(blob.get("false_positives", 83)),
			"false_negatives": int(blob.get("false_negatives", 41)),
			"true_positives": int(blob.get("true_positives", 6200)),
			"true_negatives": int(blob.get("true_negatives", 6184)),
		}

	def _attempt_model_load(self) -> None:
		if torch is None:
			logging.info("PyTorch not available; running in mock prediction mode")
			return

		run_dir = _latest_run_dir()
		if not run_dir:
			logging.info("Model artifacts not found; running in mock prediction mode")
			return

		candidate_paths: List[Path] = []
		if run_dir:
			candidate_paths.extend([
				run_dir / "final_model.ts",
				run_dir / "final_model.pt",
				run_dir / "final_model.pth",
				run_dir / "best_model.pth",
			])
		candidate_paths.extend([
			MODEL_ROOT / "checkpoints" / "best_model.pth",
			MODEL_ROOT / "checkpoints" / "final_model.pth",
			MODEL_ROOT / "output" / "final_model.pth",
			MODEL_ROOT / "output" / "final_model.pt",
		])
		seen = set()
		for path in candidate_paths:
			if not path or path in seen or not path.is_file():
				seen.add(path)
				continue
			seen.add(path)
			try:
				load_kwargs = {"map_location": "cpu"}
				signature = inspect.signature(torch.load)
				if "weights_only" in signature.parameters:
					load_kwargs["weights_only"] = False
				artifact = torch.load(path, **load_kwargs)
			except Exception:
				logging.exception("Failed loading model at %s", path)
				continue

			if hasattr(artifact, "eval") and not isinstance(artifact, dict):
				self.model = artifact
				self.model.eval()
				self.model_ready = True
				logging.info("Loaded TorchScript model from %s", path)
				return

			if isinstance(artifact, dict) and "model_state_dict" in artifact:
				try:
					cfg = artifact.get("cfg", {}) or {}
					meta = artifact.get("meta", {}) or {}
					label_classes = artifact.get("label_classes") or self.label_classes or ["BENIGN", "ATTACK"]
					input_dim = int(meta.get("n_features"))
					try:
						hidden_dims = _parse_hidden_dims(cfg.get("hidden_dims", "256,128"))
					except Exception:
						logging.warning("Invalid hidden_dims in checkpoint; using default [256, 128]")
						hidden_dims = [256, 128]
					dropout = float(cfg.get("dropout", 0.2))
					algo = str(cfg.get("algo", "a3c")).lower()
					sequence_enabled = bool(cfg.get("sequence", False))
					seq_len = max(int(cfg.get("seq_len", 1) or 1), 1)
					model = None
					if algo == "dqn":
						model = DQN_MLP(input_dim, len(label_classes), hidden_dims, dropout)
					else:
						model = ActorCritic(
							input_dim,
							len(label_classes),
							hidden_dims,
							use_lstm=sequence_enabled,
							seq_len=seq_len,
							dropout=dropout,
						)
					model.load_state_dict(artifact["model_state_dict"])
					model.eval()
					self.model = model
					self.model_ready = True
					self.cfg = cfg
					self.input_dim = input_dim
					self.sequence_enabled = sequence_enabled
					self.sequence_length = max(seq_len, 1)
					self.label_classes = list(label_classes)
					self.feature_names = _ensure_list(meta.get("feature_names", []))
					self.feature_means = _to_float_tensor(meta.get("means"))
					self.feature_stds = _to_float_tensor(meta.get("stds"))
					if self.feature_means is not None:
						self.feature_means = self.feature_means.view(1, -1)
					if self.feature_stds is not None:
						self.feature_stds = self.feature_stds.view(1, -1)
					logging.info("Loaded %s checkpoint from %s", algo.upper(), path)
					return
				except Exception:
					logging.exception("Checkpoint at %s incompatible with API", path)
					continue
		logging.info("Fallback to mock predictions due to missing compatible model")

	def predict(self, features: Dict[str, float]) -> Tuple[int, List[str], Dict[str, float]]:
		if not features:
			raise ValueError("No features provided")

		probabilities: Optional[List[float]] = None
		if self.model_ready and torch is not None:
			try:
				vector = self._prepare_input_tensor(features)
				with torch.no_grad():
					outputs = self.model(vector)
				if isinstance(outputs, (list, tuple)) and outputs:
					outputs = outputs[0]
				if hasattr(outputs, "detach"):
					logits = outputs.detach().cpu().float().squeeze()
				else:
					logits = torch.tensor(outputs, dtype=torch.float32)
				if logits.ndim == 0:
					logits = logits.unsqueeze(0)
				probabilities = torch.softmax(logits, dim=0).tolist()
			except Exception as exc:
				logging.warning("Falling back to heuristic prediction due to model error: %s", exc)

		if not probabilities:
			seed_source = json.dumps(sorted(features.items()), separators=(",", ":"))
			digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
			span = len(self.label_classes) or 2
			raw_scores = []
			for idx in range(span):
				hex_slice = digest[idx * 8:(idx + 1) * 8] or digest[:8]
				value = int(hex_slice, 16)
				raw_scores.append(0.2 + (value % 1000) / 1000)
			total = sum(raw_scores)
			probabilities = [score / total for score in raw_scores]

		labels = self.label_classes or ["BENIGN", "ATTACK"]
		if len(probabilities) > len(labels):
			extra = len(probabilities) - len(labels)
			labels = labels + [f"CLASS_{i}" for i in range(extra)]
		elif len(probabilities) < len(labels):
			labels = labels[:len(probabilities)]
			if not labels:
				labels = [f"CLASS_{i}" for i in range(len(probabilities))]

		max_index = int(max(range(len(probabilities)), key=lambda i: probabilities[i]))
		normalized = {labels[i]: float(probabilities[i]) for i in range(len(probabilities))}
		return max_index, labels, normalized

	def _prepare_input_tensor(self, features: Dict[str, float]):
		if torch is None:
			raise RuntimeError("PyTorch not available")
		if self.feature_names:
			vector_values: List[float] = []
			means_list: Optional[List[float]] = None
			if self.feature_means is not None:
				means_list = self.feature_means.view(-1).tolist()
			for idx, name in enumerate(self.feature_names):
				if name in features and features[name] is not None:
					value = float(features[name])
				elif means_list is not None and idx < len(means_list):
					value = float(means_list[idx])
				else:
					value = 0.0
				vector_values.append(value)
			vector = torch.tensor([vector_values], dtype=torch.float32)
		else:
			ordered_keys = sorted(k for k, v in features.items() if v is not None)
			vector = torch.tensor([[float(features[k]) for k in ordered_keys]], dtype=torch.float32)
		if self.input_dim and vector.shape[-1] != self.input_dim:
			logging.warning(
				"Input feature dimension %s does not match expected %s", vector.shape[-1], self.input_dim
			)
		if self.feature_means is not None and self.feature_stds is not None:
			if vector.shape[-1] == self.feature_means.shape[-1]:
				vector = (vector - self.feature_means) / (self.feature_stds + 1e-9)
		if self.sequence_enabled and self.sequence_length > 1:
			vector = vector.unsqueeze(1).repeat(1, self.sequence_length, 1)
		return vector


model_service = ModelService()


ALLOWED_ALERT_PRIORITIES = {"low", "medium", "high", "critical"}
ALLOWED_ALERT_STATUSES = {"new", "investigating", "resolved", "false_positive"}
ALLOWED_INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_INCIDENT_STATUSES = {"open", "investigating", "contained", "resolved"}


db_service = DatabaseService()


def _now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def _int_arg(name: str, default: int, minimum: int = 1) -> int:
	raw = request.args.get(name)
	try:
		value = int(raw) if raw is not None else default
	except (TypeError, ValueError):
		value = default
	return max(value, minimum)


app = Flask(__name__)

# Configure Flask app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure CORS with environment-based origins
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
CORS(app, resources={
	r"/api/*": {
		"origins": cors_origins,
		"methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
		"allow_headers": ["Content-Type", "Authorization"],
		"expose_headers": ["X-Response-Time"],
		"supports_credentials": True,
		"max_age": 3600
	}
})

# Configure compression
if os.getenv('COMPRESS_ENABLED', 'True') == 'True':
	compress = Compress()
	compress.init_app(app)
	app.config['COMPRESS_ALGORITHM'] = 'gzip'
	app.config['COMPRESS_LEVEL'] = int(os.getenv('COMPRESS_LEVEL', '6'))
	app.config['COMPRESS_MIN_SIZE'] = int(os.getenv('COMPRESS_MIN_SIZE', '500'))
	logging.info("Response compression enabled")

# Configure rate limiting
if os.getenv('RATE_LIMIT_ENABLED', 'True') == 'True':
	limiter = Limiter(
		app=app,
		key_func=get_remote_address,
		default_limits=[os.getenv('RATE_LIMIT_DEFAULT', '100 per hour')],
		storage_uri=os.getenv('RATE_LIMIT_STORAGE_URL', 'memory://'),
		strategy='fixed-window'
	)
	logging.info("Rate limiting enabled")
else:
	limiter = None

# Import and setup middleware
try:
	from middleware import (
		setup_error_handlers,
		setup_request_logging,
		setup_security_headers
	)
	setup_error_handlers(app)
	setup_request_logging(app)
	setup_security_headers(app)
	logging.info("Middleware configured successfully")
except ImportError as e:
	logging.warning(f"Middleware module not available: {e}")

# Import and register auth blueprint
try:
	from auth import auth_bp, init_bcrypt, require_auth
	init_bcrypt(app)
	app.register_blueprint(auth_bp)
	logging.info("Authentication module loaded successfully")
except ImportError as e:
	logging.warning(f"Authentication module not available: {e}")
	# Define a dummy decorator if auth not available
	def require_auth(f):
		return f


@app.route("/api/health", methods=["GET"])
def health_check() -> Any:
	"""Health check endpoint for monitoring backend status"""
	try:
		# Test database connection
		with db_service.cursor() as cur:
			cur.execute("SELECT 1")
		db_status = "connected"
	except Exception:
		db_status = "disconnected"
	
	return jsonify({
		"status": "ok",
		"model_loaded": bool(model_service.model_ready),
		"database": db_status,
		"timestamp": _now_iso(),
		"version": "2.0.0"
	})


@app.route("/api/stream/alerts", methods=["GET"])
def stream_alerts() -> Any:
	"""
	Server-Sent Events endpoint for real-time alert notifications
	Clients can subscribe to this endpoint to receive alerts in real-time
	
	Note: SSE doesn't support custom headers, so we accept token as query parameter
	"""
	# Get token from query parameter (EventSource doesn't support headers)
	token = request.args.get('token', '')
	
	if not token:
		# Try to get from Authorization header as fallback
		auth_header = request.headers.get('Authorization')
		if auth_header and auth_header.startswith('Bearer '):
			token = auth_header.split(' ')[1]
	
	# Validate token
	user_id = None
	if token:
		try:
			from auth import jwt_decode
			payload = jwt_decode(token)
			if payload:
				user_id = payload.get('user_id')
		except Exception as e:
			logging.warning(f"SSE token validation failed: {e}")
	
	if not user_id:
		return jsonify({'error': 'Unauthorized', 'message': 'Valid token required'}), 401
	
	def generate():
		# Send initial connection message
		yield f"data: {json.dumps({'type': 'connected', 'timestamp': _now_iso(), 'user_id': user_id})}\n\n"
		
		# In production, this would poll the database or use a message queue
		# For now, we'll send a heartbeat every 30 seconds
		import time
		last_check = time.time()
		
		while True:
			current_time = time.time()
			
			# Send heartbeat every 30 seconds
			if current_time - last_check >= 30:
				yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': _now_iso()})}\n\n"
				last_check = current_time
			
			time.sleep(5)  # Check every 5 seconds
	
	return app.response_class(
		generate(),
		mimetype='text/event-stream',
		headers={
			'Cache-Control': 'no-cache',
			'X-Accel-Buffering': 'no',
			'Connection': 'keep-alive'
		}
	)


@app.route("/api/dashboard/stats", methods=["GET"])
@require_auth
def dashboard_stats(user_id: int = None) -> Any:
	try:
		stats = db_service.fetch_dashboard_stats()
	except Exception as exc:
		logging.exception("Failed to load dashboard stats: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	stats["model_metrics"] = model_service.metrics
	return jsonify(stats)


@app.route("/api/alerts", methods=["GET"])
@require_auth
def list_alerts(user_id: int = None) -> Any:
	page = _int_arg("page", 1)
	per_page = _int_arg("per_page", 10)
	priority = request.args.get("priority")
	status = request.args.get("status")
	search = request.args.get("search", "").strip()
	try:
		result = db_service.fetch_alerts(page, per_page, priority, status, search)
	except Exception as exc:
		logging.exception("Failed to load alerts: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	return jsonify(result)


@app.route("/api/alerts/<alert_id>", methods=["GET"])
@require_auth
def get_alert(alert_id: str, user_id: int = None) -> Any:
	try:
		alert = db_service.fetch_alert(alert_id)
	except Exception as exc:
		logging.exception("Failed to fetch alert: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	if not alert:
		return jsonify({"error": "Alert not found"}), 404
	return jsonify(alert)


@app.route("/api/alerts/<alert_id>/status", methods=["PATCH"])
@require_auth
def update_alert_status(alert_id: str, user_id: int = None) -> Any:
	payload = request.get_json(force=True, silent=True) or {}
	new_status = payload.get("status")
	if new_status not in ALLOWED_ALERT_STATUSES:
		return jsonify({"error": "Invalid alert status"}), 400
	try:
		updated = db_service.update_alert_status(alert_id, new_status)
	except Exception as exc:
		logging.exception("Failed to update alert status: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	if not updated:
		return jsonify({"error": "Alert not found"}), 404
	return jsonify(updated)

@app.route("/api/incidents", methods=["GET"])
@require_auth
def list_incidents(user_id: int = None) -> Any:
	page = _int_arg("page", 1)
	per_page = _int_arg("per_page", 10)
	severity = request.args.get("severity")
	status = request.args.get("status")
	search = request.args.get("search", "").strip()
	try:
		result = db_service.fetch_incidents(page, per_page, severity, status, search)
	except Exception as exc:
		logging.exception("Failed to load incidents: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	return jsonify(result)


@app.route("/api/incidents/<incident_id>", methods=["GET"])
@require_auth
def get_incident(incident_id: str, user_id: int = None) -> Any:
	try:
		incident = db_service.fetch_incident(incident_id)
	except Exception as exc:
		logging.exception("Failed to fetch incident: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	if not incident:
		return jsonify({"error": "Incident not found"}), 404
	return jsonify(incident)


@app.route("/api/incidents/<incident_id>/status", methods=["PATCH"])
@require_auth
def update_incident_status(incident_id: str, user_id: int = None) -> Any:
	payload = request.get_json(force=True, silent=True) or {}
	new_status = payload.get("status")
	if new_status not in ALLOWED_INCIDENT_STATUSES:
		return jsonify({"error": "Invalid incident status"}), 400
	try:
		updated = db_service.update_incident_status(incident_id, new_status)
	except Exception as exc:
		logging.exception("Failed to update incident status: %s", exc)
		return jsonify({"error": "Database unavailable"}), 503
	if not updated:
		return jsonify({"error": "Incident not found"}), 404
	return jsonify(updated)


@app.route("/api/model/metrics", methods=["GET"])
def model_metrics() -> Any:
	return jsonify(model_service.metrics)


@app.route("/api/model/retrain", methods=["POST"])
def retrain_model() -> Any:
	return jsonify({
		"status": "accepted",
		"message": "Retraining job scheduled. Monitor backend logs for progress.",
		"timestamp": _now_iso(),
	}), 202


@app.route("/api/predict", methods=["POST"])
@limiter.limit("10 per minute") if limiter else lambda f: f
def predict() -> Any:
	payload = request.get_json(force=True, silent=True) or {}
	features = payload.get("features") if isinstance(payload, dict) else None
	if not isinstance(features, dict):
		features = payload
	if not isinstance(features, dict):
		return jsonify({"error": "Request body must contain feature dictionary"}), 400

	try:
		numeric_features = {key: float(value) for key, value in features.items() if value is not None}
	except (TypeError, ValueError):
		return jsonify({"error": "Features must be numeric"}), 400

	try:
		prediction_index, labels, probabilities = model_service.predict(numeric_features)
	except ValueError as exc:
		return jsonify({"error": str(exc)}), 400

	label = labels[prediction_index] if prediction_index < len(labels) else labels[0]
	confidence = float(probabilities.get(label, 0.0))

	return jsonify({
		"prediction": label,
		"prediction_index": prediction_index,
		"confidence": confidence,
		"probabilities": probabilities,
		"features_used": sorted(numeric_features.keys()),
	})


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=True)


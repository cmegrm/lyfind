"""AI runtime loader: supports Google AI Studio (Gemini) or local offline DINOv2 + CLIP."""
import os
from pathlib import Path
from threading import RLock
from lyfind.matching import CLIP_CALIBRATION, Calibration, ClipAdapter, DinoAdapter, DINO_CALIBRATION, HybridAdapter
from matching import ScoreWeights
STRONG, POSSIBLE = 60, 40

ROOT = Path(__file__).resolve().parents[1]
CLIP_DIR = ROOT / 'models' / 'clip-ViT-B-32'
DINO_DIR = ROOT / 'models' / 'dinov2-base'
if not (DINO_DIR / 'config.json').is_file():
    DINO_DIR = ROOT / 'models' / 'dinov2-small'
MODEL_DIR = CLIP_DIR  # tests and older scripts look for CLIP here


class LocalAI:
    def __init__(self):
        self.adapter = None
        self.attempted = False
        self.reason = 'AI has not been checked yet.'
        self.weights = ScoreWeights.from_environment()
        self.calibration = Calibration()
        self._method = 'typed_details'
        self._model_name = ''
        self._local_only = True
        self._lock = RLock()

    def prepare(self):
        with self._lock:
            if self.attempted:
                return self.adapter
            self.attempted = True
            if os.getenv('ENABLE_AI', '1').casefold() not in {'1','true','yes'}:
                self.reason = 'AI is disabled in the local configuration.'
                return None
            provider = os.getenv('AI_PROVIDER', 'auto').strip().casefold()
            if provider == 'off':
                self.reason = 'AI is disabled in the local configuration.'
                return None
            api_key = os.getenv('GEMINI_API_KEY', '').strip()
            if provider == 'gemini' or (provider == 'auto' and api_key):
                gemini = self._load_gemini(api_key)
                if gemini is not None:
                    self.adapter = gemini
                    self._method = 'gemini_ai'
                    self._model_name = f'Gemini ({gemini.model})'
                    self._local_only = False
                    self.reason = f'Google Gemini ({gemini.model}) compares photos and descriptions via AI Studio. Typed details stay as an offline fallback.'
                    return self.adapter
                if provider == 'gemini':
                    return None
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            clip = self._load_clip()
            dino = self._load_dino()
            if dino is not None and clip is not None:
                self.adapter = HybridAdapter(dino, clip)
                self.calibration = DINO_CALIBRATION
                self._method = 'dino_clip_ai'
                self._model_name = f'DINOv2 ({DINO_DIR.name}) + CLIP ViT-B/32'
                self._local_only = True
                self.reason = 'DINOv2 compares photos on this computer. CLIP compares words to photos. Nothing is sent online.'
            elif dino is not None:
                self.adapter = dino
                self.calibration = DINO_CALIBRATION
                self._method = 'dino_ai'
                self._model_name = f'DINOv2 ({DINO_DIR.name})'
                self._local_only = True
                self.reason = 'DINOv2 compares photos on this computer. Word-to-photo CLIP is not loaded. Nothing is sent online.'
            elif clip is not None:
                self.adapter = clip
                self.calibration = CLIP_CALIBRATION
                self._method = 'clip_ai'
                self._model_name = 'CLIP ViT-B/32'
                self._local_only = True
                self.reason = 'CLIP is running on this server (photo fallback). No photos are sent externally.'
            else:
                self.reason = 'Local model is not prepared. Set GEMINI_API_KEY in .env or run python3 setup_ai.py.'
            return self.adapter

    def _load_gemini(self, api_key):
        if not api_key:
            self.reason = 'GEMINI_API_KEY is missing. Add it to .env or switch AI_PROVIDER to local.'
            return None
        try:
            from lyfind.gemini_matching import GeminiClientAdapter
            return GeminiClientAdapter(api_key=api_key)
        except ImportError:
            self.reason = 'Install google-genai (pip install -r requirements-web.txt) to enable Gemini AI.'
            return None
        except Exception as error:
            self.reason = f'Gemini AI could not start ({type(error).__name__}). Using fallback matching.'
            return None

    def _load_clip(self):
        if not (CLIP_DIR / 'modules.json').is_file():
            return None
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
            model = SentenceTransformer(str(CLIP_DIR), device='cpu', local_files_only=True,
                                        trust_remote_code=False)
            model.eval()
            return ClipAdapter(model)
        except Exception:
            return None

    def _load_dino(self):
        if not (DINO_DIR / 'config.json').is_file():
            return None
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModel
            torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
            processor = AutoImageProcessor.from_pretrained(str(DINO_DIR), local_files_only=True, use_fast=False)
            model = AutoModel.from_pretrained(str(DINO_DIR), local_files_only=True, trust_remote_code=False)
            model.eval()
            return DinoAdapter(model, processor)
        except Exception:
            return None

    def status(self):
        from dataclasses import asdict
        return dict(ready=self.adapter is not None, method=self._method if self.adapter else 'typed_details',
                    reason=self.reason, model=self._model_name or ('none' if self.attempted else ''),
                    weights=asdict(self.weights),
                    thresholds=dict(strong=STRONG, possible=POSSIBLE), local_only=self._local_only)
